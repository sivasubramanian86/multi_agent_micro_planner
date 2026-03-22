import asyncio
import os
import logging
from typing import Dict

from dotenv import load_dotenv

from google.adk import Agent
from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.tools.tool_context import ToolContext

from google.adk.models.google_llm import Gemini
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from google.genai.errors import ClientError
from fastapi.middleware.cors import CORSMiddleware

# --- CONFIGURATION & LOGGING ---
load_dotenv()
model_name = os.getenv("MODEL", "gemini-2.5-flash") # Native 2.0+ models only
logging.basicConfig(level=logging.INFO)

class FallbackGemini(Gemini):
    """
    Custom LLM wrapper for Google ADK.
    Intercepts 429 (Rate Limit) errors and retries using fallback models.
    Ensures the agent remains responsive during high traffic or quota limits.
    """
    def __init__(self, primary_model: str, fallback_models: list[str]):
        super().__init__(model=primary_model)
        self._fallback_models = fallback_models

    async def generate_content_async(self, llm_request, stream=False):
        try:
            async for response in super().generate_content_async(llm_request, stream=stream):
                yield response
        except ClientError as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                for fallback_model in self._fallback_models:
                    try:
                        await asyncio.sleep(2)  # Wait a bit to let quota reset
                        logging.warning(f"Attempting fallback to {fallback_model}...")
                        llm_request.model = fallback_model
                        fallback_llm = Gemini(model=fallback_model)
                        async for response in fallback_llm.generate_content_async(llm_request, stream=stream):
                            yield response
                        return
                    except Exception as inner_e:
                        if "429" in str(inner_e) or "RESOURCE_EXHAUSTED" in str(inner_e):
                            logging.warning(f"Fallback {fallback_model} also hit rate limit. Continuing...")
                            continue
                        raise inner_e
            raise e

# --- CALLBACKS & MODELS ---

async def on_model_error(callback_context, llm_request, error):
    error_str = str(error).replace('"', "'").replace('\n', ' ')
    logging.error(f"Final Model Error Catch: {error_str}")
    # Return a JSON string that the frontend can parse, indicating an error state
    return LlmResponse(
        content=types.Content(
            parts=[types.Part(text=f'{{"error": "API Initialization Error: {error_str}"}}')]
        )
    )

# Create the fallback-enabled model instance to use across agents
model_instance = FallbackGemini(
    primary_model=model_name,
    fallback_models=["gemini-2.5-flash-lite", "gemini-2.0-flash-001"]
)


# --- TOOLS (SKILLS) ---

def collect_inbox(tool_context: ToolContext, inbox_text: str) -> Dict[str, str]:
    """
    Tool called by the Root Agent to ingest the raw user input into the shared state.
    """
    tool_context.state["INBOX_RAW"] = inbox_text
    logging.info(f"Stored INBOX_RAW: {len(inbox_text)} chars")
    return {"status": "stored"}


def set_user_preference(tool_context: ToolContext, preference: str, value: str) -> Dict[str, str]:
    """
    Tool to store user-specific configuration (e.g., 'Work Hours').
    The Planner Agent uses these to optimize the suggested slots.
    """
    state_key = f"user:{preference}"
    tool_context.state[state_key] = value
    logging.info(f"Updated preference {state_key} = {value}")
    return {"status": "preference_updated"}


# --- SUB-AGENTS (The Worker Bees) ---
inbox_segmenter = LlmAgent(
    name="inbox_segmenter",
    model=model_instance,
    on_model_error_callback=on_model_error,
    description="Normalizes raw inbox text into a list of concise items.",
    instruction=(
        "You are an inbox segmenter. Read the raw text from INBOX_RAW in the state. "
        "Split the text into a JSON-style list of short 'items'. "
        "Each item should be a minimal unit of work or message. "
        "Store this list of objects exactly as an array in INBOX_ITEMS."
    ),
    output_key="INBOX_ITEMS",
)


# 4) Sub-agent: item_triage_agent
item_triage_agent = LlmAgent(
    name="item_triage_agent",
    model=model_instance,
    on_model_error_callback=on_model_error,
    description="Triages each item into type, category, urgency, and effort.",
    instruction=(
        "You are a triage agent. Read the list of items from INBOX_ITEMS in the state. "
        "For each item, analyze and assign the following properties: "
        "- 'type': must be one of ['Message', 'Task', 'Info', 'Junk'] "
        "- 'category': must be one of ['Work', 'Personal', 'Finance', 'Health', 'Other'] "
        "- 'urgency': must be one of ['Now', 'Today', 'This Week', 'Later'] "
        "- 'effort': must be one of ['5m', '15m', '30m+'] "
        "Ensure the original 'raw' text of the item is perfectly preserved in the 'raw' field. "
        "Return the result as a JSON array of these triaged items."
    ),
    output_key="TRIAGED_ITEMS",
)


# 5) Sub-agent: planner_agent
planner_agent = LlmAgent(
    name="planner_agent",
    model=model_instance,
    on_model_error_callback=on_model_error,
    description="Creates a plan and suggestions based on triaged items and user preferences.",
    instruction=(
        "You are a micro-planner agent. Read TRIAGED_ITEMS from state, as well as any user preferences "
        "(keys starting with 'user:'). "
        "For each item in the triaged items array: "
        "1. Assign a 'suggested_slot' from ['Morning', 'Afternoon', 'Evening', 'Weekend'] "
        "based on urgency, category, and any relevant user preferences (e.g., if a user prefers "
        "deep work in the morning, schedule 'Work' tasks there. Personal low-priority tasks in evening/weekend). "
        "2. For items with 'type' in ['Message', 'Task'] that clearly involve other people, optionally "
        "create a 'suggested_reply' draft string. "
        "\n\nThen, compute the following metrics for the overall plan: "
        "- 'summary': A short concise textual summary of what the user's day looks like based on the items. "
        "- 'must_do_today': An integer count of items that are 'Now' or 'Today'. "
        "- 'can_defer': An integer count of items that are 'This Week' or 'Later'. "
        "- 'items': The final augmented list of objects containing 'raw', 'type', 'category', 'urgency', "
        "'effort', 'suggested_slot', and 'suggested_reply'. "
        "\nReturn ONLY this final JSON payload containing 'items', 'summary', 'must_do_today', and 'can_defer'."
    ),
    output_key="DAILY_PLAN",
)


# --- ORCHESTRATION ---

# triage_workflow: A sequential chain that processes the inbox items through the agents.
triage_workflow = SequentialAgent(
    name="triage_workflow",
    description="Runs the inbox segmentation, item triage, and daily plan generation sequentially.",
    sub_agents=[inbox_segmenter, item_triage_agent, planner_agent],
)


# root_agent: The primary entry point. It manages state initialization via tools
# and then invokes the core triage workflow.
root_agent = Agent(
    name="attention_triage_root",
    on_model_error_callback=on_model_error,
    model=model_instance,
    description="Entry point for attention triage and micro-planning.",
    instruction=(
        "You receive an input payload with `inbox_text`. "
        "1. Call the `collect_inbox` tool with the full `inbox_text` to store it in state. "
        "2. Optionally, if the user provides preference info in a separate message, call `set_user_preference`. "
        "3. Wait for the tools to finish, then hand off work to the `triage_workflow` SequentialAgent. "
        "4. Output the final `DAILY_PLAN` structure (the JSON returned by planner_agent) completely as your "
        "final response. Do not add conversational wrappers; present the final plan clearly."
    ),
    tools=[collect_inbox, set_user_preference],
    sub_agents=[triage_workflow],
)
