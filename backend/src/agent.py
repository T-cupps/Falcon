# ======================================================
# 🎨 DAY 5: ARTZOLO — ART MARKETPLACE SDR (cute edition)
# 🌸 ArtZolo — Auto-Lead Capture & FAQ Agent
# 🚀 Features: FAQ Retrieval, Lead/Artist Qualification, JSON Database
# ======================================================

import logging
import json
import os
import asyncio
from datetime import datetime
from typing import Annotated, Optional
from dataclasses import dataclass, asdict

print("\n" + "🎨" * 20)
print("🚀 ARTZOLO AGENT ✨")
print("🖼️ ROLE: Marketplace assistant for ArtZolo (artists & buyers)")
print("💖 agent.py LOADED SUCCESSFULLY!")
print("🎨" * 20 + "\n")

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

# 🔌 PLUGINS (keep only what you actually use)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")
load_dotenv(".env.local")

# ======================================================
# 📂 1. KNOWLEDGE BASE (FAQ)
# ======================================================

FAQ_FILE = "artzolo_faq.json"
LEADS_FILE = "artzolo_leads.json"

# Default FAQ data tailored for ArtZolo (marketplace-focused)
DEFAULT_FAQ = [
    {
        "question": "What is ArtZolo?",
        "answer": "ArtZolo is an online marketplace where artists can showcase and sell original artworks, prints, photography, and home décor. Buyers can browse, commission, and purchase art directly from creators."
    },
    {
        "question": "How do I sell my art on ArtZolo?",
        "answer": "You can sign up as an artist, create a profile, upload images and descriptions, set prices, and choose shipping options. ArtZolo may review listings before they go live."
    },
    {
        "question": "Can I commission a custom artwork?",
        "answer": "Yes — buyers can request commissions. Use the commission form on an artist's profile or message the artist directly. The artist and buyer agree on scope, timeline, and price."
    },
    {
        "question": "How are payments handled?",
        "answer": "Payments are processed via our secure payment gateway. Artists receive payouts according to the platform's payout schedule after fees and holds (if any) are applied."
    },
    {
        "question": "What about shipping and returns?",
        "answer": "Artists choose shipping options and costs per listing. For returns or disputes, ArtZolo provides a resolution workflow — buyers should contact support within the return window."
    },
    {
        "question": "Do you verify authenticity?",
        "answer": "We encourage artists to provide provenance and certificates of authenticity where applicable. ArtZolo may offer verification or badges for trusted sellers."
    }
]

def load_knowledge_base():
    """Generates FAQ file if missing, then loads it."""
    try:
        path = os.path.join(os.path.dirname(__file__), FAQ_FILE)
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_FAQ, f, indent=4)
        with open(path, "r", encoding="utf-8") as f:
            return json.dumps(json.load(f))  # Return as string for the Prompt
    except Exception as e:
        print(f"⚠️ Error loading FAQ: {e}")
        return ""

ARTZOLO_FAQ_TEXT = load_knowledge_base()

# ======================================================
# 💾 2. LEAD / ARTIST DATA STRUCTURE
# ======================================================

@dataclass
class LeadProfile:
    # The profile is generic — can represent a buyer enquiry or an artist sign-up
    name: Optional[str] = None
    company: Optional[str] = None  # gallery or studio name (optional)
    email: Optional[str] = None
    role: Optional[str] = None     # 'buyer' or 'artist' or job/title
    interest: Optional[str] = None # e.g., "commission", "sell art", "buy painting"
    art_style: Optional[str] = None
    timeline: Optional[str] = None

    def is_qualified(self) -> bool:
        """Basic qualification: name + email + interest (what they want)."""
        return bool(self.name and self.email and self.interest)

@dataclass
class Userdata:
    lead_profile: LeadProfile

# ======================================================
# 🛠️ 3. ARTZOLO TOOLS (function tools the agent can call)
# ======================================================

