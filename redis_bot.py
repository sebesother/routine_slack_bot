import datetime
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import redis

from config import Config

# Setup logging
logger = logging.getLogger(__name__)

# Redis connection with error handling
try:
    r = redis.Redis.from_url(Config.REDIS_URL)
    # Test connection
    r.ping()
    logger.info("Successfully connected to Redis")
except redis.ConnectionError as e:
    logger.error(f"Failed to connect to Redis: {e}")
    raise
except Exception as e:
    logger.error(f"Unexpected error connecting to Redis: {e}")


def load_state(debug_mode: bool = False) -> Dict[str, Any]:
    """Load routine state (normal or debug mode)."""
    try:
        key = Config.DEBUG_ROUTINE_STATE if debug_mode else Config.SLACK_ROUTINE_STATE
        data = r.get(key)
        if data:
            try:
                return json.loads(data)
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing JSON from Redis key '{key}': {e}")
                logger.error(f"Corrupted data: {data[:200]}")  # Log first 200 chars
                # Return empty state to allow system to continue
                return {}
        return {}
    except redis.RedisError as e:
        logger.error(f"Redis error loading state (debug_mode={debug_mode}): {e}")
        return {}


def save_state(state: Dict[str, Any], debug_mode: bool = False) -> bool:
    """Save routine state (normal or debug mode)."""
    try:
        key = Config.DEBUG_ROUTINE_STATE if debug_mode else Config.SLACK_ROUTINE_STATE
        # Ensure state is serializable
        json_data = json.dumps(state, ensure_ascii=False, indent=2)
        r.set(key, json_data)
        logger.debug(f"State saved successfully to '{key}' (debug_mode={debug_mode})")
        return True
    except (redis.RedisError, TypeError, ValueError) as e:
        logger.error(f"Error saving state to '{key}' (debug_mode={debug_mode}): {e}")
        logger.error(f"State data: {state}")
        return False


def load_task_base() -> Dict[str, Any]:
    """Load task base from Redis."""
    try:
        data = r.get(Config.TASK_BASE)
        if data:
            return json.loads(data)
        logger.warning("Task base is empty or not found")
        return {}
    except (redis.RedisError, json.JSONDecodeError) as e:
        logger.error(f"Error loading task base: {e}")
        return {}


def save_task_base(task_base: Dict[str, Any]) -> bool:
    """Save task base to Redis."""
    try:
        r.set(Config.TASK_BASE, json.dumps(task_base))
        logger.debug("Task base saved successfully")
        return True
    except (redis.RedisError, json.JSONDecodeError) as e:
        logger.error(f"Error saving task base: {e}")
        return False


def set_thread_ts(thread_ts, debug_mode=False):
    """Set thread_ts for a new day."""
    state = load_state(debug_mode)
    state["date"] = datetime.date.today().isoformat()
    state["thread_ts"] = thread_ts
    state["completed"] = {}
    save_state(state, debug_mode)


def get_thread_ts(debug_mode=False):
    """Get current thread_ts."""
    state = load_state(debug_mode)
    return state.get("thread_ts")


def record_task(task, user, debug_mode=False):
    """Record completed task."""
    state = load_state(debug_mode)
    today = datetime.date.today().isoformat()

    if state.get("date") != today:
        return False, "Старое состояние — новое утро, нет активного треда."

    if "completed" not in state:
        state["completed"] = {}

    if task in state["completed"]:
        return False, "Эта задача уже была отмечена ранее."

    now = datetime.datetime.now().strftime("%H:%M")
    state["completed"][task] = {"user": user, "time": now}
    save_state(state, debug_mode)
    return True, None


def get_completed_tasks(debug_mode=False):
    """Get list of completed tasks."""
    state = load_state(debug_mode)
    return state.get("completed", {})


def get_tasks_for_day(day_name):
    """Get tasks for a specific day of the week from task_base."""
    task_base = load_task_base()

    if not task_base:
        return []

    tasks = []
    for task_id, task_data in task_base.items():
        # Check if task should be executed on this day
        task_days = task_data.get("days", "all")
        if task_days == "all" or day_name.lower() in task_days.lower():
            # Add task ID to the data
            task_with_id = task_data.copy()
            task_with_id["id"] = task_id
            tasks.append(task_with_id)

    # Sort by deadline time
    tasks.sort(key=lambda x: x.get("deadline", "23:59"))
    return tasks


