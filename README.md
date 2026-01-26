# Routine Slack Bot

A Slack bot for managing team's daily tasks with automatic list posting, completion tracking, and reminders.

## Components

- **main_bot.py** - Interactive bot (task completion via mentions and modal window, duty management)
- **cron_bot.py** - Morning task posting (Monday - weekly schedule with duties, Tuesday-Friday - daily tasks)
- **reminder_bot.py** - Automatic reminders for incomplete tasks
- **remote_summary_bot.py** - Weekly remote work schedule summary (sent on Fridays)
- **redis_bot.py** - Data layer for Redis operations
- **remote_bot.py** - Remote work days management

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure environment variables:
   ```bash
   export SLACK_BOT_TOKEN="xoxb-..."
   export SLACK_APP_TOKEN="xapp-..."
   export SLACK_CHANNEL_ID="C..."
   export REDIS_URL="redis://..."
   # Optional: Override default remote summary channel
   export REMOTE_SUMMARY_CHANNEL_ID="C01VAR1KUS1"
   ```

3. Run the bot:
   ```bash
   python main_bot.py
   ```

4. Setup cron for automatic posting:
   ```bash
   # Post tasks at 09:00 on weekdays
   0 9 * * 1-5 cd /path/to/bot && python cron_bot.py
   
   # Reminders at 13:00 on weekdays
   0 13 * * 1-5 cd /path/to/bot && python reminder_bot.py
   
   # Remote summary on Fridays at 16:00
   0 16 * * 5 cd /path/to/bot && python remote_summary_bot.py
   ```

5. **Add bot to channels:**
   
   The bot needs to be added as a member to channels where it will post messages:
   
   - Open the Slack channel (e.g., `C01VAR1KUS1` for remote summaries)
   - Click on channel name → "Integrations" tab
   - Click "Add apps"
   - Search for your bot name and click "Add"
   
   Alternatively, type in the channel: `/invite @YourBotName`
   
   **Required permissions:**
   - `chat:write` - to send messages
   - `channels:read` - to access channel info
   
   Without adding the bot to the channel, you'll get an error: `not_in_channel`

## Usage

### Task Completion

**Via modal window (recommended):**
1. Click ✅ "Complete Task"
2. Select tasks from the list
3. Submit the form

**Via mention:**
```
@bot Task Name done
```

### Remote Work Days

**Setting remote days:**
1. Click 🏠 "Mark Remote Days" button in daily message
2. Select up to 2 days from next week (Monday-Friday)
3. Submit the form

Remote days are automatically included in daily messages and sent as a weekly summary every Friday.

**Weekly summary:**
- Sent automatically every Friday at 16:00 (configurable via cron)
- Shows all remote work days for the next week
- Includes statistics (total days, unique employees)
- Posted to configured channel (default: `C01VAR1KUS1`)

### Debug Mode

```
@bot debug              # Today's message
@bot debug monday       # Monday message with duties
@bot debug tuesday      # Tuesday message
```

Uses separate Redis state (`debug_routine_state`) and doesn't affect production.

### Duty Management

```bash
# Assign duty for current week
/set-duty fin @username current

# Assign for next week
/set-duty asana @username next

# Assign for specific week (Monday date)
/set-duty tg @username 09/12

# Remove assignment
/set-duty fin current
```

**Duty types:** `fin`, `asana`, `tg`, `notification`, `supervision`

## Data Structure

### task_base.json
```json
{
  "1": {
    "name": "Task Name",
    "deadline": "12:00",
    "days": "all",              // "all" or "monday,friday"
    "period": "morning",         // "morning" or "evening"
    "type": "regular",
    "asana_url": "https://...",
    "comments": "Description"
  }
}
```

### employees.json
```json
{
  "dates": {
    "09/12": {
      "morning": ["U123ABC", "U456DEF"],
      "evening": ["U789GHI"]
    }
  },
  "weekly_duties": {
    "09/12": {
      "FIN-DUTY": "U123ABC",
      "ASANA-DUTY": "U456DEF"
    }
  }
}
```

## Loading Data to Redis

```bash
cd ignore_data
python upload_task_base.py
python upload_employees.py
```

## Features

- Works on weekdays only (Mon-Fri)
- Timezone: Europe/Riga
- Monday messages are automatically pinned
- Special dates support with emoji
- Task grouping by periods (morning/evening)
