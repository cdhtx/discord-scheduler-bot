import discord
from datetime import datetime, time
import pytz
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

def parse_time(time_str: str) -> Optional[time]:
    """Parse a time string (HH:MM) into a time object."""
    try:
        return datetime.strptime(time_str, "%H:%M").time()
    except ValueError:
        return None

def parse_datetime(dt_str: str, timezone: str = "UTC") -> Optional[datetime]:
    """
    Parse a datetime string (YYYY-MM-DD HH:mm) and localize it.
    Returns a timezone-aware datetime object.
    """
    try:
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        tz = pytz.timezone(timezone)
        return tz.localize(dt)
    except (ValueError, pytz.UnknownTimeZoneError) as e:
        logger.error(f"Error parsing datetime '{dt_str}' with tz '{timezone}': {e}")
        return None

def format_timestamp(dt: datetime, style: str = "F") -> str:
    """Return a Discord timestamp string."""
    return f"<t:{int(dt.timestamp())}:{style}>"

def get_aware_now(timezone: str = "UTC") -> datetime:
    """Get current time with timezone."""
    return datetime.now(pytz.timezone(timezone))

class EmbedBuilder:
    """Helper to build consistent embeds."""
    
    @staticmethod
    def error(title: str, description: str) -> discord.Embed:
        return discord.Embed(
            title=title,
            description=description,
            color=discord.Color.red()
        )

    @staticmethod
    def success(title: str, description: str) -> discord.Embed:
        return discord.Embed(
            title=title,
            description=description,
            color=discord.Color.green()
        )
        
    @staticmethod
    def info(title: str, description: str) -> discord.Embed:
        return discord.Embed(
            title=title,
            description=description,
            color=discord.Color.blue()
        )

from datetime import timedelta
import re

def parse_relative_reminders(reminders_str: str, start_time: datetime) -> List[datetime]:
    """
    Parse a string like '24h, 30m' into datetimes relative to start_time.
    Returns list of reminder datetimes.
    """
    if not reminders_str:
        return []
    
    times = []
    parts = [p.strip() for p in reminders_str.split(",")]
    
    for p in parts:
        # Regex for simple duration: 1h, 30m, 1d
        match = re.match(r"(\d+)([hmd])", p)
        if match:
             val = int(match.group(1))
             unit = match.group(2)
             delta = timedelta()
             if unit == 'h':
                 delta = timedelta(hours=val)
             elif unit == 'm':
                 delta = timedelta(minutes=val)
             elif unit == 'd':
                 delta = timedelta(days=val)
             
             remind_at = start_time - delta
             times.append(remind_at)
             
    return times
