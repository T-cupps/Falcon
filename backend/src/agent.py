# ======================================================
# 🌸 DAY 4: TEACH-THE-TUTOR (CLOUD COMPUTING EDITION)
# 🚀 Features: Cloud Architecture, Virtualization, Containers & Active Recall
# ======================================================

import logging
import json
import os
import asyncio
from typing import Annotated, Literal, Optional
from dataclasses import dataclass

print("\n" + "💖" * 50)
print("✨ CLOUD COMPUTING TUTOR")
print("🌼 agent.py LOADED SUCCESSFULLY!")
print("💖" * 50 + "\n")

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

# 🔌 PLUGINS
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")
load_dotenv(".env.local")

# ======================================================
# 🐣 KNOWLEDGE BASE (CLOUD CONTENT)
# ======================================================

# Filename for generated cloud content
CONTENT_FILE = "cloud_content.json"

# CLOUD COMPUTING TOPICS
DEFAULT_CONTENT = [
  {
    "id": "cloud_intro",
    "title": "Introduction to Cloud Computing",
    "summary": "Cloud computing delivers computing services — servers, storage, databases, networking, software — over the internet ('the cloud') to offer faster innovation, flexible resources, and economies of scale.",
    "sample_question": "What is cloud computing and what are three key benefits of using it?"
  },
  {
    "id": "service_models",
    "title": "Service Models (IaaS, PaaS, SaaS)",
    "summary": "IaaS provides virtualized computing resources, PaaS offers platforms for building applications, and SaaS delivers ready-to-use software over the internet.",
    "sample_question": "Give one example of IaaS, PaaS, and SaaS and a use-case for each."
  },
  {
    "id": "virtualization",
    "title": "Virtualization & Hypervisors",
    "summary": "Virtualization creates multiple simulated environments or dedicated resources from a single physical hardware system using a hypervisor, improving utilization and isolation.",
    "sample_question": "What is a hypervisor and why is virtualization important for cloud providers?"
  },
  {
    "id": "containers_k8s",
    "title": "Containers & Kubernetes",
    "summary": "Containers package applications and their dependencies into lightweight, portable units. Kubernetes automates deployment, scaling, and management of containerized apps.",
    "sample_question": "What is the difference between a virtual machine and a container?"
  },
  {
    "id": "cloud_security",
    "title": "Cloud Security Basics",
    "summary": "Cloud security covers identity & access management, encryption, network controls, and the shared responsibility model between cloud providers and customers.",
    "sample_question": "What is the shared responsibility model in cloud security?"
  }
]

def load_content():
    """
    🌟 Checks if cloud content JSON exists.
    If NO: Generates it from DEFAULT_CONTENT.
    If YES: Loads it.
    """
    try:
        path = os.path.join(os.path.dirname(__file__), CONTENT_FILE)

        # Check if file exists
        if not os.path.exists(path):
            print(f"⚠️ {CONTENT_FILE} not found. Generating cloud content data...")
            with open(path, "w", encoding='utf-8') as f:
                json.dump(DEFAULT_CONTENT, f, indent=4)
            print("✅ Cloud content file created successfully.")

        # Read the file
        with open(path, "r", encoding='utf-8') as f:
            data = json.load(f)
            return data

    except Exception as e:
        print(f"⚠️ Error managing content file: {e}")
        return []

# Load data immediately on startup
COURSE_CONTENT = load_content()

# ======================================================
# 🩷 STATE MANAGEMENT
# ======================================================

@dataclass
class TutorState:
    """🌼 Tracks the current learning context"""
    current_topic_id: str | None = None
    current_topic_data: dict | None = None
    mode: Literal["learn", "quiz", "teach_back"] = "learn"

    def set_topic(self, topic_id: str):
        # Find topic in loaded content
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

# ======================================================
# 🛠️ TUTOR TOOLS
# ======================================================

