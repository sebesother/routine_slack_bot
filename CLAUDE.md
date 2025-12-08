# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment Setup

Required environment variables:
- `SLACK_BOT_TOKEN` - Bot user OAuth token
- `SLACK_APP_TOKEN` - App-level token for Socket Mode  
- `SLACK_CHANNEL_ID` - Target channel for daily messages
- `REDIS_URL` - Redis connection string (default: `redis://localhost:6379`)

Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the System

**Main bot (interactive task tracking):**
```bash
python main_bot.py
```

**Daily cron job (sends morning task lists):**
```bash
python cron_bot.py
```

**Reminder system (checks for incomplete tasks):**
```bash
python reminder_bot.py
```

## Architecture Overview

### Core Components

**config.py** - Centralized configuration:
- Manages environment variables and Redis keys
- Defines timezone (`Europe/Riga`) and logging configuration
- Validates required environment variables on startup

**redis_bot.py** - Data layer (all Redis interactions):
- Task management: `load_task_base()`, `save_task_base()`, `get_tasks_for_day()`, `get_duty_tasks()`
- State management: `load_state()`, `save_state()` (separate production/debug states)
- Task completion: `record_task()`, `get_completed_tasks()`
- Task matching: `find_task_in_text()` - builds regex from task names in Redis
- Task formatting: `format_task_line()`, `generate_message_from_redis()`, `generate_weekly_message_from_redis()`
- Employee management: `load_employees()`, `get_employees_for_date_and_period()`
- Task assignments: `set_task_assignment()`, `get_task_assignment()`, `find_task_by_pattern()`
- Weekly duty management: `set_weekly_duty_assignment()`, `get_weekly_duty_assignments()`, `validate_employee_for_duty()`
- Special dates: `check_special_date()`, `get_special_date_header()`
- Week utilities: `get_week_monday()`, `get_week_dates()`

**main_bot.py** - Interactive Slack bot:
- Listens for @mentions in Socket Mode
- Handles task completion: `@bot TaskName done`
- Supports debug mode: `@bot debug` or `@bot debug monday`
- Validates deadlines against current Riga time
- Implements `/set-duty` slash command for weekly duty assignments
- Adds ✅ reaction for on-time completion, posts warning for late tasks

**cron_bot.py** - Daily task poster:
- Runs weekdays only (Monday-Friday)
- **Monday**: Posts weekly message with duty assignments and daily tasks, automatically pins message
- **Tuesday-Friday**: Posts regular daily tasks only
- Creates new thread and stores `thread_ts` in Redis state

**reminder_bot.py** - Notification system:
- Filters incomplete tasks based on time and deadlines
- At 13:00: excludes tasks with 16:00+ deadlines
- Tags team for overdue tasks using `<!subteam^S07BD1P55GT|@sup>`
- Posts reminders in the daily task thread

### Redis Data Structure

**task_base** - Task definitions:
```json
{
  "task_id": {
    "name": "Task Name",
    "type": "regular",
    "deadline": "HH:MM",
    "days": ["Monday", "Tuesday"] | "all",
    "period": "morning" | "evening" | "",
    "asana_url": "optional",
    "comments": "optional"
  },
  "duty_task_id": {
    "name": "Fin-duty",
    "type": "duty",
    "description": "Финансовое дежурство",
    "days": "all"
  }
}
```

**employees** - Employee data and task assignments:
```json
{
  "employee_id": {
    "name": "Full Name",
    "slack_id": "U...",
    "username": "username",
    "morning_dates": ["dd/mm"],
    "evening_dates": ["dd/mm"]
  },
  "task_assignments": {
    "TASK_NAME": "slack_user_id"
  },
  "weekly_duty_assignments": {
    "09/12": {
      "FIN-DUTY": "U123",
      "ASANA-DUTY": "U456"
    }
  },
  "special_dates": {
    "24/12": {
      "type": "christmas",
      "description": "Рождественский сочельник"
    },
    "01/01": {
      "type": "new_year",
      "description": "Новый год"
    }
  }
}
```

**slack_routine_state** / **debug_routine_state** - Daily completion tracking:
```json
{
  "date": "YYYY-MM-DD",
  "thread_ts": "slack_timestamp",
  "completed": {
    "TASK_NAME": {
      "user": "U...",
      "time": "HH:MM"
    }
  }
}
```

### Key Workflows

**Daily Task Flow:**
1. `cron_bot.py` posts morning message at start of day
2. **Monday**: Posts weekly message with duty assignments, pins message to channel
3. **Tuesday-Friday**: Posts regular daily tasks only (duty tasks excluded)
4. Creates new thread, stores `thread_ts` in `slack_routine_state`
5. `main_bot.py` listens for `@bot TaskName done` in thread
6. Validates deadline, records completion in Redis
7. `reminder_bot.py` sends periodic reminders for incomplete tasks

**Weekly Duty Flow:**
1. Use `/set-duty <type> @username <week>` to assign duties for the week
2. System validates employee works majority of days (3+ out of 5)
3. Assignment stored in `employees.weekly_duty_assignments[monday_date]`
4. Monday message displays all duty assignments for the week
5. Duty tasks don't participate in deadline tracking or completion flow

**Debug Mode:**
- Triggered by mentioning bot with "debug" keyword
- Uses separate Redis state (`debug_routine_state`)
- Prefixes messages with "🔧 DEBUG:"
- Allows testing without affecting production tracking
- Thread detection: bot determines mode by comparing `thread_ts`

**Special Dates:**
- Dates marked in `employees.special_dates` trigger special notifications
- Types: `christmas` (🎄✨), `new_year` (🎆❄️), or custom
- Headers include emoji, greeting, and operational notice
- Applies to both Monday weekly and daily messages

**Period Grouping:**
- Tasks can have `period: "morning"` or `period: "evening"`
- Morning/evening tasks are grouped separately in messages
- Employee mentions appear at group headers based on `morning_dates`/`evening_dates`

### Timezone Handling

- All operations use `Europe/Riga` timezone (defined in config.py:66)
- Deadline validation compares current Riga time against task deadline
- Cron jobs respect weekday-only operation (Monday-Friday)

### Task Matching

- `find_task_in_text()` builds regex from all task names in Redis
- Pattern: `(?i)(task1|task2|...).*done`
- Task names are normalized to uppercase for comparison
- New tasks added to Redis are automatically recognized

## Adding New Tasks

1. Update Redis `task_base` with new task entry
2. Set appropriate `days` restriction (`"all"` or specific weekdays)
3. Add `deadline` for reminder logic (optional)
4. Set `period` for grouping: `"morning"`, `"evening"`, or `""` (optional)
5. Task will automatically be included in regex matching

## Slack Command Reference

**Task Completion:**
- `@bot TaskName done` - Mark task complete
- `@bot debug` - Send debug task list for today
- `@bot debug monday` - Send debug task list for Monday

**Weekly Duty Management:**
- `/set-duty <type> @username <week>` - Assign user to weekly duty
- `/set-duty <type> <week>` - Clear duty assignment

**Examples:**
```
/set-duty fin @d.ciruks current       # Assign to current week
/set-duty asana @a.vaver next         # Assign to next week
/set-duty tg @i.konovalov 09/12      # Assign to specific week
/set-duty fin current                 # Clear assignment
```

**Available duty types:** fin, asana, tg, notification, supervision
**Week formats:** current, next, dd/mm (Monday date)
