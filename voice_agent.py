import asyncio
import logging
import os
import re
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    StopResponse,
    TurnHandlingOptions,
    cli,
    get_job_context,
    room_io,
)

from livekit.plugins import cartesia, groq
from livekit.plugins.silero import VAD as SileroVAD


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv(".env", override=True)


# ============================================================
# API KEYS
# ============================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
CARTESIA_API_KEY = os.getenv("CARTESIA_API_KEY", "").strip()


# ============================================================
# AGENT CONFIGURATION
# ============================================================

AGENT_NAME = (
    os.getenv("AGENT_NAME", "Sara").strip()
    or "Sara"
)

COMPANY_NAME = (
    os.getenv("COMPANY_NAME", "Senior Care").strip()
    or "Senior Care"
)

MIN_AGE = int(os.getenv("MIN_AGE", "50"))
MAX_AGE = int(os.getenv("MAX_AGE", "80"))

LICENSED_AGENT_NUMBER = (
    os.getenv("LICENSED_AGENT_NUMBER", "").strip()
)

ENABLE_TRANSFER = (
    os.getenv(
        "ENABLE_SIP_TRANSFER",
        os.getenv("ENABLE_TRANSFER", "true"),
    )
    .strip()
    .lower()
    == "true"
)


# ============================================================
# CARTESIA
# ============================================================

CARTESIA_VOICE_ID = (
    os.getenv(
        "CARTESIA_VOICE_ID",
        "9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
    ).strip()
    or "9626c31c-bec5-4cca-baa8-f8ba9e84c8bc"
)

CARTESIA_TTS_MODEL = "sonic-3"


# ============================================================
# GROQ STT
# ============================================================

GROQ_STT_MODEL = "whisper-large-v3-turbo"


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("final-expense-agent")


# ============================================================
# STARTUP VALIDATION
# ============================================================

if not GROQ_API_KEY:
    raise RuntimeError(
        "GROQ_API_KEY is required."
    )

if not CARTESIA_API_KEY:
    raise RuntimeError(
        "CARTESIA_API_KEY is required."
    )


# ============================================================
# STATE
# ============================================================

@dataclass
class CallState:
    age: Optional[int] = None
    name: Optional[str] = None
    interested: Optional[bool] = None

    transfer_attempted: bool = False
    transfer_completed: bool = False
    transfer_failed: bool = False

    call_ending: bool = False


# ============================================================
# NUMBER WORDS
# ============================================================

NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}


# ============================================================
# AGE EXTRACTION
# ============================================================

def extract_age(text: str) -> Optional[int]:
    """
    Extract age from common speech:

        65
        I'm 65
        I am sixty five
        sixty-five years old
    """

    text = (text or "").lower().strip()

    # Numeric age.
    match = re.search(
        r"\b(100|10[1-9]|11\d|120|[5-9]\d)\b",
        text,
    )

    if match:
        try:
            age = int(match.group(1))

            if 1 <= age <= 120:
                return age

        except ValueError:
            pass

    normalized = text.replace("-", " ")
    words = normalized.split()

    for index, word in enumerate(words):

        if word not in NUMBER_WORDS:
            continue

        value = NUMBER_WORDS[word]

        # sixty five / seventy two / etc.
        if (
            value in {50, 60, 70, 80, 90}
            and index + 1 < len(words)
        ):
            second = words[index + 1]

            if second in NUMBER_WORDS:
                second_value = NUMBER_WORDS[second]

                if 0 <= second_value <= 9:
                    age = value + second_value

                    if 1 <= age <= 120:
                        return age

        if 1 <= value <= 120:
            return value

    return None


# ============================================================
# NAME CLEANING
# ============================================================

def clean_name(text: str) -> str:
    """
    Clean phrases such as:

        My name is John Smith
        I'm John Smith
        This is John Smith
    """

    name = (text or "").strip()

    patterns = [
        r"^my name is\s+",
        r"^my name's\s+",
        r"^i am\s+",
        r"^i'm\s+",
        r"^this is\s+",
        r"^it's\s+",
        r"^it is\s+",
        r"^the name is\s+",
    ]

    for pattern in patterns:
        if re.match(
            pattern,
            name,
            flags=re.IGNORECASE,
        ):
            name = re.sub(
                pattern,
                "",
                name,
                flags=re.IGNORECASE,
            )
            break

    name = name.strip(" .,!?")

    return name


# ============================================================
# INTEREST DETECTION
# ============================================================

POSITIVE_INTEREST_MARKERS = (
    "yes",
    "yeah",
    "yep",
    "sure",
    "okay",
    "ok",
    "interested",
    "i'm interested",
    "im interested",
    "i am interested",
    "sounds good",
    "sounds great",
    "tell me more",
    "learn more",
    "hear more",
    "more information",
    "more info",
    "i'd like to know more",
    "id like to know more",
    "i would like to know more",
    "i want it",
    "i want to hear more",
    "i'd like that",
)

