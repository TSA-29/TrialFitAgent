# DeskPilot - Mock Personal Assistant

DeskPilot is a conversational AI assistant that simulates real productivity workflows using mock data.

## Capabilities

- Draft emails
- Create and list calendar appointments
- Book and list trips
- Launch/control a mock music app session
- Edit and read mock Notion pages

All integrations are simulated in-memory so the experience feels real without requiring external accounts.

## Setup

### Prerequisites

- Python 3.8+
- `STEP_API_KEY` set in your environment (for the model API)

### Install

```bash
pip install -r requirements.txt
```

### Run Web UI

```bash
.\.venv\Scripts\python.exe -m chainlit run ui.py -w
```

Default login credentials (for history support):
- Username: `deskpilot`
- Password: `deskpilot`

You can override them with environment variables:
- `DESKPILOT_LOGIN_USERNAME`
- `DESKPILOT_LOGIN_PASSWORD`

### Run CLI

```bash
python agent.py
```

## Deploy on Render

This repo includes `render.yaml` for one-click Render setup.

1. Create a new **Web Service** in Render from this repo.
2. Let Render detect `render.yaml`.
3. Set `STEP_API_KEY` in Render environment variables.
4. Deploy.

The service starts with:

```bash
python start_render.py
```

`start_render.py` runs Chainlit with Render-safe host/port and guards against invalid
`DEBUG` values (for example `DEBUG=release`) that can make Chainlit fail at boot.

If you still get a white page, check Render logs for startup errors and confirm:
- `STEP_API_KEY` is set
- Service type is **Web Service** (not Static Site)
- Start command is `python start_render.py`

## Example Prompts

- `Draft an email to alex@company.com about moving tomorrow's meeting to 4 PM.`
- `Create a calendar appointment called Product Sync on 2026-03-12 from 14:00 to 15:00 with sam@company.com.`
- `Book a trip for Jamie from Shanghai to Tokyo departing 2026-04-20 returning 2026-04-24.`
- `Open Spotify and play midnight drive.`
- `Create a Notion page called Q2 Plan and add a todo: finalize roadmap.`

## Project Structure

- `agent.py` - core assistant tools and tool-calling loop
- `ui.py` - Chainlit chat UI with tool execution visualization
- `requirements.txt` - dependencies
- `.chainlit/config.toml` - Chainlit settings

## Notes

- Tool actions are mock-only and stored in process memory.
- Restarting the app resets all mock emails, appointments, trips, and Notion pages.
- Chat history is persisted in `.files/deskpilot_history.json` and shown in the left sidebar.
- A visible running/thinking indicator appears during model and tool execution.
