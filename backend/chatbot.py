"""Chat orchestration: context assembly, streaming and persistence."""

from __future__ import annotations

from typing import Any, Iterator

from .conversation import ConversationNotFound, ConversationService
from .ollama_client import OllamaClient, OllamaError
from .time_engine import get_time_context
from .tool_router import ToolRouter
from .web_search import WebSearch, WebSearchError


class ChatBot:
    def __init__(
        self,
        client: OllamaClient,
        conversations: ConversationService,
        *,
        system_prompt: str,
        context_char_budget: int,
        max_message_chars: int,
        timezone: str = "Asia/Kolkata",
        location: str = "Pune, India",
        enable_web_search: bool = False,
    ):
        self.client = client
        self.conversations = conversations
        self.system_prompt = system_prompt
        self.context_char_budget = context_char_budget
        self.max_message_chars = max_message_chars
        self.timezone = timezone
        self.location = location
        self.web_search = WebSearch(enabled=enable_web_search)
        self.router = ToolRouter(web_search=self.web_search)

    # -- context ------------------------------------------------------------
    def build_context(self, history: list[dict[str, Any]], user_message: str = "") -> list[dict[str, str]]:
        """Trim history to the character budget, keeping the newest turns.

        The system prompt is always first with fresh real-time context.
        After trimming, leading assistant messages are dropped.
        """
        time_ctx = get_time_context(tz_name=self.timezone, location=self.location)
        full_system = time_ctx + "\n" + self.system_prompt

        budget = self.context_char_budget - len(full_system)
        selected: list[dict[str, str]] = []
        used = 0
        for message in reversed(history):
            role = message.get("role")
            content = message.get("content") or ""
            if role not in {"user", "assistant"} or not content:
                continue
            cost = len(content) + 16
            if used + cost > budget and selected:
                break
            selected.append({"role": role, "content": content})
            used += cost

        selected.reverse()
        while selected and selected[0]["role"] != "user":
            selected.pop(0)

        return [{"role": "system", "content": full_system}, *selected]

    # -- generation ---------------------------------------------------------
    def stream_reply(
        self, conversation_id: int, user_text: str
    ) -> Iterator[dict[str, Any]]:
        """Persist the user turn, stream the reply and persist the answer.

        Yields event dictionaries:
          meta   -> conversation id/title, user message id
          token  -> incremental content
          done   -> assistant message id, stats, title
          error  -> friendly message and error kind
        """
        user_text = (user_text or "").strip()
        if not user_text:
            yield {
                "type": "error",
                "error": "invalid_message",
                "message": "Message must not be empty.",
            }
            return
        if len(user_text) > self.max_message_chars:
            yield {
                "type": "error",
                "error": "message_too_long",
                "message": (
                    f"Message is too long ({len(user_text)} characters). "
                    f"The limit is {self.max_message_chars} characters."
                ),
            }
            return

        try:
            conversation = self.conversations.get_meta(conversation_id)
        except ConversationNotFound:
            yield {
                "type": "error",
                "error": "conversation_not_found",
                "message": f"Conversation {conversation_id} no longer exists.",
            }
            return

        user_message = self.conversations.add_message(
            conversation_id, "user", user_text
        )
        title = self.conversations.maybe_auto_title(conversation_id, user_text)
        conversation = self.conversations.get_meta(conversation_id)

        yield {
            "type": "meta",
            "conversation": conversation,
            "user_message": user_message,
        }

        try:
            self.client.require_model()
            history = self.conversations.messages(conversation_id)
            # Route the query
            action, route_data = self.router.route(user_text)
            if action == "time":
                # Handle locally without LLM
                response_text = self._format_time_response(route_data)
                assistant = self.conversations.add_message(conversation_id, "assistant", response_text)
                yield {
                    "type": "done",
                    "conversation": self.conversations.get_meta(conversation_id),
                    "assistant_message": assistant,
                    "title": title,
                    "stats": {"local_tool": True},
                }
                return
            elif action == "web_search" and route_data:
                try:
                    search_res = self.web_search.search(route_data.get("query", user_text))
                    search_ctx = self.web_search.format_results_for_llm(search_res)
                    # Add search results to context
                    context = self.build_context(history, user_text)
                    # Inject search context
                    if context and context[0]["role"] == "system":
                        context[0]["content"] = context[0]["content"] + "\n\n" + search_ctx
                    else:
                        context.insert(0, {"role": "system", "content": search_ctx})
                except WebSearchError as exc:
                    yield {
                        "type": "error",
                        "error": "web_search_unavailable",
                        "message": str(exc),
                    }
                    return
            else:
                context = self.build_context(history, user_text)
        except OllamaError as exc:
            yield {"type": "error", **exc.to_dict()}
            return
        except Exception as exc:  # pragma: no cover - defensive
            yield {
                "type": "error",
                "error": "internal_error",
                "message": f"Could not prepare the conversation: {exc}",
            }
            return

        parts: list[str] = []
        stats: dict[str, Any] = {}
        saved = False
        finished = False

        try:
            for event in self.client.chat_stream(context):
                if event["type"] == "token":
                    parts.append(event["content"])
                    yield {"type": "token", "content": event["content"]}
                elif event["type"] == "done":
                    stats = event.get("stats") or {}

            content = "".join(parts).strip()
            if content:
                assistant = self.conversations.add_message(
                    conversation_id, "assistant", content
                )
                saved = True
            else:
                assistant = None
            finished = True
            yield {
                "type": "done",
                "conversation": self.conversations.get_meta(conversation_id),
                "assistant_message": assistant,
                "title": title,
                "stats": stats,
            }
        except OllamaError as exc:
            content = "".join(parts).strip()
            if content and not saved:
                self.conversations.add_message(conversation_id, "assistant", content)
                saved = True
            yield {"type": "error", **exc.to_dict()}
        except GeneratorExit:
            # Client disconnected mid-stream: keep whatever was generated.
            if not saved and not finished:
                content = "".join(parts).strip()
                if content:
                    try:
                        self.conversations.add_message(
                            conversation_id, "assistant", content
                        )
                    except Exception:
                        pass
            raise
        except Exception as exc:  # pragma: no cover - defensive
            content = "".join(parts).strip()
            if content and not saved:
                self.conversations.add_message(conversation_id, "assistant", content)
            yield {
                "type": "error",
                "error": "internal_error",
                "message": f"Unexpected error while generating a reply: {exc}",
            }

    def _format_time_response(self, data: dict[str, Any]) -> str:
        action = data.get("action")
        if action == "current_time":
            return f"The current time is {data['time']} ({data['timezone']})."
        elif action == "current_date":
            full = data.get("full", {})
            return f"Today's date is {full.get('date', data.get('date'))} ({full.get('day', data.get('day'))})."
        elif action == "current_day":
            return f"Today is {data['day']}."
        elif action == "current_month":
            return f"The current month is {data['month']}."
        elif action == "current_year":
            return f"The current year is {data['year']}."
        elif action == "tomorrow":
            return f"Tomorrow's date is {data['date']} ({data['day']})."
        elif action == "yesterday":
            return f"Yesterday's date was {data['date']} ({data['day']})."
        elif action == "add_days":
            return f"{data['days']} day(s) from now will be {data['date']} ({data['day']})."
        elif action == "add_hours":
            return f"{data['hours']} hour(s) from now it will be {data['time']} on {data['date']}."
        elif action == "add_minutes":
            return f"{data['minutes']} minute(s) from now it will be {data['time']} on {data['date']}."
        elif action == "tz_time":
            return f"The current time in {data['city']} ({data['timezone']}) is {data['current_time']} on {data['current_date']}."
        elif action == "tz_diff":
            cities = data.get('cities', [])
            if len(cities) == 2:
                return f"Time difference between {cities[0]} and {cities[1]}: {data['difference_str']} (currently {data['time1']} vs {data['time2']})."
        elif action == "days_until":
            return f"There are {data['days']} day(s) left until {data['target']}."
        full = data.get("full", {})
        if full:
            return f"Current date: {full.get('date')}, Day: {full.get('day')}, Time: {full.get('time')}, Timezone: {full.get('timezone')}"
        return "Time information retrieved."
