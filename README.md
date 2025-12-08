# Routine Slack Bot

A comprehensive Slack bot system for daily task tracking, completion monitoring, automated reminders, and weekly duty assignments.

## Overview

This bot system helps teams manage daily routines by:
- Posting morning task lists to Slack channels
- Tracking task completion through @mentions
- Sending reminders for incomplete or overdue tasks
- Managing weekly duty assignments (Fin-duty, Asana-duty, TG-duty, etc.)
- Automatic pinning of Monday weekly schedules
- Special date notifications (holidays, special events)
- Supporting debug mode for testing workflows

## Components

- **main_bot.py** - Interactive bot handling task completion via @mentions and duty assignments
- **cron_bot.py** - Daily cron job posting morning task lists (weekly on Monday, daily on Tue-Fri)
- **reminder_bot.py** - Automated reminder system for incomplete tasks
- **redis_bot.py** - Central data layer managing Redis storage

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set environment variables:
   ```bash
   export SLACK_BOT_TOKEN="xoxb-..."
   export SLACK_APP_TOKEN="xapp-..."
   export SLACK_CHANNEL_ID="C..."
   export REDIS_URL="redis://..."
   ```

3. Run components:
   ```bash
   # Interactive bot
   python main_bot.py
   
   # Daily task poster (via cron)
   python cron_bot.py
   
   # Reminder system (via cron)
   python reminder_bot.py
   ```

## Usage

### Task Completion
- Complete tasks: `@bot TaskName done`
- Debug mode: `@bot debug` or `@bot debug monday`

### Weekly Duty Management

The `/set-duty` command manages weekly duty assignments (Fin-duty, Asana-duty, TG-duty, Notification-duty, Supervision-duty).

**Assign duty for current week:**
```
/set-duty fin @username current
```

**Assign duty for next week:**
```
/set-duty asana @username next
```

**Assign duty for specific week (by Monday date):**
```
/set-duty tg @username 09/12
```

**Remove duty assignment:**
```
/set-duty fin current
/set-duty asana 16/12
```

**Available duty types:**
- `fin` - Fin-duty (Financial tasks, Statements)
- `asana` - Asana-duty (Task management in Asana)
- `tg` - TG-duty (Telegram monitoring)
- `notification` - Notification-duty (Slack notifications management)
- `supervision` - Supervision-duty (Oversight and control)

**Week specification:**
- `current` - Current week
- `next` - Next week
- `dd/mm` - Specific Monday date (e.g., `09/12`)

### Special Features

- **Monday Messages**: Weekly schedule with duty assignments, automatically pinned
- **Tuesday-Friday Messages**: Daily tasks only
- **Special Dates**: Automatic holiday notifications with emoji (Christmas 🎄✨, New Year 🎆❄️)
- **Timezone-aware**: All operations use Europe/Riga timezone
- **Weekday-only**: Operates Monday-Friday

## Data Storage

Tasks stored in Redis with structure supporting:
- Deadlines and day restrictions
- Asana integration
- Task types (regular/duty)
- Weekly duty assignments
- Special dates (holidays, events)
- Employee schedules (morning/evening shifts)