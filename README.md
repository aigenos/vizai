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

## Demo Apps

Once the server is running, paste any of these into the editor and press **Run** (or `Ctrl+Enter`) to see them live.

### 1. Interactive Sales Dashboard

A bar chart with dropdown filtering — demonstrates `dcc.Graph`, `dcc.Dropdown`, and callbacks.

```python
import dash
from dash import html, dcc, Input, Output
import plotly.express as px
import pandas as pd

app = dash.Dash(__name__)

df = pd.DataFrame({
    "Fruit": ["Apples", "Oranges", "Bananas", "Grapes", "Strawberries"] * 2,
    "Amount": [4, 2, 5, 3, 6, 3, 4, 2, 5, 4],
    "City": ["San Francisco"] * 5 + ["New York"] * 5,
})

app.layout = html.Div([
    html.H1("Fruit Sales Dashboard", style={"textAlign": "center"}),
    dcc.Dropdown(
        id="city-dropdown",
        options=[{"label": c, "value": c} for c in df["City"].unique()],
        value="San Francisco",
        style={"width": "300px", "margin": "0 auto"},
    ),
    dcc.Graph(id="sales-graph"),
], style={"maxWidth": "800px", "margin": "0 auto", "padding": "20px"})


@app.callback(Output("sales-graph", "figure"), Input("city-dropdown", "value"))
def update_graph(city):
    filtered = df[df["City"] == city]
    fig = px.bar(filtered, x="Fruit", y="Amount", color="Fruit",
                 title=f"Sales in {city}")
    fig.update_layout(template="plotly_white", showlegend=False)
    return fig


if __name__ == "__main__":
    app.run(debug=True)
```

### 2. Real-time Scatter Plot with Sliders

Multiple `dcc.Slider` controls driving a scatter plot — demonstrates multi-input callbacks and `dcc.Slider`.

```python
import dash
from dash import html, dcc, Input, Output
import plotly.express as px
import numpy as np
import pandas as pd

app = dash.Dash(__name__)

app.layout = html.Div([
    html.H1("Random Data Explorer", style={"textAlign": "center"}),

    html.Div([
        html.Label("Number of points:"),
        dcc.Slider(id="n-points", min=10, max=500, step=10, value=100,
                   marks={i: str(i) for i in range(0, 501, 100)}),
    ], style={"margin": "20px 40px"}),

    html.Div([
        html.Label("Noise level:"),
        dcc.Slider(id="noise", min=0, max=5, step=0.1, value=1,
                   marks={i: str(i) for i in range(6)}),
    ], style={"margin": "20px 40px"}),

    dcc.Graph(id="scatter"),
], style={"maxWidth": "900px", "margin": "0 auto"})


@app.callback(
    Output("scatter", "figure"),
    Input("n-points", "value"),
    Input("noise", "value"),
)
def update(n, noise):
    np.random.seed(42)
    x = np.linspace(0, 10, n)
    y = np.sin(x) + np.random.normal(0, noise, n)
    df = pd.DataFrame({"x": x, "y": y})
    fig = px.scatter(df, x="x", y="y", title=f"{n} points, noise={noise}",
                     color="y", color_continuous_scale="Viridis")
    fig.update_layout(template="plotly_white")
    return fig


if __name__ == "__main__":
    app.run(debug=True)
```

### 3. Multi-Tab Dashboard with DataTable

Tabs, DataTable with sorting/filtering, and a linked histogram — demonstrates `dcc.Tabs`, `dash_table.DataTable`, and multi-output callbacks.

```python
import dash
from dash import html, dcc, dash_table, Input, Output
import plotly.express as px
import pandas as pd
import numpy as np

app = dash.Dash(__name__)

np.random.seed(0)
df = pd.DataFrame({
    "Product": [f"Product {i}" for i in range(1, 51)],
    "Category": np.random.choice(["Electronics", "Clothing", "Food", "Books"], 50),
    "Price": np.round(np.random.uniform(5, 500, 50), 2),
    "Rating": np.round(np.random.uniform(1, 5, 50), 1),
    "Stock": np.random.randint(0, 200, 50),
})

app.layout = html.Div([
    html.H1("Product Inventory", style={"textAlign": "center"}),
    dcc.Tabs(id="tabs", value="table", children=[
        dcc.Tab(label="Data Table", value="table"),
        dcc.Tab(label="Analytics", value="analytics"),
    ]),
    html.Div(id="tab-content"),
], style={"maxWidth": "1000px", "margin": "0 auto", "padding": "20px"})


@app.callback(Output("tab-content", "children"), Input("tabs", "value"))
def render_tab(tab):
    if tab == "table":
        return html.Div([
            dcc.Dropdown(
                id="cat-filter",
                options=[{"label": c, "value": c} for c in df["Category"].unique()],
                value=df["Category"].unique().tolist(),
                multi=True,
                placeholder="Filter by category...",
            ),
            dash_table.DataTable(
                id="product-table",
                columns=[{"name": c, "id": c} for c in df.columns],
                data=df.to_dict("records"),
                page_size=10,
                sort_action="native",
                filter_action="native",
                style_table={"overflowX": "auto"},
                style_cell={"textAlign": "left", "padding": "8px"},
                style_header={"backgroundColor": "#f0f0f0", "fontWeight": "bold"},
            ),
        ])
    else:
        return html.Div([
            dcc.Graph(figure=px.histogram(df, x="Price", color="Category",
                                          title="Price Distribution")),
            dcc.Graph(figure=px.box(df, x="Category", y="Rating",
                                    title="Ratings by Category")),
        ])


if __name__ == "__main__":
    app.run(debug=True)
```

