from collections.abc import Iterator
import re
from typing import NamedTuple

from .marker import extract_extra
from .name import canonicalize


__all__ = ('Requirement',)

PARTS: re.Pattern[str] = re.compile(
    r"""
        ^
               (?P<package>   [^[(;\s]+    )    [ ]*
        (?: \[ (?P<extras>    [^]]+        ) \] [ ]* )?
        (?: \( (?P<versions1> [^)]*        ) \) [ ]* )?
        (?:    (?P<versions2> [<!=>~][^;]* )    [ ]* )?
        (?:  ; (?P<marker>    .*           )         )?
        $
    """,
    re.VERBOSE)


class Requirement(NamedTuple):
    """
    Preliminary, rough representation of a requirement. Clearly, this class is
    not the final word, but it turns one huge problem into several smaller ones.
    """

    package: str
    extras: tuple[str,...]
    versions: tuple[str,...]
    extra: None | str

    @classmethod
    def from_string(cls, requirement: str) -> 'Requirement':
        if (parts := PARTS.match(requirement)) is None:
            raise ValueError(f'invalid requirement "{requirement}')

        package = canonicalize(parts.group('package').strip())

        extras_text = parts.group('extras')
        if extras_text is None:
            raw_extras: Iterator[str] = iter(())
        else:
            raw_extras = (e.strip() for e in extras_text.split(','))
        extras = tuple(e for e in dict((canonicalize(e), None) for e in raw_extras))

        raw_versions = parts.group('versions1') or parts.group('versions2')
        if raw_versions is None:
            versions: tuple[str, ...] = ()
        else:
            versions = tuple(
                v.strip().replace(' ', '') for v in raw_versions.split(','))

        extra = None
        raw_marker = parts.group('marker')
        if raw_marker is not None:
            extra = extract_extra(raw_marker.strip())

        return Requirement(package, extras, versions, extra)
