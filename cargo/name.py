import datetime
import re


__all__ = ('canonicalized', 'split_hash', 'today_as_version')


_DASHING = re.compile(r'[-_.]+')


def canonicalize(name: str, separator: str = '-') -> str:
    """Canonicalize the distribution, package, or package extra name."""
    return _DASHING.sub(separator, name).lower()


def split_hash(url: str) -> None | tuple[str, str, str]:
    """Remove the URL's anchor, which identifies the resource's hash value."""
    url, _, hash = url.partition('#')
    if len(hash) == 0:
        return None

    algo, _, value = hash.partition('=')
    if len(algo) == 0 or len(value) == 0:
        return None

    return url, algo, value


def today_as_version() -> str:
    return '.'.join(str(part) for part in datetime.date.today().isocalendar())