@function_tool
async def select_topic(
    ctx: RunContext[Userdata],
    topic_id: Annotated[str, Field(description="The ID of the topic to study (e.g., 'cloud_intro', 'service_models', 'containers_k8s')")]
) -> str:
    """🌸 Selects a topic to study from the available list."""
    state = ctx.userdata.tutor_state
    success = state.set_topic(topic_id.lower())

    if success:
        return f"Topic set to {state.current_topic_data['title']}. Ask the user if they want to 'Learn', be 'Quizzed', or 'Teach it back'."
    else:
        available = ", ".join([t["id"] for t in COURSE_CONTENT])
        return f"Topic not found. Available topics are: {available}"

@function_tool
async def set_learning_mode(
    ctx: RunContext[Userdata],
    mode: Annotated[str, Field(description="The mode to switch to: 'learn', 'quiz', or 'teach_back'")]
) -> str:
    """🔄 Switches the interaction mode and updates the agent's voice/persona."""

    # 1. Update State
    state = ctx.userdata.tutor_state
    state.mode = mode.lower()

    # 2. Switch Voice based on Mode
    agent_session = ctx.userdata.agent_session

    if agent_session:
        if state.mode == "learn":
            # Instructor voice
            agent_session.tts.update_options(voice="en-US-matthew", style="Promo")
            instruction = f"Mode: LEARN. Explain: {state.current_topic_data['summary']}"

        elif state.mode == "quiz":
            # Examiner voice
            agent_session.tts.update_options(voice="en-US-alicia", style="Conversational")
            instruction = f"Mode: QUIZ. Ask this question: {state.current_topic_data['sample_question']}"

        elif state.mode == "teach_back":
            # Student/coach voice
            agent_session.tts.update_options(voice="en-US-ken", style="Promo")
            instruction = "Mode: TEACH_BACK. Ask the user to explain the concept to you as if YOU are the beginner."
        else:
            return "Invalid mode."
    else:
        instruction = "Voice switch failed (Session not found)."

    print(f"🔄 SWITCHING MODE -> {state.mode.upper()}")
    return f"Switched to {state.mode} mode. {instruction}"

@function_tool
async def evaluate_teaching(
    ctx: RunContext[Userdata],
    user_explanation: Annotated[str, Field(description="The explanation given by the user during teach-back")]
) -> str:
    """📝 Call this when the user has finished explaining a concept in 'teach_back' mode."""
    print(f"📝 EVALUATING EXPLANATION: {user_explanation}")
    # NOTE: Replace with real evaluation logic or LLM call if desired.
    return "Analyze the user's explanation. Give them a score out of 10 on accuracy and clarity, and correct any mistakes."

# ======================================================
# 🌟 AGENT DEFINITION
# ======================================================

class TutorAgent(Agent):
    def __init__(self):
        # Generate list of topics for the prompt
        topic_list = ", ".join([f"{t['id']} ({t['title']})" for t in COURSE_CONTENT])

        super().__init__(
            instructions=f"""
            You are an approachable Cloud Computing Tutor designed to help users master concepts like cloud architecture and services.

            🌼 **AVAILABLE TOPICS:** {topic_list}

            🔄 **YOU HAVE 3 MODES:**
            1. **LEARN Mode (Voice: Matthew):** You explain the concept clearly using the summary data.
            2. **QUIZ Mode (Voice: Alicia):** You ask the user a specific question to test knowledge.
            3. **TEACH_BACK Mode (Voice: Ken):** YOU pretend to be a student. Ask the user to explain the concept to you.

            ⚙️ **BEHAVIOR:**
            - Start by asking what topic they want to study.
            - Use the `set_learning_mode` tool immediately when the user asks to learn, take a quiz, or teach.
            - In 'teach_back' mode, listen to their explanation and then use `evaluate_teaching` to give feedback.
            """,
            tools=[select_topic, set_learning_mode, evaluate_teaching],
        )

# ======================================================
# ✨ ENTRYPOINT
# ======================================================

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    print("\n" + "💖" * 25)
    print("✨ STARTING CLOUD COMPUTING TUTOR SESSION")
    print(f"🌼 Loaded {len(COURSE_CONTENT)} topics from Knowledge Base")

    # 1. Initialize State
    userdata = Userdata(tutor_state=TutorState())

    # 2. Setup Agent
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

    # 3. Store session in userdata for tools to access
    userdata.agent_session = session

    # 4. Start
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
