import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
import ctypes
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request
import webbrowser
from openai import OpenAI

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, will use system env vars

# --- 1. Setup Stepfun Client ---
MODEL = "step-3.5-flash"
DEBUG = os.environ.get("BULKBOT_DEBUG", "").lower() in {"1", "true", "yes", "on"}
SYSTEM_PROMPT = (
    "You are BulkBot, an expert fitness AI. "
    "You MUST use your tools for any math or food data. "
    "If the user asks to create or save a markdown file, use write_markdown_file. "
    "If the user asks to draft an email in Outlook, use create_outlook_draft and never auto-send. "
    "If the user asks to add a calendar event in Outlook, use create_outlook_calendar_event. "
    "If the user asks to view calendar events, use list_outlook_calendar_events. "
    "For Apple Music requests, use Apple Music tools to search, open, and control playback. "
    "For Apple Music 'play now' requests, prefer auto preview mode so playback starts without extra clicks. "
    "Never guess calories or macros. "
    "Keep responses eye-friendly and concise by default. "
    "Unless the user asks for depth, use this format with short lines: "
    "Verdict: one sentence. "
    "Why: 2-4 bullet points max. "
    "Next step: 1 practical action. "
    "Limit total length to about 80-140 words. "
    "Avoid long paragraphs."
)


def build_client():
    api_key = os.environ.get("STEP_API_KEY")
    if not api_key:
        raise RuntimeError("Missing STEP_API_KEY. Set it in your environment before running.")
    return OpenAI(api_key=api_key, base_url="https://api.stepfun.com/v1")


# --- 2. Define Deterministic Python Tools ---
def calculate_tdee_macros(age, weight_kg, height_cm):
    """Calculates clean bulk macros using the Mifflin-St Jeor Equation."""
    bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) + 5
    tdee = bmr * 1.55 # Assuming moderate activity (3-5 days/week)
    bulk_calories = tdee + 300 # 300 surplus for clean bulk
    
    protein_g = weight_kg * 2.2 
    fat_g = (bulk_calories * 0.25) / 9 
    carbs_g = (bulk_calories - (protein_g * 4) - (fat_g * 9)) / 4
    
    return json.dumps({
        "status": "success",
        "target_calories": int(bulk_calories),
        "macros": {"protein_g": int(protein_g), "fats_g": int(fat_g), "carbs_g": int(carbs_g)}
    })

def lookup_food_macros(food_name, grams):
    """Mocks a database lookup for exact food macronutrients."""
    # A real agent would hit a USDA API or database here
    database = {
        "chicken breast": {"protein": 0.31, "carbs": 0.0, "fat": 0.036, "cals": 1.65},
        "white rice": {"protein": 0.027, "carbs": 0.28, "fat": 0.003, "cals": 1.30},
        "salmon": {"protein": 0.20, "carbs": 0.0, "fat": 0.13, "cals": 2.08}
    }
    
    food_key = next((key for key in database.keys() if key in food_name.lower()), None)
    
    if food_key:
        data = database[food_key]
        return json.dumps({
            "food": food_key,
            "amount_grams": grams,
            "calories": int(data["cals"] * grams),
            "protein_g": int(data["protein"] * grams),
            "carbs_g": int(data["carbs"] * grams),
            "fat_g": int(data["fat"] * grams)
        })
    return json.dumps({"error": f"Food '{food_name}' not found in database."})


def write_markdown_file(filename, content):
    """Writes markdown content to a local file in the project directory."""
    file_path = Path(filename)
    if file_path.suffix.lower() != ".md":
        file_path = file_path.with_suffix(".md")

    if file_path.is_absolute():
        return json.dumps({"status": "error", "message": "Use a relative path only."})

    target_path = (Path.cwd() / file_path).resolve()
    project_root = Path.cwd().resolve()
    if project_root not in target_path.parents and target_path != project_root:
        return json.dumps({"status": "error", "message": "Path escapes project directory."})

    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(content, encoding="utf-8")
    return json.dumps({
        "status": "success",
        "message": "Markdown file written.",
        "path": str(file_path).replace("\\", "/"),
    })