NEGATIVE_INTEREST_MARKERS = (
    "no",
    "nope",
    "not interested",
    "not really",
    "don't want",
    "dont want",
    "do not want",
    "no thanks",
    "no thank you",
    "goodbye",
    "good bye",
    "stop calling",
)


def detect_interest(text: str) -> Optional[bool]:

    normalized = (
        text or ""
    ).lower().strip()

    if not normalized:
        return None

    for marker in NEGATIVE_INTEREST_MARKERS:
        if marker in normalized:
            return False

    for marker in POSITIVE_INTEREST_MARKERS:
        if marker in normalized:
            return True

    return None


# ============================================================
# AGENT
# ============================================================

class FinalExpenseAssistant(Agent):

    def __init__(self) -> None:

        super().__init__(
            instructions=(
                f"You are {AGENT_NAME} from {COMPANY_NAME}. "
                "This conversation is controlled by a deterministic "
                "Python workflow. Do not generate your own qualification "
                "questions."
            )
        )

        self.state = CallState()

    # ========================================================
    # SPEAK
    # ========================================================

    async def speak(
        self,
        text: str,
        allow_interruptions: bool = False,
    ) -> None:

        logger.info(
            "AGENT SPEAK | %s",
            text,
        )

        handle = self.session.say(
            text,
            allow_interruptions=allow_interruptions,
        )

        await handle.wait_for_playout()

    # ========================================================
    # FIND SIP PARTICIPANT
    # ========================================================

    def find_sip_participant(
        self,
    ) -> Optional[rtc.RemoteParticipant]:

        ctx = get_job_context()

        participants = list(
            ctx.room.remote_participants.values()
        )

        logger.info(
            "REMOTE PARTICIPANTS | count=%d",
            len(participants),
        )

        for participant in participants:

            logger.info(
                "REMOTE PARTICIPANT | identity=%s | kind=%s",
                participant.identity,
                participant.kind,
            )

            if (
                participant.kind
                == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
            ):
                return participant

        return None

    # ========================================================
    # SIP TRANSFER
    # ========================================================

    async def transfer_to_senior(self) -> bool:

        if self.state.transfer_attempted:

            logger.warning(
                "TRANSFER ALREADY ATTEMPTED"
            )

            return self.state.transfer_completed

        self.state.transfer_attempted = True

        logger.info(
            "TRANSFER START | enabled=%s | number=%s",
            ENABLE_TRANSFER,
            LICENSED_AGENT_NUMBER or "(missing)",
        )

        if not ENABLE_TRANSFER:

            logger.error(
                "TRANSFER IS DISABLED"
            )

            self.state.transfer_failed = True

            return False

        if not LICENSED_AGENT_NUMBER:

            logger.error(
                "LICENSED_AGENT_NUMBER IS MISSING"
            )

            self.state.transfer_failed = True

            return False

        ctx = get_job_context()

        sip_participant = self.find_sip_participant()

        if sip_participant is None:

            logger.error(
                "NO SIP PARTICIPANT FOUND"
            )

            logger.error(
                "This is expected for a browser/WebRTC test room. "
                "Browser calls cannot be SIP-transferred."
            )

            self.state.transfer_failed = True

            return False

        transfer_target = LICENSED_AGENT_NUMBER.strip()

        if not (
            transfer_target.startswith("tel:")
            or transfer_target.startswith("sip:")
        ):
            transfer_target = f"tel:{transfer_target}"

        logger.info(
            "SIP TRANSFER | participant=%s | target=%s",
            sip_participant.identity,
            transfer_target,
        )

        try:

            await ctx.transfer_sip_participant(
                participant=sip_participant,
                transfer_to=transfer_target,
                play_dialtone=False,
            )

            self.state.transfer_completed = True

            logger.info(
                "SIP TRANSFER SUCCESS | target=%s",
                transfer_target,
            )

            return True

        except Exception as exc:

            self.state.transfer_failed = True

            logger.exception(
                "SIP TRANSFER FAILED | target=%s | error=%s",
                transfer_target,
                exc,
            )

            return False

    # ========================================================
    # USER TURN
    # ========================================================

    async def on_user_turn_completed(
        self,
        turn_ctx,
        new_message,
    ) -> None:

        if self.state.call_ending:

            raise StopResponse()

        transcript = (
            new_message.text_content or ""
        ).strip()

        logger.info(
            "CUSTOMER SPEECH | %s",
            transcript,
        )

        if not transcript:

            logger.warning(
                "EMPTY CUSTOMER TRANSCRIPT"
            )

            raise StopResponse()

        # ====================================================
        # AGE
        # ====================================================

        if self.state.age is None:

            age = extract_age(transcript)

            if age is None:

                await self.speak(
                    "Sorry, I didn't catch that. "
                    "How old are you?"
                )

                raise StopResponse()

            self.state.age = age

            logger.info(
                "AGE CAPTURED | age=%d",
                age,
            )

            if age < MIN_AGE or age > MAX_AGE:

                self.state.call_ending = True

                logger.info(
                    "AGE OUTSIDE RANGE | age=%d | range=%d-%d",
                    age,
                    MIN_AGE,
                    MAX_AGE,
                )

                await self.speak(
                    "Thank you for your time. "
                    "It looks like this may not be a fit "
                    "for your age group. Take care."
                )

                raise StopResponse()

            await self.speak(
                "Thank you. And what is your name?"
            )

            raise StopResponse()

        # ====================================================
        # NAME
        # ====================================================

        if self.state.name is None:

            name = clean_name(transcript)

            if not name:

                await self.speak(
                    "Sorry, I didn't catch your name. "
                    "What is your first and last name?"
                )

                raise StopResponse()

            self.state.name = name

            logger.info(
                "CUSTOMER NAME CAPTURED | name=%s",
                name,
            )

            await self.speak(
                "Thank you. Would you like to hear more "
                "about the final expense policy?"
            )

            raise StopResponse()

        # ====================================================
        # INTEREST
        # ====================================================

        if self.state.interested is None:

            interest = detect_interest(transcript)

            if interest is None:

                await self.speak(
                    "Just to make sure I understand, "
                    "would you like to hear more about the policy?"
                )

                raise StopResponse()

            self.state.interested = interest

            logger.info(
                "CUSTOMER INTEREST | interested=%s",
                interest,
            )

            if not interest:

                self.state.call_ending = True

                await self.speak(
                    "No problem. Thank you for your time. "
                    "Have a great day."
                )

                raise StopResponse()

            # =================================================
            # INTEREST = YES
            # =================================================

            await self.speak(
                "Great. Please hold for just a moment "
                "while I connect you with a licensed "
                "senior representative."
            )

            transferred = await self.transfer_to_senior()

            self.state.call_ending = True

            if transferred:

                logger.info(
                    "CALL HANDOFF COMPLETE"
                )

                raise StopResponse()

            await self.speak(
                "I'm sorry, I wasn't able to complete "
                "the connection to the senior representative. "
                "Thank you for your time."
            )

            raise StopResponse()

        raise StopResponse()

    # ========================================================
    # CALL START
    # ========================================================

    async def on_enter(self) -> None:

        greeting = (
            f"Hi, this is {AGENT_NAME} from {COMPANY_NAME}. "
            "The average cost of a funeral and burial is now over "
            "twelve thousand dollars, and I'm reaching out about "
            "final expense coverage that can help your family "
            "with those expenses. "
            "Can you tell me how old you are?"
        )

        logger.info(
            "GREETING START | %s",
            greeting,
        )

        await self.speak(
            greeting,
            allow_interruptions=False,
        )

        logger.info(
            "GREETING COMPLETE | waiting for customer age"
        )


