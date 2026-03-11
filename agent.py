import json
import os
import random
import string
from datetime import datetime, timedelta

from openai import OpenAI

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

MODEL = "step-3.5-flash"
DEBUG = os.environ.get("BULKBOT_DEBUG", "").lower() in {"1", "true", "yes", "on"}
SYSTEM_PROMPT = (
    "You are DeskPilot, a personal assistant AI. "
    "Use tools whenever the user asks for email drafting, calendar scheduling, "
    "trip booking, music app actions, or Notion editing. "
    "All tools are mock and simulated but should be treated as operational. "
    "Never claim an action happened without calling the matching tool first. "
    "If key details are missing, ask one concise follow-up question. "
    "Keep answers concise and practical."
)


def build_client():
    api_key = os.environ.get("STEP_API_KEY")
    if not api_key:
        raise RuntimeError("Missing STEP_API_KEY. Set it in your environment before running.")
    return OpenAI(api_key=api_key, base_url="https://api.stepfun.com/v1")


MOCK_DB = {
    "emails": [],
    "appointments": [],
    "trips": [],
    "notion_pages": {},
    "music": {
        "app_open": False,
        "app_name": "",
        "state": "stopped",
        "now_playing": "",
        "queue": [],
    },
}

MOCK_MUSIC_LIBRARY = [
    {"title": "Midnight Drive", "artist": "Nova Lane"},
    {"title": "City of Echoes", "artist": "Luna Arcade"},
    {"title": "Afterglow", "artist": "Jasper Vale"},
    {"title": "Neon Skyline", "artist": "The Static Club"},
    {"title": "Paper Planes", "artist": "Ari Bloom"},
]


def _new_id(prefix):
    suffix = "".join(random.choices(string.digits, k=6))
    return f"{prefix}-{suffix}"


def _parse_iso_datetime(value, field_name):
    try:
        return datetime.fromisoformat(value), None
    except ValueError:
        return None, f"Invalid {field_name}. Use ISO format like 2026-03-15T14:00:00."


def draft_email(to, subject, body, cc="", bcc="", priority="normal", send_time_iso=""):
    if not to.strip():
        return json.dumps({"status": "error", "message": "Recipient is required."})
    if not subject.strip():
        return json.dumps({"status": "error", "message": "Subject is required."})

    send_time = ""
    if send_time_iso:
        send_dt, err = _parse_iso_datetime(send_time_iso, "send_time_iso")
        if err:
            return json.dumps({"status": "error", "message": err})
        send_time = send_dt.isoformat()

    email = {
        "email_id": _new_id("EML"),
        "to": to,
        "cc": cc,
        "bcc": bcc,
        "subject": subject,
        "body": body,
        "priority": str(priority or "normal").lower(),
        "scheduled_send_time": send_time,
        "status": "drafted",
        "created_at": datetime.now().isoformat(),
        "mock": True,
    }
    MOCK_DB["emails"].append(email)

    return json.dumps(
        {
            "status": "success",
            "message": "Mock email draft created.",
            "email": email,
        }
    )


def list_email_drafts(limit=10, recipient_filter=""):
    try:
        limit = max(1, min(int(limit), 100))
    except (TypeError, ValueError):
        limit = 10

    items = MOCK_DB["emails"]
    if recipient_filter:
        needle = recipient_filter.lower()
        items = [x for x in items if needle in x["to"].lower()]

    return json.dumps(
        {
            "status": "success",
            "count": min(len(items), limit),
            "emails": items[-limit:],
        }
    )


