import json
import os
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from livekit import api


# ============================================================
# ENVIRONMENT
# ============================================================

PROJECT_DIR = Path(__file__).resolve().parent
CLIENT_DIR = PROJECT_DIR / "test-client"

load_dotenv(PROJECT_DIR / ".env", override=True)


# ============================================================
# CONFIG
# ============================================================

HOST = "0.0.0.0"
PORT = 8080

LIVEKIT_URL = os.getenv(
    "LIVEKIT_URL",
    "ws://16.170.161.101:7880",
).strip()

LIVEKIT_API_KEY = os.getenv(
    "LIVEKIT_API_KEY",
    "",
).strip()

LIVEKIT_API_SECRET = os.getenv(
    "LIVEKIT_API_SECRET",
    "",
).strip()

AGENT_NAME = os.getenv(
    "AGENT_DISPATCH_NAME",
    "final-expense-agent",
).strip() or "final-expense-agent"


# ============================================================
# VALIDATION
# ============================================================

if not LIVEKIT_API_KEY:
    raise RuntimeError(
        "LIVEKIT_API_KEY is missing from .env"
    )

if not LIVEKIT_API_SECRET:
    raise RuntimeError(
        "LIVEKIT_API_SECRET is missing from .env"
    )

if not CLIENT_DIR.exists():
    raise RuntimeError(
        f"Frontend directory does not exist: {CLIENT_DIR}"
    )

if not (CLIENT_DIR / "index.html").exists():
    raise RuntimeError(
        f"Missing frontend file: {CLIENT_DIR / 'index.html'}"
    )


# ============================================================
# TOKEN CREATION
# ============================================================

def create_browser_token():
    """
    Create a completely fresh browser room and token.

    The agent dispatch is embedded directly into the room
    configuration. No manual dispatch creation is required.
    """

    room_name = (
        "browser-final-expense-"
        + uuid.uuid4().hex[:8]
    )

    token = (
        api.AccessToken(
            api_key=LIVEKIT_API_KEY,
            api_secret=LIVEKIT_API_SECRET,
        )
        .with_identity("browser-user")
        .with_name("Browser User")
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True,
            )
        )
        .with_room_config(
            api.RoomConfiguration(
                agents=[
                    api.RoomAgentDispatch(
                        agent_name=AGENT_NAME,
                    )
                ]
            )
        )
        .to_jwt()
    )

    return {
        "token": token,
        "room": room_name,
        "livekit_url": LIVEKIT_URL,
        "agent": AGENT_NAME,
    }


# ============================================================
# HTTP SERVER
# ============================================================

