"""
Remote work management module.

This module handles remote work days tracking for employees.
Employees can mark up to 2 days per week as remote work days.
"""

import datetime
import logging
from typing import Any, Dict, List, Optional, Tuple

from redis_bot import load_employees, save_employees

# Setup logging
logger = logging.getLogger(__name__)


def get_next_monday() -> str:
    """
    Get the date of the next Monday in dd/mm format.
    
    Returns:
        str: Next Monday's date in dd/mm format (e.g., "03/02")
    """
    today = datetime.datetime.now()
    # Calculate days until next Monday
    days_ahead = 7 - today.weekday()  # 0 = Monday, so if today is Monday, we want next Monday
    if days_ahead <= 0:  # If today is Monday, get next Monday (7 days ahead)
        days_ahead += 7
    
    next_monday = today + datetime.timedelta(days=days_ahead)
    return next_monday.strftime("%d/%m")


def get_week_dates_from_monday(monday_str: str) -> List[str]:
    """
    Get all dates for a week (Monday to Friday) from a Monday date.
    
    Args:
        monday_str: Monday date in dd/mm format
        
    Returns:
        List of dates in dd/mm format for the week (Monday to Friday)
    """
    try:
        day, month = map(int, monday_str.split("/"))
        # Use current year
        year = datetime.datetime.now().year
        monday = datetime.datetime(year, month, day)
        
        # Generate Monday to Friday
        week_dates = []
        for i in range(5):  # Monday to Friday
            date = monday + datetime.timedelta(days=i)
            week_dates.append(date.strftime("%d/%m"))
        
        return week_dates
    except (ValueError, AttributeError) as e:
        logger.error(f"Error parsing Monday date '{monday_str}': {e}")
        return []


def get_remote_days_for_employee(employee_id: str) -> Dict[str, List[str]]:
    """
    Get remote days for a specific employee.
    
    Args:
        employee_id: Employee ID
        
    Returns:
        Dict mapping week Monday dates to list of remote work dates
        Example: {"03/02": ["04/02", "06/02"]}
    """
    employees = load_employees()
    
    if employee_id not in employees:
        logger.warning(f"Employee {employee_id} not found")
        return {}
    
    return employees[employee_id].get("remote_dates", {})


def get_remote_employees_for_date(date_str: str) -> List[Dict[str, str]]:
    """
    Get list of employees working remotely on a specific date.
    
    Args:
        date_str: Date in dd/mm format
        
    Returns:
        List of dicts with employee info: [{"name": "...", "slack_id": "...", "employee_id": "..."}]
    """
    employees = load_employees()
    remote_employees = []
    
    for emp_id, emp_data in employees.items():
        # Skip non-employee entries
        if not isinstance(emp_data, dict) or "name" not in emp_data:
            continue
            
        remote_dates = emp_data.get("remote_dates", {})
        
        # Check all weeks for this date
        for week_monday, dates in remote_dates.items():
            if date_str in dates:
                remote_employees.append({
                    "name": emp_data.get("name", ""),
                    "slack_id": emp_data.get("slack_id", ""),
                    "employee_id": emp_id
                })
                break  # Employee found, no need to check other weeks
    
    return remote_employees