def create_outlook_draft(to, subject, body, cc="", bcc="", display=True):
    """Creates an Outlook email draft on the local machine. Never sends automatically."""
    try:
        import win32com.client as win32
    except ImportError:
        return json.dumps({
            "status": "error",
            "message": "pywin32 is not installed. Run: pip install pywin32",
        })

    try:
        outlook = win32.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)  # 0 = Mail item
        mail.To = to
        mail.Subject = subject
        mail.Body = body
        if cc:
            mail.CC = cc
        if bcc:
            mail.BCC = bcc

        if display:
            mail.Display()
            action = "draft_opened"
        else:
            mail.Save()
            action = "draft_saved"

        return json.dumps({
            "status": "success",
            "action": action,
            "to": to,
            "subject": subject,
        })
    except Exception as exc:
        return json.dumps({
            "status": "error",
            "message": f"Failed to create Outlook draft: {exc}",
        })


def create_outlook_calendar_event(
    subject,
    start_iso,
    end_iso,
    location="",
    body="",
    busy_status="busy",
    reminder_minutes=15,
    all_day=False,
    display=True
):
    """Creates an Outlook calendar event on the local machine."""
    try:
        import win32com.client as win32
    except ImportError:
        return json.dumps({
            "status": "error",
            "message": "pywin32 is not installed. Run: pip install pywin32",
        })

    status_map = {
        "free": 0,
        "tentative": 1,
        "busy": 2,
        "oof": 3,
        "working_elsewhere": 4,
    }
    busy_code = status_map.get(str(busy_status).lower(), 2)

    try:
        start_dt = datetime.fromisoformat(start_iso)
        end_dt = datetime.fromisoformat(end_iso)
    except ValueError:
        return json.dumps({
            "status": "error",
            "message": "Invalid datetime format. Use ISO format, e.g. 2026-03-06T14:00:00",
        })

    if end_dt <= start_dt:
        return json.dumps({
            "status": "error",
            "message": "end_iso must be later than start_iso.",
        })

    try:
        outlook = win32.Dispatch("Outlook.Application")
        appointment = outlook.CreateItem(1)  # 1 = olAppointmentItem
        appointment.Subject = subject
        appointment.Start = start_dt.strftime("%Y-%m-%d %H:%M")
        appointment.End = end_dt.strftime("%Y-%m-%d %H:%M")
        appointment.Location = location
        appointment.Body = body
        appointment.BusyStatus = busy_code
        appointment.AllDayEvent = bool(all_day)

        reminder_minutes = int(reminder_minutes)
        if reminder_minutes >= 0:
            appointment.ReminderSet = True
            appointment.ReminderMinutesBeforeStart = reminder_minutes
        else:
            appointment.ReminderSet = False

        if display:
            appointment.Display()
            action = "event_opened"
        else:
            appointment.Save()
            action = "event_saved"

        return json.dumps({
            "status": "success",
            "action": action,
            "subject": subject,
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat(),
        })
    except Exception as exc:
        return json.dumps({
            "status": "error",
            "message": f"Failed to create Outlook calendar event: {exc}",
        })


