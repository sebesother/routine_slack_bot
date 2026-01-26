"""
Constants and translations for the Slack bot.

This module contains all text constants, day names, period labels,
and other static data used throughout the application.
"""

# Weekday names mapping (English only)
WEEKDAY_NAMES_EN = {
    "Monday": "Monday",
    "Tuesday": "Tuesday",
    "Wednesday": "Wednesday",
    "Thursday": "Thursday",
    "Friday": "Friday",
    "Saturday": "Saturday",
    "Sunday": "Sunday",
}

# Short weekday names (lowercase for day filtering in tasks)
WEEKDAY_NAMES_LOWER = {
    "monday": "Monday",
    "tuesday": "Tuesday",
    "wednesday": "Wednesday",
    "thursday": "Thursday",
    "friday": "Friday",
}

# Period labels for task grouping
PERIOD_LABELS = {
    "morning": "Morning",
    "evening": "Evening (done after 3:00 PM)",
}

# Period emoji
PERIOD_EMOJI = {
    "morning": "🌅 ",
    "evening": "🌙 ",
}

# Special date type emoji and messages
SPECIAL_DATE_CONFIG = {
    "christmas": {
        "emoji": "🎄✨",
        "greeting_template": "Happy Holidays! {description}!",
        "notice": "⚠️ _Note: Working on a holiday, staff may be reduced_",
    },
    "new_year": {
        "emoji": "🎆❄️",
        "greeting_template": "Happy New Year! {description}!",
        "notice": "⚠️ _Note: Working on a holiday, processing speed may be reduced_",
    },
    "default": {
        "emoji": "⚡",
        "greeting_template": "Special day: {description}",
        "notice": "⚠️ _Note: Special working mode_",
    },
}

# Message templates
MESSAGE_TEMPLATES = {
    "no_tasks_today": "_No tasks for today_",
    "no_regular_tasks": "_No regular tasks for today_",
    "all_tasks_completed": "All tasks already completed ✓",
    "task_already_completed": "This task was already marked as completed earlier.",
    "old_state_no_thread": "Old state - new morning, no active thread.",
    "redis_fallback": "No tasks found in Redis, check database",
    "weekend_skip": "Today is a weekend, tasks are not sent",
    "no_reminder_tasks": "No tasks to remind about",
    "error_processing_command": "Error processing command",
    "error_debug_message": "Error sending debug message",
    "marked_as_completed": "marked as completed",
    "completed_late": "Completed with delay",
    "task_not_understood": "I didn't understand which task you're referring to 🤔. Try writing, for example: `@bot LPB done`",
}

# Command help messages
COMMAND_HELP = {
    "set_duty_usage": (
        "❌ Invalid command format\n"
        "Usage:\n"
        "• `/set-duty <duty-type> @username <week>` - assign\n"
        "• `/set-duty <duty-type> <week>` - remove assignment\n\n"
        "Duty types: fin, asana, tg, notification, supervision\n"
        "Week: current, next, or dd/mm (Monday date)"
    ),
    "set_duty_invalid_type": "❌ Unknown duty type: `{duty_type}`\nAvailable types: {types}",
    "set_duty_user_not_found": "❌ Employee with username '{username}' not found in database",
    "set_duty_invalid_week": "❌ Could not determine week from '{week_input}'\nUse: current, next, or dd/mm",
    "set_duty_validation_failed": "❌ {error_msg}",
    "set_duty_assigned": "✅ User <@{user_id}> assigned to *{duty_name}* for week {week_monday}",
    "set_duty_removed": "✅ Assignment removed from *{duty_name}* for week {week_monday}",
    "set_duty_change_notification": "📝 *Duty change:*\n<@{user_id}> assigned to *{duty_name}*",
    "set_duty_removal_notification": "📝 *Duty change:*\nAssignment removed from *{duty_name}*",
}

# Modal UI text
MODAL_TEXT = {
    "title": "Mark tasks",
    "title_debug": "🔧 DEBUG: Mark tasks",
    "submit": "Done",
    "cancel": "Cancel",
    "select_label": "Select completed tasks:",
    "tasks_label": "Tasks",
    "all_completed": "All tasks already completed ✓",
    "button_label": "✅ Mark completed",
}

# Remote work modal UI text
REMOTE_MODAL_TEXT = {
    "title": "Mark Remote Days",
    "title_debug": "🔧 DEBUG: Mark Remote Days",
    "submit": "Set Remote Days",
    "cancel": "Cancel",
    "select_label": "Select remote work days for *next week* (max 2):",
    "days_label": "Days",
    "button_label": "🏠 Mark Remote Days",
    "info_text": "_You can select up to 2 days for remote work next week (Monday-Friday)_",
}

# Debug mode prefixes
DEBUG_PREFIX = "🔧 DEBUG: "

# Log messages
LOG_MESSAGES = {
    "bot_mentioned": "Bot mentioned: {user} - {text}",
    "debug_mode_enabled": "🔧 DEBUG MODE: using debug_routine_state",
    "production_mode_enabled": "📋 PRODUCTION MODE: using slack_routine_state",
    "default_mode_enabled": "📋 DEFAULT MODE: using slack_routine_state",
    "debug_message_sent": "Debug message sent by user {user}: {message_type}",
    "modal_opened_debug": "Modal opened in DEBUG mode",
    "modal_opened_production": "Modal opened in PRODUCTION mode",
    "task_completion_modal_opened": "Task completion modal opened",
    "modal_submission_debug": "Modal submission in DEBUG mode",
    "modal_submission_production": "Modal submission in PRODUCTION mode",
    "remote_modal_opened": "Remote days modal opened",
    "remote_modal_submission": "Remote days set by user {user}",
}
