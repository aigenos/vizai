"""
Python/Dash code execution engine.

Manages user sessions, launches Dash apps as subprocesses,
and handles their lifecycle (start, stop, restart).
"""

import asyncio
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# Template that wraps user code to run as a managed Dash app.
# Intercepts app.run() calls, discovers the Dash app instance,
# configures the proxy prefix, and starts the server on an assigned port.
LAUNCHER_TEMPLATE = r'''#!/usr/bin/env python3
"""VizAI Dash App Launcher - auto-generated."""
import sys
import os
import importlib.util
import io

session_id = "__SESSION_ID__"
port = __PORT__
user_code_path = r"__USER_CODE_PATH__"

# Redirect output to be line-buffered for real-time streaming
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, line_buffering=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, line_buffering=True)

# --- Patch Dash to inject proxy prefix at construction time ---
import dash

_original_init = dash.Dash.__init__
_original_run = dash.Dash.run
_original_run_server = getattr(dash.Dash, "run_server", None)
_captured_app = None

def _patched_init(self, *args, **kwargs):
    """Inject requests_pathname_prefix into every Dash app constructor."""
    kwargs["requests_pathname_prefix"] = f"/app/{session_id}/"
    kwargs["routes_pathname_prefix"] = "/"
    _original_init(self, *args, **kwargs)

def _intercept_run(self, *args, **kwargs):
    """Capture the app instance when user calls app.run()."""
    global _captured_app
    _captured_app = self

dash.Dash.__init__ = _patched_init
dash.Dash.run = _intercept_run
if _original_run_server:
    dash.Dash.run_server = _intercept_run

# --- Load user code as a module ---
spec = importlib.util.spec_from_file_location("user_app", user_code_path)
module = importlib.util.module_from_spec(spec)
sys.modules["user_app"] = module

# Add the user code directory to sys.path so relative imports work
user_code_dir = os.path.dirname(user_code_path)
if user_code_dir not in sys.path:
    sys.path.insert(0, user_code_dir)

try:
    spec.loader.exec_module(module)
except SystemExit:
    pass  # Some scripts call sys.exit() after app.run()
except Exception as e:
    print(f"ERROR loading user code: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)

# --- Restore original methods ---
dash.Dash.__init__ = _original_init
dash.Dash.run = _original_run
if _original_run_server:
    dash.Dash.run_server = _original_run_server

# --- Find the Dash app instance ---
app_instance = _captured_app

if app_instance is None:
    # Search module namespace for a Dash instance
    for name in dir(module):
        obj = getattr(module, name)
        if isinstance(obj, dash.Dash):
            app_instance = obj
            break

if app_instance is None:
    print("ERROR: No Dash app instance found in the code.", file=sys.stderr)
    print("Make sure your code creates a dash.Dash() instance.", file=sys.stderr)
    sys.exit(1)

# Signal readiness
print(f"VIZAI_READY:{port}", flush=True)

# --- Run the Dash app ---
try:
    app_instance.run(
        debug=False,
        port=port,
        host="127.0.0.1",
        use_reloader=False,
    )
except Exception as e:
    print(f"ERROR running app: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)
'''


@dataclass
class Session:
    """Represents a running Dash app session."""
    id: str
    port: int
    process: Optional[subprocess.Popen]
    code: str
    status: str  # "starting", "running", "stopped", "error"
    code_dir: str = ""
    output_lines: List[str] = field(default_factory=list)
    error_lines: List[str] = field(default_factory=list)


