import datetime
import json
import re
from typing import Any, Dict, Optional

import pytz
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from config import Config
from constants import (
    DEBUG_PREFIX,
    LOG_MESSAGES,
    MESSAGE_TEMPLATES,
    COMMAND_HELP,
    MODAL_TEXT,
)
from redis_bot import (
    find_employee_by_username,
    find_task_by_pattern,
    find_task_in_text,
    generate_message_blocks,
    generate_message_from_redis,
    generate_weekly_message_blocks,
    generate_weekly_message_from_redis,
    get_completed_tasks,
    get_task_deadlines,
    get_tasks_for_day,
    get_thread_ts,
    get_week_dates,
    get_week_monday,
    get_weekly_duty_assignments,
    record_task,
    set_task_assignment,
    set_thread_ts,
    set_weekly_duty_assignment,
    validate_employee_for_duty,
)

# Setup logging and validate config
logger = Config.setup_logging()
Config.validate_required_env_vars()

# IMPORTANT: Use Bot Token for App, App Token for Socket Mode
app = App(token=Config.SLACK_BOT_TOKEN)


def generate_debug_message(day_override: Optional[str] = None, is_monday: bool = False):
    """
    Generate message for debug mode with Block Kit support.

    Args:
        day_override: Override day name (e.g., "Monday")
        is_monday: If True, generate weekly message with duties

    Returns:
        Dict with 'text' and 'blocks' for Block Kit format
    """
    try:
        if is_monday:
            # Generate weekly message with duty assignments
            message_data = generate_weekly_message_blocks(debug_mode=True)
            logger.info("Generated debug weekly message (Monday)")
        else:
            # Generate regular daily message
            message_data = generate_message_blocks(
                day_override=day_override, debug_mode=True
            )
            logger.info(f"Generated debug daily message (day_override={day_override})")

        # Check for empty message
        message_text = message_data.get("text", "")
        if (
            MESSAGE_TEMPLATES["no_tasks_today"] in message_text
            or MESSAGE_TEMPLATES["no_regular_tasks"] in message_text
        ):
            logger.warning("Tasks not found in Redis, using fallback logic")

        return message_data
    except Exception as e:
        logger.error(f"Error generating debug message: {e}")
        fallback = f"❌ {MESSAGE_TEMPLATES['error_debug_message']}"
        return {
            "text": fallback,
            "blocks": [
                {"type": "section", "text": {"type": "mrkdwn", "text": fallback}}
            ],
        }


