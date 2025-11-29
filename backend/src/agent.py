# ======================================================
# 🌙 DAY 8 – DRAMATIC VOICE ADVENTURE GAME MASTER
# Cozy, atmospheric, dramatic voice-only adventure agent
# ======================================================


import json
import logging
import os
import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Annotated

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

from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# -------------------------
# Logging
# -------------------------
logger = logging.getLogger("dramatic_voice_gm")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(handler)

load_dotenv(".env.local")

# -----------------------------------------------------
# 🌑 DRAMATIC WORLD — “THE ASHEN VALE”
# -----------------------------------------------------
WORLD = {
    "intro": {
        "title": "The Ashen Vale",
        "desc": (
            "Cold mist curls around your boots as you awaken in the Ashen Vale — a forest that once "
            "thrived with life, now hushed beneath a pale sky. A lantern flickers beside you, its flame "
            "violet and unnaturally steady. In the distance, a cathedral bell tolls a single, lonely note."
        ),
        "choices": {
            "take_lantern": {
                "desc": "pick up the strange violet lantern",
                "result_scene": "lantern_scene",
            },
            "follow_bell": {
                "desc": "walk toward the distant cathedral bell",
                "result_scene": "cathedral_path",
            },
            "explore_forest": {
                "desc": "step deeper into the silent forest",
                "result_scene": "forest",
            },
        },
    },

    "lantern_scene": {
        "title": "The Lantern's Whisper",
        "desc": (
            "The lantern hums faintly in your hand, its glass warm despite the chill. A soft whisper "
            "brushes your ear, subtle yet clear: 'Not all that is lost wishes to be found…'"
        ),
        "choices": {
            "keep_lantern": {
                "desc": "keep the lantern and move forward",
                "result_scene": "cathedral_path",
                "effects": {"add_inventory": "violet_lantern", "add_journal": "The lantern whispered to me."},
            },
            "leave_lantern": {
                "desc": "leave the lantern where it lies",
                "result_scene": "intro",
            },
        },
    },

    "cathedral_path": {
        "title": "Path of Echoes",
        "desc": (
            "The forest parts slowly, revealing a stone path cracked with age. Each step you take echoes "
            "slightly louder than it should, as if the Vale itself is listening."
        ),
        "choices": {
            "approach_cathedral": {
                "desc": "continue toward the cathedral",
                "result_scene": "cathedral",
            },
            "search_surroundings": {
                "desc": "inspect the path and the trees around you",
                "result_scene": "forest",
            },
            "retreat": {
                "desc": "return to where you awoke",
                "result_scene": "intro",
            },
        },
    },

    "forest": {
        "title": "Boughs of Silence",
        "desc": (
            "The trees loom tall and skeletal. Feathers drift from the branches — though no birds "
            "can be seen. A faint heartbeat seems to pulse through the bark."
        ),
        "choices": {
            "touch_tree": {
                "desc": "place your hand on the ancient tree",
                "result_scene": "tree_memory",
                "effects": {"add_journal": "The forest heartbeat grew louder when I touched the tree."},
            },
            "return_path": {
                "desc": "return to the stone path",
                "result_scene": "cathedral_path",
            },
            "hide": {
                "desc": "hide behind the trees and observe",
                "result_scene": "shadow_pass",
            },
        },
    },

    "shadow_pass": {
        "title": "The Passing Shadow",
        "desc": (
            "A tall, indistinct figure drifts along the path, carrying a small silver bell. As it moves, "
            "the forest seems to breathe in and out. Just before vanishing, it pauses… as if sensing you."
        ),
        "choices": {
            "follow_shadow": {
                "desc": "follow the mysterious figure",
                "result_scene": "cathedral",
                "effects": {"add_journal": "I followed the figure with the silver bell."},
            },
            "stay_hidden": {
                "desc": "remain hidden until it leaves",
                "result_scene": "forest",
            },
        },
    },

    "tree_memory": {
        "title": "Melody of the Roots",
        "desc": (
            "As your hand touches the wood, visions flood your mind — laughter, warmth, sunlight. The Vale "
            "was once alive. A final image lingers: the cathedral, glowing gold rather than gray."
        ),
        "choices": {
            "go_to_cathedral": {
                "desc": "head toward the cathedral with new purpose",
                "result_scene": "cathedral",
            },
            "return": {
                "desc": "retreat from the overwhelming vision",
                "result_scene": "forest",
            },
        },
    },

    "cathedral": {
        "title": "Cathedral of Last Light",
        "desc": (
            "The doors stand open. Candles float weightlessly in the air, forming a path toward a stone altar. "
            "A tome rests atop it, humming softly — waiting."
        ),
        "choices": {
            "open_tome": {
                "desc": "open the humming tome",
                "result_scene": "tome_reveal",
                "effects": {"add_journal": "The tome reacted when I touched it."},
            },
            "leave_cathedral": {
                "desc": "step out and rethink your path",
                "result_scene": "cathedral_path",
            },
        },
    },

    "tome_reveal": {
        "title": "Revelation of the Vale",
        "desc": (
            "The tome reveals a single phrase amidst swirling ink: 'Light is memory. Memory is the key.' "
            "As the words fade, the violet lantern (if you carry it) glows brighter."
        ),
        "choices": {
            "take_tome": {
                "desc": "take the tome and accept its calling",
                "result_scene": "ending",
                "effects": {"add_inventory": "tome_of_memory"},
            },
            "close_tome": {
                "desc": "close the tome and step back",
                "result_scene": "cathedral",
            },
        },
    },

    "ending": {
        "title": "Dawn Over Ash",
        "desc": (
            "Light sweeps across the Vale, chasing away the mist. The lantern warms your chest, and the sky "
            "brightens to gold. The Ashen Vale remembers itself — because you remembered it."
        ),
        "choices": {
            "restart": {
                "desc": "return to the beginning and walk the Vale again",
                "result_scene": "intro",
            }
        },
    },
}

