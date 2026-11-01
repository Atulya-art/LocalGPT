"""Thin client for the local Ollama HTTP API.

Only http://127.0.0.1:11434 is ever contacted. No cloud services, no API
keys and no telemetry are involved.
"""

from __future__ import annotations

import json
import subprocess
import threading
import time
from typing import Any, Iterator, Optional

import requests


class OllamaError(Exception):
    """A user-presentable Ollama failure."""

    def __init__(self, message: str, kind: str = "ollama_error", status: int = 502):
        super().__init__(message)
        self.message = message
        self.kind = kind
        self.status = status

    def to_dict(self) -> dict[str, Any]:
        return {"error": self.kind, "message": self.message}


class OllamaClient:
    def __init__(
        self,
        host: str,
        model: str,
        *,
        connect_timeout: float = 5,
        read_timeout: float = 300,
        num_ctx: int = 4096,
        num_predict: int = 1024,
        temperature: float = 0.7,
        top_p: float = 0.9,
        repeat_penalty: float = 1.1,
        keep_alive: str = "10m",
    ):
        self.host = host.rstrip("/")
        self.model = model
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.num_ctx = num_ctx
        self.num_predict = num_predict
        self.temperature = temperature
        self.top_p = top_p
        self.repeat_penalty = repeat_penalty
        self.keep_alive = keep_alive

        self._status_cache: Optional[dict[str, Any]] = None
        self._status_cached_at = 0.0
        self._status_lock = threading.Lock()
        self._gpu_cache: Optional[dict[str, Any]] = None
        self._gpu_cached_at = 0.0
        self._gpu_lock = threading.Lock()

    # -- low level ----------------------------------------------------------
    def _timeout(self, read: Optional[float] = None):
        return (self.connect_timeout, read or self.read_timeout)

    def _get(self, path: str, timeout: Optional[float] = 4) -> dict[str, Any]:
        try:
            response = requests.get(
                f"{self.host}{path}", timeout=self._timeout(timeout)
            )
        except requests.exceptions.ConnectionError as exc:
            raise OllamaError(
                f"Cannot reach Ollama at {self.host}. Make sure Ollama is "
                "running (run 'ollama serve' or start the Ollama app).",
                kind="ollama_unreachable",
                status=503,
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise OllamaError(
                "Ollama did not respond in time. It may still be loading the model.",
                kind="ollama_timeout",
                status=504,
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise OllamaError(
                f"Ollama request failed: {exc}", kind="ollama_error", status=502
            ) from exc

        if response.status_code >= 400:
            raise OllamaError(
                f"Ollama returned HTTP {response.status_code}: "
                f"{_short_body(response)}",
                kind="ollama_http_error",
                status=502,
            )
        try:
            return response.json()
        except ValueError as exc:
            raise OllamaError(
                "Ollama returned an invalid response.", kind="ollama_error", status=502
            ) from exc

    def list_models(self) -> list[dict[str, Any]]:
        payload = self._get("/api/tags", timeout=5)
        models = []
        for item in payload.get("models", []) or []:
            details = item.get("details") or {}
            models.append(
                {
                    "name": item.get("name"),
                    "size": item.get("size"),
                    "family": details.get("family"),
                    "parameter_size": details.get("parameter_size"),
                    "quantization": details.get("quantization_level"),
                    "modified_at": item.get("modified_at"),
                }
            )
        return models

    def is_model_installed(self, models: Optional[list[dict[str, Any]]] = None) -> bool:
        names = {m.get("name") for m in (models if models is not None else self.list_models())}
        if self.model in names:
            return True
        # Accept "llama3.2" when "llama3.2:latest" is installed and vice versa.
        base = self.model.split(":")[0]
        return any(name == base or name == f"{base}:latest" for name in names if name)

    def running_models(self) -> list[dict[str, Any]]:
        try:
            payload = self._get("/api/ps", timeout=4)
        except OllamaError:
            return []
        result = []
        for item in payload.get("models", []) or []:
            result.append(
                {
                    "name": item.get("name") or item.get("model"),
                    "size": item.get("size"),
                    "size_vram": item.get("size_vram"),
                }
            )
        return result

    # -- status -------------------------------------------------------------
    def status(self, *, force: bool = False, ttl: float = 5.0) -> dict[str, Any]:
        with self._status_lock:
            now = time.monotonic()
            if (
                not force
                and self._status_cache is not None
                and now - self._status_cached_at < ttl
            ):
                return self._status_cache

            status: dict[str, Any] = {
                "online": False,
                "host": self.host,
                "model": self.model,
                "model_installed": False,
                "models": [],
                "version": None,
                "running": [],
                "gpu": self.gpu_info(),
                "error": None,
                "checked_at": time.time(),
            }
            try:
                version = self._get("/api/version", timeout=3)
                models = self.list_models()
                status.update(
                    {
                        "online": True,
                        "version": version.get("version"),
                        "models": models,
                        "model_installed": self.is_model_installed(models),
                        "running": self.running_models(),
                    }
                )
            except OllamaError as exc:
                status["error"] = exc.message

            self._status_cache = status
            self._status_cached_at = now
            return status

    def require_model(self) -> None:
        """Raise a friendly error when Ollama or the configured model is missing."""
        status = self.status(ttl=2)
        if not status["online"]:
            raise OllamaError(
                status.get("error")
                or f"Cannot reach Ollama at {self.host}.",
                kind="ollama_unreachable",
                status=503,
            )
        if not status["model_installed"]:
            raise OllamaError(
                f"The model '{self.model}' is not installed. "
                f"Run: ollama pull {self.model}",
                kind="model_missing",
                status=409,
            )

    # -- hardware -----------------------------------------------------------
    def gpu_info(self) -> Optional[dict[str, Any]]:
        """Best-effort local GPU detection via nvidia-smi. Never fatal."""
        with self._gpu_lock:
            now = time.monotonic()
            if self._gpu_cache is not None and now - self._gpu_cached_at < 60:
                return self._gpu_cache
            info: Optional[dict[str, Any]] = None
            try:
                completed = subprocess.run(
                    [
                        "nvidia-smi",
                        "--query-gpu=name,memory.total,memory.used,utilization.gpu",
                        "--format=csv,noheader,nounits",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=3,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                line = (completed.stdout or "").strip().splitlines()
                if completed.returncode == 0 and line:
                    parts = [p.strip() for p in line[0].split(",")]
                    if len(parts) >= 4:
                        info = {
                            "name": parts[0],
                            "memory_total_mb": _to_int(parts[1]),
                            "memory_used_mb": _to_int(parts[2]),
                            "utilization_percent": _to_int(parts[3]),
                        }
            except (OSError, subprocess.SubprocessError):
                info = None
            self._gpu_cache = info
            self._gpu_cached_at = now
            return info

    # -- generation ---------------------------------------------------------
    def _options(self) -> dict[str, Any]:
        return {
            "num_ctx": self.num_ctx,
            "num_predict": self.num_predict,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "repeat_penalty": self.repeat_penalty,
        }

    def chat_stream(self, messages: list[dict[str, str]]) -> Iterator[dict[str, Any]]:
        """Stream a chat completion as event dictionaries.

        Yields ``{"type": "token", "content": "..."}`` chunks and a final
        ``{"type": "done", "stats": {...}}`` event. Raises OllamaError on
        connection, model or HTTP failures.
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": self._options(),
            "keep_alive": self.keep_alive,
        }

        try:
            response = requests.post(
                f"{self.host}/api/chat",
                json=payload,
                stream=True,
                timeout=self._timeout(),
                headers={"Accept": "application/x-ndjson"},
            )
        except requests.exceptions.ConnectionError as exc:
            raise OllamaError(
                f"Cannot reach Ollama at {self.host}. Make sure Ollama is "
                "running (run 'ollama serve' or start the Ollama app).",
                kind="ollama_unreachable",
                status=503,
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise OllamaError(
                "Ollama did not respond in time. It may still be loading the model.",
                kind="ollama_timeout",
                status=504,
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise OllamaError(
                f"Ollama request failed: {exc}", kind="ollama_error", status=502
            ) from exc

        try:
            if response.status_code >= 400:
                body = _short_body(response)
                if response.status_code == 404:
                    raise OllamaError(
                        f"The model '{self.model}' is not installed. "
                        f"Run: ollama pull {self.model}",
                        kind="model_missing",
                        status=409,
                    )
                raise OllamaError(
                    f"Ollama returned HTTP {response.status_code}: {body}",
                    kind="ollama_http_error",
                    status=502,
                )

            for raw_line in response.iter_lines(decode_unicode=True):
                if not raw_line:
                    continue
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except ValueError:
                    continue
                if isinstance(chunk, dict) and chunk.get("error"):
                    raise OllamaError(
                        f"Ollama error: {chunk['error']}",
                        kind="ollama_error",
                        status=502,
                    )
                message = chunk.get("message") or {}
                content = message.get("content")
                if content:
                    yield {"type": "token", "content": content}
                if chunk.get("done"):
                    yield {
                        "type": "done",
                        "stats": {
                            "model": chunk.get("model") or self.model,
                            "done_reason": chunk.get("done_reason"),
                            "total_duration": chunk.get("total_duration"),
                            "load_duration": chunk.get("load_duration"),
                            "prompt_eval_count": chunk.get("prompt_eval_count"),
                            "eval_count": chunk.get("eval_count"),
                        },
                    }
                    return
        except requests.exceptions.Timeout as exc:
            raise OllamaError(
                "Ollama stopped responding while generating a reply.",
                kind="ollama_timeout",
                status=504,
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise OllamaError(
                f"The connection to Ollama was interrupted: {exc}",
                kind="ollama_stream_error",
                status=502,
            ) from exc
        finally:
            response.close()


def _short_body(response: requests.Response, limit: int = 300) -> str:
    try:
        text = response.text.strip()
    except Exception:  # pragma: no cover - defensive
        return "no details"
    if not text:
        return "no details"
    try:
        data = json.loads(text)
        if isinstance(data, dict) and data.get("error"):
            return str(data["error"])
    except ValueError:
        pass
    return text[:limit]


def _to_int(value: str) -> Optional[int]:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None