@app.event("app_mention")
def handle_task_update(event: Dict[str, Any], say, client) -> None:
    """Handle app mentions for task completion and debug commands."""
    try:
        logger.info(f"Bot mentioned: {event.get('user')} - {event.get('text', '')}")

        text = event.get("text", "")
        user = event.get("user")
        thread_ts = event.get("thread_ts") or event.get("ts")
        riga = pytz.timezone(Config.TIMEZONE)
        ts = datetime.datetime.now(riga)

        # Debug command to simulate cron task
        if "debug" in text.lower():
            try:
                debug_text = text.lower()

                # Detect debug mode type
                is_monday = "monday" in debug_text or "weekly" in debug_text
                day_override = None

                if "monday" in debug_text:
                    day_override = "Monday"
                elif "tuesday" in debug_text:
                    day_override = "Tuesday"
                elif "wednesday" in debug_text:
                    day_override = "Wednesday"
                elif "thursday" in debug_text:
                    day_override = "Thursday"
                elif "friday" in debug_text:
                    day_override = "Friday"

                # Generate appropriate message
                message_data = generate_debug_message(
                    day_override=day_override, is_monday=is_monday
                )

                # Create new message with tasks
                response = client.chat_postMessage(
                    channel=Config.SLACK_CHANNEL_ID,
                    text=message_data["text"],
                    blocks=message_data.get("blocks"),
                )
                message_ts = response["ts"]
                set_thread_ts(message_ts, debug_mode=True)

                # Pin Monday debug messages
                if is_monday:
                    try:
                        client.pins_add(
                            channel=Config.SLACK_CHANNEL_ID, timestamp=message_ts
                        )
                        logger.info(f"📌 Debug Monday message pinned: {message_ts}")
                    except Exception as pin_error:
                        logger.warning(
                            f"⚠️ Could not pin debug Monday message: {pin_error}"
                        )

                # Determine what was sent
                message_type = (
                    "weekly (Monday)"
                    if is_monday
                    else f"daily ({day_override or 'today'})"
                )

                say(
                    text=f"<@{user}> sent debug message: {message_type}",
                    thread_ts=message_ts,  # In the thread of the new message
                )
                logger.info(LOG_MESSAGES["debug_message_sent"].format(user=user, message_type=message_type))
                return

            except Exception as e:
                logger.error(f"Error handling debug command: {e}")
                # Reply in original thread
                say(
                    text=f"<@{user}> ❌ {MESSAGE_TEMPLATES['error_debug_message']}",
                    thread_ts=thread_ts,
                )
                return

        # Determine debug mode by thread_ts
        debug_mode = False
        production_thread_ts = get_thread_ts(debug_mode=False)
        debug_thread_ts = get_thread_ts(debug_mode=True)

        if thread_ts == debug_thread_ts:
            debug_mode = True
            logger.info(LOG_MESSAGES["debug_mode_enabled"])
        elif thread_ts == production_thread_ts:
            debug_mode = False
            logger.info(LOG_MESSAGES["production_mode_enabled"])
        else:
            # If not in known thread, use production by default
            debug_mode = False
            # Use production thread_ts for reply
            if production_thread_ts:
                thread_ts = production_thread_ts
            logger.info(LOG_MESSAGES["default_mode_enabled"])

        task = find_task_in_text(text)
        if task:
            ok, msg = record_task(task, user, debug_mode=debug_mode)
            if not ok:
                say(text=f"<@{user}> {msg}", thread_ts=thread_ts)
                return

            # Check deadlines
            task_deadlines = get_task_deadlines()
            deadline = task_deadlines.get(task)

            if deadline:
                deadline_dt = riga.localize(
                    datetime.datetime.combine(ts.date(), deadline)
                )
                logger.info(
                    f"⏱️ Now: {ts.strftime('%H:%M:%S')} | Deadline for {task}: {deadline_dt.strftime('%H:%M:%S')}"
                )

                if ts > deadline_dt:
                    prefix = DEBUG_PREFIX if debug_mode else ""
                    delay_minutes = int((ts - deadline_dt).total_seconds() / 60)
                    if delay_minutes < 60:
                        delay_text = f"{delay_minutes} min"
                    else:
                        delay_hours = delay_minutes // 60
                        delay_text = f"{delay_hours}h {delay_minutes % 60}min"

                    say(
                        text=f"{prefix}<@{user}> ⚠️ {task} {MESSAGE_TEMPLATES['marked_as_completed']} (delay: {delay_text})",
                        thread_ts=thread_ts,
                    )
                else:
                    client.reactions_add(
                        channel=event["channel"],
                        timestamp=event["ts"],
                        name="white_check_mark",
                    )
            else:
                # Tasks without deadline - just checkmark
                client.reactions_add(
                    channel=event["channel"],
                    timestamp=event["ts"],
                    name="white_check_mark",
                )
        else:
            prefix = DEBUG_PREFIX if debug_mode else ""
            say(
                text=f"{prefix}<@{user}> {MESSAGE_TEMPLATES['task_not_understood']}",
                thread_ts=thread_ts,
            )

    except Exception as e:
        logger.error(f"Error in handle_task_update: {e}")
        try:
            say(
                text=f"<@{user}> ❌ {MESSAGE_TEMPLATES['error_processing_command']}",
                thread_ts=thread_ts,
            )
        except:
            logger.error("Failed to send error message to user")