def create_calendar_appointment(
    title,
    start_iso,
    end_iso,
    attendees="",
    location="",
    notes="",
    reminder_minutes=15,
):
    if not title.strip():
        return json.dumps({"status": "error", "message": "Appointment title is required."})

    start_dt, start_err = _parse_iso_datetime(start_iso, "start_iso")
    if start_err:
        return json.dumps({"status": "error", "message": start_err})
    end_dt, end_err = _parse_iso_datetime(end_iso, "end_iso")
    if end_err:
        return json.dumps({"status": "error", "message": end_err})

    if end_dt <= start_dt:
        return json.dumps({"status": "error", "message": "end_iso must be later than start_iso."})

    try:
        reminder = int(reminder_minutes)
    except (TypeError, ValueError):
        reminder = 15

    attendee_list = [p.strip() for p in str(attendees).replace(";", ",").split(",") if p.strip()]

    appointment = {
        "appointment_id": _new_id("CAL"),
        "title": title,
        "start": start_dt.isoformat(),
        "end": end_dt.isoformat(),
        "attendees": attendee_list,
        "location": location,
        "notes": notes,
        "reminder_minutes": reminder,
        "status": "confirmed",
        "created_at": datetime.now().isoformat(),
        "mock": True,
    }
    MOCK_DB["appointments"].append(appointment)

    return json.dumps(
        {
            "status": "success",
            "message": "Mock calendar appointment created.",
            "appointment": appointment,
        }
    )


def list_calendar_appointments(start_iso="", end_iso="", limit=10):
    try:
        limit = max(1, min(int(limit), 100))
    except (TypeError, ValueError):
        limit = 10

    if start_iso:
        start_dt, err = _parse_iso_datetime(start_iso, "start_iso")
        if err:
            return json.dumps({"status": "error", "message": err})
    else:
        start_dt = datetime.now() - timedelta(days=30)

    if end_iso:
        end_dt, err = _parse_iso_datetime(end_iso, "end_iso")
        if err:
            return json.dumps({"status": "error", "message": err})
    else:
        end_dt = datetime.now() + timedelta(days=90)

    if end_dt <= start_dt:
        return json.dumps({"status": "error", "message": "end_iso must be later than start_iso."})

    filtered = []
    for item in MOCK_DB["appointments"]:
        item_start = datetime.fromisoformat(item["start"])
        if start_dt <= item_start <= end_dt:
            filtered.append(item)

    filtered.sort(key=lambda x: x["start"])

    return json.dumps(
        {
            "status": "success",
            "count": min(len(filtered), limit),
            "appointments": filtered[:limit],
        }
    )


def book_trip(
    traveler_name,
    origin,
    destination,
    depart_date,
    return_date="",
    transport="flight",
    hotel_required=True,
    budget_usd=0,
):
    if not traveler_name.strip():
        return json.dumps({"status": "error", "message": "traveler_name is required."})
    if not origin.strip() or not destination.strip():
        return json.dumps({"status": "error", "message": "origin and destination are required."})

    try:
        depart_dt = datetime.strptime(depart_date, "%Y-%m-%d")
    except ValueError:
        return json.dumps({"status": "error", "message": "depart_date must be YYYY-MM-DD."})

    if return_date:
        try:
            return_dt = datetime.strptime(return_date, "%Y-%m-%d")
        except ValueError:
            return json.dumps({"status": "error", "message": "return_date must be YYYY-MM-DD."})
        if return_dt < depart_dt:
            return json.dumps({"status": "error", "message": "return_date must be on/after depart_date."})
        return_iso = return_dt.date().isoformat()
    else:
        return_iso = ""

    trip = {
        "trip_id": _new_id("TRP"),
        "traveler_name": traveler_name,
        "origin": origin,
        "destination": destination,
        "depart_date": depart_dt.date().isoformat(),
        "return_date": return_iso,
        "transport": str(transport or "flight").lower(),
        "hotel_required": bool(hotel_required),
        "budget_usd": float(budget_usd or 0),
        "booking_reference": _new_id("BK"),
        "status": "booked",
        "created_at": datetime.now().isoformat(),
        "mock": True,
    }
    MOCK_DB["trips"].append(trip)

    return json.dumps(
        {
            "status": "success",
            "message": "Mock trip booked.",
            "trip": trip,
        }
    )


def list_trips(limit=10):
    try:
        limit = max(1, min(int(limit), 100))
    except (TypeError, ValueError):
        limit = 10

    return json.dumps(
        {
            "status": "success",
            "count": min(len(MOCK_DB["trips"]), limit),
            "trips": MOCK_DB["trips"][-limit:],
        }
    )