def list_outlook_calendar_events(start_iso="", end_iso="", max_items=10, include_body=False):
    """Lists Outlook calendar events from the local machine in a date window."""
    try:
        import win32com.client as win32
    except ImportError:
        return json.dumps({
            "status": "error",
            "message": "pywin32 is not installed. Run: pip install pywin32",
        })

    try:
        start_dt = datetime.fromisoformat(start_iso) if start_iso else None
        end_dt = datetime.fromisoformat(end_iso) if end_iso else None
    except ValueError:
        return json.dumps({
            "status": "error",
            "message": "Invalid datetime format. Use ISO format, e.g. 2026-03-06T14:00:00",
        })

    if start_dt and end_dt and end_dt <= start_dt:
        return json.dumps({
            "status": "error",
            "message": "end_iso must be later than start_iso.",
        })

    # Keep default reads bounded so recurring events don't explode the result set.
    if not start_dt and not end_dt:
        start_dt = datetime.now()
        end_dt = start_dt + timedelta(days=30)
    elif start_dt and not end_dt:
        end_dt = start_dt + timedelta(days=30)
    elif end_dt and not start_dt:
        start_dt = end_dt - timedelta(days=30)

    try:
        max_items = max(1, min(int(max_items), 100))
    except (TypeError, ValueError):
        max_items = 10

    def outlook_datetime(dt):
        return dt.strftime("%m/%d/%Y %I:%M %p")

    def to_iso(value):
        if hasattr(value, "strftime"):
            return value.strftime("%Y-%m-%dT%H:%M:%S")
        return str(value)

    try:
        outlook = win32.Dispatch("Outlook.Application")
        namespace = outlook.GetNamespace("MAPI")
        calendar_folder = namespace.GetDefaultFolder(9)  # 9 = Calendar
        items = calendar_folder.Items
        items.IncludeRecurrences = True
        items.Sort("[Start]")

        restrictions = [
            f"[End] >= '{outlook_datetime(start_dt)}'",
            f"[Start] <= '{outlook_datetime(end_dt)}'",
        ]
        items = items.Restrict(" AND ".join(restrictions))

        total = items.Count
        results = []
        for idx in range(1, min(total, max_items) + 1):
            item = items.Item(idx)
            event = {
                "subject": str(getattr(item, "Subject", "") or ""),
                "start": to_iso(getattr(item, "Start", "")),
                "end": to_iso(getattr(item, "End", "")),
                "location": str(getattr(item, "Location", "") or ""),
                "all_day": bool(getattr(item, "AllDayEvent", False)),
            }
            if include_body:
                body = str(getattr(item, "Body", "") or "")
                event["body"] = body[:500] + ("..." if len(body) > 500 else "")
            results.append(event)

        return json.dumps({
            "status": "success",
            "range_start": start_dt.isoformat(),
            "range_end": end_dt.isoformat(),
            "returned": len(results),
            "total_in_range": int(total),
            "events": results,
        })
    except Exception as exc:
        return json.dumps({
            "status": "error",
            "message": f"Failed to list Outlook calendar events: {exc}",
        })


def _apple_music_search_api(query, country_code="us", limit=5):
    """Search Apple Music/iTunes catalog and return normalized song hits."""
    try:
        limit = max(1, min(int(limit), 25))
    except (TypeError, ValueError):
        limit = 5

    country = (country_code or "us").strip().lower()[:2] or "us"
    params = urllib_parse.urlencode({
        "term": query,
        "media": "music",
        "entity": "song",
        "country": country,
        "limit": limit,
    })
    url = f"https://itunes.apple.com/search?{params}"
    req = urllib_request.Request(url, headers={"User-Agent": "BulkBot/1.0"})

    try:
        with urllib_request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib_error.HTTPError as exc:
        return None, json.dumps({
            "status": "error",
            "message": f"Apple Music search failed with HTTP {exc.code}",
        })
    except Exception as exc:
        return None, json.dumps({
            "status": "error",
            "message": f"Apple Music search request failed: {exc}",
        })

    results = []
    for item in payload.get("results", []):
        results.append({
            "track_name": item.get("trackName", ""),
            "artist_name": item.get("artistName", ""),
            "album_name": item.get("collectionName", ""),
            "track_url": item.get("trackViewUrl", ""),
            "preview_url": item.get("previewUrl", ""),
        })
    return results, None


def _open_url(url):
    """Open URL with system default handler."""
    try:
        if os.name == "nt":
            os.startfile(url)  # type: ignore[attr-defined]
            return True
    except Exception:
        pass
    return bool(webbrowser.open(url))


def search_apple_music(query, country_code="us", limit=5, open_search_page=False):
    """Searches Apple Music and optionally opens the Apple Music search page."""
    results, err = _apple_music_search_api(query=query, country_code=country_code, limit=limit)
    if err:
        return err

    country = (country_code or "us").strip().lower()[:2] or "us"
    search_url = f"https://music.apple.com/{country}/search?term={urllib_parse.quote_plus(query)}"
    opened = _open_url(search_url) if open_search_page else False
    return json.dumps({
        "status": "success",
        "query": query,
        "search_url": search_url,
        "opened_search_page": opened,
        "count": len(results),
        "results": results,
    })