# -------------------------
# Per-session Userdata
# -------------------------
@dataclass
class Userdata:
    player_name: Optional[str] = None
    current_scene: str = "intro"
    history: List[Dict] = field(default_factory=list)
    journal: List[str] = field(default_factory=list)
    inventory: List[str] = field(default_factory=list)
    named_npcs: Dict[str, str] = field(default_factory=dict)
    choices_made: List[str] = field(default_factory=list)
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


# -------------------------
# Helper functions (voice-first — list choices as natural phrases)
# -------------------------
def _choices_list_for_scene(scene_key: str) -> List[tuple]:
    scene = WORLD.get(scene_key, {})
    choices = list(scene.get("choices", {}).items())
    return choices


def scene_text(scene_key: str, userdata: Userdata) -> str:
    """Build a spoken description for the scene suitable for TTS.
    It lists choices as natural phrases (no numbers, no internal keys).
    Example: "You can: pick up the strange violet lantern, walk toward the distant cathedral bell, or step deeper into the silent forest."
    """
    scene = WORLD.get(scene_key)
    if not scene:
        return "You find yourself in a silent void. What do you do?"

    parts = []
    parts.append(scene.get("desc", ""))

    choices = _choices_list_for_scene(scene_key)
    if choices:
        # Build a natural-language list of choice descriptions
        descs = [cmeta.get("desc", "").rstrip('.') for _, cmeta in choices]
        if len(descs) == 1:
            choices_line = f"You can {descs[0]}."
        else:
            # join with commas and 'or' before final item
            choices_line = "You can " + ", ".join(descs[:-1]) + ", or " + descs[-1] + "."
        parts.append(choices_line)

    parts.append("What do you do?")
    return "\n".join(parts)


def _normalize_number_word(text: str) -> Optional[int]:
    text = (text or "").strip().lower()
    mapping = {
        "one": 1, "1": 1, "first": 1,
        "two": 2, "2": 2, "second": 2,
        "three": 3, "3": 3, "third": 3,
        "four": 4, "4": 4, "fourth": 4,
    }
    for k, v in mapping.items():
        if k in text:
            return v
    return None


def apply_effects(effects: dict, userdata: Userdata):
    if not effects:
        return
    if "add_journal" in effects:
        userdata.journal.append(effects["add_journal"])
    if "add_inventory" in effects:
        userdata.inventory.append(effects["add_inventory"])


def summarize_scene_transition(old_scene: str, action_key: str, result_scene: str, userdata: Userdata) -> str:
    entry = {"from": old_scene, "action": action_key, "to": result_scene, "time": datetime.utcnow().isoformat() + "Z"}
    userdata.history.append(entry)
    userdata.choices_made.append(action_key)
    return f"You chose '{action_key}'."


# -------------------------
# Agent Tools
# -------------------------
@function_tool
async def start_adventure(
    ctx: RunContext[Userdata],
    player_name: Annotated[Optional[str], Field(description="Player name", default=None)] = None,
) -> str:
    userdata = ctx.userdata
    if player_name:
        userdata.player_name = player_name
    userdata.current_scene = "intro"
    userdata.history = []
    userdata.journal = []
    userdata.inventory = []
    userdata.named_npcs = {}
    userdata.choices_made = []
    userdata.session_id = str(uuid.uuid4())[:8]
    userdata.started_at = datetime.utcnow().isoformat() + "Z"

    opening = (
        f"{userdata.player_name or 'Traveler'}, your journey begins in {WORLD['intro']['title']}.\n\n"
        + scene_text("intro", userdata)
    )
    return opening


