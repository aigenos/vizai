#!/usr/bin/env python3
"""
VizAI Studio - Entry point.

Usage:
    python run.py [--host HOST] [--port PORT]

Starts the VizAI Studio server which serves:
- The UI Studio (editor, chat, preview) at /
- The REST API at /api/
- Running Dash apps at /app/<session_id>/
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="VizAI Studio Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    args = parser.parse_args()

    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn is not installed. Run: pip install -r requirements.txt")
        sys.exit(1)

    print(f"Starting VizAI Studio at http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop.\n")

    uvicorn.run(
        "server.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
