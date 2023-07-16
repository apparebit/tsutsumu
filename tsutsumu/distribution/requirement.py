import re
from typing import cast

from .marker import extract_extra
from cargo.name import canonicalize


__all__ = ('parse_requirement',)


REQUIREMENT_PARTS: re.Pattern[str] = re.compile(
    r"""
        ^
               (?P<package>  [^[(;\s]+    )    [ ]*
        (?: \[ (?P<extras>   [^]]+        ) \] [ ]* )?
        (?: \( (?P<version1> [^)]*        ) \) [ ]* )?
        (?:    (?P<version2> [<!=>~][^;]* )    [ ]* )?
        (?:  ; (?P<marker>   .*           )         )?
        $
    """,
    re.VERBOSE)

def parse_requirement(
    requirement: str
) -> tuple[str, list[str], list[str], None | str]:
    if (parts := REQUIREMENT_PARTS.match(requirement)) is None:
        raise ValueError(f'requirement "{requirement} is malformed')

    package = canonicalize(cast(str, parts.group('package')).strip())

    extras = []
    if (extras_text := cast(str, parts['extras'])):
        extras = [canonicalize(extra.strip()) for extra in extras_text.split(',')]

    versions = []
    if (version_text := parts['version1'] or parts['version2']): # type: ignore[misc]
        versions = [
            v.strip().replace(' ', '') for v in cast(str, version_text).split(',')]

    marker = None
    marker_text = cast(str, parts['marker'])
    if marker_text is not None:
        marker = extract_extra(marker_text.strip())

    return package, extras, versions, marker

