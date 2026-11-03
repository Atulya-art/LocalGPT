"""LocalGPT - a fully local, ChatGPT-style assistant.

Run with:  python app.py
Then open: http://127.0.0.1:5000
"""

from __future__ import annotations

import ipaddress
import json
from typing import Any, Iterator
from urllib.parse import urlparse

from flask import Flask, Response, abort, jsonify, request, send_from_directory

import config
from backend.chatbot import ChatBot
from backend.conversation import ConversationNotFound, ConversationService
from backend.database import Database
from backend.ollama_client import OllamaClient, OllamaError
from backend.time_engine import format_datetime, get_current_datetime
try:
    from backend.web_search import WebSearch
except Exception:
    class WebSearch:
        def __init__(self, enabled=False):
            self.enabled = enabled

        def is_available(self):
            return False


def _sse(event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


LOCAL_HOSTNAMES = {"127.0.0.1", "localhost", "::1", "[::1]"}


def _is_loopback(address: str | None) -> bool:
    if not address:
        return False
    try:
        ip = ipaddress.ip_address(address)
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        return ip.is_loopback
    except ValueError:
        return False


def _is_local_origin(origin: str | None) -> bool:
    if not origin:
        return True
    try:
        hostname = urlparse(origin).hostname
    except ValueError:
        return False
    return hostname in LOCAL_HOSTNAMES


def _json_error(message: str, status: int, code: str = "error"):
    return jsonify({"error": code, "message": message}), status


def create_app() -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH
    app.config["JSON_SORT_KEYS"] = False

    database = Database(config.DATABASE_PATH)
    database.init()
    conversations = ConversationService(database, config.MAX_TITLE_CHARS)
    ollama = OllamaClient(
        config.OLLAMA_HOST,
        config.OLLAMA_MODEL,
        connect_timeout=config.OLLAMA_CONNECT_TIMEOUT,
        read_timeout=config.OLLAMA_READ_TIMEOUT,
        num_ctx=config.NUM_CTX,
        num_predict=config.NUM_PREDICT,
        temperature=config.TEMPERATURE,
        top_p=config.TOP_P,
        repeat_penalty=config.REPEAT_PENALTY,
        keep_alive=config.KEEP_ALIVE,
    )
    chatbot = ChatBot(
        ollama,
        conversations,
        system_prompt=config.SYSTEM_PROMPT,
        context_char_budget=config.CONTEXT_CHAR_BUDGET,
        max_message_chars=config.MAX_MESSAGE_CHARS,
        timezone=config.TIMEZONE,
        location=config.LOCATION,
        enable_web_search=config.ENABLE_WEB_SEARCH,
    )
    web_search = WebSearch(enabled=config.ENABLE_WEB_SEARCH)

    app.extensions["localgpt"] = {
        "db": database,
        "conversations": conversations,
        "ollama": ollama,
        "chatbot": chatbot,
        "web_search": web_search,
    }

    # -- security headers / local-only guard --------------------------------
    @app.before_request
    def guard_local_only():
        if not request.path.startswith("/api/"):
            return None
        if not _is_loopback(request.remote_addr):
            abort(403)
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and not _is_local_origin(
            request.headers.get("Origin")
        ):
            abort(403)
        return None

    @app.after_request
    def security_headers(response: Response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
            "frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
        )
        return response

    # -- static frontend ----------------------------------------------------
    @app.get("/")
    def index():
        response = send_from_directory(config.FRONTEND_DIR, "index.html")
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/style.css")
    def styles():
        return send_from_directory(config.FRONTEND_DIR, "style.css")

    @app.get("/script.js")
    def scripts():
        return send_from_directory(config.FRONTEND_DIR, "script.js")

    @app.get("/assets/<path:filename>")
    def assets(filename: str):
        return send_from_directory(config.FRONTEND_DIR / "assets", filename)

    @app.get("/favicon.ico")
    def favicon():
        return send_from_directory(config.FRONTEND_DIR / "assets", "favicon.svg")

    # -- status / configuration --------------------------------------------
    @app.get("/api/status")
    def api_status():
        force = request.args.get("force") in {"1", "true", "yes"}
        status = ollama.status(force=force)
        status["app"] = {
            "name": "LocalGPT",
            "version": "1.0.0",
            "model": config.OLLAMA_MODEL,
            "num_ctx": config.NUM_CTX,
            "num_predict": config.NUM_PREDICT,
            "temperature": config.TEMPERATURE,
        }
        return jsonify(status)

    @app.get("/api/models")
    def api_models():
        try:
            models = ollama.list_models()
        except OllamaError as exc:
            return _json_error(exc.message, exc.status, exc.kind)
        return jsonify(
            {
                "configured": config.OLLAMA_MODEL,
                "models": models,
                "installed": ollama.is_model_installed(models),
            }
        )

    @app.get("/api/config")
    def api_config():
        try:
            dt_info = format_datetime(get_current_datetime(config.TIMEZONE))
        except Exception:
            dt_info = {}
        return jsonify(
            {
                "model": config.OLLAMA_MODEL,
                "ollama_host": config.OLLAMA_HOST,
                "num_ctx": config.NUM_CTX,
                "num_predict": config.NUM_PREDICT,
                "temperature": config.TEMPERATURE,
                "top_p": config.TOP_P,
                "repeat_penalty": config.REPEAT_PENALTY,
                "system_prompt": config.SYSTEM_PROMPT,
                "timezone": config.TIMEZONE,
                "location": config.LOCATION,
                "web_search_enabled": config.ENABLE_WEB_SEARCH,
                "web_search_available": web_search.is_available() if web_search else False,
                "realtime": dt_info,
            }
        )

    @app.get("/api/time")
    def api_time():
        try:
            dt_info = format_datetime(get_current_datetime(config.TIMEZONE))
            return jsonify({"ok": True, **dt_info, "location": config.LOCATION})
        except Exception as e:
            return _json_error(str(e), 500, "time_error")

    @app.get("/api/health")
    def api_health():
        return jsonify({"status": "ok", "app": "LocalGPT"})

    # -- conversations ------------------------------------------------------
    @app.get("/api/conversations")
    def list_conversations():
        return jsonify({"conversations": conversations.list()})

    @app.post("/api/conversations")
    def create_conversation():
        raw = request.get_data(cache=True)
        if raw and raw.strip():
            body = request.get_json(silent=True)
            if not isinstance(body, dict):
                return _json_error("Invalid JSON body.", 400, "invalid_body")
        else:
            body = {}
        title = body.get("title")
        if title is not None and not isinstance(title, str):
            return _json_error("'title' must be a string.", 400, "invalid_title")
        conversation = conversations.create(title)
        return jsonify(conversation), 201

    @app.get("/api/conversations/<int:conversation_id>")
    def get_conversation(conversation_id: int):
        try:
            return jsonify(conversations.get(conversation_id))
        except ConversationNotFound as exc:
            return _json_error(str(exc), 404, "conversation_not_found")

    @app.patch("/api/conversations/<int:conversation_id>")
    def rename_conversation(conversation_id: int):
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return _json_error("Invalid JSON body.", 400, "invalid_body")
        title = body.get("title")
        if not isinstance(title, str) or not title.strip():
            return _json_error("'title' must be a non-empty string.", 400, "invalid_title")
        try:
            return jsonify(conversations.rename(conversation_id, title))
        except ConversationNotFound as exc:
            return _json_error(str(exc), 404, "conversation_not_found")
        except ValueError as exc:
            return _json_error(str(exc), 400, "invalid_title")

    @app.delete("/api/conversations/<int:conversation_id>")
    def delete_conversation(conversation_id: int):
        try:
            conversations.delete(conversation_id)
        except ConversationNotFound as exc:
            return _json_error(str(exc), 404, "conversation_not_found")
        return jsonify({"deleted": True, "id": conversation_id})

    @app.delete("/api/conversations/<int:conversation_id>/messages")
    def clear_conversation(conversation_id: int):
        try:
            conversation = conversations.clear(conversation_id)
        except ConversationNotFound as exc:
            return _json_error(str(exc), 404, "conversation_not_found")
        return jsonify(conversation)

    # -- chat (SSE) ---------------------------------------------------------
    @app.post("/api/chat")
    def chat():
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return _json_error("Request body must be a JSON object.", 400, "invalid_body")

        message = body.get("message")
        if not isinstance(message, str) or not message.strip():
            return _json_error(
                "'message' must be a non-empty string.", 400, "invalid_message"
            )
        if len(message) > config.MAX_MESSAGE_CHARS:
            return _json_error(
                f"Message exceeds the {config.MAX_MESSAGE_CHARS} character limit.",
                400,
                "message_too_long",
            )

        conversation_id = body.get("conversation_id")
        if conversation_id is None:
            conversation = conversations.create()
            conversation_id = conversation["id"]
        elif isinstance(conversation_id, bool) or not isinstance(conversation_id, int):
            return _json_error(
                "'conversation_id' must be an integer.", 400, "invalid_conversation_id"
            )
        else:
            try:
                conversations.get_meta(conversation_id)
            except ConversationNotFound:
                return _json_error(
                    "Conversation not found.", 404, "conversation_not_found"
                )

        def generate() -> Iterator[str]:
            yield ": connected\n\n"
            try:
                for event in chatbot.stream_reply(conversation_id, message):
                    yield _sse(event["type"], event)
            except Exception as exc:  # pragma: no cover - last-resort guard
                yield _sse(
                    "error",
                    {
                        "error": "internal_error",
                        "message": f"Unexpected server error: {exc}",
                    },
                )

        response = Response(generate(), mimetype="text/event-stream")
        response.headers["Cache-Control"] = "no-cache, no-transform"
        response.headers["X-Accel-Buffering"] = "no"
        response.headers["Connection"] = "keep-alive"
        return response

    # -- error handlers -----------------------------------------------------
    @app.errorhandler(403)
    def forbidden(_error):
        if request.path.startswith("/api/"):
            return _json_error("Access is limited to localhost.", 403, "forbidden")
        return _json_error("Forbidden.", 403, "forbidden")

    @app.errorhandler(404)
    def not_found(_error):
        if request.path.startswith("/api/"):
            return _json_error("Endpoint not found.", 404, "not_found")
        return _json_error("Page not found.", 404, "not_found")

    @app.errorhandler(405)
    def method_not_allowed(_error):
        return _json_error("Method not allowed.", 405, "method_not_allowed")

    @app.errorhandler(413)
    def too_large(_error):
        return _json_error("Request body is too large.", 413, "payload_too_large")

    @app.errorhandler(500)
    def server_error(_error):  # pragma: no cover - defensive
        if request.path.startswith("/api/"):
            return _json_error("Internal server error.", 500, "internal_error")
        return _json_error("Internal server error.", 500, "internal_error")

    return app


app = create_app()


if __name__ == "__main__":
    print("=" * 62)
    print(" LocalGPT - fully local AI assistant")
    print(f" Model : {config.OLLAMA_MODEL}")
    print(f" Ollama: {config.OLLAMA_HOST}")
    print(f" URL   : http://{config.HOST}:{config.PORT}")
    print("=" * 62)
    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG,
        threaded=True,
        use_reloader=False,
    )
