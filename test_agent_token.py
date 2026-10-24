import os
from dotenv import load_dotenv
from livekit import api

load_dotenv(".env")

room_name = "token-test-001"

token = (
    api.AccessToken(
        os.environ["LIVEKIT_API_KEY"],
        os.environ["LIVEKIT_API_SECRET"],
    )
    .with_identity("test-user")
    .with_name("Test User")
    .with_grants(
        api.VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=True,
            can_subscribe=True,
        )
    )
    .with_room_config(
        api.RoomConfiguration(
            agents=[
                api.RoomAgentDispatch(
                    agent_name="my-agent",
                )
            ]
        )
    )
    .to_jwt()
)

print(f"Generated test token for room {room_name}; token value was not printed.")