# ============================================================
# STT
# ============================================================

def build_stt():

    logger.info(
        "BUILDING STT | provider=Groq | model=%s",
        GROQ_STT_MODEL,
    )

    return groq.STT(
        model=GROQ_STT_MODEL,
        language="en",
        api_key=GROQ_API_KEY,
        detect_language=False,
    )


# ============================================================
# TTS
# ============================================================

def build_tts():

    logger.info(
        "BUILDING TTS | Cartesia / %s / %s | speed=0.90",
        CARTESIA_TTS_MODEL,
        CARTESIA_VOICE_ID,
    )

    return cartesia.TTS(
        api_key=CARTESIA_API_KEY,
        model=CARTESIA_TTS_MODEL,
        voice=CARTESIA_VOICE_ID,
        language="en",
        speed=0.80,
        volume=1.0,
    )


# ============================================================
# SERVER
# ============================================================

server = AgentServer()


# ============================================================
# ENTRYPOINT
#
# IMPORTANT:
# No agent_name here.
#
# This enables automatic dispatch for prototype/browser rooms.
# LiveKit documents that omitting agent_name automatically
# dispatches the agent to newly-created rooms.
# ============================================================

@server.rtc_session()
async def entrypoint(ctx: JobContext):

    logger.info("=" * 70)
    logger.info(
        "NEW CALL | room=%s",
        ctx.room.name,
    )
    logger.info(
        "FLOW = OPENING -> AGE -> NAME -> INTEREST -> TRANSFER"
    )
    logger.info(
        "LLM = DISABLED"
    )
    logger.info(
        "STT = Groq / %s",
        GROQ_STT_MODEL,
    )
    logger.info(
        "TTS = Cartesia / %s / %s",
        CARTESIA_TTS_MODEL,
        CARTESIA_VOICE_ID,
    )
    logger.info(
        "TRANSFER ENABLED = %s",
        ENABLE_TRANSFER,
    )
    logger.info(
        "TRANSFER NUMBER = %s",
        LICENSED_AGENT_NUMBER or "(missing)",
    )
    logger.info("=" * 70)

    # ========================================================
    # MODELS
    # ========================================================

    stt_provider = build_stt()
    tts_provider = build_tts()

    # ========================================================
    # TURN HANDLING
    # ========================================================

    turn_handling = TurnHandlingOptions(
        endpointing={
            "mode": "fixed",
            "min_delay": 0.7,
            "max_delay": 2.5,
        },
        interruption={
            "min_duration": 0.7,
            "min_words": 1,
            "false_interruption_timeout": 1.5,
            "resume_false_interruption": True,
            "discard_audio_if_uninterruptible": True,
        },
        preemptive_generation={
            "enabled": False,
            "preemptive_tts": False,
        },
    )

    # ========================================================
    # SESSION
    #
    # No Groq LLM:
    # this eliminates the previous 8000 TPM / 429 problem.
    # ========================================================

    session = AgentSession(
        stt=stt_provider,
        llm=None,
        tts=tts_provider,
        vad=SileroVAD.load(),
        turn_handling=turn_handling,
        max_tool_steps=0,
    )

    # ========================================================
    # EVENTS
    # ========================================================

    @session.on("user_input_transcribed")
    def on_user_input_transcribed(event):

        if not event.is_final:
            return

        logger.info(
            "FINAL CUSTOMER TRANSCRIPT | %s",
            event.transcript,
        )

    @session.on("agent_state_changed")
    def on_agent_state_changed(event):

        logger.info(
            "AGENT STATE | %s",
            event,
        )

    @session.on("user_state_changed")
    def on_user_state_changed(event):

        logger.info(
            "USER STATE | %s",
            event,
        )

    @session.on("conversation_item_added")
    def on_conversation_item_added(event):

        try:

            item = event.item

            logger.info(
                "CONVERSATION ITEM | role=%s | item=%s",
                getattr(item, "role", None),
                item,
            )

        except Exception:

            logger.exception(
                "CONVERSATION ITEM LOGGING ERROR"
            )

    @session.on("error")
    def on_session_error(event):

        logger.error(
            "SESSION ERROR | source=%s | recoverable=%s | error=%s",
            type(event.source).__name__
            if getattr(event, "source", None)
            else "unknown",
            getattr(
                getattr(event, "error", None),
                "recoverable",
                None,
            ),
            getattr(event, "error", event),
        )

    @session.on("close")
    def on_session_close(event):

        logger.warning(
            "SESSION CLOSED | room=%s | event=%s",
            ctx.room.name,
            event,
        )

    # ========================================================
    # START SESSION
    # ========================================================

    logger.info(
        "STARTING AGENT SESSION | room=%s",
        ctx.room.name,
    )

    await session.start(
        agent=FinalExpenseAssistant(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                sample_rate=24000,
                num_channels=1,
                auto_gain_control=True,
                pre_connect_audio=True,
            ),
            audio_output=True,
            close_on_disconnect=True,
        ),
    )

    logger.info(
        "AGENT SESSION STARTED | room=%s",
        ctx.room.name,
    )

    # ========================================================
    # PARTICIPANT DIAGNOSTICS
    # ========================================================

    try:

        participants = list(
            ctx.room.remote_participants.values()
        )

        logger.info(
            "REMOTE PARTICIPANT COUNT = %d",
            len(participants),
        )

        for participant in participants:

            logger.info(
                "REMOTE PARTICIPANT | identity=%s | kind=%s",
                participant.identity,
                participant.kind,
            )

        linked = session.room_io.linked_participant

        if linked:

            logger.info(
                "LINKED PARTICIPANT | identity=%s | kind=%s",
                linked.identity,
                linked.kind,
            )

        else:

            logger.warning(
                "NO LINKED PARTICIPANT YET"
            )

    except Exception:

        logger.exception(
            "PARTICIPANT DIAGNOSTIC ERROR"
        )

    logger.info(
        "CALL READY | opening -> age -> name -> interest -> transfer"
    )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    logger.info(
        "STARTING FINAL EXPENSE AGENT"
    )

    logger.info(
        "AUTOMATIC DISPATCH ENABLED"
    )

    logger.info(
        "GROQ LLM DISABLED"
    )

    cli.run_app(server)