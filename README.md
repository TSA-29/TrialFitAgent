# BulkBot - AI Fitness Assistant 🏋️‍♂️

A modern AI-powered fitness assistant with a sleek web-based chatbot interface. BulkBot helps with macros, meal planning, Outlook integration, and Apple Music control.

## Features

- 📊 **TDEE & Macro Calculations** - Precise calorie and macronutrient targets for lean bulking
- 🍗 **Food Macro Lookups** - Find exact nutrition data for common foods
- 📧 **Outlook Integration** - Draft emails and create calendar events
- 📅 **Calendar Management** - View and manage your Outlook calendar
- 🎵 **Apple Music Control** - Search and play music hands-free
- 💬 **Modern Chat Interface** - Beautiful, responsive web UI built with Chainlit
- ✨ **Tool Execution Visualization** - Watch real-time tool execution with detailed input/output display

## Tool Visualization Feature

BulkBot now includes **detailed tool execution visualization** that shows exactly what's happening when the AI uses tools:

- 📥 **Input Parameters** - See what data is sent to each tool
- ⏳ **Execution Status** - Real-time progress indicators
- 📤 **Detailed Output** - Complete results from each tool call
- 💡 **Quick Summaries** - One-line previews for fast reading

**Example output:**
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

See [TOOL_VISUALIZATION_DEMO.md](TOOL_VISUALIZATION_DEMO.md) for detailed examples and usage guide.

## Setup

### Prerequisites

- Python 3.8 or higher
- STEP_API_KEY environment variable (for Stepfun AI API)
- Windows OS (for Outlook integration)
- pywin32 installed (for Outlook COM integration)

### Installation

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set your API key** (choose one method):

   **Method 1: Using .env file (Recommended - Easiest)** 👈
   ```bash
   # Copy the example file
   copy .env.example .env

   # Edit .env and replace "your_actual_api_key_here" with your actual key
   # STEP_API_KEY=sk-your-actual-key-here
   ```

   **Method 2: Temporary environment variable**
   ```bash
   # Windows Command Prompt
   set STEP_API_KEY=your_api_key_here

   # Windows PowerShell
   $env:STEP_API_KEY="your_api_key_here"
   ```

   **Method 3: Permanent environment variable**
   ```bash
   # Windows Command Prompt (sets it permanently)
   setx STEP_API_KEY "your_api_key_here"
   ```
   Then restart your terminal for changes to take effect.

   **Method 4: Through Windows GUI**
   1. Press `Windows Key` and search for **"Environment Variables"**
   2. Click **"Edit the system environment variables"**
   3. Click **"Environment Variables"** button
   4. Under **"User variables"**, click **"New"**
   5. Variable name: `STEP_API_KEY`
   6. Variable value: `your_api_key_here`
   7. Click **OK** and restart your terminal

### Running BulkBot

#### Web UI (Recommended) 🌐

Start the modern web interface:

```bash
chainlit run ui.py -w
```

The UI will open automatically in your browser at `http://localhost:8000`

**Features:**
- Smooth streaming responses
- Visual tool execution feedback
- Dark/light mode support
- Mobile-responsive design
- Chat history persistence

#### CLI Mode (Legacy) 💻

For a simple command-line interface:

```bash
python agent.py
```

## Usage Examples

### Calculate Macros
```
Calculate my macros for lean bulk. I'm 25 years old, 75kg, and 180cm tall.
```

### Food Lookups
```
What are the macros in 200g of chicken breast?
```

### Outlook Integration
```
Create an Outlook draft email to john@example.com about our workout session tomorrow.
```

```
Add a calendar event for gym workout tomorrow at 2pm for 2 hours.
```

### Apple Music
```
Search for "Stronger" by Kanye West on Apple Music.
```

```
Play "Eye of the Tiger" on Apple Music.
```

### File Creation
```
Create a markdown file with my weekly meal plan.
```

## Project Structure

```
AgentTask1/
├── agent.py              # Core agent logic and tools
├── ui.py                 # Chainlit web UI interface
├── requirements.txt      # Python dependencies
├── .chainlit/
│   └── config.toml       # UI configuration and branding
└── README.md            # This file
```

## Customization

### UI Theme

Edit `.chainlit/config.toml` to customize:
- App name and branding
- Color scheme (currently orange/fitness theme)
- Welcome message
- Feature list

### Adding New Tools

1. Add the tool function to `agent.py`
2. Add the tool schema to the `tools` list
3. Add the tool to `available_functions` dict
4. Update `TOOL_ICONS` and `TOOL_NAMES` in `ui.py` for visual feedback

## Troubleshooting

### API Key Error
```
RuntimeError: Missing STEP_API_KEY
```
**Solution:** Set the `STEP_API_KEY` environment variable before running.

### Outlook Integration Issues
```
error: pywin32 is not installed
```
**Solution:** Install pywin32: `pip install pywin32`

### Port Already in Use
```
OSError: [Errno 48] Address already in use
```
**Solution:** Either close the application using port 8000 or specify a different port:
```bash
chainlit run ui.py -w --port 8001
```

## Development

### Enable Debug Mode
```bash
# Windows (Command Prompt)
set BULKBOT_DEBUG=1

# Windows (PowerShell)
$env:BULKBOT_DEBUG="1"
```

### Running in Development
```bash
chainlit run ui.py -w --reload
```

## License

This project is for educational purposes.

## Credits

Built with:
- [Chainlit](https://chainlit.io/) - Modern chatbot UI framework
- [Stepfun AI](https://stepfun.com/) - AI model provider
- OpenAI SDK - API client library
