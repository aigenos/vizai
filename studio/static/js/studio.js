/**
 * VizAI Studio - Frontend Application
 *
 * Manages the code editor, chat interface, preview pane,
 * and communication with the backend execution service.
 */

(function () {
    "use strict";

    // =========================================================================
    // State
    // =========================================================================

    const state = {
        editor: null,
        sessionId: null,
        ws: null,
        isRunning: false,
    };

    // =========================================================================
    // DOM references
    // =========================================================================

    const $ = (sel) => document.querySelector(sel);
    const dom = {
        btnRun: $("#btn-run"),
        btnStop: $("#btn-stop"),
        btnRefresh: $("#btn-refresh"),
        btnSend: $("#btn-send"),
        btnClearChat: $("#btn-clear-chat"),
        btnClearConsole: $("#btn-clear-console"),
        chatMessages: $("#chat-messages"),
        chatInput: $("#chat-input"),
        editorContainer: $("#editor-container"),
        consoleOutput: $("#console-output"),
        previewPlaceholder: $("#preview-placeholder"),
        previewIframe: $("#preview-iframe"),
        statusBadge: $("#session-status"),
        resizerLeft: $("#resizer-left"),
        resizerRight: $("#resizer-right"),
    };

    // =========================================================================
    // Default code
    // =========================================================================

    const DEFAULT_CODE = `import dash
from dash import html, dcc, Input, Output
import plotly.express as px
import pandas as pd

app = dash.Dash(__name__)

# Sample data
df = pd.DataFrame({
    "Fruit": ["Apples", "Oranges", "Bananas", "Grapes", "Strawberries"],
    "Amount": [4, 2, 5, 3, 6],
    "City": ["SF", "SF", "NYC", "NYC", "SF"],
})

app.layout = html.Div([
    html.H1("Fruit Sales Dashboard", style={"textAlign": "center"}),

    dcc.Dropdown(
        id="city-dropdown",
        options=[{"label": c, "value": c} for c in df["City"].unique()],
        value="SF",
        style={"width": "300px", "margin": "20px auto"},
    ),

    dcc.Graph(id="sales-graph"),
])


@app.callback(
    Output("sales-graph", "figure"),
    Input("city-dropdown", "value"),
)
def update_graph(city):
    filtered = df[df["City"] == city]
    fig = px.bar(
        filtered, x="Fruit", y="Amount",
        color="Fruit", title=f"Fruit Sales in {city}"
    )
    fig.update_layout(template="plotly_white")
    return fig


if __name__ == "__main__":
    app.run(debug=True)
`;

    // =========================================================================
    // Editor setup
    // =========================================================================

    function initEditor() {
        state.editor = CodeMirror(dom.editorContainer, {
            value: DEFAULT_CODE,
            mode: "python",
            theme: "dracula",
            lineNumbers: true,
            matchBrackets: true,
            autoCloseBrackets: true,
            styleActiveLine: true,
            indentUnit: 4,
            tabSize: 4,
            indentWithTabs: false,
            lineWrapping: false,
            foldGutter: true,
            gutters: ["CodeMirror-linenumbers", "CodeMirror-foldgutter"],
            extraKeys: {
                "Ctrl-Enter": runCode,
                "Cmd-Enter": runCode,
                "Ctrl-/": "toggleComment",
                "Cmd-/": "toggleComment",
                Tab: (cm) => {
                    if (cm.somethingSelected()) {
                        cm.indentSelection("add");
                    } else {
                        cm.replaceSelection("    ", "end");
                    }
                },
            },
        });
    }

    // =========================================================================
    // Console
    // =========================================================================

    function consolePrint(text, cls = "stdout") {
        const line = document.createElement("div");
        line.className = cls;
        line.textContent = text;
        dom.consoleOutput.appendChild(line);
        dom.consoleOutput.scrollTop = dom.consoleOutput.scrollHeight;
    }

    function consoleClear() {
        dom.consoleOutput.innerHTML = "";
    }

    // =========================================================================
    // Status
    // =========================================================================

    function setStatus(text, cls = "") {
        dom.statusBadge.textContent = text;
        dom.statusBadge.className = "status-badge " + cls;
    }

    function setRunning(running) {
        state.isRunning = running;
        dom.btnRun.disabled = running;
        dom.btnStop.disabled = !running;
    }

    // =========================================================================
    // Code execution
    // =========================================================================

    async function runCode() {
        const code = state.editor.getValue().trim();
        if (!code) {
            consolePrint("No code to run.", "stderr");
            return;
        }

        consoleClear();
        consolePrint("Starting app...", "info");
        setStatus("Starting...", "starting");
        setRunning(true);

        // Hide preview, show placeholder
        dom.previewIframe.style.display = "none";
        dom.previewPlaceholder.style.display = "flex";

        try {
            const resp = await fetch("/api/execute", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    code: code,
                    session_id: state.sessionId,
                }),
            });

            const data = await resp.json();

            if (data.error) {
                consolePrint("Error: " + data.error, "stderr");
                setStatus("Error", "error");
                setRunning(false);
                return;
            }

            state.sessionId = data.session_id;

            // Print captured output
            if (data.output) {
                data.output.forEach((l) => {
                    if (!l.startsWith("VIZAI_READY:")) consolePrint(l, "stdout");
                });
            }
            if (data.errors) {
                data.errors.forEach((l) => consolePrint(l, "stderr"));
            }

            if (data.status === "running") {
                consolePrint("App is running at " + data.app_url, "success");
                setStatus("Running", "running");

                // Load preview
                dom.previewPlaceholder.style.display = "none";
                dom.previewIframe.style.display = "block";
                dom.previewIframe.src = data.app_url;

                // Connect WebSocket for live output
                connectWS(data.session_id);
            } else {
                consolePrint("App failed to start. Check errors above.", "stderr");
                setStatus("Error", "error");
                setRunning(false);
            }
        } catch (err) {
            consolePrint("Network error: " + err.message, "stderr");
            setStatus("Error", "error");
            setRunning(false);
        }
    }

    async function stopCode() {
        if (!state.sessionId) return;

        try {
            await fetch("/api/sessions/" + state.sessionId, { method: "DELETE" });
        } catch (_) {
            // ignore
        }

        disconnectWS();
        consolePrint("App stopped.", "info");
        setStatus("Stopped");
        setRunning(false);

        dom.previewIframe.style.display = "none";
        dom.previewIframe.src = "";
        dom.previewPlaceholder.style.display = "flex";
        state.sessionId = null;
    }

    // =========================================================================
    // WebSocket for live output
    // =========================================================================

    function connectWS(sessionId) {
        disconnectWS();

        const proto = location.protocol === "https:" ? "wss:" : "ws:";
        const url = `${proto}//${location.host}/ws/session/${sessionId}`;

        state.ws = new WebSocket(url);

        state.ws.onmessage = (evt) => {
            try {
                const msg = JSON.parse(evt.data);
                if (msg.type === "stdout") {
                    consolePrint(msg.data, "stdout");
                } else if (msg.type === "stderr") {
                    consolePrint(msg.data, "stderr");
                } else if (msg.type === "status") {
                    if (msg.data === "crashed" || msg.data === "error") {
                        consolePrint("App " + msg.data + ".", "stderr");
                        setStatus(msg.data, msg.data);
                        setRunning(false);
                    }
                }
            } catch (_) {
                // ignore parse errors
            }
        };

        state.ws.onclose = () => {
            state.ws = null;
        };
    }

    function disconnectWS() {
        if (state.ws) {
            state.ws.close();
            state.ws = null;
        }
    }

    // =========================================================================
    // Chat
    // =========================================================================

    function addChatMessage(text, role) {
        const msg = document.createElement("div");
        msg.className = "chat-message " + role;
        const content = document.createElement("div");
        content.className = "message-content";
        content.innerHTML = text;
        msg.appendChild(content);
        dom.chatMessages.appendChild(msg);
        dom.chatMessages.scrollTop = dom.chatMessages.scrollHeight;
    }

    async function sendChat() {
        const text = dom.chatInput.value.trim();
        if (!text) return;

        addChatMessage(escapeHtml(text), "user");
        dom.chatInput.value = "";

        try {
            const resp = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: text }),
            });

            const data = await resp.json();

            // Render response as simple markdown-ish HTML
            const html = simpleMarkdown(data.response || "");
            addChatMessage(html, "assistant");

            // If code was returned, load it into the editor
            if (data.code) {
                state.editor.setValue(data.code);
                addChatMessage(
                    '<em>Code loaded into editor. Press <strong>Run</strong> to preview!</em>',
                    "assistant"
                );
            }
        } catch (err) {
            addChatMessage("Error communicating with server.", "assistant");
        }
    }

    // =========================================================================
    // Resizable panels
    // =========================================================================

    function initResizers() {
        makeResizer(dom.resizerLeft, "left");
        makeResizer(dom.resizerRight, "right");
    }

    function makeResizer(el, side) {
        let startX, startWidth;

        const panel =
            side === "left" ? $("#chat-panel") : $("#preview-panel");

        el.addEventListener("mousedown", (e) => {
            e.preventDefault();
            startX = e.clientX;
            startWidth = panel.getBoundingClientRect().width;
            el.classList.add("active");

            const onMove = (e2) => {
                const dx = e2.clientX - startX;
                const newW = side === "left" ? startWidth + dx : startWidth - dx;
                if (newW >= 200 && newW <= 600) {
                    panel.style.flex = `0 0 ${newW}px`;
                }
                // Refresh CodeMirror on resize
                if (state.editor) state.editor.refresh();
            };

            const onUp = () => {
                el.classList.remove("active");
                document.removeEventListener("mousemove", onMove);
                document.removeEventListener("mouseup", onUp);
                if (state.editor) state.editor.refresh();
            };

            document.addEventListener("mousemove", onMove);
            document.addEventListener("mouseup", onUp);
        });
    }

    // =========================================================================
    // Utilities
    // =========================================================================

    function escapeHtml(text) {
        const d = document.createElement("div");
        d.textContent = text;
        return d.innerHTML;
    }

    function simpleMarkdown(text) {
        // Basic markdown: bold, italic, code, line breaks
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
            .replace(/\*(.+?)\*/g, "<em>$1</em>")
            .replace(/`(.+?)`/g, "<code>$1</code>")
            .replace(/\n/g, "<br>")
            .replace(/- /g, "&bull; ");
    }

    // =========================================================================
    // Event binding
    // =========================================================================

    function bindEvents() {
        dom.btnRun.addEventListener("click", runCode);
        dom.btnStop.addEventListener("click", stopCode);

        dom.btnRefresh.addEventListener("click", () => {
            if (dom.previewIframe.src) {
                dom.previewIframe.src = dom.previewIframe.src;
            }
        });

        dom.btnSend.addEventListener("click", sendChat);
        dom.chatInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendChat();
            }
        });

        dom.btnClearChat.addEventListener("click", () => {
            dom.chatMessages.innerHTML = "";
        });

        dom.btnClearConsole.addEventListener("click", consoleClear);
    }

    // =========================================================================
    // Init
    // =========================================================================

    function init() {
        initEditor();
        initResizers();
        bindEvents();
    }

    // Wait for DOM
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
