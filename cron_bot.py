import datetime
import os

from slack_sdk import WebClient

from constants import MESSAGE_TEMPLATES
from redis_bot import (
    generate_message_blocks,
    generate_message_from_redis,
    generate_weekly_message_blocks,
    generate_weekly_message_from_redis,
    set_thread_ts,
)

client = WebClient(token=os.environ.get("SLACK_BOT_TOKEN"))
CHANNEL_ID = os.environ.get("SLACK_CHANNEL_ID")


def generate_message():
    """Generate Slack message based on Redis data and day of week."""
    today = datetime.datetime.now()
    is_monday = today.weekday() == 0  # 0 = Monday

    if is_monday:
        # Monday: send weekly message with duty assignments
        message_data = generate_weekly_message_blocks()
        print("📅 Generating Monday message with duties")
    else:
        # Tuesday-Friday: send regular daily message
        message_data = generate_message_blocks()
        print("📝 Generating daily message")

    # Check for empty message (fallback text)
    message_text = message_data.get("text", "")
    if (
        MESSAGE_TEMPLATES["no_tasks_today"] in message_text
        or MESSAGE_TEMPLATES["no_regular_tasks"] in message_text
    ):
        print("⚠️ Tasks not found in Redis, using fallback logic")
        date_str = today.strftime("%d %B (%A)")

        empty_redis_message = [MESSAGE_TEMPLATES["redis_fallback"]]

        header = f"🎓 Routine tasks for *{date_str}*"
        fallback_text = header + "\n\n" + "\n".join(empty_redis_message)
        return {
            "text": fallback_text,
            "blocks": [
                {"type": "section", "text": {"type": "mrkdwn", "text": fallback_text}}
            ],
        }

    return message_data


if __name__ == "__main__":
    today = datetime.datetime.today()
    is_monday = today.weekday() == 0  # 0 = Monday

    if today.weekday() < 5:  # 0-4: Monday-Friday
        try:
            message_data = generate_message()
            response = client.chat_postMessage(
                channel=CHANNEL_ID,
                text=message_data["text"],
                blocks=message_data.get("blocks"),
            )
            message_ts = response["ts"]
            set_thread_ts(message_ts)
            print("✅ Message sent to Slack")

            # Pin Monday message with weekly duty assignments
            if is_monday:
                try:
                    client.pins_add(channel=CHANNEL_ID, timestamp=message_ts)
                    print("📌 Monday message pinned to channel")
                except Exception as pin_error:
                    print(f"⚠️ Could not pin message: {pin_error}")

        except Exception as e:
            print(f"❌ Error sending message: {e}")
    else:
        print(MESSAGE_TEMPLATES["weekend_skip"])
