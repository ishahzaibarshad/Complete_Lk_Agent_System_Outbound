import json
import os
import uuid

from dotenv import load_dotenv

from livekit import api


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv(".env")


# ============================================================
# CONFIGURATION
# ============================================================

LIVEKIT_API_KEY = os.getenv(
    "LIVEKIT_API_KEY",
    "",
).strip()

LIVEKIT_API_SECRET = os.getenv(
    "LIVEKIT_API_SECRET",
    "",
).strip()

LIVEKIT_URL = os.getenv(
    "LIVEKIT_URL",
    "ws://16.170.161.101:7880",
).strip()

AGENT_NAME = "final-expense-agent"

OUTPUT_FILE = (
    "test-client/public/token.json"
)


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


# ============================================================
# CREATE UNIQUE ROOM
# ============================================================

room_name = (
    "browser-final-expense-"
    + uuid.uuid4().hex[:8]
)


# ============================================================
# CREATE TOKEN
# ============================================================

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


# ============================================================
# WRITE TOKEN FILE
# ============================================================

os.makedirs(
    os.path.dirname(OUTPUT_FILE),
    exist_ok=True,
)

with open(
    OUTPUT_FILE,
    "w",
    encoding="utf-8",
) as f:

    json.dump(
        {
            "token": token,
            "room": room_name,
            "livekit_url": LIVEKIT_URL,
            "agent": AGENT_NAME,
        },
        f,
        indent=4,
    )


# ============================================================
# OUTPUT
# ============================================================

print()
print("=" * 70)
print("LIVEKIT BROWSER TEST TOKEN CREATED")
print("=" * 70)
print(f"ROOM        : {room_name}")
print(f"AGENT       : {AGENT_NAME}")
print(f"LIVEKIT URL : {LIVEKIT_URL}")
print(f"TOKEN FILE  : {OUTPUT_FILE}")
print("=" * 70)
print()