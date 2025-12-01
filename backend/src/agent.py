import logging
import random
import os
from typing import Dict, Any

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    WorkerOptions,
    cli,
    metrics,
    tokenize,
    function_tool,
    RunContext,
)
from livekit.plugins import murf, silero, google, deepgram
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")

load_dotenv(".env.local")

# Cozy, cute improv scenarios
IMPROV_SCENARIOS = [
"You are a small tea shop owner offering the perfect calming blend to a nervous traveler.",
"You are a librarian helping a child find the coziest bedtime story — but every book has a tiny, silly surprise.",
"You are a baker who accidentally created a croissant that hums lullabies.",
"You are a gardener trying to explain to a curious neighbor why the moonflowers only open for polite conversations.",
"You are a kindly innkeeper reassuring a tired adventurer that their room comes with a complimentary cookie and a cat.",
"You are a stitcher teaching a friend how to knit a scarf that remembers warm memories.",
"You are a gentle park ranger guiding visitors to a secret glade where friendly fireflies tell jokes.",
"You are a sleepy dragon who just wants a cup of chamomile tea before bed and keeps apologizing for tiny hiccups of smoke.",
"You are a candle maker describing a scent that smells like rainy afternoons and old books.",
"You are a curious gnome explaining to a child why mushrooms make the best tiny umbrellas.",
"You are a neighbor who hosts a surprise porch concert for a friend who's had a long week.",
"You are a friendly spooky-but-not-scary ghost who gives out compliments instead of scares.",
"You are a tea kettle with very strong feelings about punctual boiling.",
"You are a bedtime storyteller who keeps getting distracted by the characters asking questions back.",
"You are a cat cafe barista trying to match each customer with their purr-fect feline companion.",
"You are a clockmaker who makes tiny clocks that tick in rhythm with people's happy memories.",
"You are a postmaster delivering tiny handwritten notes that make people smile.",
]


