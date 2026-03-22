import asyncio
import os
import sys

# Ensure the module can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from attention_triage_agent.agent import root_agent
from google.adk.runners import AgentRunner
from google.adk.app import App

async def test_root_agent():
    print("Starting test...")
    inbox = (
        "1) Email from HR: Need your self-evaluation form completed by EOD tomorrow.\n"
        "2) Slack from John: Hey, critical bug in the payment gateway, production is failing for 5% of users. Can you look NOW?"
    )
    
    app = App(name="attention_triage_agent", root_agent=root_agent)
    runner = AgentRunner(app)
    
    response_text = ""
    async for event in runner.run_async(user_id="test-user", session_id="test-session-local", new_message=inbox):
        if hasattr(event, "content") and event.content:
            for part in event.content.parts:
                response_text += part.text or ""
                
    print("\nTest Output:\n", response_text)
    
if __name__ == "__main__":
    asyncio.run(test_root_agent())