class SessionManager:
    """Manages Dash app sessions and their lifecycle."""

    def __init__(self, port_start: int = 8050, port_end: int = 8200):
        self.sessions: Dict[str, Session] = {}
        self._port_start = port_start
        self._port_end = port_end
        self._used_ports: set = set()
        self._output_tasks: Dict[str, asyncio.Task] = {}

    def _find_free_port(self) -> int:
        """Find an available port in the configured range."""
        for port in range(self._port_start, self._port_end):
            if port in self._used_ports:
                continue
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(("127.0.0.1", port))
                    return port
                except OSError:
                    continue
        raise RuntimeError("No free ports available")

    async def execute(self, code: str, session_id: Optional[str] = None) -> dict:
        """
        Execute user Python/Dash code in a new subprocess.

        If session_id is provided and already exists, stops the old session first.
        Returns session info dict with id, status, and app URL.
        """
        # Stop existing session if re-executing
        if session_id and session_id in self.sessions:
            await self.stop(session_id)

        if not session_id:
            session_id = uuid.uuid4().hex[:8]

        port = self._find_free_port()
        self._used_ports.add(port)

        # Write user code to a temp directory
        code_dir = tempfile.mkdtemp(prefix=f"vizai_{session_id}_")
        code_path = os.path.join(code_dir, "user_app.py")
        with open(code_path, "w") as f:
            f.write(code)

        # Generate launcher script
        launcher_code = LAUNCHER_TEMPLATE
        launcher_code = launcher_code.replace("__SESSION_ID__", session_id)
        launcher_code = launcher_code.replace("__PORT__", str(port))
        launcher_code = launcher_code.replace("__USER_CODE_PATH__", code_path.replace("\\", "\\\\"))

        launcher_path = os.path.join(code_dir, "launcher.py")
        with open(launcher_path, "w") as f:
            f.write(launcher_code)

        # Start the subprocess
        process = subprocess.Popen(
            [sys.executable, launcher_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=code_dir,
            preexec_fn=os.setsid,  # Create new process group for clean shutdown
        )

        session = Session(
            id=session_id,
            port=port,
            process=process,
            code=code,
            status="starting",
            code_dir=code_dir,
        )
        self.sessions[session_id] = session

        # Start async output reader
        self._output_tasks[session_id] = asyncio.create_task(
            self._read_output(session)
        )

        # Wait for app to be ready (or fail)
        ready = await self._wait_for_ready(session, timeout=30)

        if ready:
            session.status = "running"
        else:
            # Check if process died
            if process.poll() is not None:
                session.status = "error"
            else:
                session.status = "error"
                # Kill the process if it didn't start properly
                self._kill_process(process)

        return {
            "session_id": session_id,
            "status": session.status,
            "app_url": f"/app/{session_id}/",
            "output": session.output_lines[-50:],
            "errors": session.error_lines[-50:],
        }

    async def _read_output(self, session: Session) -> None:
        """Read stdout and stderr from the subprocess asynchronously."""
        loop = asyncio.get_event_loop()

        async def read_stream(stream, target_list):
            while True:
                line = await loop.run_in_executor(None, stream.readline)
                if not line:
                    break
                decoded = line.decode("utf-8", errors="replace").rstrip()
                target_list.append(decoded)

        if session.process and session.process.stdout and session.process.stderr:
            await asyncio.gather(
                read_stream(session.process.stdout, session.output_lines),
                read_stream(session.process.stderr, session.error_lines),
            )

    async def _wait_for_ready(self, session: Session, timeout: int = 30) -> bool:
        """Wait for the Dash app to be ready by checking for the VIZAI_READY signal."""
        elapsed = 0.0
        interval = 0.3

        while elapsed < timeout:
            # Check if process has exited
            if session.process and session.process.poll() is not None:
                # Process exited - give output reader a moment to capture remaining output
                await asyncio.sleep(0.5)
                return False

            # Check for ready signal in output
            for line in session.output_lines:
                if line.startswith("VIZAI_READY:"):
                    # Also verify the port is actually accepting connections
                    if self._port_is_open(session.port):
                        return True

            # Also try connecting to the port directly
            if self._port_is_open(session.port):
                return True

            await asyncio.sleep(interval)
            elapsed += interval

        return False

    @staticmethod
    def _port_is_open(port: int) -> bool:
        """Check if a port is accepting connections."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            try:
                s.connect(("127.0.0.1", port))
                return True
            except (OSError, ConnectionRefusedError):
                return False

    @staticmethod
    def _kill_process(process: subprocess.Popen) -> None:
        """Kill a process and its entire process group."""
        try:
            pgid = os.getpgid(process.pid)
            os.killpg(pgid, signal.SIGTERM)
        except (OSError, ProcessLookupError):
            pass
        try:
            process.kill()
        except (OSError, ProcessLookupError):
            pass

    async def stop(self, session_id: str) -> dict:
        """Stop a running session and clean up resources."""
        session = self.sessions.get(session_id)
        if not session:
            return {"status": "not_found"}

        # Kill the process
        if session.process:
            self._kill_process(session.process)
            session.process.wait()

        # Cancel output reader
        if session_id in self._output_tasks:
            self._output_tasks[session_id].cancel()
            del self._output_tasks[session_id]

        # Release port
        self._used_ports.discard(session.port)

        # Clean up temp directory
        if session.code_dir and os.path.exists(session.code_dir):
            shutil.rmtree(session.code_dir, ignore_errors=True)

        session.status = "stopped"
        del self.sessions[session_id]

        return {"status": "stopped"}

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by ID."""
        return self.sessions.get(session_id)

    def get_status(self, session_id: str) -> dict:
        """Get the status of a session."""
        session = self.sessions.get(session_id)
        if not session:
            return {"status": "not_found"}

        # Check if process is still alive
        if session.process and session.process.poll() is not None:
            if session.status == "running":
                session.status = "crashed"

        return {
            "session_id": session.id,
            "status": session.status,
            "app_url": f"/app/{session.id}/",
            "output": session.output_lines[-50:],
            "errors": session.error_lines[-50:],
        }

    def list_sessions(self) -> list:
        """List all active sessions."""
        return [
            {
                "session_id": s.id,
                "status": s.status,
                "app_url": f"/app/{s.id}/",
            }
            for s in self.sessions.values()
        ]

    async def stop_all(self) -> None:
        """Stop all running sessions. Called during shutdown."""
        session_ids = list(self.sessions.keys())
        for sid in session_ids:
            await self.stop(sid)