class ImprovHost(Agent):
    def __init__(self, improv_state: Dict[str, Any]) -> None:
        self.improv_state = improv_state
        super().__init__(
            instructions="""You are the host of a TV improv show called "Improv Battle". 

CRITICAL FIRST MESSAGE: When you first join a room, you MUST immediately speak first and welcome the player. Do NOT wait for them to speak. Start with: "heyy buddy, welcome to Improv Battle! I'm your host Amayra"

Your role and style:
- High-energy, witty, and clear about rules
- Reactions should be realistic: sometimes amused, sometimes unimpressed, sometimes pleasantly surprised
- Not always supportive; light teasing and honest critique are allowed, but stay respectful and non-abusive
- Vary your tone: randomly choose between more supportive, neutral, or mildly critical tones, while staying constructive and safe

Your responses are concise, natural, and conversational. No emojis, asterisks, or special formatting.

CRITICAL: You MUST always respond to user input. When a user speaks (like "Hello"), you MUST respond immediately. Do not ignore user messages. Always acknowledge and respond to what the user says.

Game structure - follow this flow EXACTLY - NO EXCEPTIONS:

MANDATORY SEQUENCE: Round 1 → Round 2 → Round 3 → Closing Summary

1. PHASE: intro
   - IMPORTANT: As soon as you join the room, immediately welcome the player warmly
   - Start speaking right away - don't wait for the user to speak first
   - Welcome them: "heyy buddy, welcome to Improv Battle! I'm your host amayra"
   - Ask for their name if not provided
   - Explain the rules: "I'll give you a scenario, you improvise it, then I'll react. We'll do 3 rounds."
   - Use set_player_name tool if they give their name
   - Then call start_new_round to begin round 1

2. PHASE: awaiting_improv (for each round)
   - Announce the scenario clearly: "Round X of 3. Here's your scenario: [scenario from start_new_round]"
   - Tell them to start: "Alright, let's see what you've got. Start whenever you're ready!"
   - Wait for them to perform
   - If they say "end scene", "done", "that's it", or pause for a while, move to reacting

3. PHASE: reacting (after each scene) - CRITICAL WORKFLOW:
   
   AFTER ROUND 1:
   - Give your reaction (2-3 sentences max)
   - Call complete_round with your reaction
   - Call check_if_done → it will return "no" (because only 1 round is done)
   - You MUST call start_new_round to begin Round 2
   - Announce Round 2 scenario
   
   AFTER ROUND 2:
   - Give your reaction (2-3 sentences max)
   - Call complete_round with your reaction
   - Call check_if_done → it will return "no" (because only 2 rounds are done, Round 3 is still needed)
   - CRITICAL: You MUST call start_new_round to begin Round 3 - DO NOT skip Round 3
   - Announce Round 3 scenario: "Round 3 of 3. Here's your scenario: [scenario]"
   - Wait for Round 3 performance
   
   AFTER ROUND 3:
   - Give your reaction (2-3 sentences max)
   - Call complete_round with your reaction
   - Call check_if_done → it will return "yes" (because all 3 rounds are done)
   - NOW you can give the closing summary

4. PHASE: done (closing)
   - Only enter this phase after Round 3 is complete and check_if_done returns "yes"
   - Summarize their improv style (character work, absurdity, emotional range, etc.)
   - Mention 1-2 specific moments that stood out
   - Thank them warmly and close the show

CRITICAL WORKFLOW RULES - ABSOLUTE REQUIREMENTS:

THE MANDATORY SEQUENCE (DO NOT DEVIATE):
Round 1 → React → complete_round → check_if_done ("no") → start_new_round → Round 2
Round 2 → React → complete_round → check_if_done ("no") → start_new_round → Round 3  
Round 3 → React → complete_round → check_if_done ("yes") → Closing Summary

AFTER EVERY ROUND COMPLETION:
1. Call complete_round with your reaction
2. Call check_if_done immediately
3. READ the check_if_done result:
   - "no" = More rounds needed → You MUST call start_new_round. Do NOT give closing summary.
   - "yes" = All rounds done → Only then give closing summary.

ABSOLUTE PROHIBITIONS:
- ❌ NEVER give closing summary after Round 1
- ❌ NEVER give closing summary after Round 2
- ❌ NEVER skip Round 3 - Round 3 is MANDATORY
- ❌ NEVER skip calling start_new_round when check_if_done returns "no"
- ❌ NEVER end the game before Round 3 is complete
- ❌ NEVER assume all rounds are done if you've only done 1 or 2 rounds
- ✅ ONLY give closing summary after Round 3 is complete AND check_if_done returns "yes"

ROUND TRACKING - EXACT SEQUENCE:
- After Round 1 completes: check_if_done returns "no" (1/3 done) → MUST call start_new_round → Round 2
- After Round 2 completes: check_if_done returns "no" (2/3 done) → MUST call start_new_round → Round 3
- After Round 3 completes: check_if_done returns "yes" (3/3 done) → NOW give closing summary

CRITICAL: You MUST complete Round 1, then Round 2, then Round 3. You cannot skip Round 3.
If check_if_done returns "no", it means you have NOT completed all 3 rounds yet - you MUST continue.

If the player says "stop", "end game", "quit", call end_game_early and gracefully wrap up.""",
        )

    @function_tool
    async def get_current_state(self, context: RunContext) -> str:
        """Get the current game state information."""
        completed = len(self.improv_state["rounds"])
        current = self.improv_state["current_round"]
        max_rounds = self.improv_state["max_rounds"]
        return f"Phase: {self.improv_state['phase']}, Current Round: {current}/{max_rounds}, Completed Rounds: {completed}/{max_rounds}, Player: {self.improv_state.get('player_name', 'Unknown')}"

    @function_tool
    async def set_player_name(self, context: RunContext, name: str) -> str:
        """Set the player's name from their response."""
        if not self.improv_state.get("player_name"):
            self.improv_state["player_name"] = name
            logger.info(f"Player name set to: {name}")
            return f"Player name set to {name}"
        return "Player name already set"

    @function_tool
    async def start_new_round(self, context: RunContext) -> str:
        """Start a new improv round. Returns the scenario for this round.
        
        CRITICAL: This MUST be called in sequence: Round 1 → Round 2 → Round 3.
        You cannot skip rounds. This increments the round counter and selects a new scenario.
        Call this after completing a round when check_if_done returns "no".
        """
        completed_rounds = len(self.improv_state["rounds"])
        max_rounds = self.improv_state["max_rounds"]
        current_round = self.improv_state["current_round"]
        
        if completed_rounds >= max_rounds:
            logger.warning("Attempted to start new round but all rounds are already completed")
            return "ERROR: All rounds already completed. Do NOT call start_new_round. Give the closing summary instead."
        
        if current_round >= max_rounds:
            logger.warning(f"Current round {current_round} already at max {max_rounds}")
            return f"ERROR: Already at round {current_round}. All rounds should be complete. Call check_if_done to verify, then give closing summary."
        
        self.improv_state["current_round"] += 1
        self.improv_state["phase"] = "awaiting_improv"
        new_round_num = self.improv_state["current_round"]
        
        # Select a random scenario (avoid repeating the last one if possible)
        last_scenario = self.improv_state.get("current_scenario")
        available_scenarios = [s for s in IMPROV_SCENARIOS if s != last_scenario] or IMPROV_SCENARIOS
        scenario = random.choice(available_scenarios)
        self.improv_state["current_scenario"] = scenario
        
        logger.info(f"✅ Starting round {new_round_num} of {max_rounds} with scenario: {scenario}")
        return f"Round {new_round_num} of {max_rounds} started. Scenario: {scenario}. You MUST announce this to the player: 'Round {new_round_num} of 3. Here's your scenario: {scenario}. Alright, let's see what you've got. Start whenever you're ready!'"

    @function_tool
    async def complete_round(self, context: RunContext, reaction: str) -> str:
        """Complete the current round and store the host's reaction.
        
        CRITICAL: After calling this, you MUST:
        1. Call check_if_done immediately
        2. If check_if_done returns 'no', you MUST call start_new_round
        3. If check_if_done returns 'yes', give the closing summary
        
        DO NOT skip calling start_new_round after check_if_done returns 'no'.
        """
        current_round_num = self.improv_state["current_round"]
        round_data = {
            "round": current_round_num,
            "scenario": self.improv_state.get("current_scenario", ""),
            "host_reaction": reaction,
        }
        self.improv_state["rounds"].append(round_data)
        self.improv_state["phase"] = "reacting"
        completed = len(self.improv_state["rounds"])
        max_rounds = self.improv_state["max_rounds"]
        logger.info(f"Round {current_round_num} completed. Total completed: {completed}/{max_rounds}")
        
        if completed < max_rounds:
            return f"Round {current_round_num} completed. You have completed {completed} out of {max_rounds} rounds. You MUST call check_if_done now, and if it returns 'no', you MUST call start_new_round to continue."
        else:
            return f"Round {current_round_num} completed. You have completed all {max_rounds} rounds. Call check_if_done to confirm, then give the closing summary."

    @function_tool
    async def check_if_done(self, context: RunContext) -> str:
        """Check if all rounds are complete. Returns 'yes' if all rounds are done, 'no' if more rounds remain.
        
        CRITICAL: This checks the number of COMPLETED rounds in the rounds array. 
        - You need EXACTLY 3 completed rounds before this returns 'yes'.
        - After Round 1: returns 'no' (1 completed, need 2 more) → MUST call start_new_round for Round 2
        - After Round 2: returns 'no' (2 completed, need 1 more) → MUST call start_new_round for Round 3  
        - After Round 3: returns 'yes' (3 completed, all done) → give closing summary
        
        DO NOT end the game unless this returns 'yes'. DO NOT skip rounds. You MUST do Round 1, Round 2, AND Round 3.
        """
        # Check if we've completed all rounds by comparing completed rounds count
        completed_rounds = len(self.improv_state["rounds"])
        max_rounds = self.improv_state["max_rounds"]
        current_round = self.improv_state["current_round"]
        
        logger.info(f"Checking if done: {completed_rounds} completed out of {max_rounds} max rounds (current_round={current_round})")
        
        # CRITICAL: Only return 'yes' if we have EXACTLY 3 completed rounds
        # This means: completed_rounds must be exactly 3, not 1, not 2, but 3
        if completed_rounds == max_rounds:
            self.improv_state["phase"] = "done"
            logger.info(f"✅ All rounds complete - game is done ({completed_rounds}/{max_rounds})")
            return "yes - all 3 rounds complete, you can now give the closing summary"
        
        # If we have less than 3 rounds completed, we MUST continue
        remaining = max_rounds - completed_rounds
        next_round = completed_rounds + 1
        
        # Special check: If we're at Round 2 and trying to end, force Round 3
        if completed_rounds == 2 and current_round == 2:
            logger.warning(f"⚠️ Round 2 completed but Round 3 not started! Forcing Round 3.")
            return f"no - CRITICAL: You have completed 2 rounds but Round 3 is missing! You MUST call start_new_round to start Round 3. DO NOT give closing summary - you must complete Round 3 first."
        
        logger.info(f"❌ Not done yet - need {remaining} more round(s). Current round: {current_round}. Next round should be: Round {next_round}. You MUST call start_new_round now.")
        return f"no - you have completed {completed_rounds} out of {max_rounds} rounds. You need {remaining} more round(s). You MUST call start_new_round to start Round {next_round}. DO NOT give closing summary yet - you must complete Round {next_round} first."

    @function_tool
    async def end_game_early(self, context: RunContext) -> str:
        """End the game early if the player wants to stop."""
        self.improv_state["phase"] = "done"
        logger.info("Game ended early by player request")
        return "Game ended"


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    # Logging setup
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }
    
    logger.info("=" * 80)
    logger.info(f"🚀 AGENT ENTRYPOINT CALLED FOR ROOM: {ctx.room.name}")
    logger.info("=" * 80)

    # Initialize game state
    improv_state: Dict[str, Any] = {
        "player_name": None,
        "current_round": 0,
        "max_rounds": 3,
        "rounds": [],
        "phase": "intro",
        "current_scenario": None,
    }

    # Check for Google API key
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        logger.error("=" * 80)
        logger.error("❌ GOOGLE_API_KEY not found in environment variables!")
        logger.error("=" * 80)
        logger.error("To use a different Google account's API key:")
        logger.error("1. Go to: https://aistudio.google.com/apikey")
        logger.error("2. Sign in with your Google account")
        logger.error("3. Click 'Create API Key'")
        logger.error("4. Copy the API key")
        logger.error("5. Add it to backend/.env.local as: GOOGLE_API_KEY=your_key_here")
        logger.error("6. Restart the backend agent")
        logger.error("=" * 80)
        raise ValueError("GOOGLE_API_KEY is required")
    
    # Set up a voice AI pipeline
    # Using Google Gemini 2.5 Flash (fast, efficient, free tier available)
    logger.info("Setting up voice AI pipeline...")
    logger.info("  - STT: Deepgram (nova-3)")
    logger.info("  - LLM: Google Gemini 2.5 Flash (gemini-2.5-flash)")
    logger.info("  - TTS: Murf Falcon")
    
    try:
        session = AgentSession(
            stt=deepgram.STT(model="nova-3"),
            llm=google.LLM(model="gemini-2.5-flash"),  # Flash model (faster, cheaper than Pro)
            tts=murf.TTS(
                voice="en-US-river",
                style="Conversation",
                tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
                text_pacing=True
            ),
            turn_detection=MultilingualModel(),
            vad=ctx.proc.userdata["vad"],
            preemptive_generation=True,
        )
        logger.info("✅ Voice AI pipeline configured successfully")
    except Exception as e:
        logger.error(f"❌ Failed to set up voice AI pipeline: {e}")
        raise

    # Metrics collection
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)
        
        # Log specific metrics for debugging
        if hasattr(ev.metrics, 'llm') and ev.metrics.llm:
            llm_metrics = ev.metrics.llm
            model_name = llm_metrics.get('model_name', 'unknown') if isinstance(llm_metrics, dict) else getattr(llm_metrics, 'model_name', 'unknown')
            prompt_tokens = llm_metrics.get('prompt_tokens', 0) if isinstance(llm_metrics, dict) else getattr(llm_metrics, 'prompt_tokens', 0)
            completion_tokens = llm_metrics.get('completion_tokens', 0) if isinstance(llm_metrics, dict) else getattr(llm_metrics, 'completion_tokens', 0)
            logger.info(f"🤖 LLM CALLED - Model: {model_name}, Prompt: {prompt_tokens}, Completion: {completion_tokens}")
        if hasattr(ev.metrics, 'stt') and ev.metrics.stt:
            stt_metrics = ev.metrics.stt
            audio_duration = stt_metrics.get('audio_duration', 0) if isinstance(stt_metrics, dict) else getattr(stt_metrics, 'audio_duration', 0)
            logger.info(f"🎤 STT - Audio duration: {audio_duration:.2f}s")
        if hasattr(ev.metrics, 'tts') and ev.metrics.tts:
            tts_metrics = ev.metrics.tts
            chars = tts_metrics.get('characters_count', 0) if isinstance(tts_metrics, dict) else getattr(tts_metrics, 'characters_count', 0)
            logger.info(f"🔊 TTS - Characters: {chars}")
        
    # Add error handler for session errors
    @session.on("error")
    def _on_error(error):
        logger.error(f"❌ Session error: {error}")
        import traceback
        logger.error(traceback.format_exc())


    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    # Create the improv host agent
    agent = ImprovHost(improv_state)

    # Start the session
    # Note: Noise cancellation (BVC) requires LiveKit Cloud, so we skip it for local dev
    await session.start(
        agent=agent,
        room=ctx.room,
    )

    # Join the room and connect to the user
    logger.info(f"Connecting to room: {ctx.room.name}")
    try:
        await ctx.connect()
        logger.info("✅ Agent successfully connected to room!")
        logger.info("Agent is ready to listen and respond to voice input.")
        logger.info("The agent will respond when the user speaks or speak first based on instructions.")
    except Exception as e:
        logger.error(f"❌ Failed to connect to room: {e}")
        raise


if __name__ == "__main__":
    logger.info("=" * 80)
    logger.info("Starting LiveKit agent worker...")
    logger.info("Waiting for job requests from LiveKit server...")
    logger.info("Make sure LiveKit server is running: npx livekit-server --dev")
    logger.info("=" * 80)
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
