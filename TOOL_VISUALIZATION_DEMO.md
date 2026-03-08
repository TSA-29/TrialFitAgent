# Tool Visualization Feature Guide

## Overview

BulkBot now includes **detailed tool execution visualization** that shows exactly what's happening when the AI uses tools. You'll see:

- 📥 **Input Parameters** - What data is being sent to each tool
- ⏳ **Execution Status** - Real-time progress as tools run
- 📤 **Detailed Output** - Complete results from each tool call
- 💡 **Summary** - Quick preview of key results

## Example: TDEE Calculation

**Your prompt:**
```
Calculate my macros. I'm 25, 75kg, 180cm.
```

**What you'll see:**

```
Step 1: 📊 Calculating TDEE & Macros

📥 Input Parameters:
  • Age (years): `25`
  • Weight (kg): `75`
  • Height (cm): `180`

⏳ Executing...
✅ Success

📤 Output:
  • Daily Calories: 2854 kcal
  • Protein: 165g
  • Carbs: 357g
  • Fats: 79g

💡 Summary: Target: 2854 kcal/day | P: 165g | C: 357g | F: 79g
```

## Example: Food Lookup

**Your prompt:**
```
What's in 200g of chicken breast?
```

**What you'll see:**

```
Step 1: 🍗 Looking up Food Macros

📥 Input Parameters:
  • Food item: "chicken breast"
  • Amount (grams): `200`

⏳ Executing...
✅ Success

📤 Output:
  • Food: chicken breast
  • Amount: 200g
  • Calories: 330 kcal
  • Protein: 62g
  • Carbs: 0g
  • Fats: 7g

💡 Summary: 200g chicken breast: 330 kcal | P: 62g | C: 0g | F: 7g
```

## Example: Apple Music Search

**Your prompt:**
```
Search for "Stronger" on Apple Music
```

**What you'll see:**

```
Step 1: 🔍 Searching Apple Music

📥 Input Parameters:
  • Search query: "Stronger"
  • Country: "us"
  • Max results: `5`

⏳ Executing...
✅ Success

📤 Output:
  • Query: Stronger
  • Results Found: 5
  • Search URL: https://music.apple.com/us/search?term=Stronger

  Top Results:
    1. Stronger by Kanye West
    2. Stronger by Clean Bandit
    3. Stronger by Britney Spears

💡 Summary: Found 5 songs
```

## Example: Calendar Event Creation

**Your prompt:**
```
Add a gym workout to my calendar tomorrow at 2pm for 2 hours
```

**What you'll see:**

```
Step 1: 📅 Creating Calendar Event

📥 Input Parameters:
  • Event title: "Gym Workout"
  • Start time: "2026-03-06T14:00:00"
  • End time: "2026-03-06T16:00:00"
  • Location: "Gym"

⏳ Executing...
✅ Success

📤 Output:
  • Action: event_saved
  • Subject: Gym Workout
  • Start: 2026-03-06T14:00:00
  • End: 2026-03-06T16:00:00

💡 Summary: Event created: Gym Workout
```

## Multi-Step Tool Execution

When BulkBot needs to use multiple tools, you'll see each step numbered:

```
Step 1: 📊 Calculating TDEE & Macros
[... tool output ...]

Step 2: 📝 Writing Markdown File
[... tool output ...]

---

📝 Final Response:

I've calculated your macros and saved them to a file...
```

## Key Features

### 1. Transparent Process
See exactly what parameters are being used - no black box!

### 2. Real-Time Feedback
Watch as tools execute with status indicators (⏳ → ✅/❌)

### 3. Detailed Results
Get complete output from every tool, not just summaries

### 4. Error Handling
Clear error messages if something goes wrong

### 5. Quick Summaries
One-line previews for fast reading

## Tool Icons Reference

| Tool | Icon | Description |
|------|------|-------------|
| calculate_tdee_macros | 📊 | TDEE & macro calculations |
| lookup_food_macros | 🍗 | Food nutrition lookup |
| write_markdown_file | 📝 | Create/save markdown files |
| create_outlook_draft | 📧 | Draft Outlook emails |
| create_outlook_calendar_event | 📅 | Create calendar events |
| list_outlook_calendar_events | 📋 | List calendar events |
| search_apple_music | 🔍 | Search Apple Music |
| play_apple_music | 🎵 | Play music |
| open_apple_music_url | 🔗 | Open music URL |
| control_media_playback | ▶️ | Media playback controls |

## Customization

You can adjust the level of detail by:

1. **Enable DEBUG mode** - See additional system logs:
   ```bash
   set BULKBOT_DEBUG=1
   ```

2. **Edit `ui.py`** - Modify the display functions:
   - `display_tool_parameters()` - Change how inputs are shown
   - `display_tool_output()` - Change how outputs are formatted
   - `get_tool_result_preview()` - Adjust summary format

3. **Edit `.chainlit/config.toml`** - Customize the UI appearance and features

## Testing the Feature

Try these prompts to see tool visualization in action:

1. **Simple tool use:**
   ```
   Calculate macros for age 30, weight 80kg, height 175cm
   ```

2. **Food lookup:**
   ```
   What are the macros in 150g salmon?
   ```

3. **File creation:**
   ```
   Create a meal plan file with breakfast, lunch, and dinner
   ```

4. **Music search:**
   ```
   Search for workout music on Apple Music
   ```

5. **Multi-tool workflow:**
   ```
   Calculate my macros (25, 75kg, 180cm) and save it to a file
   ```

## Benefits

- **Educational**: Learn how AI agents use tools
- **Debugging**: Identify issues when something goes wrong
- **Trust**: See exactly what the AI is doing with your data
- **Efficiency**: Quick summaries + detailed results when needed
- **Professional**: Clear communication of all operations
