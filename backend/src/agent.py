import logging
import json
import os
import asyncio
from typing import Annotated, Literal, Optional
from dataclasses import dataclass

from dotenv import load_dotenv
from pydantic import Field
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    RoomInputOptions,
    WorkerOptions,
    cli,
    function_tool,
    RunContext,
)

# Plugins
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")
load_dotenv(".env.local")


# Cybersecurity Knowledge Base


CONTENT_FILE = "cyber_security.json"

DEFAULT_CONTENT = [
    {
        "id": "cyber_basics",
        "title": "What is Cybersecurity?",
        "summary": "Cybersecurity is the practice of protecting computers, networks, and data from unauthorized access, attacks, or damage.",
        "sample_question": "What is the main goal of cybersecurity?"
    },
    {
        "id": "passwords",
        "title": "Strong Passwords",
        "summary": "A strong password uses a mix of letters, numbers, and symbols. It is difficult to guess and helps secure accounts.",
        "sample_question": "What makes a password strong?"
    },
    {
        "id": "malware",
        "title": "Malware",
        "summary": "Malware is malicious software designed to harm or gain unauthorized access to a system. Examples include viruses, worms, and ransomware.",
        "sample_question": "What is malware and can you name one type?"
    },
    {
        "id": "phishing",
        "title": "Phishing Attacks",
        "summary": "Phishing is an attack where someone pretends to be a trusted source to trick users into giving personal information.",
        "sample_question": "What is the goal of a phishing attack?"
    }
]

def load_content():
    """Load or create cybersecurity content."""
    try:
        path = os.path.join(os.path.dirname(__file__), CONTENT_FILE)

        if not os.path.exists(path):
            with open(path, "w", encoding='utf-8') as f:
                json.dump(DEFAULT_CONTENT, f, indent=4)

        with open(path, "r", encoding='utf-8') as f:
            return json.load(f)

    except Exception as e:
        print(f"Error loading content: {e}")
        return []

COURSE_CONTENT = load_content()


# State Management


@dataclass
class TutorState:
    current_topic_id: str | None = None
    current_topic_data: dict | None = None
    mode: Literal["learn", "quiz", "teach_back"] = "learn"
    
    def set_topic(self, topic_id: str):
        topic = next((item for item in COURSE_CONTENT if item["id"] == topic_id), None)
        if topic:
            self.current_topic_id = topic_id
            self.current_topic_data = topic
            return True
        return False

@dataclass
class Userdata:
    tutor_state: TutorState
    agent_session: Optional[AgentSession] = None


# Tools


@function_tool
async def select_topic(
    ctx: RunContext[Userdata],
    topic_id: Annotated[str, Field(description="Topic ID to study")]
) -> str:
    state = ctx.userdata.tutor_state
    success = state.set_topic(topic_id.lower())
    
    if success:
        return f"Topic set to {state.current_topic_data['title']}. Ask the user if they want to learn, take a quiz, or teach back."
    else:
        available = ", ".join([t["id"] for t in COURSE_CONTENT])
        return f"Topic not found. Available topics: {available}"

@function_tool
async def set_learning_mode(
    ctx: RunContext[Userdata],
    mode: Annotated[str, Field(description="learn, quiz, or teach_back")]
) -> str:
    
    state = ctx.userdata.tutor_state
    state.mode = mode.lower()
    agent_session = ctx.userdata.agent_session
    
    if agent_session:
        if state.mode == "learn":
            agent_session.tts.update_options(voice="en-US-matthew", style="Promo")
            instruction = f"Explain: {state.current_topic_data['summary']}"
            
        elif state.mode == "quiz":
            agent_session.tts.update_options(voice="en-US-alicia", style="Conversational")
            instruction = f"Ask: {state.current_topic_data['sample_question']}"
            
        elif state.mode == "teach_back":
            agent_session.tts.update_options(voice="en-US-ken", style="Promo")
            instruction = "Ask the user to explain the concept."
            
        else:
            return "Invalid mode."

    return f"Switched to {state.mode} mode. {instruction}"

@function_tool
async def evaluate_teaching(
    ctx: RunContext[Userdata],
    user_explanation: Annotated[str, Field(description="User's explanation")]
) -> str:
    return ("Evaluate the user's explanation. Give a score out of 10 for accuracy and clarity. "
            "Provide corrections if needed.")

# Agent Definition


class TutorAgent(Agent):
    def __init__(self):
        topic_list = ", ".join([f"{t['id']} ({t['title']})" for t in COURSE_CONTENT])
        
        super().__init__(
            instructions=f"""
            You are a pro Cybersecurity Tutor.

            Available topics: {topic_list}

            Modes:
            - Learn Mode: Explain the topic summary.
            - Quiz Mode: Ask the provided sample question.
            - Teach-back Mode: Ask the user to explain the topic, then evaluate them.

            When the user chooses a mode, call the set_learning_mode tool.
            When in teach-back mode, listen to the explanation and call evaluate_teaching.
            """,
            tools=[select_topic, set_learning_mode, evaluate_teaching],
        )

# Entrypoint


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

async def entrypoint(ctx: JobContext):
    userdata = Userdata(tutor_state=TutorState())

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(
            voice="en-US-matthew",
            style="Promo",
            text_pacing=True,
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        userdata=userdata,
    )
    
    userdata.agent_session = session

    await session.start(
        agent=TutorAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC()
        ),
    )

    await ctx.connect()

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