def format_task_line(task):
    """Format task line for Slack with assignments."""
    name = task.get("name", "")
    deadline = task.get("deadline", "")
    asana_url = task.get("asana_url", "")
    comments = task.get("comments", "")

    # Check if there's an assigned user for this task
    assigned_user = get_task_assignment(name)

    # Base line with checkbox and assigned user
    if assigned_user:
        # If there's an assigned user, add them at the beginning
        if deadline:
            task_line = f"- [<@{assigned_user}>] *{name}* до {deadline}"
        else:
            task_line = f"- [<@{assigned_user}>] *{name}*"
    else:
        # Regular line without assignment
        if deadline:
            task_line = f"- [ ] *{name}* до {deadline}"
        else:
            task_line = f"- [ ] *{name}*"

    # Add Asana link in Slack-specific format
    if asana_url:
        task_line += f" • <{asana_url}|Asana>"

    # Add comments at the end of the line with indentation
    if comments:
        task_line += f"     _{comments}_"

    return task_line


def generate_message_from_redis(day_override=None, debug_mode=False):
    """Generate Slack message based on Redis data with grouping and employees."""
    today = datetime.datetime.now()

    if day_override:
        day_name = day_override.capitalize()
        # For day_override use current date in dd/mm format
        current_date = today.strftime("%d/%m")
    else:
        day_name = today.strftime("%A")
        current_date = today.strftime("%d/%m")

    # Get tasks for the day (filter out duty tasks for regular daily messages)
    tasks = get_tasks_for_day(day_name)
    tasks = [t for t in tasks if t.get("type") != "duty"]

    # Form header with new format
    debug_prefix = "🔧 DEBUG: " if debug_mode else ""
    today_full = today.strftime("%d/%m/%Y")
    day_name_ru = {
        "Monday": "понедельник",
        "Tuesday": "вторник",
        "Wednesday": "среда",
        "Thursday": "четверг",
        "Friday": "пятница",
    }.get(day_name, day_name)

    header = f"{debug_prefix}🎓 Сегодня {today_full} ({day_name_ru})"

    # Check if this is a special date
    special_info = check_special_date(current_date)
    if special_info:
        header += get_special_date_header(special_info)

    # If no tasks
    if not tasks:
        return header + "\n\n_Нет задач на сегодня_"

    # Group tasks
    grouped_tasks = group_tasks_by_period(tasks)

    message_parts = [header]

    # First show tasks without group
    if grouped_tasks["ungrouped"]:
        message_parts.append("")  # Empty line for spacing
        for task in grouped_tasks["ungrouped"]:
            message_parts.append(format_task_line(task))

    # Then morning tasks
    if grouped_tasks["morning"]:
        # Get employees for morning shift
        morning_employees = get_employees_for_date_and_period(current_date, "morning")
        employees_mention = format_employees_mention(morning_employees)

        if employees_mention:
            message_parts.append(f"\n*Утро*:\n{employees_mention}")
        else:
            message_parts.append("\n*Утро*:")

        for task in grouped_tasks["morning"]:
            message_parts.append(format_task_line(task))

    # Then evening tasks
    if grouped_tasks["evening"]:
        # Get employees for evening shift
        evening_employees = get_employees_for_date_and_period(current_date, "evening")
        employees_mention = format_employees_mention(evening_employees)

        if employees_mention:
            message_parts.append(
                f"\n*Вечер* _(делается после 15:00)_:\n{employees_mention}"
            )
        else:
            message_parts.append("\n*Вечер*:")

        for task in grouped_tasks["evening"]:
            message_parts.append(format_task_line(task))

    return "\n".join(message_parts)


def generate_message_blocks(day_override=None, debug_mode=False):
    """
    Generate Slack message in Block Kit format with interactive button.

    Returns dict with 'text' (fallback) and 'blocks' (Block Kit).
    """
    # Get regular text message
    message_text = generate_message_from_redis(day_override, debug_mode)

    # Create blocks with completion button
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": message_text}},
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✅ Отметить выполненные"},
                    "action_id": "open_task_completion_modal",
                    "style": "primary",
                }
            ],
        },
    ]

    return {"text": message_text, "blocks": blocks}


def generate_weekly_message_blocks(debug_mode=False):
    """
    Generate Monday's weekly message in Block Kit format with interactive button.

    Returns dict with 'text' (fallback) and 'blocks' (Block Kit).
    """
    # Get regular text message
    message_text = generate_weekly_message_from_redis(debug_mode)

    # Create blocks with completion button
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": message_text}},
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✅ Отметить выполненные"},
                    "action_id": "open_task_completion_modal",
                    "style": "primary",
                }
            ],
        },
    ]

    return {"text": message_text, "blocks": blocks}