@app.command("/set-duty")
def handle_set_duty(ack, command, say, client):
    """Handle /set-duty command for weekly duty assignments."""
    ack()

    try:
        user_name = command.get("user_name", "")
        text = command.get("text", "").strip()

        logger.info(f"set-duty: user={user_name}, text='{text}'")

        # Parse command: /set-duty <duty-type> <@username> <week>
        # or: /set-duty <duty-type> <week> (to clear assignment)
        parts = text.split()

        if len(parts) < 2:
            say(COMMAND_HELP["set_duty_usage"])
            return

        duty_type = parts[0].lower()

        # Validate duty type
        if duty_type not in Config.DUTY_TYPES:
            say(
                COMMAND_HELP["set_duty_invalid_type"].format(
                    duty_type=duty_type, types=", ".join(Config.DUTY_TYPES.keys())
                )
            )
            return

        duty_name = Config.DUTY_TYPES[duty_type]

        # Check if this is an assignment or removal
        if len(parts) == 3:
            # Assignment: /set-duty fin @username current
            username_part = parts[1]
            week_input = parts[2]

            # Extract username
            target_username = username_part.lstrip("@").strip()

            # Find user in database
            slack_user_id = find_employee_by_username(target_username)

            if not slack_user_id:
                say(COMMAND_HELP["set_duty_user_not_found"].format(username=target_username))
                return

            # Get week Monday
            week_monday = get_week_monday(week_input)

            if not week_monday:
                say(COMMAND_HELP["set_duty_invalid_week"].format(week_input=week_input))
                return

            # Validate employee for duty
            is_valid, error_msg = validate_employee_for_duty(slack_user_id, week_monday)

            if not is_valid:
                say(COMMAND_HELP["set_duty_validation_failed"].format(error_msg=error_msg))
                return

            # Assign duty
            if set_weekly_duty_assignment(duty_name, week_monday, slack_user_id):
                say(
                    COMMAND_HELP["set_duty_assigned"].format(
                        user_id=slack_user_id, duty_name=duty_name, week_monday=week_monday
                    )
                )

                # If changing current week, post notification in Monday thread
                if week_input.lower() == "current":
                    try:
                        thread_ts = get_thread_ts(debug_mode=False)
                        if thread_ts:
                            # Check if this is current week's Monday message
                            today = datetime.datetime.now()
                            current_week_monday = get_week_monday("current")
                            week_dates = get_week_dates(current_week_monday)

                            # Only post if we're in the same week
                            if week_dates and today.strftime("%d/%m") in week_dates:
                                notification = COMMAND_HELP["set_duty_change_notification"].format(
                                    user_id=slack_user_id, duty_name=duty_name
                                )
                                client.chat_postMessage(
                                    channel=Config.SLACK_CHANNEL_ID,
                                    text=notification,
                                    thread_ts=thread_ts,
                                )
                                logger.info(
                                    f"Posted duty change notification to thread {thread_ts}"
                                )
                    except Exception as e:
                        logger.warning(f"Could not post thread notification: {e}")
            else:
                say("❌ Error assigning duty")

        elif len(parts) == 2:
            # Removal: /set-duty fin current
            week_input = parts[1]

            # Get week Monday
            week_monday = get_week_monday(week_input)

            if not week_monday:
                say(COMMAND_HELP["set_duty_invalid_week"].format(week_input=week_input))
                return

            # Remove assignment
            if set_weekly_duty_assignment(duty_name, week_monday, None):
                say(COMMAND_HELP["set_duty_removed"].format(duty_name=duty_name, week_monday=week_monday))

                # If changing current week, post notification in Monday thread
                if week_input.lower() == "current":
                    try:
                        thread_ts = get_thread_ts(debug_mode=False)
                        if thread_ts:
                            # Check if this is current week's Monday message
                            today = datetime.datetime.now()
                            current_week_monday = get_week_monday("current")
                            week_dates = get_week_dates(current_week_monday)

                            # Only post if we're in the same week
                            if week_dates and today.strftime("%d/%m") in week_dates:
                                notification = COMMAND_HELP["set_duty_removal_notification"].format(
                                    duty_name=duty_name
                                )
                                client.chat_postMessage(
                                    channel=Config.SLACK_CHANNEL_ID,
                                    text=notification,
                                    thread_ts=thread_ts,
                                )
                                logger.info(
                                    f"Posted duty removal notification to thread {thread_ts}"
                                )
                    except Exception as e:
                        logger.warning(f"Could not post thread notification: {e}")
            else:
                say("❌ Error removing assignment")

        else:
            say(COMMAND_HELP["set_duty_usage"])

    except Exception as e:
        logger.error(f"Error in handle_set_duty: {e}")
        say(f"❌ {MESSAGE_TEMPLATES['error_processing_command']}")


