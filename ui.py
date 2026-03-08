"""
BulkBot - Modern Chatbot UI
A Chainlit-based web interface for the BulkBot fitness agent
"""

import json
import asyncio
from typing import Optional
import chainlit as cl

from agent import (
    build_client,
    SYSTEM_PROMPT,
    MODEL,
    tools,
    available_functions,
    DEBUG
)


# Tool icons for visual feedback
TOOL_ICONS = {
    "calculate_tdee_macros": "📊",
    "lookup_food_macros": "🍗",
    "write_markdown_file": "📝",
    "create_outlook_draft": "📧",
    "create_outlook_calendar_event": "📅",
    "list_outlook_calendar_events": "📋",
    "search_apple_music": "🔍",
    "play_apple_music": "🎵",
    "open_apple_music_url": "🔗",
    "control_media_playback": "▶️"
}

TOOL_NAMES = {
    "calculate_tdee_macros": "Calculating TDEE & Macros",
    "lookup_food_macros": "Looking up Food Macros",
    "write_markdown_file": "Writing Markdown File",
    "create_outlook_draft": "Creating Outlook Draft",
    "create_outlook_calendar_event": "Creating Calendar Event",
    "list_outlook_calendar_events": "Listing Calendar Events",
    "search_apple_music": "Searching Apple Music",
    "play_apple_music": "Playing Music",
    "open_apple_music_url": "Opening Music URL",
    "control_media_playback": "Controlling Playback"
}


@cl.on_chat_start
async def on_chat_start():
    """Initialize the chat session with a welcome message."""
    # Initialize the message history with the system prompt
    msg = cl.Message(
        content="""👋 Hey! I'm **BulkBot**, your AI fitness assistant. I'm ready to help you with macros, meal planning, Outlook, and music! 💪

**✨ New Feature**: Tool Execution Visualization
Watch exactly what I'm doing in real-time! When I use tools like calculating macros or searching music, you'll see:
- 📥 Input parameters I'm using
- ⏳ Execution progress
- 📤 Detailed output and results

**What I can help with:**
- 📊 Calculate precise TDEE & macros for lean bulk
- 🍗 Look up nutrition data for foods
- 📧 Draft emails & create calendar events in Outlook
- 🎵 Search & play music on Apple Music
- 📝 Create and save markdown files

Try asking: *"Calculate my macros"* or *"Search for workout music"*"""
    )
    await msg.send()

    # Store the client and message history in the session
    cl.user_session.set("client", build_client())
    cl.user_session.set("messages", [{"role": "system", "content": SYSTEM_PROMPT}])


@cl.on_chat_end
async def on_chat_end():
    """Clean up when chat session ends."""
    messages = cl.user_session.get("messages")
    if DEBUG:
        print(f"--> [System]: Session ended. Total messages: {len(messages)}")


@cl.on_message
async def on_message(message: cl.Message):
    """Handle incoming user messages and generate responses."""
    # Get the session state
    client = cl.user_session.get("client")
    messages_history = cl.user_session.get("messages")

    # Add user message to history
    user_prompt = message.content
    messages_history.append({"role": "user", "content": user_prompt})

    # Create a response message with streaming
    response_msg = cl.Message(content="")
    await response_msg.send()

    try:
        # Run the agent turn with tool support
        final_answer = await run_agent_turn_with_tools(
            client,
            messages_history,
            response_msg
        )
        # Update the final message
        await response_msg.update()
        # Add assistant response to history
        messages_history.append({"role": "assistant", "content": final_answer})
    except Exception as exc:
        error_text = f"Sorry, I hit an internal error: {exc}"
        response_msg.content = error_text
        await response_msg.update()
        messages_history.append({"role": "assistant", "content": error_text})
        if DEBUG:
            print(f"--> [System]: on_message error: {exc}")