def get_task_deadlines():
    """Get task deadlines for checking completion time."""
    task_base = load_task_base()
    deadlines = {}

    for task_id, task_data in task_base.items():
        deadline_str = task_data.get("deadline", "")
        if deadline_str:
            try:
                # Convert "HH:MM" string to time object
                hour, minute = map(int, deadline_str.split(":"))
                deadlines[task_data.get("name", "").upper()] = datetime.time(
                    hour=hour, minute=minute
                )
            except ValueError:
                # If unable to parse time, skip
                continue
        else:
            # Tasks without deadline
            deadlines[task_data.get("name", "").upper()] = None

    return deadlines


def get_task_names():
    """Get all task names for regex."""
    task_base = load_task_base()

    if not task_base:
        print("Скорее всего, Redis пуст")

    names = []
    for task_id, task_data in task_base.items():
        name = task_data.get("name", "")
        if name:
            names.append(name)

    return names


def build_task_regex():
    """Build regex pattern for finding tasks."""
    task_names = get_task_names()

    # Escape special characters in names (e.g., hyphens)
    escaped_names = [re.escape(name) for name in task_names]

    # Create pattern: (LPB|KYC-1|Проверка KYC-2|Statements - выгрузки).*done
    pattern = r"(?i)(" + "|".join(escaped_names) + r").*done"
    return pattern


def find_task_in_text(text):
    """Find task mention in text."""
    pattern = build_task_regex()
    match = re.search(pattern, text)

    if match:
        # Return found task name
        found_name = match.group(1)

        # Normalize name for deadline lookup
        # (convert to format used in get_task_deadline)
        normalized_name = found_name.upper()

        return normalized_name

    return None


def group_tasks_by_period(tasks):
    """Group tasks by periods (morning/evening)."""
    groups = {
        "ungrouped": [],  # Tasks without group
        "morning": [],  # Morning tasks
        "evening": [],  # Evening tasks
    }

    for task in tasks:
        period = task.get("period", "")
        if period == "morning":
            groups["morning"].append(task)
        elif period == "evening":
            groups["evening"].append(task)
        else:
            groups["ungrouped"].append(task)

    # Sort tasks in each group by deadline time
    for group_name in groups:
        groups[group_name].sort(key=lambda x: x.get("deadline", "23:59"))

    return groups


# Employees


def load_employees() -> Dict[str, Any]:
    """Load employee data from Redis."""
    try:
        data = r.get(Config.EMPLOYEES)
        if data:
            return json.loads(data)
        logger.warning("Employee data is empty or not found")
        return {}
    except (redis.RedisError, json.JSONDecodeError) as e:
        logger.error(f"Error loading employees: {e}")
        return {}


def save_employees(employees: Dict[str, Any]) -> bool:
    """Save employee data to Redis."""
    try:
        r.set(Config.EMPLOYEES, json.dumps(employees))
        logger.debug("Employees data saved successfully")
        return True
    except (redis.RedisError, json.JSONDecodeError) as e:
        logger.error(f"Error saving employees: {e}")
        return False


def get_employees_for_date_and_period(
    date_str: str, period: str
) -> List[Dict[str, str]]:
    """Get employees working on specified date and period."""
    employees = load_employees()
    working_employees = []

    for emp_id, emp_data in employees.items():
        name = emp_data.get("name", "")
        slack_id = emp_data.get("slack_id", "")

        # Get work dates for specified period
        if period == "morning":
            work_dates = emp_data.get("morning_dates", [])
        elif period == "evening":
            work_dates = emp_data.get("evening_dates", [])
        else:
            continue

        # Check if employee works on this date
        if date_str in work_dates:
            working_employees.append(
                {"name": name, "slack_id": slack_id, "employee_id": emp_id}
            )

    return working_employees


def format_employees_mention(employees: List[Dict[str, str]]) -> str:
    """Format employee mentions for Slack."""
    if not employees:
        return ""

    mentions = []
    for emp in employees:
        slack_id = emp.get("slack_id", "")
        if slack_id:
            mentions.append(f"<@{slack_id}>")
        else:
            # If no slack_id, use name
            mentions.append(emp.get("name", "Unknown"))

    return "[" + " + ".join(mentions) + "]"