@function_tool
async def get_scene(ctx: RunContext[Userdata]) -> str:
    return scene_text(ctx.userdata.current_scene, ctx.userdata)


@function_tool
async def player_action(
    ctx: RunContext[Userdata],
    action: Annotated[str, Field(description="Player spoken action or a spoken option number")],
) -> str:
    userdata = ctx.userdata
    current = userdata.current_scene
    scene = WORLD.get(current, {})
    action_text = (action or "").strip().lower()

    # Try numeric interpretation first
    num = _normalize_number_word(action_text)
    choices = _choices_list_for_scene(current)
    chosen_key = None

    if num is not None and 1 <= num <= len(choices):
        chosen_key = choices[num - 1][0]

    # exact key match
    if not chosen_key and action_text in scene.get("choices", {}):
        chosen_key = action_text

    # fuzzy match using description words
    if not chosen_key:
        for cid, cmeta in choices:
            desc = cmeta.get("desc", "").lower()
            # check if the user's words map to several words in the desc
            if any(word for word in desc.split()[:6] if word in action_text):
                chosen_key = cid
                break

    # last resort: full substring match
    if not chosen_key:
        for cid, cmeta in choices:
            if cmeta.get("desc", "").lower() in action_text:
                chosen_key = cid
                break

    if not chosen_key:
        return (
            "I didn't catch that. Please say one of the choices aloud — for example: 'pick up the lantern' or 'follow the bell'.\n\n"
            + scene_text(current, userdata)
        )

    choice_meta = scene.get("choices", {}).get(chosen_key, {})
    result_scene = choice_meta.get("result_scene", current)
    effects = choice_meta.get("effects", None)

    apply_effects(effects or {}, userdata)
    note = summarize_scene_transition(current, chosen_key, result_scene, userdata)
    userdata.current_scene = result_scene

    reply = "The Game Master intones:\n\n" + note + "\n\n" + scene_text(result_scene, userdata)
    return reply


@function_tool
async def show_journal(ctx: RunContext[Userdata]) -> str:
    userdata = ctx.userdata
    lines = [f"Session: {userdata.session_id} | Started at: {userdata.started_at}"]
    if userdata.player_name:
        lines.append(f"Player: {userdata.player_name}")
    lines.append("\nJournal:")
    if userdata.journal:
        for j in userdata.journal:
            lines.append(f"- {j}")
    else:
        lines.append("- (empty)")
    lines.append("\nInventory:")
    if userdata.inventory:
        for it in userdata.inventory:
            lines.append(f"- {it}")
    else:
        lines.append("- (none)")
    lines.append("\nRecent choices:")
    for h in userdata.history[-6:]:
        lines.append(f"- {h['time']} | from {h['from']} -> {h['to']} via {h['action']}")
    lines.append("\nWhat do you do?")
    return "\n".join(lines)


@function_tool
async def restart_adventure(ctx: RunContext[Userdata]) -> str:
    return await start_adventure(ctx)


# -------------------------
# Agent
# -------------------------
class DramaticGameMasterAgent(Agent):
    def __init__(self):
        instructions = """
        You are 'Aurek', a dramatic and cinematic Game Master.
        Keep responses short enough for voice delivery, use evocative sentences. Always end with 'What do you do?'.
        Present choices as natural phrases (no numbers or internal keys). Players will hear: "You can ... or ...".
        """
        super().__init__(
            instructions=instructions,
            tools=[start_adventure, get_scene, player_action, show_journal, restart_adventure],
        )


# -------------------------
# Entrypoint & prewarm
# -------------------------
def prewarm(proc: JobProcess):
    try:
        proc.userdata["vad"] = silero.VAD.load()
    except Exception:
        logger.warning("VAD prewarm failed; continuing without preloaded VAD.")


async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}
    logger.info("⚡️ STARTING DRAMATIC VOICE GAME MASTER (natural choices)")

    userdata = Userdata()

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(
            voice="en-US-riley",
            style="Narration",
            text_pacing=True,
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata.get("vad"),
        userdata=userdata,
    )

    await session.start(
        agent=DramaticGameMasterAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(noise_cancellation=noise_cancellation.BVC()),
    )

    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))