def launch_music_app(app_name="Spotify", action="open", query=""):
    app = str(app_name or "Spotify").strip()
    action = str(action or "open").strip().lower()
    music = MOCK_DB["music"]

    if action == "open":
        music["app_open"] = True
        music["app_name"] = app
        message = f"{app} launched (mock)."
    elif action == "close":
        music["app_open"] = False
        music["state"] = "stopped"
        music["now_playing"] = ""
        message = f"{music.get('app_name') or app} closed (mock)."
    elif action == "search":
        needle = query.lower().strip()
        matches = [
            t
            for t in MOCK_MUSIC_LIBRARY
            if needle in t["title"].lower() or needle in t["artist"].lower()
        ]
        return json.dumps(
            {
                "status": "success",
                "action": "search",
                "query": query,
                "matches": matches[:5],
                "mock": True,
            }
        )
    elif action in {"play", "pause", "next"}:
        if not music["app_open"]:
            music["app_open"] = True
            music["app_name"] = app

        if action == "play":
            if query.strip():
                track = {"title": query.strip().title(), "artist": "Mock Artist"}
            else:
                track = random.choice(MOCK_MUSIC_LIBRARY)
            music["now_playing"] = f"{track['title']} - {track['artist']}"
            music["state"] = "playing"
            message = f"Now playing: {music['now_playing']} (mock)."
        elif action == "pause":
            music["state"] = "paused"
            message = "Playback paused (mock)."
        else:
            track = random.choice(MOCK_MUSIC_LIBRARY)
            music["now_playing"] = f"{track['title']} - {track['artist']}"
            music["state"] = "playing"
            message = f"Skipped to next: {music['now_playing']} (mock)."
    else:
        return json.dumps(
            {
                "status": "error",
                "message": "Invalid action. Use open, close, search, play, pause, or next.",
            }
        )

    return json.dumps(
        {
            "status": "success",
            "action": action,
            "message": message,
            "music_state": music,
            "mock": True,
        }
    )


def notion_edit_page(page_title, operation, content="", block_type="paragraph", task_done=False):
    title = str(page_title or "").strip()
    op = str(operation or "").strip().lower()
    if not title:
        return json.dumps({"status": "error", "message": "page_title is required."})
    if not op:
        return json.dumps({"status": "error", "message": "operation is required."})

    pages = MOCK_DB["notion_pages"]
    page = pages.get(title)

    if op == "create_page":
        if page:
            return json.dumps({"status": "error", "message": f"Page '{title}' already exists."})
        page = {
            "title": title,
            "blocks": [],
            "updated_at": datetime.now().isoformat(),
            "mock": True,
        }
        pages[title] = page
    elif op == "read_page":
        if not page:
            return json.dumps({"status": "error", "message": f"Page '{title}' does not exist."})
    elif op == "replace_page":
        if not page:
            page = {"title": title, "blocks": [], "mock": True}
            pages[title] = page
        page["blocks"] = [{"type": "paragraph", "content": content}]
        page["updated_at"] = datetime.now().isoformat()
    elif op == "append_text":
        if not page:
            page = {"title": title, "blocks": [], "mock": True}
            pages[title] = page
        page["blocks"].append(
            {
                "type": str(block_type or "paragraph").lower(),
                "content": content,
            }
        )
        page["updated_at"] = datetime.now().isoformat()
    elif op == "add_todo":
        if not page:
            page = {"title": title, "blocks": [], "mock": True}
            pages[title] = page
        page["blocks"].append(
            {
                "type": "todo",
                "content": content,
                "done": bool(task_done),
            }
        )
        page["updated_at"] = datetime.now().isoformat()
    else:
        return json.dumps(
            {
                "status": "error",
                "message": "Invalid operation. Use create_page, read_page, replace_page, append_text, or add_todo.",
            }
        )

    return json.dumps(
        {
            "status": "success",
            "message": f"Notion mock operation '{op}' completed.",
            "page": pages[title],
        }
    )


def list_notion_pages(limit=20):
    try:
        limit = max(1, min(int(limit), 100))
    except (TypeError, ValueError):
        limit = 20

    pages = list(MOCK_DB["notion_pages"].values())
    pages.sort(key=lambda p: p.get("updated_at", ""), reverse=True)

    return json.dumps(
        {
            "status": "success",
            "count": min(len(pages), limit),
            "pages": pages[:limit],
        }
    )


