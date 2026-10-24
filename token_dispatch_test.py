import asyncio
import os
from dotenv import load_dotenv
from livekit import api, rtc

load_dotenv(".env")

ROOM = "terminal-final-expense-1425"

async def main():
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
                room=ROOM,
                can_publish=True,
                can_subscribe=True,
            )
        )
        .with_room_config(
            api.RoomConfiguration(
                agents=[
                    api.RoomAgentDispatch(
                        agent_name="final-expense-agent",
                    )
                ]
            )
        )
        .to_jwt()
    )

    room = rtc.Room()

    print(f"Connecting to {ROOM}...")
    await room.connect("ws://localhost:7880", token)

    print("CONNECTED")
    print("Room:", room.name)
    print("Identity:", room.local_participant.identity)
    print("Waiting... Press Ctrl+C to exit.")

    try:
        while True:
            await asyncio.sleep(1)
    finally:
        await room.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
