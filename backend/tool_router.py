"""Tool router for LocalGPT.
Routes user queries to appropriate handlers: local time, calculations,
timezone conversion, web search, or normal LLM conversation.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional, Tuple

from .time_engine import (
    get_current_datetime,
    format_datetime,
    add_time,
    subtract_time,
    convert_timezone,
    time_difference,
    get_timezone_info,
    DEFAULT_TIMEZONE,
)


class ToolRouter:
    def __init__(self, web_search=None):
        self.web_search = web_search

    def route(self, user_message: str) -> Tuple[str, Optional[dict[str, Any]]]:
        """
        Route query and return (action, data).
        Actions: 'time', 'date_calc', 'tz_convert', 'web_search', 'chat'
        """
        msg = user_message.lower().strip()

        # Time queries
        if re.search(r'\b(what time|current time|time is it|tell me the time)\b', msg):
            return self._handle_time_query(msg)

        # Date queries
        if re.search(r"\b(what.*date|today.*date|current date|what day is|what month|what year|which day|which month|which year)\b", msg):
            return self._handle_date_query(msg)

        # Tomorrow/yesterday
        if re.search(r'\b(tomorrow|yesterday)\b', msg):
            return self._handle_relative_date(msg)

        # Date calculations (days until, etc.)
        if re.search(r'\b(days until|how many days|date.*after|date.*before)\b', msg):
            return self._handle_date_calc(msg)

        # Time calculations
        if re.search(r'\b(time.*after|time.*in.*hours|after \d+ hour)\b', msg):
            return self._handle_time_calc(msg)

        # Timezone conversion
        if re.search(r'\b(time in|current time in|what.*time.*in [a-z]+)\b', msg):
            return self._handle_tz_query(msg)

        # Time difference
        if re.search(r'\b(time difference|difference between.*and)\b', msg):
            return self._handle_tz_diff(msg)

        # Web search triggers
        if self.web_search and self.web_search.enabled:
            if re.search(r'\b(latest|current news|today.*news|weather|stock price|sports result|recent.*event|breaking news)\b', msg):
                if self.web_search.is_available():
                    return ('web_search', {'query': user_message})
            # More specific triggers
            if re.search(r'\b(news|weather in|price of|score of|who won)\b', msg):
                if self.web_search.is_available():
                    return ('web_search', {'query': user_message})

        return ('chat', None)

    def _handle_time_query(self, msg: str) -> Tuple[str, dict[str, Any]]:
        dt = get_current_datetime()
        info = format_datetime(dt)
        return ('time', {
            'action': 'current_time',
            'time': info['time'],
            'time_24h': info['time_24h'],
            'timezone': info['timezone'],
            'full': info,
        })

    def _handle_date_query(self, msg: str) -> Tuple[str, dict[str, Any]]:
        dt = get_current_datetime()
        info = format_datetime(dt)
        if 'day' in msg and 'what day' in msg:
            return ('time', {'action': 'current_day', 'day': info['day'], 'full': info})
        if 'month' in msg:
            return ('time', {'action': 'current_month', 'month': info['month'], 'full': info})
        if 'year' in msg:
            return ('time', {'action': 'current_year', 'year': info['year'], 'full': info})
        return ('time', {'action': 'current_date', 'date': info['date'], 'day': info['day'], 'time': info['time'], 'full': info})

    def _handle_relative_date(self, msg: str) -> Tuple[str, dict[str, Any]]:
        dt = get_current_datetime()
        if 'tomorrow' in msg:
            tomorrow = add_time(dt, days=1)
            info = format_datetime(tomorrow)
            return ('time', {'action': 'tomorrow', 'date': info['date'], 'day': info['day'], 'full': info})
        if 'yesterday' in msg:
            yesterday = subtract_time(dt, days=1)
            info = format_datetime(yesterday)
            return ('time', {'action': 'yesterday', 'date': info['date'], 'day': info['day'], 'full': info})
        return ('time', {'action': 'current_date', 'full': format_datetime(dt)})

    def _handle_date_calc(self, msg: str) -> Tuple[str, dict[str, Any]]:
        dt = get_current_datetime()
        # Try to extract days
        m = re.search(r'(\d+)\s+days?', msg)
        if m:
            days = int(m.group(1))
            future = add_time(dt, days=days)
            info = format_datetime(future)
            return ('time', {'action': 'add_days', 'days': days, 'date': info['date'], 'day': info['day'], 'full': info})
        # Days until end of year / specific date (simple cases)
        if 'days until' in msg:
            if 'january' in msg or '1 january' in msg or 'new year' in msg:
                end = dt.replace(month=1, day=1, year=dt.year + 1, hour=0, minute=0, second=0, microsecond=0)
                days_left = (end - dt.replace(hour=0, minute=0, second=0, microsecond=0)).days
                return ('time', {'action': 'days_until', 'target': '1 January ' + str(dt.year + 1), 'days': days_left})
        return ('time', {'action': 'current_date', 'full': format_datetime(dt)})

    def _handle_time_calc(self, msg: str) -> Tuple[str, dict[str, Any]]:
        dt = get_current_datetime()
        m = re.search(r'(\d+)\s+hours?', msg)
        if m:
            hours = int(m.group(1))
            future = add_time(dt, hours=hours)
            info = format_datetime(future)
            return ('time', {'action': 'add_hours', 'hours': hours, 'time': info['time'], 'date': info['date'], 'full': info})
        m = re.search(r'(\d+)\s+minutes?', msg)
        if m:
            mins = int(m.group(1))
            future = add_time(dt, minutes=mins)
            info = format_datetime(future)
            return ('time', {'action': 'add_minutes', 'minutes': mins, 'time': info['time'], 'date': info['date'], 'full': info})
        return ('time', {'action': 'current_time', 'full': format_datetime(dt)})

    def _handle_tz_query(self, msg: str) -> Tuple[str, dict[str, Any]]:
        # Common city mappings
        city_map = {
            'london': 'Europe/London',
            'new york': 'America/New_York',
            'nyc': 'America/New_York',
            'paris': 'Europe/Paris',
            'tokyo': 'Asia/Tokyo',
            'sydney': 'Australia/Sydney',
            'dubai': 'Asia/Dubai',
            'singapore': 'Asia/Singapore',
            'los angeles': 'America/Los_Angeles',
            'la': 'America/Los_Angeles',
            'chicago': 'America/Chicago',
            'beijing': 'Asia/Shanghai',
            'mumbai': 'Asia/Kolkata',
            'delhi': 'Asia/Kolkata',
            'pune': 'Asia/Kolkata',
        }
        for city, tz in city_map.items():
            if city in msg:
                try:
                    info = get_timezone_info(tz)
                    return ('time', {'action': 'tz_time', 'city': city.title(), 'timezone': tz, **info})
                except Exception:
                    pass
        return ('chat', None)  # Fall back to LLM if unknown

    def _handle_tz_diff(self, msg: str) -> Tuple[str, dict[str, Any]]:
        city_map = {
            'india': 'Asia/Kolkata',
            'new york': 'America/New_York',
            'london': 'Europe/London',
            'paris': 'Europe/Paris',
            'tokyo': 'Asia/Tokyo',
        }
        tzs = []
        cities = []
        for city, tz in city_map.items():
            if city in msg:
                tzs.append(tz)
                cities.append(city.title())
        if len(tzs) >= 2:
            try:
                diff = time_difference(tzs[0], tzs[1])
                return ('time', {'action': 'tz_diff', 'cities': cities, **diff})
            except Exception:
                pass
        return ('chat', None)