### 4. Multi-Page App with Navigation

Client-side routing with `dcc.Location` and `dcc.Link` — demonstrates multi-page Dash apps.

```python
import dash
from dash import html, dcc, Input, Output, callback
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np

app = dash.Dash(__name__, suppress_callback_exceptions=True)

np.random.seed(42)
dates = pd.date_range("2024-01-01", periods=90)
df = pd.DataFrame({
    "Date": dates,
    "Revenue": np.cumsum(np.random.normal(100, 30, 90)),
    "Users": np.cumsum(np.random.poisson(5, 90)),
    "Region": np.random.choice(["North", "South", "East", "West"], 90),
})

nav_style = {"padding": "12px 20px", "background": "#2c3e50",
             "display": "flex", "gap": "20px"}
link_style = {"color": "white", "fontSize": "14px", "textDecoration": "none"}

nav = html.Div([
    html.Strong("MyApp", style={"color": "#3498db", "fontSize": "16px"}),
    dcc.Link("Dashboard", href="/", style=link_style),
    dcc.Link("Users", href="/users", style=link_style),
    dcc.Link("About", href="/about", style=link_style),
], style=nav_style)

app.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    nav,
    html.Div(id="page"),
])


@callback(Output("page", "children"), Input("url", "pathname"))
def route(path):
    if path == "/users":
        return html.Div([
            html.H2("User Growth"),
            dcc.Graph(figure=px.area(df, x="Date", y="Users",
                                     title="Cumulative Users")),
        ], style={"padding": "20px"})
    elif path == "/about":
        return html.Div([
            html.H2("About"),
            html.P("A demo multi-page Dash application built with VizAI Studio."),
            html.P("Navigate using the links above to explore different pages."),
        ], style={"padding": "20px"})
    else:
        return html.Div([
            html.H2("Revenue Dashboard"),
            dcc.Dropdown(id="region", options=[{"label": r, "value": r}
                         for r in df["Region"].unique()],
                         value=df["Region"].unique().tolist(), multi=True),
            dcc.Graph(id="rev-chart"),
        ], style={"padding": "20px"})


@callback(Output("rev-chart", "figure"), Input("region", "value"))
def update_rev(regions):
    filtered = df[df["Region"].isin(regions)] if regions else df
    fig = px.line(filtered, x="Date", y="Revenue", color="Region",
                  title="Revenue Over Time")
    fig.update_layout(template="plotly_white")
    return fig


if __name__ == "__main__":
    app.run(debug=True)
```

### 5. Live-Updating Dashboard with Intervals

Auto-refreshing metrics using `dcc.Interval` — demonstrates real-time updates without user interaction.

```python
import dash
from dash import html, dcc, Input, Output
import plotly.graph_objects as go
import random
import datetime

app = dash.Dash(__name__)

app.layout = html.Div([
    html.H1("Live System Monitor", style={"textAlign": "center"}),
    dcc.Interval(id="timer", interval=2000, n_intervals=0),

    html.Div(id="metrics", style={
        "display": "flex", "justifyContent": "center", "gap": "30px",
        "margin": "20px",
    }),

    dcc.Graph(id="cpu-gauge"),
], style={"maxWidth": "800px", "margin": "0 auto", "padding": "20px"})


def metric_card(title, value, color):
    return html.Div([
        html.H4(title, style={"margin": "0", "color": "#666"}),
        html.H2(value, style={"margin": "5px 0", "color": color}),
    ], style={"textAlign": "center", "padding": "15px 30px",
              "border": "1px solid #eee", "borderRadius": "8px"})


@app.callback(
    Output("metrics", "children"),
    Output("cpu-gauge", "figure"),
    Input("timer", "n_intervals"),
)
def update(n):
    cpu = random.uniform(20, 95)
    mem = random.uniform(40, 85)
    net = random.randint(50, 500)

    cards = [
        metric_card("CPU", f"{cpu:.1f}%", "#e74c3c" if cpu > 80 else "#2ecc71"),
        metric_card("Memory", f"{mem:.1f}%", "#e67e22" if mem > 70 else "#3498db"),
        metric_card("Network", f"{net} Mbps", "#9b59b6"),
    ]

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=cpu,
        title={"text": f"CPU Usage — {datetime.datetime.now().strftime('%H:%M:%S')}"},
        delta={"reference": 50},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "#e74c3c" if cpu > 80 else "#2ecc71"},
            "steps": [
                {"range": [0, 50], "color": "#eafaf1"},
                {"range": [50, 80], "color": "#fef9e7"},
                {"range": [80, 100], "color": "#fdedec"},
            ],
        },
    ))
    fig.update_layout(height=350)

    return cards, fig


if __name__ == "__main__":
    app.run(debug=True)
```

## Chat Assistant Integration

The built-in chat provides template-based code generation. To integrate a real LLM:

1. Edit `server/app.py`, find the `/api/chat` endpoint
2. Replace the template matching with your LLM API call (OpenAI, Anthropic, etc.)
3. Return `{"response": "...", "code": "..."}` where `code` is optional Python code to load into the editor
