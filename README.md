# LiveKit Final-Expense Voice Agent

A room-based voice-agent prototype with a deterministic qualification flow and optional SIP transfer to a licensed agent.

## Implemented flow

The Python workflow collects an age and name, asks whether the caller is interested, and tracks transfer outcomes. Speech recognition uses Groq Whisper (`whisper-large-v3-turbo`), speech output uses Cartesia (`sonic-3`), and Silero VAD handles voice activity detection. Qualification decisions are deterministic; the agent does not use an LLM.

SIP transfer is disabled by default. Enable it only after configuring a licensed-agent destination and testing the flow in a controlled environment. The browser token server is intended for local testing and binds to `127.0.0.1`; this repository does not provide an authenticated public token-broker service.

## Setup

Use Python 3.10+ and install the runtime dependencies:

```bash
python -m pip install -r requirements.txt
cp .env.example .env
```

Set `GROQ_API_KEY` and `CARTESIA_API_KEY` in `.env`. To enable transfer, also set `ENABLE_SIP_TRANSFER=true` and `LICENSED_AGENT_NUMBER`. Existing deployment environment variables take precedence over values in `.env`.

## Run and test

Run the LiveKit worker:

```bash
python voice_agent.py dev
```

The token server and browser-token helper are for local development only:

```bash
python token_server.py
python generate_browser_token.py
```

Generated browser tokens are ignored by Git. Do not publish them or expose the local token endpoint. A LiveKit room and SIP participant are required to test the transfer path.

Run the focused configuration tests:

```bash
python -m pip install -r requirements-test.txt
python -m pytest -q
```

No live calls or provider integrations are exercised by the test suite. This is a prototype; the repository does not establish legal compliance, production deployment, or end-to-end SIP reliability.

## Stack

Python · LiveKit Agents · Groq STT · Cartesia TTS · Silero VAD · LiveKit SIP
