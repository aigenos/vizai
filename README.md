# VizAI Studio

A Python/Dash code execution service with an integrated UI studio for vibe coding interactive Dash applications.

## Features

- **Code Editor** - Full-featured Python editor (CodeMirror) with syntax highlighting, bracket matching, code folding, and keyboard shortcuts
- **Live Preview** - Run Dash apps and see them rendered in a live preview pane with full interactivity
- **Chat Assistant** - Built-in chat for vibe coding with template-based suggestions (pluggable LLM backend)
- **Full Dash Support** - No limitations: callbacks, multi-page apps, DataTables, graphs, all dcc/html components, pattern-matching callbacks, clientside callbacks
- **Real-time Console** - WebSocket-based live stdout/stderr streaming from running apps
- **Session Management** - Multiple sessions, start/stop/restart apps, automatic cleanup
- **Reverse Proxy** - Transparent proxying of Dash app requests so all component interactions work seamlessly

## Architecture

```
┌──────────────────────────────────────────────────────┐
│  Browser - VizAI Studio UI                           │
│  ┌──────────┬──────────────┬───────────────────────┐ │
│  │   Chat   │    Editor    │       Preview          │ │
│  │  Panel   │  (CodeMirror)│  (iframe → Dash app)  │ │
│  └──────────┴──────────────┴───────────────────────┘ │
└────────────────────┬─────────────────────────────────┘
                     │ HTTP / WebSocket
┌────────────────────▼─────────────────────────────────┐
│  FastAPI Server (port 8000)                          │
│  ├── /api/execute     - Submit code for execution    │
│  ├── /api/sessions/*  - Session management           │
│  ├── /api/chat        - Chat assistant               │
│  ├── /api/install     - pip install packages         │
│  ├── /ws/session/*    - Live output streaming        │
│  └── /app/{id}/*      - Reverse proxy to Dash apps   │
└────────────────────┬─────────────────────────────────┘
                     │ Subprocess management
┌────────────────────▼─────────────────────────────────┐
│  Dash App Processes (ports 8050-8200)                │
│  Each user session runs an isolated Dash server      │
└──────────────────────────────────────────────────────┘
```

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Start the server
python run.py

# Open in browser
# http://localhost:8000
```

## Usage

1. Open `http://localhost:8000` in your browser
2. Write Dash app code in the editor (a sample app is pre-loaded)
3. Press **Run** (or `Ctrl+Enter`) to execute
4. The Dash app renders in the Preview pane with full interactivity
5. Use the Chat panel to get code templates and suggestions

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/api/execute` | POST | Execute Python/Dash code `{"code": "...", "session_id": "..."}` |
| `/api/sessions` | GET | List all active sessions |
| `/api/sessions/{id}` | GET | Get session status and output |
| `/api/sessions/{id}` | DELETE | Stop a running session |
| `/api/chat` | POST | Chat with assistant `{"message": "..."}` |
| `/api/install` | POST | Install pip package `{"package": "..."}` |
| `/ws/session/{id}` | WS | Real-time output streaming |
| `/app/{id}/` | * | Reverse proxy to running Dash app |

## Chat Assistant Integration

The built-in chat provides template-based code generation. To integrate a real LLM:

1. Edit `server/app.py`, find the `/api/chat` endpoint
2. Replace the template matching with your LLM API call (OpenAI, Anthropic, etc.)
3. Return `{"response": "...", "code": "..."}` where `code` is optional Python code to load into the editor
