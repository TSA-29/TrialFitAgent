# DeskPilot - Vercel-Friendly Assistant

DeskPilot is a conversational assistant with mock productivity tools (email, calendar, travel, music, Notion).

This repo is now structured for Vercel:
- Static frontend: `index.html`
- Python serverless API: `api/index.py`

## Features

- Tool-calling assistant using your existing `agent.py` tools
- Stateless serverless chat endpoint (`/api/chat`)
- Browser-side multi-thread chat history (localStorage sidebar)
- "Thinking" effect in UI with animated assistant state + tool step cards
- Health endpoint (`/api/health`)

## Requirements

- Python 3.10+
- `STEP_API_KEY` set in environment variables

## Local Run

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Set API key:

```bash
# PowerShell
$env:STEP_API_KEY="your_key_here"
```

3. Run local API:

```bash
python api/index.py
```

4. Open `index.html` (or serve it with any static server) and use the chat UI.

## Deploy to Vercel

1. Import this repo into Vercel.
2. Vercel will read `vercel.json` automatically.
3. In Vercel Project Settings -> Environment Variables, set:
   - `STEP_API_KEY` = your key
4. Deploy.

No custom build/start command is needed because `vercel.json` defines routing/build behavior.

## API Contract

- `POST /api/chat`
  - Request body:

```json
{
  "prompt": "Draft an email to Alex about meeting reschedule",
  "history": [
    {"role": "user", "content": "..."}, 
    {"role": "assistant", "content": "..."}
  ]
}
```

  - Response body:

```json
{
  "reply": "Assistant response",
  "history": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}],
  "tool_events": []
}
```

- `GET /api/health`
  - Returns `{ "status": "ok" }`

## Notes

- Tool data is still mock/in-memory and resets with cold starts/redeploys.
- If `STEP_API_KEY` is missing, `/api/chat` returns a startup error.
