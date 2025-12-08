import logging
import os
from typing import Dict


class Config:
    """Centralized configuration management for the Slack bot system."""

    # Slack Configuration
    SLACK_BOT_TOKEN: str = os.environ.get("SLACK_BOT_TOKEN", "")
    SLACK_APP_TOKEN: str = os.environ.get("SLACK_APP_TOKEN", "")
    SLACK_CHANNEL_ID: str = os.environ.get("SLACK_CHANNEL_ID", "")

    # Redis Configuration
    REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379")

    # Redis Keys
    SLACK_ROUTINE_STATE: str = "slack_routine_state"
    DEBUG_ROUTINE_STATE: str = "debug_routine_state"
    TASK_BASE: str = "task_base"
    EMPLOYEES: str = "employees"

    # Timezone
    TIMEZONE: str = "Europe/Riga"

    # Team Mention (hardcoded for now)
    TEAM_MENTION: str = "<!subteam^S07BD1P55GT|@sup>"

    # Duty Types
    DUTY_TYPES: Dict[str, str] = {
        "fin": "FIN-DUTY",
        "asana": "ASANA-DUTY",
        "tg": "TG-DUTY",
        "notification": "NOTIFICATION-DUTY",
        "supervision": "SUPERVISION-DUTY",
    }

    # Logging
    LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    @classmethod
    def validate_required_env_vars(cls) -> None:
        """Validate that all required environment variables are set."""
        required_vars = [
            ("SLACK_BOT_TOKEN", cls.SLACK_BOT_TOKEN),
            ("SLACK_APP_TOKEN", cls.SLACK_APP_TOKEN),
            ("SLACK_CHANNEL_ID", cls.SLACK_CHANNEL_ID),
        ]

        missing_vars = [
            var_name for var_name, var_value in required_vars if not var_value
        ]

        if missing_vars:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing_vars)}"
            )

    @classmethod
    def setup_logging(cls) -> logging.Logger:
        """Setup centralized logging configuration."""
        logging.basicConfig(
            level=getattr(logging, cls.LOG_LEVEL.upper()),
            format=cls.LOG_FORMAT,
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        return logging.getLogger(__name__)
