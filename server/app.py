"""
FastAPI server for VizAI Studio.

Provides:
- REST API for code execution, session management, and chat
- Reverse proxy for running Dash apps
- WebSocket endpoint for real-time output streaming
- Static file serving for the frontend UI
"""

import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from .executor import SessionManager

# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

session_manager = SessionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hook."""
    yield
    await session_manager.stop_all()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="VizAI Studio", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared httpx client for proxying
_proxy_client: Optional[httpx.AsyncClient] = None


async def get_proxy_client() -> httpx.AsyncClient:
    global _proxy_client
    if _proxy_client is None or _proxy_client.is_closed:
        _proxy_client = httpx.AsyncClient(timeout=httpx.Timeout(60.0))
    return _proxy_client


# ---------------------------------------------------------------------------
# API: Code execution
# ---------------------------------------------------------------------------


@app.post("/api/execute")
async def execute_code(request: Request) -> JSONResponse:
    """Submit Python/Dash code for execution."""
    data = await request.json()
    code = data.get("code", "")
    session_id = data.get("session_id")

    if not code.strip():
        return JSONResponse({"error": "No code provided"}, status_code=400)

    result = await session_manager.execute(code, session_id)
    return JSONResponse(result)


@app.post("/api/install")
async def install_package(request: Request) -> JSONResponse:
    """Install a Python package via pip."""
    data = await request.json()
    package = data.get("package", "")
    if not package.strip():
        return JSONResponse({"error": "No package specified"}, status_code=400)

    proc = await asyncio.create_subprocess_exec(
        "pip", "install", package,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return JSONResponse({
        "status": "ok" if proc.returncode == 0 else "error",
        "stdout": stdout.decode(errors="replace"),
        "stderr": stderr.decode(errors="replace"),
    })


# ---------------------------------------------------------------------------
# API: Session management
# ---------------------------------------------------------------------------


@app.get("/api/sessions")
async def list_sessions() -> JSONResponse:
    """List all active sessions."""
    return JSONResponse(session_manager.list_sessions())


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str) -> JSONResponse:
    """Get session status and output."""
    return JSONResponse(session_manager.get_status(session_id))


@app.delete("/api/sessions/{session_id}")
async def stop_session(session_id: str) -> JSONResponse:
    """Stop a running session."""
    result = await session_manager.stop(session_id)
    return JSONResponse(result)


# ---------------------------------------------------------------------------
# API: Chat (pluggable LLM backend)
# ---------------------------------------------------------------------------

# Dash app templates for the chat assistant
TEMPLATES = {
    "basic": '''import dash
from dash import html, dcc

app = dash.Dash(__name__)

app.layout = html.Div([
    html.H1("Hello Dash"),
    html.P("Edit this code to build your app!"),
])

if __name__ == "__main__":
    app.run(debug=True)
''',
    "callback": '''import dash
from dash import html, dcc, Input, Output

app = dash.Dash(__name__)

app.layout = html.Div([
    html.H1("Interactive Dash App"),
    dcc.Input(id="input-text", type="text", value="World", debounce=True),
    html.Div(id="output-text"),
])

@app.callback(
    Output("output-text", "children"),
    Input("input-text", "value"),
)
def update_output(value):
    return f"Hello, {value}!"

if __name__ == "__main__":
    app.run(debug=True)
''',
    "graph": '''import dash
from dash import html, dcc, Input, Output
import plotly.express as px
import pandas as pd

app = dash.Dash(__name__)

df = pd.DataFrame({
    "Fruit": ["Apples", "Oranges", "Bananas", "Grapes", "Strawberries"],
    "Amount": [4, 2, 5, 3, 6],
    "City": ["SF", "SF", "NYC", "NYC", "SF"],
})

app.layout = html.Div([
    html.H1("Fruit Sales Dashboard"),
    dcc.Dropdown(
        id="city-dropdown",
        options=[{"label": c, "value": c} for c in df["City"].unique()],
        value=df["City"].unique()[0],
    ),
    dcc.Graph(id="sales-graph"),
])

@app.callback(
    Output("sales-graph", "figure"),
    Input("city-dropdown", "value"),
)
def update_graph(city):
    filtered = df[df["City"] == city]
    fig = px.bar(filtered, x="Fruit", y="Amount", title=f"Sales in {city}")
    return fig

if __name__ == "__main__":
    app.run(debug=True)
''',
    "multi_page": '''import dash
from dash import html, dcc, Input, Output, callback
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np

app = dash.Dash(__name__, suppress_callback_exceptions=True)

# --- Data ---
np.random.seed(42)
df = pd.DataFrame({
    "Date": pd.date_range("2024-01-01", periods=100),
    "Sales": np.random.randint(100, 1000, 100),
    "Region": np.random.choice(["North", "South", "East", "West"], 100),
})

# --- Layouts ---
nav = html.Div([
    dcc.Link("Dashboard", href="/"), html.Span(" | "),
    dcc.Link("Analytics", href="/analytics"),
], style={"padding": "10px", "background": "#f0f0f0"})

dashboard_layout = html.Div([
    nav,
    html.H1("Sales Dashboard"),
    dcc.Dropdown(
        id="region-filter",
        options=[{"label": r, "value": r} for r in df["Region"].unique()],
        value=df["Region"].unique().tolist(),
        multi=True,
    ),
    dcc.Graph(id="sales-timeline"),
])

analytics_layout = html.Div([
    nav,
    html.H1("Analytics"),
    dcc.Graph(
        id="region-pie",
        figure=px.pie(df, names="Region", values="Sales", title="Sales by Region"),
    ),
])

app.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    html.Div(id="page-content"),
])

@callback(Output("page-content", "children"), Input("url", "pathname"))
def display_page(pathname):
    if pathname == "/analytics":
        return analytics_layout
    return dashboard_layout

@callback(Output("sales-timeline", "figure"), Input("region-filter", "value"))
def update_timeline(regions):
    filtered = df[df["Region"].isin(regions)] if regions else df
    fig = px.line(filtered, x="Date", y="Sales", color="Region", title="Sales Over Time")
    return fig

if __name__ == "__main__":
    app.run(debug=True)
''',
    "datatable": '''import dash
from dash import html, dcc, dash_table, Input, Output
import pandas as pd
import numpy as np
import plotly.express as px

app = dash.Dash(__name__)

np.random.seed(0)
df = pd.DataFrame({
    "Name": [f"Product {i}" for i in range(1, 51)],
    "Category": np.random.choice(["Electronics", "Clothing", "Food", "Books"], 50),
    "Price": np.round(np.random.uniform(5, 500, 50), 2),
    "Rating": np.round(np.random.uniform(1, 5, 50), 1),
    "Stock": np.random.randint(0, 200, 50),
})

app.layout = html.Div([
    html.H1("Product Inventory"),
    dcc.Dropdown(
        id="cat-filter",
        options=[{"label": c, "value": c} for c in df["Category"].unique()],
        value=df["Category"].unique().tolist(),
        multi=True,
    ),
    dash_table.DataTable(
        id="product-table",
        columns=[{"name": c, "id": c} for c in df.columns],
        page_size=10,
        sort_action="native",
        filter_action="native",
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "left", "padding": "8px"},
        style_header={"backgroundColor": "#f0f0f0", "fontWeight": "bold"},
    ),
    dcc.Graph(id="price-distribution"),
])

@app.callback(
    [Output("product-table", "data"), Output("price-distribution", "figure")],
    Input("cat-filter", "value"),
)
def update(categories):
    filtered = df[df["Category"].isin(categories)] if categories else df
    fig = px.histogram(filtered, x="Price", color="Category", title="Price Distribution")
    return filtered.to_dict("records"), fig

if __name__ == "__main__":
    app.run(debug=True)
''',
}


@app.post("/api/chat")
async def chat(request: Request) -> JSONResponse:
    """
    Chat endpoint for vibe coding assistant.

    Accepts {"message": "...", "history": [...]} and returns a response.
    This is a template-based assistant. Replace with an LLM integration
    (OpenAI, Anthropic, etc.) for production use.
    """
    data = await request.json()
    message = data.get("message", "").lower().strip()

    # Simple keyword-based matching for templates
    if any(kw in message for kw in ["basic", "hello", "simple", "start", "begin"]):
        return JSONResponse({
            "response": "Here's a basic Dash app to get you started:",
            "code": TEMPLATES["basic"],
        })
    elif any(kw in message for kw in ["callback", "interactive", "input", "click"]):
        return JSONResponse({
            "response": "Here's an interactive app with callbacks:",
            "code": TEMPLATES["callback"],
        })
    elif any(kw in message for kw in ["graph", "chart", "plot", "bar", "visualization", "plotly"]):
        return JSONResponse({
            "response": "Here's a Dash app with an interactive Plotly chart:",
            "code": TEMPLATES["graph"],
        })
    elif any(kw in message for kw in ["multi", "page", "navigation", "route", "routing"]):
        return JSONResponse({
            "response": "Here's a multi-page Dash app with navigation:",
            "code": TEMPLATES["multi_page"],
        })
    elif any(kw in message for kw in ["table", "data", "datatable", "inventory", "grid"]):
        return JSONResponse({
            "response": "Here's a Dash app with DataTable and filtering:",
            "code": TEMPLATES["datatable"],
        })
    else:
        return JSONResponse({
            "response": (
                "I can help you build Dash apps! Try asking for:\n"
                "- **basic** - A simple starter app\n"
                "- **callback** - Interactive app with callbacks\n"
                "- **graph** - App with Plotly charts\n"
                "- **multi page** - Multi-page navigation app\n"
                "- **datatable** - App with sortable/filterable data tables\n\n"
                "Or just describe what you want to build, and paste your code in the editor!"
            ),
            "code": None,
        })


# ---------------------------------------------------------------------------
# WebSocket: Real-time output streaming
# ---------------------------------------------------------------------------


@app.websocket("/ws/session/{session_id}")
async def session_output_ws(websocket: WebSocket, session_id: str):
    """Stream session stdout/stderr in real-time via WebSocket."""
    await websocket.accept()
    last_stdout_idx = 0
    last_stderr_idx = 0

    try:
        while True:
            session = session_manager.get_session(session_id)
            if not session:
                await websocket.send_json({"type": "error", "data": "Session not found"})
                break

            # Send new stdout lines
            if len(session.output_lines) > last_stdout_idx:
                new_lines = session.output_lines[last_stdout_idx:]
                for line in new_lines:
                    if not line.startswith("VIZAI_READY:"):
                        await websocket.send_json({"type": "stdout", "data": line})
                last_stdout_idx = len(session.output_lines)

            # Send new stderr lines
            if len(session.error_lines) > last_stderr_idx:
                new_lines = session.error_lines[last_stderr_idx:]
                for line in new_lines:
                    await websocket.send_json({"type": "stderr", "data": line})
                last_stderr_idx = len(session.error_lines)

            # Check if session ended
            if session.status in ("stopped", "error", "crashed"):
                await websocket.send_json({"type": "status", "data": session.status})
                break

            await asyncio.sleep(0.3)
    except WebSocketDisconnect:
        pass


# ---------------------------------------------------------------------------
# Reverse proxy for Dash apps
# ---------------------------------------------------------------------------


@app.api_route(
    "/app/{session_id}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
)
async def proxy_dash_app(session_id: str, path: str, request: Request) -> Response:
    """Reverse-proxy requests to the running Dash app."""
    session = session_manager.get_session(session_id)
    if not session:
        return JSONResponse({"error": "Session not found"}, status_code=404)
    if session.status != "running":
        return JSONResponse(
            {"error": f"Session is {session.status}"}, status_code=503
        )

    target_url = f"http://127.0.0.1:{session.port}/{path}"

    # Build query string
    if request.url.query:
        target_url += f"?{request.url.query}"

    client = await get_proxy_client()

    # Forward headers, skipping hop-by-hop ones
    skip_headers = {"host", "transfer-encoding", "connection"}
    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in skip_headers
    }

    try:
        body = await request.body()
        resp = await client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=body,
            follow_redirects=False,
        )
    except httpx.ConnectError:
        return JSONResponse(
            {"error": "Dash app is not responding"}, status_code=502
        )
    except httpx.TimeoutException:
        return JSONResponse(
            {"error": "Dash app timed out"}, status_code=504
        )

    # Build response, preserving content type
    resp_headers = dict(resp.headers)
    # Remove hop-by-hop
    for h in ("transfer-encoding", "connection", "content-encoding", "content-length"):
        resp_headers.pop(h, None)

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=resp_headers,
    )


# Handle root of app path (no trailing path)
@app.api_route(
    "/app/{session_id}",
    methods=["GET"],
)
async def proxy_dash_app_root(session_id: str, request: Request) -> Response:
    """Redirect to include trailing slash so Dash routing works correctly."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/app/{session_id}/")


# ---------------------------------------------------------------------------
# Serve frontend (must be last - catch-all mount)
# ---------------------------------------------------------------------------

STUDIO_DIR = Path(__file__).parent.parent / "studio"

if STUDIO_DIR.exists():
    app.mount("/static", StaticFiles(directory=STUDIO_DIR / "static"), name="static")

    @app.get("/")
    async def serve_index() -> HTMLResponse:
        index_path = STUDIO_DIR / "index.html"
        return HTMLResponse(index_path.read_text())
