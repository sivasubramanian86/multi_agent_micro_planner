import os
from google import genai
from dotenv import load_dotenv

# Load environment variables from the parent directory
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# Ensure Vertex AI configuration is preferred
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "1"
os.environ["GOOGLE_CLOUD_PROJECT"] = os.environ.get("GOOGLE_CLOUD_PROJECT", "genai-apac-2026-491004")
os.environ["GOOGLE_CLOUD_LOCATION"] = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

client = genai.Client()
print(f"Listing available Gemini models in {os.environ['GOOGLE_CLOUD_LOCATION']} for project {os.environ['GOOGLE_CLOUD_PROJECT']}...\n")
try:
    models = client.models.list()
    for m in models:
        if "gemini" in m.name:
            print("- " + m.name)
except Exception as e:
    print("Error listing models:", e)
