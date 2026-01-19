import datetime
import os

import pytz
from slack_sdk import WebClient

from config import Config
from constants import MESSAGE_TEMPLATES, PERIOD_EMOJI
from redis_bot import (
    get_completed_tasks,
    get_tasks_for_day,
    get_thread_ts,
    group_tasks_by_period,
)

client = WebClient(token=os.environ.get("SLACK_BOT_TOKEN"))
CHANNEL_ID = os.environ.get("SLACK_CHANNEL_ID")


def get_incomplete_tasks():
    """Get incomplete tasks with reminder time filtering."""
    riga = pytz.timezone("Europe/Riga")
    today = datetime.datetime.now(riga)
    day_name = today.strftime("%A")
    current_hour = today.hour

    # Get all tasks for today
    all_tasks = get_tasks_for_day(day_name)

    # Filter out duty tasks - only regular tasks should be reminded about
    all_tasks = [task for task in all_tasks if task.get("type") != "duty"]

    # Get completed tasks from slack_routine_state
    completed_tasks = get_completed_tasks(debug_mode=False)
    completed_names = [name.upper() for name in completed_tasks.keys()]

    # Filter incomplete tasks
    incomplete_tasks = []
    overdue_tasks = []

    for task in all_tasks:
        task_name_upper = task.get("name", "").upper()

        # Skip completed tasks
        if task_name_upper in completed_names:
            continue

        deadline_str = task.get("deadline", "")

        # If deadline exists, check time-based logic
        if deadline_str:
            try:
                hour, minute = map(int, deadline_str.split(":"))
                deadline_hour = hour

                # At 13:00 don't show tasks with 16:00+ deadline
                if current_hour == Config.REMINDER_TIME and deadline_hour >= Config.LATE_DEADLINE_THRESHOLD:
                    continue

                # Check if task is overdue
                current_time = today.time()
                deadline_time = datetime.time(hour=hour, minute=minute)

                if current_time > deadline_time:
                    overdue_tasks.append(task)
                else:
                    incomplete_tasks.append(task)

            except ValueError:
                # If unable to parse time, add to regular tasks
                incomplete_tasks.append(task)
        else:
            # Tasks without deadline are always shown
            incomplete_tasks.append(task)

    return incomplete_tasks, overdue_tasks


def format_reminder_task_line(task, is_overdue=False):
    """Format task line for reminder."""
    name = task.get("name", "")
    deadline = task.get("deadline", "")
    period = task.get("period", "")

    # Emoji for group
    period_emoji = ""
    if period == "morning":
        period_emoji = PERIOD_EMOJI["morning"]
    elif period == "evening":
        period_emoji = PERIOD_EMOJI["evening"]

    if is_overdue and deadline:
        line = f"• {period_emoji}*{name}* (deadline was at {deadline})"
    else:
        line = f"• {period_emoji}*{name}*"
        if deadline:
            line += f" (by {deadline})"

    return line


def format_reminder_message():
    """Format reminder message."""
    riga = pytz.timezone("Europe/Riga")
    today = datetime.datetime.now(riga)
    current_time = today.strftime("%H:%M")
    date_str = today.strftime("%d %B (%A)")

    incomplete_tasks, overdue_tasks = get_incomplete_tasks()

    # If no tasks to remind about
    if not incomplete_tasks and not overdue_tasks:
        return None

    message_parts = []

    # Header
    header = f"⏰ Reminder at {current_time} - {date_str}"
    message_parts.append(header)

    # Overdue tasks
    if overdue_tasks:
        message_parts.append("\n🚨 *OVERDUE TASKS:*")

        # Group overdue tasks
        grouped_overdue = group_tasks_by_period(overdue_tasks)

        for task in grouped_overdue["ungrouped"]:
            message_parts.append(format_reminder_task_line(task, is_overdue=True))
        for task in grouped_overdue["morning"]:
            message_parts.append(format_reminder_task_line(task, is_overdue=True))
        for task in grouped_overdue["evening"]:
            message_parts.append(format_reminder_task_line(task, is_overdue=True))

    # Other incomplete tasks
    if incomplete_tasks:
        message_parts.append("\n📋 *INCOMPLETE TASKS:*")

        # Group incomplete tasks
        grouped_incomplete = group_tasks_by_period(incomplete_tasks)

        for task in grouped_incomplete["ungrouped"]:
            message_parts.append(format_reminder_task_line(task))
        for task in grouped_incomplete["morning"]:
            message_parts.append(format_reminder_task_line(task))
        for task in grouped_incomplete["evening"]:
            message_parts.append(format_reminder_task_line(task))

    # Add team tag at the end
    message_parts.append(f"\n{Config.TEAM_MENTION}")

    return "\n".join(message_parts)


def send_reminder():
    """Send reminder to Slack."""
    message = format_reminder_message()

    if not message:
        print(f"ℹ️ {MESSAGE_TEMPLATES['no_reminder_tasks']}")
        return False

    # Get thread_ts for current day
    thread_ts = get_thread_ts(debug_mode=False)

    try:
        if thread_ts:
            # Send in thread with daily tasks
            response = client.chat_postMessage(
                channel=CHANNEL_ID, text=message, thread_ts=thread_ts
            )
            print(f"✅ Reminder sent to thread")
        else:
            # If no active thread, send as separate message
            response = client.chat_postMessage(channel=CHANNEL_ID, text=message)
            print(f"✅ Reminder sent as separate message")

        return True

    except Exception as e:
        print(f"❌ Error sending reminder: {e}")
        return False


if __name__ == "__main__":
    # Check if it's a working day
    today = datetime.datetime.now()
    if today.weekday() < 5:  # Only working days
        current_time = today.strftime("%H:%M")
        print(f"⏰ Running reminder at {current_time}")
        send_reminder()
    else:
        print(MESSAGE_TEMPLATES["weekend_skip"])