async def run_agent_turn_with_tools(client, messages: list, response_msg: cl.Message) -> str:
    """
    Execute an agent turn with tool calling support and streaming updates.

    This is an async version of the run_fitness_agent_turn function from agent.py,
    adapted for Chainlit's async framework with enhanced tool visualization.
    """
    tool_execution_count = 0

    while True:
        # Call the LLM
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.4
            )
        except Exception as exc:
            await response_msg.stream_token(f"\nError while contacting the model: {exc}\n")
            return "I could not reach the model service."
        response_message = response.choices[0].message

        # If there are tool calls, execute them
        if response_message.tool_calls:
            # Add the assistant message with tool calls to history
            messages.append({
                "role": "assistant",
                "content": response_message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in response_message.tool_calls
                ]
            })

            # Execute each tool call with detailed visualization
            for idx, tool_call in enumerate(response_message.tool_calls, 1):
                tool_execution_count += 1
                func_name = tool_call.function.name
                func_args = json.loads(tool_call.function.arguments)

                # Get visual elements
                icon = TOOL_ICONS.get(func_name, "🔧")
                tool_name = TOOL_NAMES.get(func_name, func_name.replace("_", " ").title())

                # Display tool execution header
                await response_msg.stream_token(f"\n\n---\n")
                await response_msg.stream_token(f"**Step {tool_execution_count}**: {icon} **{tool_name}**\n\n")

                # Display input parameters
                if DEBUG or True:  # Always show parameters in web UI
                    await response_msg.stream_token("📥 **Input Parameters**:\n")
                    await display_tool_parameters(response_msg, func_name, func_args)

                if DEBUG:
                    print(f"--> [System]: Executing tool '{func_name}' with args: {func_args}")

                # Execute the tool
                await response_msg.stream_token(f"⏳ **Executing**...\n")

                try:
                    result = available_functions[func_name](**func_args)
                    tool_result = json.loads(result) if isinstance(result, str) else result
                    execution_status = "✅ Success"
                except Exception as e:
                    tool_result = {"status": "error", "message": str(e)}
                    result = json.dumps(tool_result)
                    execution_status = "❌ Error"

                # Display execution status
                await response_msg.stream_token(f"{execution_status}\n\n")

                # Display detailed output
                await display_tool_output(response_msg, func_name, tool_result)

                # Show compact preview if available
                if tool_result.get("status") == "success":
                    preview = get_tool_result_preview(func_name, tool_result)
                    if preview:
                        await response_msg.stream_token(f"💡 **Summary**: {preview}\n\n")

                # Add tool result to history
                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": func_name,
                    "content": result,
                })

            # Continue the loop to get the final response
            continue

        # No more tool calls - we have the final answer
        final_content = response_message.content or ""

        # If tools were executed, add a separator before final response
        if tool_execution_count > 0:
            await response_msg.stream_token(f"\n\n---\n\n**📝 Final Response**:\n\n")

        # Stream the final response
        if final_content:
            await response_msg.stream_token(final_content)

        return final_content


def get_tool_result_preview(func_name: str, result: dict) -> Optional[str]:
    """Generate a concise preview of tool results for display in the UI."""
    if result.get("status") != "success":
        return None

    previews = {
        "calculate_tdee_macros": lambda r: (
            f"Target: **{r['target_calories']}** kcal/day | "
            f"P: {r['macros']['protein_g']}g | "
            f"C: {r['macros']['carbs_g']}g | "
            f"F: {r['macros']['fats_g']}g"
        ),
        "lookup_food_macros": lambda r: (
            f"{r['amount_grams']}g {r['food']}: "
            f"**{r['calories']}** kcal | "
            f"P: {r['protein_g']}g | "
            f"C: {r['carbs_g']}g | "
            f"F: {r['fat_g']}g"
        ),
        "write_markdown_file": lambda r: f"File saved: `{r['path']}`",
        "create_outlook_draft": lambda r: f"Draft created: {r['subject']}",
        "create_outlook_calendar_event": lambda r: f"Event created: {r['subject']}",
        "list_outlook_calendar_events": lambda r: f"Found {r['returned']} events",
        "search_apple_music": lambda r: f"Found {r['count']} songs",
        "play_apple_music": lambda r: f"Playing: {r['track']['track_name']} by {r['track']['artist_name']}",
        "open_apple_music_url": lambda r: "Opening Apple Music URL",
        "control_media_playback": lambda r: f"Media: {r['action']}"
    }

    preview_func = previews.get(func_name)
    return preview_func(result) if preview_func else None


async def display_tool_parameters(message: cl.Message, func_name: str, args: dict):
    """Display formatted tool input parameters."""
    # Format parameters nicely based on the tool
    param_descriptions = {
        "calculate_tdee_macros": {
            "age": "Age (years)",
            "weight_kg": "Weight (kg)",
            "height_cm": "Height (cm)"
        },
        "lookup_food_macros": {
            "food_name": "Food item",
            "grams": "Amount (grams)"
        },
        "write_markdown_file": {
            "filename": "File name",
            "content": "Content (truncated)"
        },
        "create_outlook_draft": {
            "to": "Recipient(s)",
            "subject": "Subject",
            "body": "Body (truncated)",
            "cc": "CC",
            "bcc": "BCC"
        },
        "create_outlook_calendar_event": {
            "subject": "Event title",
            "start_iso": "Start time",
            "end_iso": "End time",
            "location": "Location",
            "body": "Description"
        },
        "list_outlook_calendar_events": {
            "start_iso": "Start date",
            "end_iso": "End date",
            "max_items": "Max events"
        },
        "search_apple_music": {
            "query": "Search query",
            "country_code": "Country",
            "limit": "Max results"
        },
        "play_apple_music": {
            "query": "Search query",
            "play_mode": "Play mode"
        },
        "open_apple_music_url": {
            "url": "Music URL"
        },
        "control_media_playback": {
            "action": "Action"
        }
    }

    descriptions = param_descriptions.get(func_name, {})

    for key, value in args.items():
        label = descriptions.get(key, key.replace("_", " ").title())

        # Truncate long content for display
        if key in ["content", "body"] and isinstance(value, str) and len(value) > 100:
            value = value[:97] + "..."

        # Format the value
        if isinstance(value, str):
            value_str = f'`"{value}"`'
        elif isinstance(value, bool):
            value_str = "✓" if value else "✗"
        else:
            value_str = f"`{value}`"

        await message.stream_token(f"  • **{label}**: {value_str}\n")

    await message.stream_token("\n")


