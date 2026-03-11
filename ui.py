"""
DeskPilot - Mock Personal Assistant UI
A Chainlit-based web interface for the DeskPilot assistant.
"""

import asyncio
import json
import os
from typing import Optional

# Authentication must have a JWT secret when login is enabled.
os.environ.setdefault("CHAINLIT_AUTH_SECRET", "deskpilot-local-dev-secret-change-me")

import chainlit as cl
from chainlit.types import ThreadDict

from agent import (
    DEBUG,
    MODEL,
    SYSTEM_PROMPT,
    available_functions,
    build_client,
    tools,
)
from local_data_layer import LocalJSONDataLayer


AUTH_USERNAME = os.environ.get("DESKPILOT_LOGIN_USERNAME", "deskpilot")
AUTH_PASSWORD = os.environ.get("DESKPILOT_LOGIN_PASSWORD", "deskpilot")
HISTORY_STORE_PATH = os.environ.get(
    "DESKPILOT_HISTORY_FILE", ".files/deskpilot_history.json"
)
DATA_LAYER = LocalJSONDataLayer(store_path=HISTORY_STORE_PATH)


TOOL_ICONS = {
    "draft_email": "[EMAIL]",
    "list_email_drafts": "[EMAIL-LIST]",
    "create_calendar_appointment": "[CALENDAR]",
    "list_calendar_appointments": "[CALENDAR-LIST]",
    "book_trip": "[TRIP]",
    "list_trips": "[TRIP-LIST]",
    "launch_music_app": "[MUSIC]",
    "notion_edit_page": "[NOTION]",
    "list_notion_pages": "[NOTION-LIST]",
}

TOOL_NAMES = {
    "draft_email": "Drafting Email",
    "list_email_drafts": "Listing Email Drafts",
    "create_calendar_appointment": "Creating Calendar Appointment",
    "list_calendar_appointments": "Listing Calendar Appointments",
    "book_trip": "Booking Trip",
    "list_trips": "Listing Trips",
    "launch_music_app": "Music App Action",
    "notion_edit_page": "Editing Notion Page",
    "list_notion_pages": "Listing Notion Pages",
}


@cl.data_layer
def get_data_layer():
    return DATA_LAYER


@cl.password_auth_callback
def auth_callback(username: str, password: str):
    if username == AUTH_USERNAME and password == AUTH_PASSWORD:
        return cl.User(
            identifier=username,
            metadata={"provider": "password", "app": "deskpilot"},
        )
    return None


def _rebuild_messages_from_thread(thread: ThreadDict) -> list:
    restored = [{"role": "system", "content": SYSTEM_PROMPT}]
    steps = sorted(
        thread.get("steps", []),
        key=lambda s: str(s.get("createdAt") or s.get("start") or ""),
    )

    for step in steps:
        step_type = str(step.get("type") or "")
        content = str(step.get("output") or step.get("input") or "").strip()
        if not content:
            continue

        if step_type == "user_message":
            restored.append({"role": "user", "content": content})
        elif step_type == "assistant_message":
            restored.append({"role": "assistant", "content": content})

    return restored


@cl.on_chat_start
async def on_chat_start():
    """Initialize the chat session with a welcome message."""
    cl.user_session.set("client", build_client())
    cl.user_session.set("messages", [{"role": "system", "content": SYSTEM_PROMPT}])

    msg = cl.Message(
        content=(
            "Hi, I am **DeskPilot**.\n\n"
            "I can simulate real assistant workflows with mock data:\n"
            "- Draft emails\n"
            "- Schedule calendar appointments\n"
            "- Book trips\n"
            "- Launch/control a music app\n"
            "- Edit Notion pages\n\n"
            "History is enabled: use the left sidebar to reopen previous chats."
        )
    )
    await msg.send()


@cl.on_chat_resume
async def on_chat_resume(thread: ThreadDict):
    """Restore runtime context when a user opens a historical thread."""
    cl.user_session.set("client", build_client())
    cl.user_session.set("messages", _rebuild_messages_from_thread(thread))


@cl.on_chat_end
async def on_chat_end():
    """Clean up when chat session ends."""
    messages = cl.user_session.get("messages") or []
    if DEBUG:
        print(f"--> [System]: Session ended. Total messages: {len(messages)}")