class Handler(BaseHTTPRequestHandler):

    # --------------------------------------------------------
    # Logging
    # --------------------------------------------------------

    def log_message(self, format, *args):
        print(
            f"[HTTP] {self.address_string()} - {format % args}"
        )

    # --------------------------------------------------------
    # Headers
    # --------------------------------------------------------

    def send_common_headers(
        self,
        content_type="text/plain; charset=utf-8",
    ):
        self.send_header(
            "Content-Type",
            content_type,
        )

        self.send_header(
            "Cache-Control",
            "no-store, no-cache, must-revalidate",
        )

        self.send_header(
            "Pragma",
            "no-cache",
        )

        self.send_header(
            "Access-Control-Allow-Origin",
            "*",
        )

        self.send_header(
            "Access-Control-Allow-Methods",
            "GET, OPTIONS",
        )

        self.send_header(
            "Access-Control-Allow-Headers",
            "*",
        )

        self.end_headers()

    # --------------------------------------------------------
    # OPTIONS
    # --------------------------------------------------------

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_common_headers()

    # --------------------------------------------------------
    # GET
    # --------------------------------------------------------

    def do_GET(self):

        parsed = urlparse(self.path)
        path = parsed.path

        print(
            f"[REQUEST] {self.command} {path}"
        )

        # ====================================================
        # HEALTH
        # ====================================================

        if path == "/health":

            body = json.dumps(
                {
                    "status": "ok",
                    "server": "final-expense-test-client",
                    "agent": AGENT_NAME,
                    "livekit_url": LIVEKIT_URL,
                },
                indent=2,
            ).encode("utf-8")

            self.send_response(200)

            self.send_common_headers(
                "application/json; charset=utf-8"
            )

            self.wfile.write(body)

            return

        # ====================================================
        # TOKEN
        # ====================================================

        if path == "/token":

            try:

                data = create_browser_token()

                body = json.dumps(
                    data,
                    indent=2,
                ).encode("utf-8")

                print(
                    "--------------------------------------------------"
                )

                print(
                    "[TOKEN] NEW BROWSER SESSION"
                )

                print(
                    f"[TOKEN] ROOM  = {data['room']}"
                )

                print(
                    f"[TOKEN] AGENT = {data['agent']}"
                )

                print(
                    f"[TOKEN] URL   = {data['livekit_url']}"
                )

                print(
                    "--------------------------------------------------"
                )

                self.send_response(200)

                self.send_common_headers(
                    "application/json; charset=utf-8"
                )

                self.wfile.write(body)

                return

            except Exception as exc:

                print(
                    "[TOKEN ERROR]",
                    repr(exc),
                )

                body = json.dumps(
                    {
                        "error": str(exc),
                    }
                ).encode("utf-8")

                self.send_response(500)

                self.send_common_headers(
                    "application/json; charset=utf-8"
                )

                self.wfile.write(body)

                return

        # ====================================================
        # ROOT
        # ====================================================

        if path == "/":

            path = "/index.html"

        # ====================================================
        # STATIC FILE
        # ====================================================

        requested = (
            CLIENT_DIR
            / path.lstrip("/")
        ).resolve()

        client_root = CLIENT_DIR.resolve()

        # Security: don't allow ../ outside test-client
        try:
            requested.relative_to(client_root)
        except ValueError:

            self.send_error(
                403,
                "Forbidden",
            )

            return

        if not requested.exists():
            self.send_error(
                404,
                "File not found",
            )

            return

        if not requested.is_file():
            self.send_error(
                404,
                "Not a file",
            )

            return

        # MIME
        suffix = requested.suffix.lower()

        mime_types = {
            ".html": "text/html; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".svg": "image/svg+xml",
            ".ico": "image/x-icon",
        }

        content_type = mime_types.get(
            suffix,
            "application/octet-stream",
        )

        try:

            content = requested.read_bytes()

            self.send_response(200)

            self.send_common_headers(
                content_type
            )

            self.wfile.write(content)

        except Exception as exc:

            print(
                "[STATIC ERROR]",
                repr(exc),
            )

            self.send_error(
                500,
                "Internal server error",
            )


# ============================================================
# START
# ============================================================

def main():

    print()
    print("=" * 70)
    print("FINAL EXPENSE LIVEKIT TEST CLIENT")
    print("=" * 70)
    print(f"Frontend directory : {CLIENT_DIR}")
    print(f"Frontend URL       : http://16.170.161.101:{PORT}")
    print(f"Token endpoint     : http://16.170.161.101:{PORT}/token")
    print(f"Health endpoint    : http://16.170.161.101:{PORT}/health")
    print(f"LiveKit URL        : {LIVEKIT_URL}")
    print(f"Agent              : {AGENT_NAME}")
    print(f"API key            : {'SET' if LIVEKIT_API_KEY else 'MISSING'}")
    print(f"API secret         : {'SET' if LIVEKIT_API_SECRET else 'MISSING'}")
    print("=" * 70)
    print()

    server = ThreadingHTTPServer(
        (HOST, PORT),
        Handler,
    )

    print(
        f"[SERVER] Listening on {HOST}:{PORT}"
    )

    print(
        "[SERVER] Press Ctrl+C to stop."
    )

    try:

        server.serve_forever()

    except KeyboardInterrupt:

        print()
        print(
            "[SERVER] Stopping..."
        )

    finally:

        server.server_close()


if __name__ == "__main__":
    main()