async def display_tool_output(message: cl.Message, func_name: str, result: dict):
    """Display formatted tool output with full details."""
    await message.stream_token("Output:\n")

    if result.get("status") == "error":
        error_msg = result.get("message", "Unknown error")
        await message.stream_token(f"Error: {error_msg}\n")
        return

    if func_name == "calculate_tdee_macros":
        await message.stream_token(
            f"  - Daily Calories: {result.get('target_calories')} kcal\n"
            f"  - Protein: {result.get('macros', {}).get('protein_g')}g\n"
            f"  - Carbs: {result.get('macros', {}).get('carbs_g')}g\n"
            f"  - Fats: {result.get('macros', {}).get('fats_g')}g\n"
        )
    elif func_name == "lookup_food_macros":
        await message.stream_token(
            f"  - Food: {result.get('food')}\n"
            f"  - Amount: {result.get('amount_grams')}g\n"
            f"  - Calories: {result.get('calories')} kcal\n"
            f"  - Protein: {result.get('protein_g')}g\n"
            f"  - Carbs: {result.get('carbs_g')}g\n"
            f"  - Fats: {result.get('fat_g')}g\n"
        )
    elif func_name == "write_markdown_file":
        await message.stream_token(
            f"  - Status: {result.get('status')}\n"
            f"  - Path: `{result.get('path')}`\n"
            f"  - Message: {result.get('message')}\n"
        )
    elif func_name == "create_outlook_draft":
        await message.stream_token(
            f"  - Action: {result.get('action')}\n"
            f"  - To: {result.get('to')}\n"
            f"  - Subject: {result.get('subject')}\n"
        )
    elif func_name == "create_outlook_calendar_event":
        await message.stream_token(
            f"  - Action: {result.get('action')}\n"
            f"  - Subject: {result.get('subject')}\n"
            f"  - Start: {result.get('start')}\n"
            f"  - End: {result.get('end')}\n"
        )
    elif func_name == "list_outlook_calendar_events":
        await message.stream_token(
            f"  - Range: {result.get('range_start')} to {result.get('range_end')}\n"
            f"  - Events Found: {result.get('total_in_range')} (showing {result.get('returned')})\n"
        )
        if result.get("events"):
            await message.stream_token("\n  Events:\n")
            for i, event in enumerate(result["events"][:5], 1):
                await message.stream_token(
                    f"  {i}. {event.get('subject', 'Untitled')} - {event.get('start', '')}\n"
                )
    elif func_name == "search_apple_music":
        await message.stream_token(
            f"  - Query: {result.get('query')}\n"
            f"  - Results Found: {result.get('count')}\n"
            f"  - Search URL: {result.get('search_url')}\n"
        )
        if result.get("results"):
            await message.stream_token("\n  Top Results:\n")
            for i, track in enumerate(result["results"][:3], 1):
                await message.stream_token(
                    f"  {i}. {track.get('track_name', '')} by {track.get('artist_name', '')}\n"
                )
    elif func_name == "play_apple_music":
        track = result.get("track", {})
        await message.stream_token(
            f"  - Status: {result.get('play_mode')}\n"
            f"  - Track: {track.get('track_name', 'N/A')}\n"
            f"  - Artist: {track.get('artist_name', 'N/A')}\n"
            f"  - Album: {track.get('album_name', 'N/A')}\n"
            f"  - Opened: {'yes' if result.get('opened') else 'no'}\n"
        )
    elif func_name == "open_apple_music_url":
        await message.stream_token(
            f"  - URL: {result.get('url')}\n"
            f"  - Opened: {'yes' if result.get('opened') else 'no'}\n"
        )
    elif func_name == "control_media_playback":
        await message.stream_token(
            f"  - Action: {result.get('action')}\n"
            f"  - Status: {result.get('message')}\n"
        )
    else:
        await message.stream_token(f"```json\n{json.dumps(result, indent=2)}\n```\n")

    await message.stream_token("\n")
# Main entry point for development
if __name__ == "__main__":
    # This is for development only
    # In production, use: chainlit run ui.py -w
    print("Starting BulkBot UI...")
    print("Run with: chainlit run ui.py -w")