def play_apple_music(query, country_code="us", play_mode="preview_auto"):
    """Finds the top Apple Music result and opens preview or full track page."""
    results, err = _apple_music_search_api(query=query, country_code=country_code, limit=1)
    if err:
        return err
    if not results:
        return json.dumps({
            "status": "error",
            "message": f"No Apple Music results found for '{query}'.",
        })

    top = results[0]
    mode = str(play_mode or "preview_auto").strip().lower()
    if mode == "full_track":
        url = top.get("track_url", "")
    else:
        # Default behavior favors no-click playback.
        url = top.get("preview_url", "") or top.get("track_url", "")

    if not url:
        return json.dumps({
            "status": "error",
            "message": "Top result does not include a playable URL/preview.",
        })

    opened = _open_url(url)
    sent_play = False
    if opened and mode == "full_track" and os.name == "nt":
        # Give the handler/app a moment to focus, then ask the system player to play.
        time.sleep(1.0)
        sent_play, _ = _send_windows_media_command("play")

    return json.dumps({
        "status": "success",
        "query": query,
        "play_mode": mode,
        "opened": opened,
        "sent_play_command": sent_play,
        "track": top,
        "opened_url": url,
        "note": "preview_auto usually starts immediately; full_track may require Apple Music UI interaction.",
    })


def open_apple_music_url(url):
    """Opens a specific Apple Music URL."""
    if not str(url).startswith("https://music.apple.com/"):
        return json.dumps({
            "status": "error",
            "message": "URL must start with https://music.apple.com/",
        })
    opened = _open_url(url)
    return json.dumps({
        "status": "success",
        "url": url,
        "opened": opened,
    })


def _send_windows_media_command(action):
    """Send explicit Windows media command via WM_APPCOMMAND."""
    if os.name != "nt":
        return False, "Media key control is currently implemented for Windows only."

    cmd_map = {
        "next": 11,
        "previous": 12,
        "stop": 13,
        "play_pause": 14,
        "play": 46,
        "pause": 47,
    }
    cmd = cmd_map.get(str(action).strip().lower())
    if cmd is None:
        return False, "Invalid action. Use: play, pause, play_pause, next, previous, stop."

    WM_APPCOMMAND = 0x0319
    HWND_BROADCAST = 0xFFFF
    lparam = cmd << 16
    ctypes.windll.user32.SendMessageW(HWND_BROADCAST, WM_APPCOMMAND, 0, lparam)
    return True, "Media command sent."


def control_media_playback(action):
    """Controls system media transport keys on Windows."""
    ok, message = _send_windows_media_command(action)
    if not ok:
        return json.dumps({
            "status": "error",
            "message": message,
        })

    return json.dumps({
        "status": "success",
        "action": action,
        "message": message,
    })

available_functions = {
    "calculate_tdee_macros": calculate_tdee_macros,
    "lookup_food_macros": lookup_food_macros,
    "write_markdown_file": write_markdown_file,
    "create_outlook_draft": create_outlook_draft,
    "create_outlook_calendar_event": create_outlook_calendar_event,
    "list_outlook_calendar_events": list_outlook_calendar_events,
    "search_apple_music": search_apple_music,
    "play_apple_music": play_apple_music,
    "open_apple_music_url": open_apple_music_url,
    "control_media_playback": control_media_playback,
}