def load_task_assignments() -> Dict[str, str]:
    """Load user assignments to tasks from employees."""
    try:
        employees_data = load_employees()
        # Assignments are stored in a special section of employees
        return employees_data.get("task_assignments", {})
    except Exception as e:
        logger.error(f"Error loading task assignments: {e}")
        return {}


def save_task_assignments(assignments: Dict[str, str]) -> bool:
    """Save user assignments to tasks in employees."""
    try:
        employees_data = load_employees()
        # Save assignments in a special section
        employees_data["task_assignments"] = assignments
        return save_employees(employees_data)
    except Exception as e:
        logger.error(f"Error saving task assignments: {e}")
        return False


def set_task_assignment(task_name: str, user_id: str = None) -> bool:
    """Assign or remove user from task."""
    assignments = load_task_assignments()

    # Normalize task name (convert to uppercase)
    task_key = task_name.upper()

    if user_id:
        # Assign user
        assignments[task_key] = user_id
        logger.info(f"User {user_id} assigned to task {task_name}")
    else:
        # Remove assignment
        if task_key in assignments:
            del assignments[task_key]
            logger.info(f"Assignment removed from task {task_name}")

    return save_task_assignments(assignments)


def get_task_assignment(task_name: str) -> str:
    """Get assigned user for task."""
    assignments = load_task_assignments()
    task_key = task_name.upper()
    return assignments.get(task_key, "")


def find_task_by_pattern(pattern: str) -> str:
    """Find task by pattern (e.g., fin-duty)."""
    task_base = load_task_base()

    pattern_lower = pattern.lower()
    for task_id, task_data in task_base.items():
        task_name = task_data.get("name", "").lower()
        if pattern_lower in task_name:
            return task_data.get("name", "")

    return ""


def find_employee_by_username(username: str) -> str:
    """Find employee's slack_id by username."""
    employees = load_employees()

    # Remove @ if present
    clean_username = username.lstrip("@").strip()

    for emp_id, emp_data in employees.items():
        if emp_id == "task_assignments":
            continue

        emp_username = emp_data.get("username", "")

        if emp_username == clean_username:
            slack_id = emp_data.get("slack_id", "")
            logger.info(
                f"Found employee {emp_data.get('name')} with slack_id {slack_id} for username {username}"
            )
            return slack_id

    logger.warning(f"Employee not found for username: {username}")
    return ""


# Special Dates Management


def get_special_dates() -> Dict[str, Dict[str, str]]:
    """Get all special dates from employees data."""
    employees_data = load_employees()
    return employees_data.get("special_dates", {})


def check_special_date(date_str: str) -> Optional[Dict[str, str]]:
    """
    Check if a date is marked as special.

    Args:
        date_str: Date in "dd/mm" format

    Returns:
        Dictionary with special date info or None
    """
    special_dates = get_special_dates()
    return special_dates.get(date_str)


def get_special_date_header(special_info: Dict[str, str]) -> str:
    """
    Generate special date header with emoji and greeting.

    Args:
        special_info: Dictionary with type and description

    Returns:
        Formatted header string
    """
    special_type = special_info.get("type", "")
    description = special_info.get("description", "")

    if special_type == "christmas":
        emoji = "🎄✨"
        greeting = f"С праздником! {description}!"
        notice = "⚠️ _Обратите внимание: работа в праздничный день, штат сотрудников может быть сокращен_"
    elif special_type == "new_year":
        emoji = "🎆❄️"
        greeting = f"С наступающим! {description}!"
        notice = "⚠️ _Обратите внимание: работа в праздничный день, скорость обработки может быть снижена_"
    else:
        emoji = "⚡"
        greeting = f"Особый день: {description}"
        notice = "⚠️ _Обратите внимание: особый режим работы_"

    return f"\n{emoji} *{greeting}*\n{notice}\n"


# Weekly Duty Management


def get_duty_tasks() -> List[Dict[str, Any]]:
    """Get all duty tasks from task_base."""
    task_base = load_task_base()
    duty_tasks = []

    for task_id, task_data in task_base.items():
        if task_data.get("type") == "duty":
            duty_task = task_data.copy()
            duty_task["id"] = task_id
            duty_tasks.append(duty_task)

    return duty_tasks


