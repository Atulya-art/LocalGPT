"""Chat orchestration: context assembly, streaming and persistence."""

from __future__ import annotations

from typing import Any, Iterator

from .conversation import ConversationNotFound, ConversationService
from .ollama_client import OllamaClient, OllamaError


class ChatBot:
    def __init__(
        self,
        client: OllamaClient,
        conversations: ConversationService,
        *,
        system_prompt: str,
        context_char_budget: int,
        max_message_chars: int,
    ):
        self.client = client
        self.conversations = conversations
        self.system_prompt = system_prompt
        self.context_char_budget = context_char_budget
        self.max_message_chars = max_message_chars

    # -- context ------------------------------------------------------------
    def build_context(self, history: list[dict[str, Any]]) -> list[dict[str, str]]:
        """Trim history to the character budget, keeping the newest turns.

        The system prompt is always first. After trimming, leading assistant
        messages are dropped so the model does not start on a dangling reply.
        """
        budget = self.context_char_budget - len(self.system_prompt)
        selected: list[dict[str, str]] = []
        used = 0
        for message in reversed(history):
            role = message.get("role")
            content = message.get("content") or ""
            if role not in {"user", "assistant"} or not content:
                continue
            cost = len(content) + 16  # small per-message overhead
            if used + cost > budget and selected:
                break
            selected.append({"role": role, "content": content})
            used += cost

        selected.reverse()
        while selected and selected[0]["role"] != "user":
            selected.pop(0)

        return [{"role": "system", "content": self.system_prompt}, *selected]

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
            context = self.build_context(history)
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