def validate_remote_days_selection(selected_dates: List[str]) -> Tuple[bool, str]:
    """
    Validate remote days selection.
    
    Rules:
    1. Maximum 2 days per week
    2. Only Monday-Friday allowed
    
    Args:
        selected_dates: List of dates in dd/mm format
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if len(selected_dates) > 2:
        return False, "❌ You can select maximum 2 remote days per week"
    
    if len(selected_dates) == 0:
        return False, "❌ Please select at least one day"
    
    return True, ""


def set_remote_days_for_employee(
    employee_id: str, 
    slack_user_id: str, 
    week_monday: str, 
    remote_dates: List[str]
) -> Tuple[bool, str]:
    """
    Set remote work days for an employee for a specific week.
    
    Args:
        employee_id: Employee ID (string number like "1", "2", etc.)
        slack_user_id: Slack user ID (for finding employee if employee_id not provided)
        week_monday: Monday date of the week in dd/mm format
        remote_dates: List of dates to mark as remote (in dd/mm format)
        
    Returns:
        Tuple of (success, message)
    """
    employees = load_employees()
    
    logger.info(f"Looking for employee with slack_user_id: {slack_user_id}")
    logger.info(f"Total entries in employees: {len(employees)}")
    
    # Find employee by slack_user_id if employee_id is None or not in database
    if not employee_id or employee_id not in employees:
        # Try to find by slack_id
        found = False
        for emp_id, emp_data in employees.items():
            # Skip non-employee entries
            if emp_id in ["task_assignments", "weekly_duty_assignments", "special_dates"]:
                logger.debug(f"Skipping special key: {emp_id}")
                continue
            if not isinstance(emp_data, dict):
                logger.debug(f"Skipping non-dict entry: {emp_id}")
                continue
            
            emp_slack_id = emp_data.get("slack_id", "")
            emp_name = emp_data.get("name", "")
            logger.debug(f"Checking employee {emp_id} ({emp_name}): slack_id={emp_slack_id}")
            
            if emp_slack_id == slack_user_id:
                employee_id = emp_id
                found = True
                logger.info(f"✅ Found employee {emp_name} (ID: {emp_id}) by slack_id {slack_user_id}")
                break
        
        if not found:
            logger.warning(f"❌ Employee not found for slack_id: {slack_user_id}")
            logger.warning(f"Available employees: {[(k, v.get('name', ''), v.get('slack_id', '')) for k, v in employees.items() if isinstance(v, dict) and 'name' in v]}")
            return False, f"❌ Employee not found"
    
    # Double-check employee exists
    if employee_id not in employees:
        return False, f"❌ Employee not found"
    
    # Validate selection
    is_valid, error_msg = validate_remote_days_selection(remote_dates)
    if not is_valid:
        return False, error_msg
    
    # Update employee's remote_dates
    if "remote_dates" not in employees[employee_id]:
        employees[employee_id]["remote_dates"] = {}
    
    # Clean up old weeks (keep only future weeks)
    today = datetime.datetime.now()
    cleaned_remote_dates = {}
    for week_key, dates in employees[employee_id]["remote_dates"].items():
        try:
            day, month = map(int, week_key.split("/"))
            year = today.year
            week_date = datetime.datetime(year, month, day)
            
            # Keep if it's current week or future
            if week_date.date() >= today.date() - datetime.timedelta(days=7):
                cleaned_remote_dates[week_key] = dates
        except (ValueError, AttributeError):
            pass  # Skip malformed dates
    
    # Set new remote dates for the specified week
    cleaned_remote_dates[week_monday] = remote_dates
    employees[employee_id]["remote_dates"] = cleaned_remote_dates
    
    # Save to Redis
    if save_employees(employees):
        employee_name = employees[employee_id].get("name", "Unknown")
        dates_str = ", ".join(remote_dates)
        return True, f"✅ Remote days set for {employee_name} (week of {week_monday}): {dates_str}"
    else:
        return False, "❌ Error saving remote days"


def clear_remote_days_for_employee(employee_id: str, week_monday: str) -> Tuple[bool, str]:
    """
    Clear remote work days for an employee for a specific week.
    
    Args:
        employee_id: Employee ID
        week_monday: Monday date of the week in dd/mm format
        
    Returns:
        Tuple of (success, message)
    """
    employees = load_employees()
    
    if employee_id not in employees:
        return False, f"❌ Employee {employee_id} not found"
    
    if "remote_dates" not in employees[employee_id]:
        return True, "No remote days to clear"
    
    if week_monday in employees[employee_id]["remote_dates"]:
        del employees[employee_id]["remote_dates"][week_monday]
        
        if save_employees(employees):
            return True, f"✅ Remote days cleared for week of {week_monday}"
        else:
            return False, "❌ Error saving changes"
    
    return True, "No remote days found for this week"


def format_remote_employees_mention(remote_employees: List[Dict[str, str]]) -> str:
    """
    Format remote employees for display in messages.
    
    Args:
        remote_employees: List of employee dicts with name and slack_id
        
    Returns:
        Formatted string with mentions, e.g., "🏠 Remote: <@U123> <@U456>"
    """
    if not remote_employees:
        return ""
    
    mentions = []
    for emp in remote_employees:
        slack_id = emp.get("slack_id", "")
        if slack_id:
            mentions.append(f"<@{slack_id}>")
        else:
            mentions.append(emp.get("name", "Unknown"))
    
    return "🏠 *Remote:* " + " ".join(mentions)


def get_weekday_name_from_date(date_str: str) -> Optional[str]:
    """
    Get weekday name from a date string.
    
    Args:
        date_str: Date in dd/mm format
        
    Returns:
        Weekday name (e.g., "Monday") or None if invalid
    """
    try:
        day, month = map(int, date_str.split("/"))
        year = datetime.datetime.now().year
        date_obj = datetime.datetime(year, month, day)
        return date_obj.strftime("%A")
    except (ValueError, AttributeError) as e:
        logger.error(f"Error parsing date '{date_str}': {e}")
        return None