# --- 3. Define Tool Schemas for the LLM ---
tools = [
    {
        "type": "function",
        "function": {
            "name": "calculate_tdee_macros",
            "description": "Calculates exact daily calorie and macronutrient targets for a lean bulk.",
            "parameters": {
                "type": "object",
                "properties": {
                    "age": {"type": "integer"},
                    "weight_kg": {"type": "number"},
                    "height_cm": {"type": "number"}
                },
                "required": ["age", "weight_kg", "height_cm"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_food_macros",
            "description": "Looks up exact macronutrients for a specific food item and weight.",
            "parameters": {
                "type": "object",
                "properties": {
                    "food_name": {"type": "string", "description": "Name of the food (e.g., chicken breast, white rice)"},
                    "grams": {"type": "number", "description": "Weight of the food in grams"}
                },
                "required": ["food_name", "grams"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_markdown_file",
            "description": "Creates or overwrites a markdown (.md) file in the current project directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Relative file path. Example: notes/today-plan.md"},
                    "content": {"type": "string", "description": "Markdown text to write to the file."}
                },
                "required": ["filename", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_outlook_draft",
            "description": "Creates an email draft in the local Outlook desktop app. Never sends automatically.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient email(s). Separate multiple with semicolons."},
                    "subject": {"type": "string", "description": "Email subject line."},
                    "body": {"type": "string", "description": "Plain text email body."},
                    "cc": {"type": "string", "description": "Optional CC recipients, semicolon-separated."},
                    "bcc": {"type": "string", "description": "Optional BCC recipients, semicolon-separated."},
                    "display": {"type": "boolean", "description": "If true, open draft window. If false, save draft silently."}
                },
                "required": ["to", "subject", "body"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_outlook_calendar_event",
            "description": "Creates an Outlook calendar event in the local Outlook desktop app.",
            "parameters": {
                "type": "object",
                "properties": {
                    "subject": {"type": "string", "description": "Calendar event title."},
                    "start_iso": {"type": "string", "description": "Start datetime in ISO format, e.g. 2026-03-06T14:00:00"},
                    "end_iso": {"type": "string", "description": "End datetime in ISO format, e.g. 2026-03-06T15:00:00"},
                    "location": {"type": "string", "description": "Optional event location."},
                    "body": {"type": "string", "description": "Optional event notes/body."},
                    "busy_status": {"type": "string", "description": "free, tentative, busy, oof, working_elsewhere"},
                    "reminder_minutes": {"type": "integer", "description": "Reminder minutes before start. Use -1 for no reminder."},
                    "all_day": {"type": "boolean", "description": "Set true for an all-day event."},
                    "display": {"type": "boolean", "description": "If true, open event window. If false, save event directly."}
                },
                "required": ["subject", "start_iso", "end_iso"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_outlook_calendar_events",
            "description": "Lists Outlook calendar events in a date range from the local Outlook desktop app.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_iso": {"type": "string", "description": "Optional start datetime in ISO format."},
                    "end_iso": {"type": "string", "description": "Optional end datetime in ISO format."},
                    "max_items": {"type": "integer", "description": "Max events to return (1-100)."},
                    "include_body": {"type": "boolean", "description": "Include event body text (truncated)."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_apple_music",
            "description": "Searches Apple Music catalog and returns matching songs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Song/artist/album search text."},
                    "country_code": {"type": "string", "description": "2-letter storefront, e.g. us, cn, jp."},
                    "limit": {"type": "integer", "description": "Max results to return (1-25)."},
                    "open_search_page": {"type": "boolean", "description": "If true, also open Apple Music search page."}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "play_apple_music",
            "description": "Finds the top Apple Music search result and attempts hands-free playback.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Song/artist to play."},
                    "country_code": {"type": "string", "description": "2-letter storefront, e.g. us, cn, jp."},
                    "play_mode": {"type": "string", "description": "preview_auto (default, no-click preview) or full_track (opens track page)."}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_apple_music_url",
            "description": "Opens a specific Apple Music URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "A full Apple Music URL beginning with https://music.apple.com/"}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "control_media_playback",
            "description": "Controls media playback using system media keys on Windows.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "One of: play, pause, play_pause, next, previous, stop."}
                },
                "required": ["action"]
            }
        }
    }
]

# --- 4. Agent Execution Loop ---
def run_fitness_agent_turn(client, messages, user_prompt):
    messages.append({"role": "user", "content": user_prompt})

    while True:
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.4
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
                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": func_name,
                    "content": result,
                })
            continue

        messages.append(response_message)
        return response_message.content or ""


def chat_loop():
    client = build_client()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    print("BulkBot is ready. Type 'exit' or 'quit' to stop.")
    while True:
        user_prompt = input("\nYou: ").strip()
        if not user_prompt:
            continue
        if user_prompt.lower() in {"exit", "quit"}:
            print("BulkBot: See you next session.")
            break

        answer = run_fitness_agent_turn(client, messages, user_prompt)
        print(f"BulkBot: {answer}")

# --- 5. Test It ---
if __name__ == "__main__":
    chat_loop()