def get_week_monday(date_input: str) -> str:
    """
    Get Monday date for the specified week.

    Args:
        date_input: Can be:
            - "current" - current week's Monday
            - "next" - next week's Monday
            - "dd/mm" - date, returns Monday of that week

    Returns:
        Monday date in "dd/mm" format
    """
    import pytz

    from config import Config

    riga_tz = pytz.timezone(Config.TIMEZONE)
    today = datetime.datetime.now(riga_tz).date()

    if date_input == "current":
        # Get current week's Monday
        days_since_monday = today.weekday()
        monday = today - datetime.timedelta(days=days_since_monday)
    elif date_input == "next":
        # Get next week's Monday
        days_since_monday = today.weekday()
        monday = today + datetime.timedelta(days=(7 - days_since_monday))
    else:
        # Parse dd/mm format
        try:
            day, month = map(int, date_input.split("/"))
            year = today.year

            # If the date is in the past this year, assume next year
            input_date = datetime.date(year, month, day)
            if input_date < today:
                input_date = datetime.date(year + 1, month, day)

            # Get Monday of that week
            days_since_monday = input_date.weekday()
            monday = input_date - datetime.timedelta(days=days_since_monday)
        except (ValueError, AttributeError) as e:
            logger.error(f"Error parsing date {date_input}: {e}")
            return ""

    return monday.strftime("%d/%m")


def get_week_dates(monday_str: str) -> List[str]:
    """
    Get all weekday dates (Mon-Fri) for a week starting from Monday.

    Args:
        monday_str: Monday date in "dd/mm" format

    Returns:
        List of dates in "dd/mm" format
    """
    try:
        day, month = map(int, monday_str.split("/"))
        today = datetime.datetime.now().date()
        year = today.year

        # If the date is in the past this year, assume next year
        monday = datetime.date(year, month, day)
        if monday < today:
            monday = datetime.date(year + 1, month, day)

        # Generate Mon-Fri dates
        week_dates = []
        for i in range(5):  # Monday to Friday
            date = monday + datetime.timedelta(days=i)
            week_dates.append(date.strftime("%d/%m"))

        return week_dates
    except (ValueError, AttributeError) as e:
        logger.error(f"Error generating week dates from {monday_str}: {e}")
        return []


def validate_employee_for_duty(user_id: str, week_monday: str) -> Tuple[bool, str]:
    """
    Validate if employee can be assigned to duty for the specified week.

    Employee must have morning_dates for majority of weekdays (at least 3 out of 5).

    Args:
        user_id: Employee's slack_id
        week_monday: Monday date in "dd/mm" format

    Returns:
        Tuple of (is_valid, error_message)
    """
    employees = load_employees()
    week_dates = get_week_dates(week_monday)

    if not week_dates:
        return False, "Не удалось определить даты недели"

    # Find employee by slack_id
    employee = None
    for emp_id, emp_data in employees.items():
        if emp_id in ["task_assignments", "weekly_duty_assignments"]:
            continue
        if emp_data.get("slack_id") == user_id:
            employee = emp_data
            break

    if not employee:
        return False, "Сотрудник не найден в базе"

    morning_dates = employee.get("morning_dates", [])

    # Count how many weekdays the employee works
    working_days = sum(1 for date in week_dates if date in morning_dates)

    # Need at least 3 out of 5 days (majority)
    if working_days >= 3:
        return True, ""
    else:
        employee_name = employee.get("name", "Сотрудник")
        return (
            False,
            f"{employee_name} работает только {working_days} дней на этой неделе (нужно минимум 3)",
        )


def set_weekly_duty_assignment(
    duty_name: str, week_monday: str, user_id: Optional[str] = None
) -> bool:
    """
    Assign or remove user from weekly duty.

    Args:
        duty_name: Name of the duty (e.g., "FIN-DUTY")
        week_monday: Monday date in "dd/mm" format
        user_id: User's slack_id, or None to remove assignment

    Returns:
        True if successful, False otherwise
    """
    employees_data = load_employees()

    if "weekly_duty_assignments" not in employees_data:
        employees_data["weekly_duty_assignments"] = {}

    if week_monday not in employees_data["weekly_duty_assignments"]:
        employees_data["weekly_duty_assignments"][week_monday] = {}

    duty_key = duty_name.upper()

    if user_id:
        # Assign user
        employees_data["weekly_duty_assignments"][week_monday][duty_key] = user_id
        logger.info(f"User {user_id} assigned to {duty_name} for week {week_monday}")
    else:
        # Remove assignment
        if duty_key in employees_data["weekly_duty_assignments"][week_monday]:
            del employees_data["weekly_duty_assignments"][week_monday][duty_key]
            logger.info(f"Assignment removed from {duty_name} for week {week_monday}")

    return save_employees(employees_data)