@cl.on_message
async def on_message(message: cl.Message):
    """Handle incoming user messages and generate responses."""
    client = cl.user_session.get("client")
    messages_history = cl.user_session.get("messages")

    if client is None:
        client = build_client()
        cl.user_session.set("client", client)

    if messages_history is None:
        messages_history = [{"role": "system", "content": SYSTEM_PROMPT}]
        cl.user_session.set("messages", messages_history)

    user_prompt = message.content
    messages_history.append({"role": "user", "content": user_prompt})

    response_msg = cl.Message(content="")
    await response_msg.send()

    try:
        final_answer = await run_agent_turn_with_tools(client, messages_history, response_msg)
        await response_msg.update()
        messages_history.append({"role": "assistant", "content": final_answer})
    except Exception as exc:
        error_text = f"Sorry, I hit an internal error: {exc}"
        response_msg.content = error_text
        await response_msg.update()
        messages_history.append({"role": "assistant", "content": error_text})
        if DEBUG:
            print(f"--> [System]: on_message error: {exc}")


async def run_agent_turn_with_tools(client, messages: list, response_msg: cl.Message) -> str:
    """Execute one assistant turn with tool-calling support and streaming updates."""
    tool_execution_count = 0

    while True:
        try:
            async with cl.Step(name="Thinking", type="run") as think_step:
                think_step.input = "Planning response and deciding tools..."
                response = await asyncio.to_thread(
                    client.chat.completions.create,
                    model=MODEL,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    temperature=0.4,
                )
                think_step.output = "Model response received."
        except Exception as exc:
            await response_msg.stream_token(f"\nError while contacting the model: {exc}\n")
            return "I could not reach the model service."

        response_message = response.choices[0].message

        if response_message.tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": response_message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in response_message.tool_calls
                    ],
                }
            )

            for tool_call in response_message.tool_calls:
                tool_execution_count += 1
                func_name = tool_call.function.name
                func_args = json.loads(tool_call.function.arguments or "{}")

                icon = TOOL_ICONS.get(func_name, "[TOOL]")
                tool_name = TOOL_NAMES.get(func_name, func_name.replace("_", " ").title())

                await response_msg.stream_token("\n\n---\n")
                await response_msg.stream_token(
                    f"**Step {tool_execution_count}**: {icon} **{tool_name}**\n\n"
                )

                await response_msg.stream_token("Input Parameters:\n")
                await display_tool_parameters(response_msg, func_name, func_args)

                if DEBUG:
                    print(f"--> [System]: Executing tool '{func_name}' with args: {func_args}")

                await response_msg.stream_token("Executing...\n")

                try:
                    async with cl.Step(name=f"Tool: {tool_name}", type="tool") as tool_step:
                        tool_step.input = json.dumps(func_args, ensure_ascii=False, indent=2)
                        result = await asyncio.to_thread(
                            available_functions[func_name], **func_args
                        )
                        tool_result = json.loads(result) if isinstance(result, str) else result
                        tool_step.output = json.dumps(
                            tool_result, ensure_ascii=False, indent=2
                        )[:3000]
                    execution_status = "Success"
                except Exception as exc:
                    tool_result = {"status": "error", "message": str(exc)}
                    result = json.dumps(tool_result)
                    execution_status = "Error"

                await response_msg.stream_token(f"{execution_status}\n\n")
                await display_tool_output(response_msg, func_name, tool_result)

                if tool_result.get("status") == "success":
                    preview = get_tool_result_preview(func_name, tool_result)
                    if preview:
                        await response_msg.stream_token(f"Summary: {preview}\n\n")

                messages.append(
                    {
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": func_name,
                        "content": result,
                    }
                )

            continue

        final_content = response_message.content or ""

        if tool_execution_count > 0:
            await response_msg.stream_token("\n\n---\n\nFinal Response:\n\n")

        if final_content:
            await response_msg.stream_token(final_content)

        return final_content


def get_tool_result_preview(func_name: str, result: dict) -> Optional[str]:
    """Generate a concise preview of tool results for display in the UI."""
    if result.get("status") != "success":
        return None

    previews = {
        "draft_email": lambda r: f"Drafted: {r['email']['subject']}",
        "list_email_drafts": lambda r: f"{r.get('count', 0)} drafts returned",
        "create_calendar_appointment": lambda r: f"Appointment: {r['appointment']['title']}",
        "list_calendar_appointments": lambda r: f"{r.get('count', 0)} appointments returned",
        "book_trip": lambda r: f"Trip booked: {r['trip']['origin']} -> {r['trip']['destination']}",
        "list_trips": lambda r: f"{r.get('count', 0)} trips returned",
        "launch_music_app": lambda r: r.get("message", "Music action completed"),
        "notion_edit_page": lambda r: f"Notion page updated: {r['page']['title']}",
        "list_notion_pages": lambda r: f"{r.get('count', 0)} pages returned",
    }

    preview_func = previews.get(func_name)
    return preview_func(result) if preview_func else None


