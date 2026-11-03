# LocalGPT

LocalGPT is a complete, ChatGPT-style AI assistant that runs **entirely on your own Windows computer**. It uses [Ollama](https://ollama.com) for local inference, Flask for the backend, SQLite for persistent conversation history, and a self-contained HTML/CSS/JavaScript frontend.

There are no API keys, no paid subscriptions, no cloud AI services, no telemetry, and no external requests during normal use. After the initial installation and model download, LocalGPT works completely offline.

```
Browser  ->  Flask (127.0.0.1:5000)  ->  Ollama (127.0.0.1:11434)  ->  llama3.2:3b
                    |
                    +-> SQLite (database/localgpt.db)
```

---

## Features

- Polished dark, ChatGPT-inspired interface
- Streaming responses over Server-Sent Events (SSE)
- Persistent conversations and messages in SQLite
- Conversation history sidebar with automatic titles
- New chat, clear conversation, and delete conversation
- Markdown rendering, code blocks, local syntax highlighting, and copy buttons
- Typing indicator, stop button, auto-scroll, and responsive mobile layout
- Local AI connection indicator with model and GPU information
- Configurable model, context window, sampling parameters, and system prompt
- Friendly error handling for offline Ollama, missing models, timeouts, and invalid input
- Localhost-only binding and a localhost-only API guard
- No CDN dependencies: every frontend asset is served locally
- **Real-time awareness**: Local date/time, timezone detection, date/time calculations, timezone conversion
- **Optional web search**: Free web search for current external information (disabled by default, local-first)

---

## Requirements

| Component | Requirement |
| --- | --- |
| OS | Windows 10/11 (also runs on macOS/Linux with Python) |
| Python | 3.9 or newer (tested with Python 3.14.7) |
| Ollama | Installed and available in `PATH` (tested with 0.40.13) |
| Model | `llama3.2:3b` (about 2 GB download) |
| RAM | 8 GB minimum; 16 GB recommended |
| GPU | Optional. Ollama automatically uses a supported NVIDIA/AMD GPU when available. |

The project was built and tested on Windows 11 with 16 GB RAM, an Intel Core i5, and an NVIDIA RTX 3050 6 GB Laptop GPU.

---

## Installation

### 1. Install Ollama

Download and install Ollama from <https://ollama.com/download>. Confirm it works:

```bat
ollama --version
```

### 2. Download the model

```bat
ollama pull llama3.2:3b
```

### 3. Start LocalGPT

Double-click **`run.bat`**, or run it from a terminal:

```bat
run.bat
```

`run.bat` automatically:

1. Creates a local `.venv` virtual environment if needed.
2. Installs the Python dependencies from `requirements.txt`.
3. Starts Ollama if it is not already running.
4. Downloads `llama3.2:3b` if it is missing.
5. Starts the Flask server and opens <http://127.0.0.1:5000>.

### Manual installation

```bat
py -3 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
ollama serve
ollama pull llama3.2:3b
python app.py
```

Then open <http://127.0.0.1:5000>.

---

## How to run

```bat
run.bat
```

or, with the virtual environment active:

```bat
python app.py
```

The application listens on `http://127.0.0.1:5000` by default. Press `Ctrl+C` in the terminal to stop the server.

Set `LOCALGPT_NO_BROWSER=1` before running `run.bat` if you do not want it to open a browser automatically:

```bat
set LOCALGPT_NO_BROWSER=1
run.bat
```

---

## Project structure

```
LocalGPT/
├── app.py                    Flask application, routes, SSE endpoint, security
├── config.py                 Environment-driven configuration
├── requirements.txt          Flask + requests
├── run.bat                   One-click Windows launcher
├── README.md
├── .gitignore
│
├── backend/
│   ├── __init__.py
│   ├── chatbot.py            Context assembly, streaming, persistence
│   ├── ollama_client.py      Local Ollama HTTP client + GPU detection
│   ├── conversation.py       Conversation domain logic and auto-titles
│   └── database.py           SQLite schema and queries
│
├── frontend/
│   ├── index.html            Application shell
│   ├── style.css             Dark responsive UI
│   ├── script.js             Chat logic, SSE, markdown, highlighting
│   └── assets/
│       ├── favicon.svg
│       └── logo.svg
│
└── database/
    ├── .gitkeep
    └── localgpt.db           Created automatically (git-ignored)
```

---

## Configuration

All settings can be overridden with environment variables. Defaults are tuned for a 16 GB machine with a 6 GB GPU, but Ollama decides whether to use GPU or CPU.

| Variable | Default | Description |
| --- | --- | --- |
| `LOCALGPT_HOST` | `127.0.0.1` | Flask bind address. Keep it on loopback for privacy. |
| `LOCALGPT_PORT` | `5000` | Flask port. |
| `LOCALGPT_MODEL` | `llama3.2:3b` | Ollama model to use. |
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Local Ollama API address. |
| `LOCALGPT_NUM_CTX` | `4096` | Context window size. Lower it to reduce VRAM/RAM use. |
| `LOCALGPT_NUM_PREDICT` | `1024` | Maximum tokens generated per reply. |
| `LOCALGPT_TEMPERATURE` | `0.7` | Sampling temperature. |
| `LOCALGPT_TOP_P` | `0.9` | Nucleus sampling value. |
| `LOCALGPT_REPEAT_PENALTY` | `1.1` | Repetition penalty. |
| `LOCALGPT_KEEP_ALIVE` | `10m` | How long Ollama keeps the model loaded. |
| `LOCALGPT_CONNECT_TIMEOUT` | `5` | Ollama connection timeout (seconds). |
| `LOCALGPT_READ_TIMEOUT` | `300` | Ollama generation timeout (seconds). |
| `LOCALGPT_MAX_MESSAGE_CHARS` | `32000` | Maximum user message length. |
| `LOCALGPT_DB` | `database/localgpt.db` | SQLite database path. |
| `LOCALGPT_SYSTEM_PROMPT` | built-in | Override the assistant's system prompt. |
| `LOCALGPT_DEBUG` | `0` | Set to `1` for Flask debug mode. |
| `LOCALGPT_TIMEZONE` | `Asia/Kolkata` | Timezone for real-time awareness (IANA format). |
| `LOCALGPT_LOCATION` | `Pune, India` | Configurable location shown in context. |
| `LOCALGPT_ENABLE_WEB_SEARCH` | `0` | Set to `1` to enable optional web search. |

Example (Windows Command Prompt):

```bat
set LOCALGPT_MODEL=llama3.1:8b
set LOCALGPT_NUM_CTX=8192
run.bat
```

Example (PowerShell):

```powershell
$env:LOCALGPT_MODEL = "llama3.1:8b"
$env:LOCALGPT_NUM_CTX = "8192"
.\run.bat
```

---

## Switching models

1. Pull the model you want:

   ```bat
   ollama pull llama3.1:8b
   ```

2. Start LocalGPT with `LOCALGPT_MODEL` set to that model:

   ```bat
   set LOCALGPT_MODEL=llama3.1:8b
   run.bat
   ```

3. Or edit the default in `config.py`.

Restart the server after changing the model. The active model is shown in the top bar and in the sidebar status card. `GET /api/models` lists all installed Ollama models.

Suggested alternatives for different hardware:

- `llama3.2:1b` – fastest, lowest memory
- `llama3.2:3b` – default balance
- `llama3.1:8b` / `qwen2.5:7b` – stronger reasoning, more VRAM/RAM
- `qwen2.5-coder:7b` – programming-focused

---

## API endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/` | Web interface |
| `GET` | `/api/health` | Simple health check |
| `GET` | `/api/status?force=1` | Ollama status, installed models, loaded model, GPU info |
| `GET` | `/api/models` | Installed Ollama models |
| `GET` | `/api/config` | Active non-secret configuration |
| `GET` | `/api/conversations` | List conversations (newest first) |
| `POST` | `/api/conversations` | Create a conversation (`{"title": "optional"}`) |
| `GET` | `/api/conversations/<id>` | Conversation with all messages |
| `PATCH` | `/api/conversations/<id>` | Rename (`{"title": "New title"}`) |
| `DELETE` | `/api/conversations/<id>` | Delete a conversation and its messages |
| `DELETE` | `/api/conversations/<id>/messages` | Clear all messages, keep the conversation |
| `POST` | `/api/chat` | Stream a reply as SSE (`{"conversation_id": 1, "message": "Hi"}`) |

`conversation_id` is optional in `/api/chat`; if omitted, a new conversation is created automatically.

### Streaming format

`POST /api/chat` returns `text/event-stream` with four event types:

```
event: meta
data: {"type":"meta","conversation":{...},"user_message":{...}}

event: token
data: {"type":"token","content":"Hello"}

event: done
data: {"type":"done","assistant_message":{...},"conversation":{...},"stats":{...}}

event: error
data: {"type":"error","error":"model_missing","message":"..."}
```

The frontend uses `fetch()` with a `ReadableStream` reader so it can send a POST body (native `EventSource` only supports GET). The Stop button aborts the request; the backend persists any partial reply before closing.

---

## Database

SQLite is initialized automatically on startup. WAL mode and foreign keys are enabled.

**conversations**

| Column | Type | Notes |
| --- | --- | --- |
| `id` | INTEGER | Primary key, autoincrement |
| `title` | TEXT | Auto-generated from the first user message |
| `created_at` | TEXT | ISO-8601 UTC |
| `updated_at` | TEXT | ISO-8601 UTC, updated on each message |

**messages**

| Column | Type | Notes |
| --- | --- | --- |
| `id` | INTEGER | Primary key, autoincrement |
| `conversation_id` | INTEGER | Foreign key, cascades on delete |
| `role` | TEXT | `user`, `assistant`, or `system` |
| `content` | TEXT | Message body |
| `created_at` | TEXT | ISO-8601 UTC |

Conversation history survives application restarts. To reset everything, stop the server and delete `database/localgpt.db` (plus any `-wal`/`-shm` files); it will be recreated automatically.

---

## Privacy and security

- Flask binds to `127.0.0.1` by default, not to the public network.
- All `/api/*` routes reject non-loopback clients.
- State-changing API requests from non-local browser origins are rejected.
- All AI inference goes to the local Ollama instance at `127.0.0.1:11434`.
- No OpenAI, Gemini, Claude, Groq, Together AI, or any other cloud inference is used.
- No API keys exist or are stored.
- No analytics, telemetry, or tracking.
- Frontend assets are bundled locally, so the UI works offline.
- Inputs are validated and length-limited; SQL uses parameterized queries.
- Assistant markdown is HTML-escaped before rendering, and links are restricted to `http(s)`.
- Security headers include CSP, `X-Content-Type-Options`, `X-Frame-Options`, and `Referrer-Policy`.

The only internet access is during initial setup: installing Python packages and downloading the Ollama model.

---

## Performance notes

- Ollama automatically selects GPU or CPU acceleration. LocalGPT never forces GPU usage.
- The status endpoint detects an NVIDIA GPU through `nvidia-smi` when available and shows it in the sidebar status tooltip.
- `num_ctx=4096` and `num_predict=1024` keep memory use modest while allowing long conversations. The prompt builder trims older history to fit the context window.
- `keep_alive=10m` keeps the model loaded between messages, so the first reply after starting Ollama is slower than later ones.
- If you have limited VRAM, lower `LOCALGPT_NUM_CTX` (for example, `2048`) or use a smaller model.
- If Ollama is using CPU and replies are slow, close other GPU-heavy applications and check `ollama ps`.

---

## Troubleshooting

**"Ollama offline" in the sidebar**
Start the Ollama app or run `ollama serve` in a terminal, then click the status card to refresh.

**"The model 'llama3.2:3b' is not installed"**
Run `ollama pull llama3.2:3b`, or set `LOCALGPT_MODEL` to a model you already have. Check installed models with `ollama list`.

**Port 5000 is already in use**
Set a different port and restart:

```bat
set LOCALGPT_PORT=5001
run.bat
```

Find the process using the port with `netstat -ano | findstr :5000`.

**`python` or `py` is not recognized**
Install Python 3.9+ from <https://www.python.org/downloads/> and enable "Add Python to PATH" during installation.

**The first response takes a long time**
Ollama is loading the model into memory. This is normal on the first request after startup. Later replies are faster while the model stays loaded.

**GPU is not being used**
Ollama decides hardware acceleration. Update your GPU driver, check that Ollama supports your GPU, and inspect `ollama ps` (the `size_vram` column). You can also try a smaller model or context size.

**The interface looks stale after an update**
Press `Ctrl+F5` in the browser to bypass the cache.

**Dependency installation fails**
Make sure you have an internet connection during the initial setup, then run:

```bat
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

---

## Testing performed

The application was run and tested end to end on Windows 11 with Python 3.14.7, Ollama 0.40.13, `llama3.2:3b`, and an RTX 3050 6 GB.

Backend checks:

- Server starts and serves the UI, CSS, JavaScript, and SVG assets
- Ollama status reports online, model installed, version, and GPU details
- Streaming SSE returns `meta`, `token`, and `done` events
- AI answers basic questions and maintains conversation context (tested with a remembered fact)
- Conversations are created, listed, renamed, cleared, and deleted
- Messages persist across a full server restart
- Auto-creation of a conversation when `conversation_id` is omitted
- Invalid JSON, empty messages, oversized messages, invalid IDs, and missing conversations return proper errors
- Missing model returns a friendly `model_missing` error
- Unreachable Ollama returns a friendly `ollama_unreachable` error and an offline status
- Unicode messages (accented characters, emoji, Japanese) round-trip through SSE and SQLite
- Stop button aborts generation and persists the partial reply
- No external network requests are made during chat operation

Browser checks (headless Chrome via DevTools Protocol, 18 assertions, all passed):

- Dark stylesheet loads; welcome screen and four suggestion cards render
- Conversation history renders and the model/status indicators update
- New chat creates and activates a conversation
- Typing indicator appears, tokens stream into the assistant bubble, and stats display
- Markdown and fenced code blocks render with local syntax highlighting and a copy button
- Sidebar title updates automatically from the first message
- Clear conversation and delete conversation work through the confirmation dialogs
- No uncaught browser errors

---

## Limitations

- LocalGPT is a single-user local application; there is no authentication because it only listens on loopback.
- The model cannot browse the internet or provide real-time information.
- Reply quality and speed depend on the selected model and available hardware.
- The default 4096-token context window is intentionally conservative; increase `LOCALGPT_NUM_CTX` if your hardware allows it.
- The Flask development server is used for local hosting. It is appropriate for a personal localhost app, not for public deployment.

---

Built with Python, Flask, Ollama, SQLite, HTML, CSS, and vanilla JavaScript. No cloud AI, no API keys, no subscriptions.