def get_weekly_duty_assignments(week_monday: str) -> Dict[str, str]:
    """
    Get all duty assignments for a specific week.

    Args:
        week_monday: Monday date in "dd/mm" format

    Returns:
        Dictionary mapping duty names to user slack_ids
    """
    employees_data = load_employees()

    if "weekly_duty_assignments" not in employees_data:
        return {}

    return employees_data["weekly_duty_assignments"].get(week_monday, {})


def generate_weekly_message_from_redis(debug_mode: bool = False) -> str:
    """
    Generate Monday's weekly message with regular tasks and duty assignments.

    Args:
        debug_mode: Whether to use debug mode

    Returns:
        Formatted Slack message
    """
    import pytz

    from config import Config

    riga_tz = pytz.timezone(Config.TIMEZONE)
    today = datetime.datetime.now(riga_tz)

    day_name = today.strftime("%A")
    date_str = today.strftime("%d %B (%A)")
    current_date = today.strftime("%d/%m")

    # Get Monday of current week
    week_monday = get_week_monday("current")
    week_dates = get_week_dates(week_monday)

    # Get regular tasks for Monday
    tasks = get_tasks_for_day(day_name)
    # Filter out duty tasks
    regular_tasks = [t for t in tasks if t.get("type") != "duty"]

    # Get duty assignments for this week
    duty_assignments = get_weekly_duty_assignments(week_monday)
    duty_tasks = get_duty_tasks()

    # Form header
    debug_prefix = "🔧 DEBUG: " if debug_mode else ""
    message_parts = []

    # Weekly header with dates
    today_full = today.strftime("%d/%m/%Y")
    day_name_ru = {
        "Monday": "понедельник",
        "Tuesday": "вторник",
        "Wednesday": "среда",
        "Thursday": "четверг",
        "Friday": "пятница",
    }.get(day_name, day_name)

    if week_dates and len(week_dates) == 5:
        week_range = f"{week_dates[0]} - {week_dates[4]}"
        header = f"{debug_prefix}📅 Неделя {week_range}\n\n🎓 Сегодня {today_full} ({day_name_ru})"
    else:
        header = f"{debug_prefix}🎓 Сегодня {today_full} ({day_name_ru})"

    # Check if this is a special date
    special_info = check_special_date(current_date)
    if special_info:
        header += get_special_date_header(special_info)

    message_parts.append(header)

    # Duty assignments section
    if duty_tasks:
        message_parts.append("\n📋 Дежурства на неделю:")

        for duty in duty_tasks:
            duty_name = duty.get("name", "")
            duty_desc = duty.get("description", "")
            duty_key = duty_name.upper()

            assigned_user = duty_assignments.get(duty_key, "")

            if assigned_user:
                duty_line = f"• *{duty_name}* → <@{assigned_user}>"
            else:
                duty_line = f"• *{duty_name}* → _не назначено_"

            if duty_desc:
                duty_line += f"\n  _{duty_desc}_"

            message_parts.append(duty_line)

    # Regular tasks section
    if not regular_tasks:
        message_parts.append("\n_Нет обычных задач на сегодня_")
    else:
        message_parts.append("\n📝 Задачи на сегодня:")

        grouped_tasks = group_tasks_by_period(regular_tasks)

        # Tasks without group
        if grouped_tasks["ungrouped"]:
            for task in grouped_tasks["ungrouped"]:
                message_parts.append(format_task_line(task))

        # Morning tasks
        if grouped_tasks["morning"]:
            morning_employees = get_employees_for_date_and_period(
                current_date, "morning"
            )
            employees_mention = format_employees_mention(morning_employees)

            if employees_mention:
                message_parts.append(f"\n*Утро*:\n{employees_mention}")
            else:
                message_parts.append("\n*Утро*:")

            for task in grouped_tasks["morning"]:
                message_parts.append(format_task_line(task))

        # Evening tasks
        if grouped_tasks["evening"]:
            evening_employees = get_employees_for_date_and_period(
                current_date, "evening"
            )
            employees_mention = format_employees_mention(evening_employees)

            if employees_mention:
                message_parts.append(
                    f"\n*Вечер* _(делается после 15:00)_:\n{employees_mention}"
                )
            else:
                message_parts.append("\n*Вечер*:")

            for task in grouped_tasks["evening"]:
                message_parts.append(format_task_line(task))

    return "\n".join(message_parts)