@function_tool
async def update_lead_profile(
    ctx: RunContext[Userdata],
    name: Annotated[Optional[str], Field(description="Person's name")] = None,
    company: Annotated[Optional[str], Field(description="Gallery or studio name")] = None,
    email: Annotated[Optional[str], Field(description="Email address")] = None,
    role: Annotated[Optional[str], Field(description="'buyer' or 'artist' or title")] = None,
    interest: Annotated[Optional[str], Field(description="What they want (sell, buy, commission)")] = None,
    art_style: Annotated[Optional[str], Field(description="Preferred art style or medium")] = None,
    timeline: Annotated[Optional[str], Field(description="When they want it (e.g., next month)")] = None,
) -> str:
    """
    ✍️ Captures lead/artist details provided during conversation.
    Only call when the user gives info.
    """
    profile = ctx.userdata.lead_profile

    if name: profile.name = name
    if company: profile.company = company
    if email: profile.email = email
    if role: profile.role = role
    if interest: profile.interest = interest
    if art_style: profile.art_style = art_style
    if timeline: profile.timeline = timeline

    print(f"📝 UPDATING ARTZOLO LEAD: {profile}")
    return "Lead profile updated. Keep the lovely chat going! 🌼"

@function_tool
async def submit_lead_and_end(
    ctx: RunContext[Userdata],
) -> str:
    """
    💾 Saves the lead (buyer enquiry or artist signup) and closes the conversation.
    Call this when the user indicates they are done.
    """
    profile = ctx.userdata.lead_profile

    db_path = os.path.join(os.path.dirname(__file__), LEADS_FILE)
    entry = asdict(profile)
    entry["timestamp"] = datetime.now().isoformat()

    existing_data = []
    if os.path.exists(db_path):
        try:
            with open(db_path, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
        except Exception:
            existing_data = []

    existing_data.append(entry)

    with open(db_path, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, indent=4)

    print(f"✅ ARTZOLO LEAD SAVED TO {LEADS_FILE}")

    # Friendly summary message
    summary = (
        f"Thanks {profile.name or 'friend'} — I have your details about "
        f"'{profile.interest or 'your interest'}'. We'll reach out at {profile.email or 'your email'}. "
        "Have a creative day! 🎨✨"
    )
    return summary

# ======================================================
# 🧠 4. AGENT DEFINITION (ArtZolo persona)
# ======================================================

class ArtZoloAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions=f"""
            You are 'Aria', a warm and helpful ArtZolo assistant for artists and buyers.

            📘 **KNOWLEDGE BASE (FAQ):**
            {ARTZOLO_FAQ_TEXT}

            🎯 **GOALS:**
            1. Answer marketplace questions (selling, buying, commissioning, shipping, payments).
            2. **QUALIFY** visitors gently — ask for:
               - Name
               - Email
               - Are they an 'artist' or 'buyer' (or both)?
               - Interest: sell / buy / commission / collaborate
               - Preferred style or medium (if relevant)
               - Timeline for commission or purchase

            ⚙️ **BEHAVIOR:**
            - Be friendly and curious — never interrogative.
            - Provide helpful marketplace steps when asked (how to list, commission flow, shipping tips).
            - Use `update_lead_profile` when new info appears in chat.
            - When the user finishes, use `submit_lead_and_end`.

            🚫 **RESTRICTIONS:**
            - Do not invent payout schedules, legal policies, or personal contact info — say: "I'll confirm and follow up by email."
            """,
            tools=[update_lead_profile, submit_lead_and_end],
        )

# ======================================================
# 🎬 ENTRYPOINT
# ======================================================

def prewarm(proc: JobProcess):
    # Preload VAD for faster voice handling
    proc.userdata["vad"] = silero.VAD.load()

async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    print("\n" + "🎨" * 12)
    print("🚀 STARTING ARTZOLO SESSION — hello, art friend! 🌷")

    # 1. Initialize State
    userdata = Userdata(lead_profile=LeadProfile())

    # 2. Setup Agent Session (voice + LLM)
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(
            voice="en-US-daisy",  # friendly voice
            style="Conversational",
            text_pacing=True,
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        userdata=userdata,
    )

    # 3. Start the session
    await session.start(
        agent=ArtZoloAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC()
        ),
    )

    await ctx.connect()

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
