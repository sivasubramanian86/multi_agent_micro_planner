# Attention Strategy AI Agent
An intelligent agentic dashboard for focus, prioritization, and deep work scheduling, built with Google Gen AI ADK.

## Architecture & Models

This project uses a decoupled architecture on Google Cloud Run:
- **attention-triage-agent**: The ADK backend API running `root_agent` and `triage_workflow`.
- **attention-triage-ui**: A custom Nginx-served Vanilla JS/CSS frontend that proxies requests to the backend.

### Model Configuration (Gen AI APAC 2026)
Due to rate limits in hackathon environments, the backend employs a robust fallback strategy:
- **Primary**: `gemini-2.5-flash` (cutting-edge, high performance)
- **Fallbacks**: `gemini-2.5-flash-lite`, `gemini-2.0-flash-001`

When `gemini-2.5-flash` inevitably hits its quota limit (429 Rate Limit Exceeded), the `FallbackGemini` logic automatically downgrades to the ultra-reliable fallback models without breaking the user experience.

## Usage
1. Set `MODEL="gemini-2.5-flash"` in your `.env` file.
2. Deploy backend: `cd attention_triage_agent && adk deploy cloud_run . --project <PROJECT> --region <REGION> --service_name attention-triage-agent -- --allow-unauthenticated`
3. Deploy frontend: `cd frontend && gcloud run deploy attention-triage-ui --source . --project <PROJECT> --region <REGION> --allow-unauthenticated`
4. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Or venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```

2. Create a `.env` file in the root directory (do not commit this file):
   ```env
   GOOGLE_GENAI_USE_VERTEXAI=1
   GOOGLE_CLOUD_PROJECT=<your-project-id>
   GOOGLE_CLOUD_LOCATION=us-central1
   MODEL="gemini-2.5-flash"
   ```

## Local Development

You can run the agent locally using the ADK UI or API.

## Deployment to Cloud Run

Deploy the agent to Cloud Run using the `adk` CLI tool. Make sure you are authenticated with Google Cloud (`gcloud auth login` and `gcloud config set project <your-project-id>`).

```bash
uvx --from google-adk==1.27.2 \
  adk deploy cloud_run \
  --project=$PROJECT_ID \
  --region=<your-region> \
  --service_name=attention-triage-agent \
  --with_ui \
  . \
  -- \
  --labels=dev-tutorial=genai-apac \
  --service-account=$SERVICE_ACCOUNT
```

## Example Usage

Once deployed (or running locally), you can open the Cloud Run URL directly in your browser to interact with the **Production Web UI**!

You can also send HTTP POST requests to the API service programmatically. Note that ADK requires you to initialize a session first:

**1) Create a Session:**
```bash
curl -X POST https://<your-cloud-run-url>/apps/attention_triage_agent/users/test-user/sessions/test-session-123 \
  -H "Content-Type: application/json" \
  -d '{}'
```

**2) Run the Agent:**
```bash
curl -X POST https://<your-cloud-run-url>/run \
  -H "Content-Type: application/json" \
  -d '{
    "appName": "attention_triage_agent",
    "userId": "test-user",
    "sessionId": "test-session-123",
    "new_message": {
      "parts": [{"text": "1) Email from HR about policy update...\n2) WhatsApp: Mom asking about tickets\n3) Slack: urgent bug in prod\n4) Newsletter about AI"}]
    }
  }'
```

The service will return a JSON plan with triaged items, a summary, and counts of items to do today vs. defer.