available_functions = {
    "draft_email": draft_email,
    "list_email_drafts": list_email_drafts,
    "create_calendar_appointment": create_calendar_appointment,
    "list_calendar_appointments": list_calendar_appointments,
    "book_trip": book_trip,
    "list_trips": list_trips,
    "launch_music_app": launch_music_app,
    "notion_edit_page": notion_edit_page,
    "list_notion_pages": list_notion_pages,
}

tools = [
    {
        "type": "function",
        "function": {
            "name": "draft_email",
            "description": "Create a mock email draft.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                    "cc": {"type": "string"},
                    "bcc": {"type": "string"},
                    "priority": {"type": "string", "description": "low, normal, high"},
                    "send_time_iso": {
                        "type": "string",
                        "description": "Optional scheduled send time in ISO format.",
                    },
                },
                "required": ["to", "subject", "body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_email_drafts",
            "description": "List previously created mock email drafts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer"},
                    "recipient_filter": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_calendar_appointment",
            "description": "Create a mock calendar appointment.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "start_iso": {"type": "string"},
                    "end_iso": {"type": "string"},
                    "attendees": {
                        "type": "string",
                        "description": "Comma/semicolon separated attendee list.",
                    },
                    "location": {"type": "string"},
                    "notes": {"type": "string"},
                    "reminder_minutes": {"type": "integer"},
                },
                "required": ["title", "start_iso", "end_iso"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_calendar_appointments",
            "description": "List mock calendar appointments in a date window.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_iso": {"type": "string"},
                    "end_iso": {"type": "string"},
                    "limit": {"type": "integer"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_trip",
            "description": "Book a mock trip with generated confirmation details.",
            "parameters": {
                "type": "object",
                "properties": {
                    "traveler_name": {"type": "string"},
                    "origin": {"type": "string"},
                    "destination": {"type": "string"},
                    "depart_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "return_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "transport": {"type": "string", "description": "flight, train, car"},
                    "hotel_required": {"type": "boolean"},
                    "budget_usd": {"type": "number"},
                },
                "required": ["traveler_name", "origin", "destination", "depart_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_trips",
            "description": "List mock booked trips.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "launch_music_app",
            "description": "Mock launch and control of a music app.",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "Spotify, Apple Music, etc."},
                    "action": {"type": "string", "description": "open, close, search, play, pause, next"},
                    "query": {"type": "string", "description": "Optional search text or track name."},
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "notion_edit_page",
            "description": "Mock Notion page editor.",
            "parameters": {
                "type": "object",
                "properties": {
                    "page_title": {"type": "string"},
                    "operation": {
                        "type": "string",
                        "description": "create_page, read_page, replace_page, append_text, add_todo",
                    },
                    "content": {"type": "string"},
                    "block_type": {"type": "string", "description": "paragraph, heading, bullet"},
                    "task_done": {"type": "boolean"},
                },
                "required": ["page_title", "operation"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_notion_pages",
            "description": "List mock Notion pages.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer"},
                },
            },
        },
    },
]


def run_agent_turn(client, messages, user_prompt):
    messages.append({"role": "user", "content": user_prompt})

    while True:
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.4,
        )
        response_message = response.choices[0].message

        if response_message.tool_calls:
            messages.append(response_message)
            for tool_call in response_message.tool_calls:
                func_name = tool_call.function.name
                func_args = json.loads(tool_call.function.arguments)
                if DEBUG:
                    print(f"--> [System]: Executing tool '{func_name}'")

                result = available_functions[func_name](**func_args)
                messages.append(
                    {
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": func_name,
                        "content": result,
                    }
                )
            continue

        messages.append(response_message)
        return response_message.content or ""


def chat_loop():
    client = build_client()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    print("DeskPilot is ready. Type 'exit' or 'quit' to stop.")
    while True:
        user_prompt = input("\nYou: ").strip()
        if not user_prompt:
            continue
        if user_prompt.lower() in {"exit", "quit"}:
            print("DeskPilot: Session closed.")
            break

        answer = run_agent_turn(client, messages, user_prompt)
        print(f"DeskPilot: {answer}")


if __name__ == "__main__":
    chat_loop()
