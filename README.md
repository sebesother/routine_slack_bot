# Routine Slack Bot

A Slack bot for managing team's daily tasks with automatic list posting, completion tracking, and reminders.

## Components

- **main_bot.py** - Interactive bot (task completion via mentions and modal window, duty management)
- **cron_bot.py** - Morning task posting (Monday - weekly schedule with duties, Tuesday-Friday - daily tasks)
- **reminder_bot.py** - Automatic reminders for incomplete tasks
- **redis_bot.py** - Data layer for Redis operations

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
   ```

## Usage

### Task Completion

**Via modal window (recommended):**
1. Click ✅
2. Select tasks from the list
3. Submit the form

**Via mention:**
```
@bot Task Name done
```

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
