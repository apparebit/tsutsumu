import datetime
import re

__all__ = ('today_as_version')

def today_as_version() -> str:
    return '.'.join(str(part) for part in datetime.date.today().isocalendar())
