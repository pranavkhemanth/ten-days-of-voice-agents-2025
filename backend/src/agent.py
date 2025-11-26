import logging
import json
from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    RoomInputOptions,
    WorkerOptions,
    cli,
    metrics,
    tokenize,
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")
load_dotenv(".env.local")

# Load Razorpay FAQ and lead template
with open("razorpay_faq.json", "r") as f:
    razorpay_faq = json.load(f)

class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""
            You are an SDR for Razorpay, a leading payment solutions platform for Indian businesses.
            Your role is to:
            1. Greet the visitor warmly.
            2. Ask what brought them to Razorpay and what they're working on.
            3. Use the provided FAQ to answer questions about Razorpay's product, pricing, and use cases.
            4. Collect lead information: Name, Company, Email, Role, Use Case, Team Size, Timeline.
            5. Provide a summary of the lead at the end of the call and store the details in a JSON file.

            **Conversation Flow:**
            - Start with: "Hello! Welcome to Razorpay. I’m [Your Name], your Sales Development Representative. How can I assist you today?"
            - Ask: "What brought you to Razorpay today? Are you looking to accept online payments or explore our subscription solutions?"
            - If the user asks a question, search the FAQ for relevant answers.
            - Politely collect lead details: "May I know your name, company, and email to assist you better?"
            - End the call with a summary: "To summarize, you’re [Name] from [Company], looking for [Use Case] with a team of [Team Size] and a timeline of [Timeline]. Is that correct?"
            - Store the lead details in a JSON file.
            """
        )
        self.lead = {
            "name": "",
            "company": "",
            "email": "",
            "role": "",
            "use_case": "",
            "team_size": "",
            "timeline": ""
        }
        self.faq = razorpay_faq

    def find_answer(self, question):
        for item in self.faq["faq"]:
            if question.lower() in item["question"].lower():
                return item["answer"]
        return "I couldn't find an answer to that question. Can you rephrase or ask something else?"

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(
            voice="en-US-matthew",
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    await session.start(
        agent=Assistant(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await ctx.connect()

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
