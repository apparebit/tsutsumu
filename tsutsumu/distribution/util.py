import datetime
import re

__all__ = ('canonicalize', 'today_as_version')

_DASHING = re.compile(r'[-_.]+')

def canonicalize(name: str, separator: str = '-') -> str:
    """Convert a package or tag name to its canonical form."""
    return _DASHING.sub(separator, name).lower()

def today_as_version() -> str:
    return '.'.join(str(part) for part in datetime.date.today().isocalendar())
