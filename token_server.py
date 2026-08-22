import os
import uuid

from dotenv import load_dotenv
from flask import Flask, jsonify
from livekit import api

load_dotenv(".env", override=True)

app = Flask(__name__)
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "").strip()
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "").strip()

LIVEKIT_URL = os.getenv(
    "LIVEKIT_URL",
    "ws://16.170.161.101:7880",
).strip()

AGENT_NAME = "final-expense-agent"

if not LIVEKIT_API_KEY:
    raise RuntimeError("LIVEKIT_API_KEY is missing")

if not LIVEKIT_API_SECRET:
    raise RuntimeError("LIVEKIT_API_SECRET is missing")


@app.get("/token")
def generate_token():

    # Brand-new room for EVERY browser connection.
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

    print(
        f"NEW BROWSER SESSION | "
        f"room={room_name} | "
        f"agent={AGENT_NAME}"
    )

    return jsonify(
        {
            "token": token,
            "room": room_name,
            "livekit_url": LIVEKIT_URL,
            "agent": AGENT_NAME,
        }
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
    )