@app.action("open_task_completion_modal")
def handle_open_modal(ack, body, client):
    """Handle button click to open task completion modal."""
    ack()

    try:
        # Determine debug mode from the message thread
        message_ts = body.get("message", {}).get("ts")
        debug_mode = False

        # Check if message is in debug thread
        debug_thread_ts = get_thread_ts(debug_mode=True)
        if message_ts == debug_thread_ts:
            debug_mode = True
            logger.info(LOG_MESSAGES["modal_opened_debug"])
        else:
            logger.info(LOG_MESSAGES["modal_opened_production"])

        # Get current day's tasks
        today = datetime.datetime.now()
        day_name = today.strftime("%A")
        tasks = get_tasks_for_day(day_name)

        # Filter out duty tasks
        regular_tasks = [t for t in tasks if t.get("type") != "duty"]

        # Get already completed tasks
        completed_tasks = get_completed_tasks(debug_mode=debug_mode)
        completed_names = [name.upper() for name in completed_tasks.keys()]

        # Build checkbox options
        options = []
        for task in regular_tasks:
            task_name = task.get("name", "")
            task_name_upper = task_name.upper()
            deadline = task.get("deadline", "")

            # Skip already completed tasks
            if task_name_upper in completed_names:
                continue

            # Format task display
            if deadline:
                display_text = f"*{task_name}* by {deadline}"
            else:
                display_text = f"*{task_name}*"

            options.append(
                {
                    "text": {"type": "mrkdwn", "text": display_text},
                    "value": task_name_upper,
                }
            )

        # If no tasks available
        if not options:
            options.append(
                {
                    "text": {
                        "type": "plain_text",
                        "text": MODAL_TEXT["all_completed"],
                    },
                    "value": "none",
                }
            )

        # Create modal view
        modal_title = MODAL_TEXT["title_debug"] if debug_mode else MODAL_TEXT["title"]
        modal_view = {
            "type": "modal",
            "callback_id": "task_completion_submit",
            "title": {"type": "plain_text", "text": modal_title},
            "submit": {"type": "plain_text", "text": MODAL_TEXT["submit"]},
            "close": {"type": "plain_text", "text": MODAL_TEXT["cancel"]},
            "private_metadata": str(
                debug_mode
            ),  # Pass debug mode to submission handler
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": MODAL_TEXT["select_label"]},
                },
                {
                    "type": "input",
                    "block_id": "task_selection",
                    "optional": True,
                    "element": {
                        "type": "checkboxes",
                        "action_id": "selected_tasks",
                        "options": options,
                    },
                    "label": {"type": "plain_text", "text": MODAL_TEXT["tasks_label"]},
                },
            ],
        }

        # Open modal
        client.views_open(trigger_id=body["trigger_id"], view=modal_view)
        logger.info(LOG_MESSAGES["task_completion_modal_opened"])

    except Exception as e:
        logger.error(f"Error opening modal: {e}")


@app.view("task_completion_submit")
def handle_modal_submission(ack, body, client, view):
    """Handle modal submission with selected tasks."""
    ack()

    try:
        user_id = body["user"]["id"]

        # Get debug mode from private_metadata
        debug_mode = view.get("private_metadata", "False") == "True"
        log_msg = LOG_MESSAGES["modal_submission_debug"] if debug_mode else LOG_MESSAGES["modal_submission_production"]
        logger.info(log_msg)

        # Get selected tasks
        values = view["state"]["values"]
        task_selection = values.get("task_selection", {}).get("selected_tasks", {})
        selected_options = task_selection.get("selected_options", [])

        if not selected_options:
            logger.info("No tasks selected")
            return

        # Get timezone
        riga = pytz.timezone(Config.TIMEZONE)
        now = datetime.datetime.now(riga)

        # Get deadlines
        task_deadlines = get_task_deadlines()

        # Get thread_ts
        thread_ts = get_thread_ts(debug_mode=debug_mode)

        # Process each selected task
        completed_tasks = []
        late_tasks = []

        for option in selected_options:
            task_name = option["value"]

            if task_name == "none":
                continue

            ok, msg = record_task(task_name, user_id, debug_mode=debug_mode)

            if ok:
                completed_tasks.append(task_name)

                # Check deadline
                deadline = task_deadlines.get(task_name)
                if deadline:
                    deadline_dt = riga.localize(
                        datetime.datetime.combine(now.date(), deadline)
                    )

                    if now > deadline_dt:
                        delay_minutes = int((now - deadline_dt).total_seconds() / 60)
                        if delay_minutes < 60:
                            delay_text = f"{delay_minutes} min"
                        else:
                            delay_hours = delay_minutes // 60
                            delay_text = f"{delay_hours}h {delay_minutes % 60}min"
                        late_tasks.append(f"• {task_name} (delay: {delay_text})")

        # Send confirmation message
        if completed_tasks:
            if thread_ts:
                debug_prefix = DEBUG_PREFIX if debug_mode else ""

                confirmation = (
                    f"{debug_prefix}<@{user_id}> {MESSAGE_TEMPLATES['marked_as_completed']} tasks:\n• "
                    + "\n• ".join(completed_tasks)
                    + " ✅"
                )

                if late_tasks:
                    confirmation += f"\n\n⚠️ *{MESSAGE_TEMPLATES['completed_late']}:*\n" + "\n".join(
                        late_tasks
                    )

                client.chat_postMessage(
                    channel=Config.SLACK_CHANNEL_ID,
                    text=confirmation,
                    thread_ts=thread_ts,
                )

    except Exception as e:
        logger.error(f"Error handling modal submission: {e}")


if __name__ == "__main__":
    SocketModeHandler(app, Config.SLACK_APP_TOKEN).start()
