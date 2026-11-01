"""Conversation domain logic: creation, titles, retrieval and deletion."""

from __future__ import annotations

import re
from typing import Any, Optional

from .database import DEFAULT_TITLE, Database

_WHITESPACE = re.compile(r"\s+")


class ConversationNotFound(Exception):
    pass


class ConversationService:
    def __init__(self, db: Database, max_title_chars: int = 60):
        self.db = db
        self.max_title_chars = max_title_chars

    # -- helpers ------------------------------------------------------------
    @staticmethod
    def title_from_message(message: str, max_chars: int = 60) -> str:
        cleaned = _WHITESPACE.sub(" ", message or "").strip()
        if not cleaned:
            return DEFAULT_TITLE
        if len(cleaned) <= max_chars:
            return cleaned
        cut = cleaned[: max_chars - 1].rstrip()
        # Prefer breaking on a word boundary.
        if " " in cut:
            cut = cut.rsplit(" ", 1)[0]
        return f"{cut}…" if cut else cleaned[:max_chars]

    # -- operations ---------------------------------------------------------
    def list(self) -> list[dict[str, Any]]:
        return self.db.list_conversations()

    def create(self, title: Optional[str] = None) -> dict[str, Any]:
        title = (title or "").strip() or DEFAULT_TITLE
        return self.db.create_conversation(title[: self.max_title_chars])

    def get(self, conversation_id: int) -> dict[str, Any]:
        conversation = self.db.get_conversation_with_messages(conversation_id)
        if conversation is None:
            raise ConversationNotFound(f"Conversation {conversation_id} not found")
        return conversation

    def get_meta(self, conversation_id: int) -> dict[str, Any]:
        conversation = self.db.get_conversation(conversation_id)
        if conversation is None:
            raise ConversationNotFound(f"Conversation {conversation_id} not found")
        return conversation

    def delete(self, conversation_id: int) -> bool:
        if not self.db.delete_conversation(conversation_id):
            raise ConversationNotFound(f"Conversation {conversation_id} not found")
        return True

    def clear(self, conversation_id: int) -> dict[str, Any]:
        if not self.db.clear_messages(conversation_id):
            raise ConversationNotFound(f"Conversation {conversation_id} not found")
        conversation = self.db.get_conversation(conversation_id)
        assert conversation is not None
        return conversation

    def rename(self, conversation_id: int, title: str) -> dict[str, Any]:
        title = (title or "").strip()
        if not title:
            raise ValueError("Title must not be empty")
        if not self.db.rename_conversation(
            conversation_id, title[: self.max_title_chars]
        ):
            raise ConversationNotFound(f"Conversation {conversation_id} not found")
        return self.get_meta(conversation_id)

    def add_message(self, conversation_id: int, role: str, content: str) -> dict[str, Any]:
        if role not in {"user", "assistant", "system"}:
            raise ValueError(f"Invalid role: {role}")
        return self.db.add_message(conversation_id, role, content)

    def messages(self, conversation_id: int) -> list[dict[str, Any]]:
        if self.db.get_conversation(conversation_id) is None:
            raise ConversationNotFound(f"Conversation {conversation_id} not found")
        return self.db.get_messages(conversation_id)

    def maybe_auto_title(self, conversation_id: int, first_message: str) -> Optional[str]:
        """Set a human-friendly title from the first user message."""
        conversation = self.db.get_conversation(conversation_id)
        if conversation is None:
            raise ConversationNotFound(f"Conversation {conversation_id} not found")
        if conversation["title"] != DEFAULT_TITLE:
            return None
        if self.db.message_count(conversation_id) > 1:
            return None
        title = self.title_from_message(first_message, self.max_title_chars)
        self.db.rename_conversation(conversation_id, title)
        return title
