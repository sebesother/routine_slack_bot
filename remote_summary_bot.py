"""
Remote Days Summary Bot

Sends a weekly summary of remote work days to Slack.
Should be run on Fridays via cron to notify about next week's remote schedule.
"""

import datetime
import os

from slack_sdk import WebClient

from config import Config
from remote_bot import (
    get_next_monday,
    get_remote_employees_for_date,
    get_week_dates_from_monday,
)

client = WebClient(token=os.environ.get("SLACK_BOT_TOKEN"))
REMOTE_SUMMARY_CHANNEL = Config.REMOTE_SUMMARY_CHANNEL_ID


def generate_weekly_remote_summary() -> str:
    """
    Generate a summary of remote work days for the next week.

    Returns:
        Formatted message string with remote days info
    """
    next_monday = get_next_monday()
    week_dates = get_week_dates_from_monday(next_monday)

    if not week_dates or len(week_dates) < 5:
        return "⚠️ Could not generate remote days summary - invalid week dates"

    weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

    # Header
    week_range = f"{week_dates[0]} - {week_dates[4]}"
    message_parts = [
        f"📅 *Remote Work Schedule for IT Sup Dep for Week {week_range}*",
        "",
    ]

    # Collect remote employees for each day
    has_remote_days = False
    for i, date in enumerate(week_dates[:5]):  # Monday to Friday only
        remote_employees = get_remote_employees_for_date(date)

        if remote_employees:
            has_remote_days = True
            mentions = [f"<@{emp['slack_id']}>" for emp in remote_employees]
            message_parts.append(f"🏠 *{weekdays[i]}* ({date}): {' '.join(mentions)}")

    # If no remote days scheduled
    if not has_remote_days:
        message_parts.append("_No remote days scheduled for next week_")

    # Footer
    message_parts.append("")
    message_parts.append("_Remote days are self-reported and may change._")

    return "\n".join(message_parts)


def get_remote_statistics(week_dates: list) -> dict:
    """
    Calculate statistics about remote work for the week.

    Args:
        week_dates: List of dates in dd/mm format for the week

    Returns:
        Dict with statistics: total_remote_days, unique_employees, etc.
    """
    unique_employees = set()
    total_remote_days = 0

    for date in week_dates[:5]:  # Monday to Friday
        remote_employees = get_remote_employees_for_date(date)
        for emp in remote_employees:
            unique_employees.add(emp["employee_id"])
        total_remote_days += len(remote_employees)

    return {
        "total_remote_days": total_remote_days,
        "unique_employees": len(unique_employees),
    }


def generate_detailed_remote_summary() -> str:
    """
    Generate a detailed summary with statistics.

    Returns:
        Formatted message string with remote days info and stats
    """
    next_monday = get_next_monday()
    week_dates = get_week_dates_from_monday(next_monday)

    if not week_dates or len(week_dates) < 5:
        return "⚠️ Could not generate remote days summary - invalid week dates"

    weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

    # Header
    week_range = f"{week_dates[0]} - {week_dates[4]}"
    message_parts = [
        f"📅 *Remote Work Schedule for IT Sup Dep for Week {week_range}*",
        "",
    ]

    # Collect remote employees for each day
    has_remote_days = False
    day_summaries = []

    for i, date in enumerate(week_dates[:5]):  # Monday to Friday only
        remote_employees = get_remote_employees_for_date(date)

        if remote_employees:
            has_remote_days = True
            mentions = [f"<@{emp['slack_id']}>" for emp in remote_employees]
            day_summaries.append(
                f"🏠 *{weekdays[i]}* ({date}): {' '.join(mentions)}"
            )

    # Add day summaries or no-remote message
    if has_remote_days:
        message_parts.extend(day_summaries)

        # Add statistics
        stats = get_remote_statistics(week_dates)
        message_parts.append("")
        message_parts.append(
            f"📊 *Summary:* {stats['unique_employees']} employees, "
            f"{stats['total_remote_days']} remote day(s) total"
        )
    else:
        message_parts.append("_No remote days scheduled for next week_")

    # Footer
    message_parts.append("")
    message_parts.append("_Remote days are self-reported and may change._")

    return "\n".join(message_parts)


def send_remote_summary(detailed: bool = False) -> bool:
    """
    Send weekly remote summary to Slack channel.

    Args:
        detailed: If True, includes statistics. Default is False.

    Returns:
        True if successful, False otherwise
    """
    try:
        if detailed:
            message = generate_detailed_remote_summary()
        else:
            message = generate_weekly_remote_summary()

        response = client.chat_postMessage(
            channel=REMOTE_SUMMARY_CHANNEL,
            text=message,
        )

        print(f"✅ Remote summary sent to channel {REMOTE_SUMMARY_CHANNEL}")
        print(f"📝 Message TS: {response['ts']}")
        return True

    except Exception as e:
        print(f"❌ Error sending remote summary: {e}")
        return False


if __name__ == "__main__":
    # Cron scheduling is managed by hosting service (Railways)
    # This script runs whenever triggered by cron
    today = datetime.datetime.now()
    current_time = today.strftime("%H:%M")
    
    print(f"⏰ Running remote summary at {current_time}")
    print(f"📅 Sending next week's remote schedule...")

    # Send detailed summary with statistics
    success = send_remote_summary(detailed=True)

    if success:
        print("✅ Remote summary successfully sent")
    else:
        print("❌ Failed to send remote summary")