async def display_tool_parameters(message: cl.Message, func_name: str, args: dict):
    """Display formatted tool input parameters."""
    param_descriptions = {
        "draft_email": {
            "to": "To",
            "subject": "Subject",
            "body": "Body",
            "cc": "CC",
            "bcc": "BCC",
            "priority": "Priority",
            "send_time_iso": "Scheduled Time",
        },
        "list_email_drafts": {
            "limit": "Limit",
            "recipient_filter": "Recipient Filter",
        },
        "create_calendar_appointment": {
            "title": "Title",
            "start_iso": "Start",
            "end_iso": "End",
            "attendees": "Attendees",
            "location": "Location",
            "notes": "Notes",
            "reminder_minutes": "Reminder (minutes)",
        },
        "list_calendar_appointments": {
            "start_iso": "Start",
            "end_iso": "End",
            "limit": "Limit",
        },
        "book_trip": {
            "traveler_name": "Traveler",
            "origin": "Origin",
            "destination": "Destination",
            "depart_date": "Depart Date",
            "return_date": "Return Date",
            "transport": "Transport",
            "hotel_required": "Hotel Required",
            "budget_usd": "Budget USD",
        },
        "list_trips": {
            "limit": "Limit",
        },
        "launch_music_app": {
            "app_name": "App",
            "action": "Action",
            "query": "Query",
        },
        "notion_edit_page": {
            "page_title": "Page",
            "operation": "Operation",
            "content": "Content",
            "block_type": "Block Type",
            "task_done": "Task Done",
        },
        "list_notion_pages": {
            "limit": "Limit",
        },
    }

    descriptions = param_descriptions.get(func_name, {})

    for key, value in args.items():
        label = descriptions.get(key, key.replace("_", " ").title())

        if key in {"content", "body"} and isinstance(value, str) and len(value) > 100:
            value = value[:97] + "..."

        if isinstance(value, str):
            value_str = f'`"{value}"`'
        elif isinstance(value, bool):
            value_str = "yes" if value else "no"
        else:
            value_str = f"`{value}`"

        await message.stream_token(f"  - **{label}**: {value_str}\n")

    await message.stream_token("\n")


async def display_tool_output(message: cl.Message, func_name: str, result: dict):
    """Display formatted tool output with full details."""
    await message.stream_token("Output:\n")

    if result.get("status") == "error":
        await message.stream_token(f"Error: {result.get('message', 'Unknown error')}\n\n")
        return

    if func_name == "draft_email":
        email = result.get("email", {})
        await message.stream_token(
            f"  - Email ID: {email.get('email_id')}\n"
            f"  - To: {email.get('to')}\n"
            f"  - Subject: {email.get('subject')}\n"
            f"  - Status: {email.get('status')}\n"
        )
    elif func_name == "list_email_drafts":
        await message.stream_token(f"  - Drafts Returned: {result.get('count', 0)}\n")
    elif func_name == "create_calendar_appointment":
        appt = result.get("appointment", {})
        await message.stream_token(
            f"  - Appointment ID: {appt.get('appointment_id')}\n"
            f"  - Title: {appt.get('title')}\n"
            f"  - Start: {appt.get('start')}\n"
            f"  - End: {appt.get('end')}\n"
            f"  - Status: {appt.get('status')}\n"
        )
    elif func_name == "list_calendar_appointments":
        await message.stream_token(f"  - Appointments Returned: {result.get('count', 0)}\n")
    elif func_name == "book_trip":
        trip = result.get("trip", {})
        await message.stream_token(
            f"  - Trip ID: {trip.get('trip_id')}\n"
            f"  - Route: {trip.get('origin')} -> {trip.get('destination')}\n"
            f"  - Booking Ref: {trip.get('booking_reference')}\n"
            f"  - Status: {trip.get('status')}\n"
        )
    elif func_name == "list_trips":
        await message.stream_token(f"  - Trips Returned: {result.get('count', 0)}\n")
    elif func_name == "launch_music_app":
        await message.stream_token(
            f"  - Action: {result.get('action')}\n"
            f"  - Message: {result.get('message')}\n"
        )
    elif func_name == "notion_edit_page":
        page = result.get("page", {})
        await message.stream_token(
            f"  - Page: {page.get('title')}\n"
            f"  - Blocks: {len(page.get('blocks', []))}\n"
            f"  - Updated: {page.get('updated_at')}\n"
        )
    elif func_name == "list_notion_pages":
        await message.stream_token(f"  - Pages Returned: {result.get('count', 0)}\n")
    else:
        await message.stream_token(f"```json\n{json.dumps(result, indent=2)}\n```\n")

    await message.stream_token("\n")


if __name__ == "__main__":
    print("Starting DeskPilot UI...")
    print("Login username:", AUTH_USERNAME)
    print("Login password:", AUTH_PASSWORD)
    print("Run with: chainlit run ui.py -w")
