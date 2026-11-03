"""Real-time date/time engine for LocalGPT.
Retrieves local system time, handles timezones, and provides
deterministic date/time operations without relying on LLM knowledge.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, available_timezones
from typing import Any, Optional


# Default timezone as per requirements
DEFAULT_TIMEZONE = "Asia/Kolkata"


def get_system_timezone() -> str:
    """Detect system timezone with fallback to default."""
    # Try to get from environment
    tz = os.environ.get("TZ") or os.environ.get("LOCALGPT_TIMEZONE")
    if tz and tz in available_timezones():
        return tz
    # Try common Windows timezone mapping fallback
    try:
        # On Windows, we can try to detect, but zoneinfo uses IANA names
        return DEFAULT_TIMEZONE
    except Exception:
        return DEFAULT_TIMEZONE


def get_current_datetime(tz_name: Optional[str] = None) -> datetime:
    """Get current datetime in specified timezone."""
    if tz_name is None:
        tz_name = get_system_timezone()
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        try:
            tz = ZoneInfo(DEFAULT_TIMEZONE)
            tz_name = DEFAULT_TIMEZONE
        except Exception:
            from datetime import timezone
            return datetime.now(timezone.utc)
    return datetime.now(tz)


def format_datetime(dt: Optional[datetime] = None, tz_name: Optional[str] = None) -> dict[str, Any]:
    """Format datetime into readable components."""
    if dt is None:
        dt = get_current_datetime(tz_name)
    return {
        "date": dt.strftime("%d %B %Y"),  # e.g., 2 November 2026
        "day": dt.strftime("%A"),  # e.g., Monday
        "time": dt.strftime("%I:%M %p"),  # e.g., 12:30 AM
        "time_24h": dt.strftime("%H:%M"),
        "month": dt.strftime("%B"),
        "year": dt.strftime("%Y"),
        "weekday_num": dt.weekday(),  # Monday is 0
        "timezone": str(dt.tzinfo),
        "iso": dt.isoformat(),
        "timestamp": dt.timestamp(),
    }


def get_time_context(tz_name: Optional[str] = None, location: Optional[str] = None) -> str:
    """Generate dynamic system context for LLM injection."""
    try:
        info = format_datetime(tz_name=tz_name)
        context = f"""You are LocalGPT.

REAL-TIME SYSTEM INFORMATION (Fresh - Generated for this request):
Current date: {info['date']}
Current day: {info['day']}
Current time: {info['time']}
Current month: {info['month']}
Current year: {info['year']}
Timezone: {info['timezone']}
"""
        if location:
            context += f"Location: {location}\n"
        context += """
Use this information whenever the user asks about the current date, time, day, month, year, or related calculations.
Never claim that your date and time information is outdated when the system context provides current information.
Never invent real-time information that is not available. For external current events, news, weather, or live data not in this context, use web search if enabled.
"""
        return context
    except Exception:
        from datetime import datetime
        now = datetime.now()
        return f"""You are LocalGPT.

REAL-TIME SYSTEM INFORMATION (Fresh - Generated for this request):
Current date: {now.strftime('%d %B %Y')}
Current day: {now.strftime('%A')}
Current time: {now.strftime('%I:%M %p')}
Current month: {now.strftime('%B')}
Current year: {now.strftime('%Y')}
Timezone: Local
"""



def add_time(dt: datetime, hours: float = 0, minutes: float = 0, days: float = 0) -> datetime:
    """Add time to a datetime."""
    return dt + timedelta(hours=hours, minutes=minutes, days=days)


def subtract_time(dt: datetime, hours: float = 0, minutes: float = 0, days: float = 0) -> datetime:
    """Subtract time from a datetime."""
    return dt - timedelta(hours=hours, minutes=minutes, days=days)


def convert_timezone(dt: datetime, target_tz: str) -> tuple[datetime, str]:
    """Convert datetime to target timezone."""
    try:
        target = ZoneInfo(target_tz)
        converted = dt.astimezone(target)
        return converted, str(converted.tzinfo)
    except Exception as e:
        raise ValueError(f"Invalid timezone '{target_tz}': {e}")


def get_timezone_info(tz_name: str) -> dict[str, Any]:
    """Get info about a timezone."""
    try:
        tz = ZoneInfo(tz_name)
        now = datetime.now(tz)
        return {
            "timezone": tz_name,
            "current_time": now.strftime("%I:%M %p"),
            "current_date": now.strftime("%d %B %Y"),
            "current_day": now.strftime("%A"),
            "offset": now.strftime("%z"),
        }
    except Exception as e:
        raise ValueError(f"Invalid timezone '{tz_name}': {e}")


def time_difference(tz1: str, tz2: str) -> dict[str, Any]:
    """Calculate time difference between two timezones."""
    try:
        now = datetime.now()
        dt1 = now.astimezone(ZoneInfo(tz1))
        dt2 = now.astimezone(ZoneInfo(tz2))
        diff_seconds = (dt1.utcoffset() or timedelta()) - (dt2.utcoffset() or timedelta())
        diff_hours = diff_seconds.total_seconds() / 3600
        return {
            "tz1": tz1,
            "tz2": tz2,
            "time1": dt1.strftime("%I:%M %p"),
            "time2": dt2.strftime("%I:%M %p"),
            "difference_hours": diff_hours,
            "difference_str": f"{abs(diff_hours):.1f} hours {'ahead' if diff_hours > 0 else 'behind' if diff_hours < 0 else 'same'}",
        }
    except Exception as e:
        raise ValueError(f"Error calculating difference: {e}")
