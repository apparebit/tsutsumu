#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# DO NOT EDIT! This script was automatically generated
# by Tsutsumu <https://github.com/apparebit/tsutsumu>.
# Manual edits may just break it.

if False: {
# ------------------------------------------------------------------------------
"cargo/distinfo.py":
b"""\x22\x22\x22Support for package metadata in form of .dist-info files.\x22\x22\x22

from collections import deque
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, KW_ONLY
import importlib
import importlib.metadata as md
import itertools
from pathlib import Path
import tomllib
from typing import cast, Literal, overload, TypeVar

from packaging.markers import Marker as PackagingMarker
from packaging.requirements import Requirement as PackagingRequirement

from .name import canonicalize, today_as_version
from .requirement import Requirement


# class Person(NamedTuple):
#     name: str
#     email: None | str
#     url: None | str


# class DistInfoData(NamedTuple):
#     name: str
#     version: None | str = None
#     summary: None | str = None
#     homepage: None | str = None
#     download_url: None | str = None
#     project_url: None | str = None
#     keywords: tuple[str, ...] = ()
#     classifiers: tuple[str, ...] = ()
#     platforms: tuple[str, ...] = ()
#     author: None | Person = None
#     maintainer: None | Person = None
#     license: None | str = None
#     required_python: None | str = None
#     required_dists: tuple[str, ...] = ()
#     required_resources: tuple[str, ...] = ()
#     provided_dists: tuple[str, ...] = ()
#     provided_extras: tuple[str, ...] = ()
#     obsoleted_dists: tuple[str,...] = ()
#     provenance: tuple[str, ...] = ()

__all__ = (\x22collect_dependencies\x22, \x22DistInfo\x22)


def collect_dependencies(
    pkgname: str, *pkgextras: str
) -> \x22tuple[dict[str, DistInfo], dict[str, PackagingMarker]]\x22:
    \x22\x22\x22
    Determine the transitive closure of package dependencies via a breadth-first
    search of locally installed packages. This function not only returns a
    dictionary of resolved dependencies, but also one of dependencies that were
    never installed in the first place due to their marker evaluating to false.
    \x22\x22\x22

    pyproject_path = Path.cwd() / \x22pyproject.toml\x22
    if pyproject_path.exists():
        distribution = DistInfo.from_pyproject(pyproject_path, pkgextras)
    else:
        distribution = DistInfo.from_installation(pkgname, pkgextras)

    # Breadth-first search requires a queue
    pending: deque[tuple[str, tuple[str, ...], str]] = deque(
        (pkgname, pkgextras, req) for req in distribution.required_packages
    )
    distributions = {pkgname: distribution}
    not_installed: dict[str, PackagingMarker] = {}

    while len(pending) > 0:
        # Resolve the requirement to a distribution. We first use Tsutsumu's
        # lossy parser to determine if the requirement is scoped to an extra.
        # Next, we also evaluate the marker with packaging's precise machinery,
        # since the package may not be installed at all due to a version
        # constraint on the operating system or Python runtime.

        pkgname, pkgextras, requirement = pending.pop()
        dependency, dep_extras, _, only_for_extra = Requirement.from_string(requirement)

        req = PackagingRequirement(requirement)
        if req.marker is not None:
            env = {} if only_for_extra is None else {\x22extra\x22: only_for_extra}
            if not req.marker.evaluate(env):
                not_installed[pkgname] = req.marker
                continue  # since dependency hasn't been installed
        if only_for_extra is not None and only_for_extra not in pkgextras:
            continue  # since requirement is for unused package
        if dependency in distributions:
            continue  # since dependency has already been processed

        dist = DistInfo.from_installation(dependency, dep_extras)
        distributions[dependency] = dist
        pending.extend((dist.name, dist.extras, req) for req in dist.required_packages)

    return distributions, not_installed


T = TypeVar(\x22T\x22)


@dataclass(frozen=True, slots=True)
class DistInfo:
    name: str
    extras: tuple[str, ...] = ()
    _: KW_ONLY
    version: None | str = None
    effective_version: str = field(init=False)
    summary: None | str = None
    homepage: None | str = None
    required_python: None | str = None
    required_packages: tuple[str, ...] = ()
    provenance: None | str = None

    @classmethod
    def from_pyproject(
        cls, path: str | Path, extras: tuple[str, ...] = ()
    ) -> \x22DistInfo\x22:
        with open(path, mode=\x22rb\x22) as file:
            metadata = cast(dict[str, object], tomllib.load(file))
        if not isinstance(project_metadata := metadata.get(\x22project\x22), dict):
            raise ValueError(f'\x22{path}\x22 lacks \x22project\x22 section')

        @overload
        def property(key: str, typ: type[list[str]], is_optional: bool) -> list[str]:
            ...

        @overload
        def property(key: str, typ: type[T], is_optional: Literal[False]) -> T:
            ...

        @overload
        def property(key: str, typ: type[T], is_optional: Literal[True]) -> None | T:
            ...

        def property(key: str, typ: type[T], is_optional: bool) -> None | T:
            value = project_metadata.get(key)
            if isinstance(value, typ):
                return value
            if value is None:
                if typ is list:
                    return cast(T, [])
                if is_optional:
                    return None
            if value is None:
                raise ValueError(f'\x22{path}\x22 has no \x22{key}\x22 entry in \x22project\x22 section')
            else:
                raise ValueError(f'\x22{path}\x22 has non-{typ.__name__} \x22{key}\x22 entry')

        name = canonicalize(property(\x22name\x22, str, False))
        version = property(\x22version\x22, str, True)
        summary = property(\x22description\x22, str, True)
        required_python = property(\x22requires-python\x22, str, True)

        raw_requirements = property(\x22dependencies\x22, list, True)
        if any(not isinstance(p, str) for p in raw_requirements):
            raise ValueError(f'\x22{path}\x22 has non-str item in \x22dependencies\x22')
        optional_dependencies = cast(
            dict[str, list[str]], property(\x22optional-dependencies\x22, dict, True)
        ) or cast(dict[str, list[str]], {})
        for extra in extras:
            if extra in optional_dependencies:
                for dependency in optional_dependencies[extra]:
                    raw_requirements.append(f'{dependency} ; extra == \x22{extra}\x22')
        required_packages = tuple(raw_requirements)

        homepage: None | str = None
        urls = property(\x22urls\x22, dict, True)
        if urls is not None:
            for location in (\x22homepage\x22, \x22repository\x22, \x22documentation\x22):
                if location not in urls:
                    continue
                url = urls[location]
                if isinstance(url, str):
                    homepage = url
                    break
                raise ValueError(f'\x22{path}\x22 has non-str value in \x22urls\x22')

        if version is None:
            # pyproject.toml may omit version if it is dynamic.
            if \x22version\x22 in property(\x22dynamic\x22, list, True):
                package = importlib.import_module(name)
                version = getattr(package, \x22__version__\x22)
                assert isinstance(version, str)
            else:
                raise ValueError(f'\x22{path}\x22 has no \x22version\x22 in \x22project\x22 section')

        return cls(
            name,
            extras,
            version=version,
            summary=summary,
            homepage=homepage,
            required_python=required_python,
            required_packages=required_packages,
            provenance=str(Path(path).absolute()),
        )

    @classmethod
    def from_installation(
        cls,
        name: str,
        extras: Sequence[str] = (),
        *,
        version: None | str = None,
    ) -> \x22DistInfo\x22:
        name = canonicalize(name)

        if version is None:
            try:
                distribution = md.distribution(name)
            except ModuleNotFoundError:
                return cls(name, tuple(extras))

        # Distribution's implementation reads and parses the metadata file on
        # every access to its metadata property. Since its other properties
        # internally use the metadata property as well, it's really easy to read
        # and parse the same file over and over again.
        metadata = distribution.metadata

        version = metadata[\x22Version\x22]
        summary = metadata[\x22Summary\x22]
        homepage = metadata[\x22Home-page\x22]
        required_python = metadata[\x22Requires-Python\x22]
        required_packages = tuple(
            cast(
                list[str],
                metadata.get_all(\x22Requires-Dist\x22, failobj=cast(list[str], [])),
            )
        )
        # provided_extras = metadata.get_all('Provides-Extra')
        # provided_distributions = metadata.get_all('Provides-Dist')

        provenance = None
        if hasattr(distribution, \x22_path\x22):
            provenance = str(cast(Path, getattr(distribution, \x22_path\x22)).absolute())

        return cls(
            name,
            tuple(extras),
            version=version,
            summary=summary,
            homepage=homepage,
            required_python=required_python,
            required_packages=required_packages,
            provenance=provenance,
        )

    def __post_init__(self) -> None:
        version = today_as_version() if self.version is None else self.version
        object.__setattr__(self, \x22effective_version\x22, version)

    def __hash__(self) -> int:
        return hash(self.name) + hash(self.version)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DistInfo):
            return NotImplemented
        return self.name == other.name and self.version == other.version

    def __repr__(self) -> str:
        version = \x22?.?\x22 if self.version is None else self.version
        return f\x22<DistInfo {self.name} {version}>\x22

    def metadata_path_content(self) -> tuple[str, str]:
        metadata_path = f\x22{self.name}-{self.effective_version}.dist-info/METADATA\x22
        lines = [
            \x22Metadata-Version: 2.1\x22,
            \x22Name: \x22 + self.name,
            \x22Version: \x22 + self.effective_version,
        ]

        if self.summary:
            lines.append(\x22Summary: \x22 + self.summary)
        if self.homepage:
            lines.append(\x22Home-page: \x22 + self.homepage)
        if self.required_python:
            lines.append(\x22Requires-Python: \x22 + self.required_python)
        for requirement in self.required_packages:
            lines.append(\x22Requires-Dist: \x22 + requirement)

        return metadata_path, \x22\\n\x22.join(lines) + \x22\\n\x22

    def record_path_content(self, files: Iterable[str]) -> tuple[str, str]:
        prefix = f\x22{self.name}-{self.effective_version}.dist-info/\x22
        record_path = prefix + \x22RECORD\x22
        all_files = itertools.chain((prefix + \x22METADATA\x22, record_path), files)
        content = \x22,,\\n\x22.join(f'\x22{f}\x22' if \x22,\x22 in f else f for f in all_files) + \x22,,\\n\x22
        return record_path, content
""",
# ------------------------------------------------------------------------------
"cargo/index.py":
b"""\x22\x22\x22
Support for accessing PyPI and compatible indices through the simple repository
API. Relevant PEPs are:

  * [PEP 503](https://peps.python.org/pep-0503/) defines the basic HTML-based
    API.
  * [PEP 527](https://peps.python.org/pep-0527/) disallows uploads in a number
    of unpopular formats; it also documents the use of `.zip` files for sdist's.
  * [PEP 592](https://peps.python.org/pep-0592/) adds support for *yanking*
    releases again.
  * [PEP 658](https://peps.python.org/pep-0658/) introduces accessing metadata
    without downloading distributions.
  * [PEP 691](https://peps.python.org/pep-0691/) adds support for the JSON-based
    API.
  * [PEP 714](https://peps.python.org/pep-0714/) renames the field introduced by
    PEP 658 due to an unfortunate interaction between a PyPI bug and a Pip bug.
  * [PEP 715](https://peps.python.org/pep-0715/) disallows `.egg` uploads.
\x22\x22\x22

import email.message
from html.parser import HTMLParser
import json
import logging
import re
import sys
import time
from typing import cast, Literal, NamedTuple, TypedDict

import requests

from .name import canonicalize, split_hash
from .version import Version


__all__ = ()

logger = logging.getLogger(\x22cargo.index\x22)


PACKAGE_INDEX = \x22https://pypi.org/simple\x22
ACCEPTABLE_CONTENT = (
    \x22application/vnd.pypi.simple.latest+json\x22,
    \x22application/vnd.pypi.simple.latest+html;q=0.2\x22,
    # 'text/html;q=0.01', # pfui!
)

HEADERS = {
    \x22user-agent\x22: \x22Tsutsumu (https://github.com/apparebit/tsutsumu)\x22,
    \x22accept\x22: \x22, \x22.join(ACCEPTABLE_CONTENT),
}

PYPI_CONTENT_TYPES = re.compile(
    r\x22application/vnd.pypi.simple.v(?P<version>\\d+)\\+(?P<format>html|json)\x22
)

ANCHOR_ATTRIBUTES = {
    \x22href\x22: \x22url\x22,
    \x22data-requires-python\x22: \x22requires_python\x22,
    \x22data-core-metadata\x22: \x22core_metadata\x22,  # previously data-dist-info-metadata
}

JSON_ATTRIBUTES = {
    \x22url\x22: \x22url\x22,
    \x22requires-python\x22: \x22requires_python\x22,
    \x22core-metadata\x22: \x22core_metadata\x22,
    \x22hashes\x22: \x22hashes\x22,
}

# --------------------------------------------------------------------------------------


class HashValue(TypedDict, total=False):
    sha256: str

class ReleaseMetadata(TypedDict, total=False):
    filename: str
    name: str
    version: str | Version
    url: str
    hashes: HashValue
    core_metadata: Literal[False] | HashValue
    requires_python: str
    api_version: str

class PackageMetadata(TypedDict, total=False):
    provenance: str

    name: str
    latest_version: str | Version
    url: str
    hash: HashValue
    core_metadata: Literal[False] | HashValue
    requires_python: str





# --------------------------------------------------------------------------------------


def determine_format(content_type_header: str) -> tuple[None | str, None | str]:
    \x22\x22\x22
    Parse the content type and, if it is one of the application/vnd.pypi.simple
    types, determine the version and the format.
    \x22\x22\x22
    message = email.message.Message()
    message[\x22content-type\x22] = content_type_header
    normalized_content_type = message.get_content_type()
    if (pypi_format := PYPI_CONTENT_TYPES.match(normalized_content_type)) is None:
        return None, None
    return cast(tuple[str, str], pypi_format.groups())


def retrieve_metadata(name: str) -> None | ReleaseMetadata:
    \x22\x22\x22Retrieve metadata about the most recent wheel-based release.\x22\x22\x22
    name = canonicalize(name)

    # Fetch project JSON or page
    logger.debug('fetching package metadata for \x22%s\x22', name)
    response = requests.get(f\x22{PACKAGE_INDEX}/{name}/\x22, headers=HEADERS)
    response.raise_for_status()

    content_type = response.headers.get(\x22content-type\x22, \x22\x22)
    format = determine_format(content_type)[1]
    info: None | ReleaseMetadata
    match format:
        case \x22json\x22:
            info = ingest_json(response.json())
        case \x22html\x22:
            info = ingest_html(response.text)
        case _:
            raise ValueError(
                f'unrecognized content type \x22{content_type}\x22 for package \x22{name}\x22'
            )

    if info is None:
        logger.warning('Unable to ingest metadata from %s for %s', format, name)
    else:
        info[\x22version\x22] = str(info[\x22version\x22])
        pep658 = \x22\xe2\x9c\x85\x22 if \x22core_metadata\x22 in info else \x22\xe2\x9d\x8c\x22
        logger.info(\x22%s %s v%s:\x22, pep658, name, info[\x22version\x22])
        logger.info(\x22    requires_pathon=%s\x22, info[\x22requires_python\x22])
        logger.info(\x22    filename=%s\x22, info[\x22filename\x22])
        logger.info(\x22    href=%s\x22, info[\x22url\x22])
    return info


# --------------------------------------------------------------------------------------


def ingest_json(data: dict[str, object]) -> None | ReleaseMetadata:
    \x22\x22\x22Process the JSON result from PyPI' Simple Repository API.\x22\x22\x22
    api_version = None
    if \x22meta\x22 in data and isinstance(data[\x22meta\x22], dict):
        api_version = data[\x22meta\x22].get(\x22api-version\x22)

    files = cast(list[ReleaseMetadata], data[\x22files\x22])
    latest: None | ReleaseMetadata = None

    for file in files:
        maybe_latest = find_latest_release(file[\x22filename\x22], latest)
        if maybe_latest is None:
            continue

        latest = maybe_latest
        for key, value in file.items():
            if key == \x22hashes\x22:
                latest[\x22hashes\x22] = cast(HashValue, value).copy()
            if key == \x22core-metadata\x22 and isinstance(value, dict):
                latest[\x22core_metadata\x22] = cast(HashValue, value).copy()
            elif key in JSON_ATTRIBUTES:
                latest[JSON_ATTRIBUTES[key]] = value  # type: ignore[literal-required]

    if api_version is not None and latest is not None:
        latest[\x22api_version\x22] = api_version
    return latest


# --------------------------------------------------------------------------------------


def ingest_html(html: str) -> None | ReleaseMetadata:
    \x22\x22\x22Process the HTML result from PyPI' Simple Repository API.\x22\x22\x22
    parser = LinkParser()
    parser.feed(html)
    parser.close()
    anchors = parser._anchors
    api_version = parser._api_version

    latest: None | ReleaseMetadata = None
    for filename, attributes in anchors:
        if (maybe_latest := find_latest_release(filename, latest)) is None:
            continue

        latest = maybe_latest
        for key, value in attributes:
            if key in ANCHOR_ATTRIBUTES:
                latest[ANCHOR_ATTRIBUTES[key]] = value # type: ignore[literal-required]

        url = latest[\x22url\x22]
        if isinstance(url, str) and (split := split_hash(url)) is not None:
            url, algo, value = split
            latest[\x22hashes\x22] = {algo: value}  # type: ignore[misc]
            latest[\x22url\x22] = url

    if api_version is not None and latest is not None:
        latest[\x22api_version\x22] = api_version
    return latest


class Anchor(NamedTuple):
    \x22\x22\x22The scraped information about a release.\x22\x22\x22
    filename: str
    attributes: list[tuple[str, None | str]]


class LinkParser(HTMLParser):
    \x22\x22\x22A parser for the project pages of PyPI's Simple Repository API.\x22\x22\x22

    __slots__ = (
        \x22_api_version\x22,
        \x22_handling_anchor\x22,
        \x22_current_attrs\x22,
        \x22_anchor_text\x22,
        \x22_anchors\x22,
    )

    def __init__(self) -> None:
        super().__init__()
        self._api_version: None | str = None
        self._handling_anchor: bool = False
        self._current_attrs: None | list[tuple[str, None | str]] = None
        self._anchor_text: list[str] = []
        self._anchors: list[Anchor] = []

    @property
    def version(self) -> None | str:
        return self._api_version

    @property
    def anchors(self) -> list[Anchor]:
        return self._anchors

    def handle_starttag(self, tag: str, attrs: list[tuple[str, None | str]]) -> None:
        if tag == \x22meta\x22:
            self.handle_meta(attrs)
            return
        if tag != \x22a\x22:
            return

        assert not self._handling_anchor
        self._handling_anchor = True
        self._current_attrs = attrs

    def handle_endtag(self, tag: str) -> None:
        if tag != \x22a\x22:
            return
        assert self._handling_anchor
        self._handling_anchor = False
        self.handle_anchor()

    def handle_data(self, data: str) -> None:
        if self._handling_anchor:
            self._anchor_text.append(data)

    def handle_anchor(self) -> None:
        if len(self._anchor_text) == 1:
            content = self._anchor_text[0]
        else:
            content = \x22\x22.join(self._anchor_text)
        assert self._current_attrs is not None
        self._anchors.append(Anchor(content, self._current_attrs))
        self._anchor_text.clear()
        self._current_attrs = None

    def handle_meta(self, attrs: list[tuple[str, None | str]]) -> None:
        is_version = False
        version = None

        for key, value in attrs:
            if key == \x22name\x22 and value == \x22pypi:repository-version\x22:
                is_version = True
            elif key == \x22content\x22:
                version = value

        if is_version and version is not None:
            self._api_version = version


# --------------------------------------------------------------------------------------


def parse_filename(filename: str) -> None | tuple[str, str, str]:
    filename = filename.strip()
    if filename.endswith(\x22.whl\x22):
        kind = \x22wheel\x22
        stem = filename[:-4]
    elif filename.endswith(\x22.tar.gz\x22):
        kind = \x22sdist\x22
        stem = filename[:-7]
    elif filename.endswith(\x22.egg\x22):
        kind = \x22egg\x22
        stem = filename[:-4]
    else:
        return None

    name, version, *_ = stem.split(\x22-\x22, maxsplit=2)
    return kind, name, version


def find_latest_release(
    filename: str, latest_so_far: None | ReleaseMetadata
) -> None | ReleaseMetadata:
    if (parse := parse_filename(filename)) is None:
        logger.warning('Unknown distribution format \x22%s\x22', filename)
        return None

    kind, name, version = parse
    if kind != \x22wheel\x22:
        logger.debug('Ignoring distribution in \x22%s\x22 format', kind)
        return None

    assert version is not None
    version_object = Version(version)
    if (
        latest_so_far is not None and
        version_object < latest_so_far[\x22version\x22]
    ) :
        logger.debug(\x22Skipping wheel %s < %s\x22, version, latest_so_far[\x22version\x22])
        return None

    return {\x22filename\x22: filename, \x22name\x22: name, \x22version\x22: version_object}


# ======================================================================================
# mypy: disallow_any_expr = false

def main(args: list[str]) -> None:
    with open('pypi-downloads-30-days.json', mode='rt', encoding='utf8') as fd:
        rows = json.load(fd)['rows']
    with open('pypi-dist-info.json', mode='rt', encoding='utf8') as fd:
        latest_releases: dict[str, ReleaseMetadata] = json.load(fd)
    release_count = 0
    core_metadata_count = 0

    projects = [r['project'] for r in rows[:50]]
    for name in projects:
        logger.info('Processing %s', name)
        time.sleep(2.0)

        if name in latest_releases:
            release: None | ReleaseMetadata = latest_releases[name]
        else:
            release = retrieve_metadata(name)

        if release is None:
            continue

        latest_releases[name] = release
        release_count += 1
        core_metadata_count += bool(release.get('core-metadata'))

    print()
    with open('pypi-dist-info.json', mode='wt', encoding='utf8') as fd:
        json.dump(latest_releases, fd, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main(sys.argv)
""",
# ------------------------------------------------------------------------------
"cargo/marker.py":
b"""from dataclasses import dataclass
from enum import auto, Enum
import re
from typing import Callable, cast

from .name import canonicalize


__all__ = (\x22extract_extra\x22,)


SYNTAX = re.compile(
    r\x22\x22\x22
        (?P<BLANK> \\s+)
        | (?P<OPEN> [(])
        | (?P<CLOSE> [)])
        | (?P<COMP> <=? | != | ===? | >=? | ~= | not\\s+in | in)
        | (?P<BOOL> and | or)
        | (?P<LIT> '[^']*' | \x22[^\x22]*\x22)
        | (?P<VAR>  [a-z] (?: [a-z._-]* [a-z])?)
    \x22\x22\x22,
    re.VERBOSE,
)


VARIABLE_NAMES = set(
    [
        \x22python_version\x22,
        \x22python_full_version\x22,
        \x22os_name\x22,
        \x22sys_platform\x22,
        \x22platform_release\x22,
        \x22platform_system\x22,
        \x22platform_version\x22,
        \x22platform_machine\x22,
        \x22platform_python_implementation\x22,
        \x22implementation_name\x22,
        \x22implementation_version\x22,
        \x22extra\x22,
    ]
)


class TypTok(Enum):
    \x22\x22\x22
    The type of a token.

    Tokens with the `EXTRA` or `NOT_EXTRA` type do not appear in marker
    expressions. But a marker expression is reducible to one of these tokens
    with `distill_extra()`.
    \x22\x22\x22

    BLANK = auto()  # spacing

    LIT = auto()  # string literals, incl. their quotes
    VAR = auto()  # variables incl. extra
    COMP = auto()  # comparison operators, which combine LIT and VAR
    BOOL = auto()  # boolean and/or, which combine COMP-triples
    OPEN = auto()  # open parenthesis
    CLOSE = auto()  # close parenthesis

    EXTRA = auto()  # an \x22extra == 'tag'\x22 expression
    NOT_EXTRA = auto()  # any combination of well-formed expressions without extra


# The single letter version makes the code eminently more readable.
T = TypTok


@dataclass(frozen=True, slots=True)
class Token:
    \x22\x22\x22Representation of a token.\x22\x22\x22
    tag: TypTok
    content: str


# The canonical not-extra token
ELIDED = Token(T.NOT_EXTRA, \x22\xf0\x9f\x9f\x85\x22)

# ======================================================================================

def apply_operator(left: Token, op: Token, right: Token) -> Token:
    \x22\x22\x22
    Apply the infix operator on its arguments. The left and right tokens must be
    a variable, literal, extra, or not-extra token. The operator token must be a
    comparison or boolean combinator.
    \x22\x22\x22
    assert op.tag in (T.COMP, T.BOOL)

    match left.tag, op.tag, right.tag:
        # Yes, the following two cases are symmetric and could be factored into
        # their own function. But ensuring that the function was invoked with
        # the right arguments would require repeating the match again. So I'd
        # rather have some minor code duplication.

        case T.VAR, T.COMP, T.LIT:
            if left.content == 'extra':
                if op.content == '==' and len(right.content) >= 3:
                    return Token(T.EXTRA, canonicalize(right.content[1:-1]))
                raise SyntaxError(f'invalid term \x22extra {op.content} {right.content}\x22')
            else:
                return ELIDED

        case T.LIT, T.COMP, T.VAR:
            if right.content == 'extra':
                if op.content == '==' and len(left.content) >= 3:
                    return Token(T.EXTRA, canonicalize(left.content[1:-1]))
                raise SyntaxError(f'invalid term \x22{left.content} {op.content} extra\x22')
            else:
                return ELIDED

        case _, T.COMP, _:
            l, o, r = left.content, op.content, right.content
            raise SyntaxError(f'not a valid comparison \x22{l} {o} {r}\x22')

        case (T.EXTRA, T.BOOL, T.EXTRA) if left.content == right.content:
            return left
        case T.EXTRA, T.BOOL, T.EXTRA:
            l, r = left.content, right.content
            raise SyntaxError(f'marker with multiple extras \x22{l}\x22 and \x22{r}\x22')

        case (T.EXTRA, T.BOOL, T.NOT_EXTRA) if op.content == \x22and\x22:
            return left
        case T.EXTRA, T.BOOL, T.NOT_EXTRA:
            raise SyntaxError(f'disjunction of extra \x22{left.content}\x22 and non-extra')

        case (T.NOT_EXTRA, T.BOOL, T.EXTRA) if op.content == \x22and\x22:
            return right
        case T.NOT_EXTRA, T.BOOL, T.EXTRA:
            raise SyntaxError(f'disjunction of non-extra and extra \x22{right.content}\x22')

        case T.NOT_EXTRA, T.BOOL, T.NOT_EXTRA:
            return ELIDED

    raise AssertionError('unreachable')


class TokenString:
    \x22\x22\x22
    A token string.

    This class represents the input for marker evaluation as a sequence of
    tokens. It also tracks the start, current, and stop index. While that
    implies that instances of this class are mutable, only the current position
    ever changes. That facilitates optimized recursive evaluation of
    (parenthesized) substrings through (zero-copy) buffer sharing.

    As usual for Python ranges, slices, and sequences, the stop index is one
    larger than the last token. If the start index is the same, the token string
    is empty. If the current index is the same, then there are no more tokens
    available for reading via `peek()` or `next()`. Before invoking either
    method, code using this class must check for the availability of tokens with
    `has_next()`.
    \x22\x22\x22

    @classmethod
    def from_string(cls, marker: str) -> \x22TokenString\x22:
        \x22\x22\x22Tokenize the given character string.\x22\x22\x22
        tokens = []
        cursor = 0
        while t := SYNTAX.match(marker, cursor):
            cursor = t.end()
            tag = cast(str, t.lastgroup)
            content = t.group()
            if tag == \x22VAR\x22:
                content = content.replace('-', '_').replace('.', '_')
                if content not in VARIABLE_NAMES:
                    raise SyntaxError(f'marker contains unknown variable \x22{content}\x22')
            tokens.append(Token(TypTok[tag], content))

        if cursor < len(marker):
            raise SyntaxError(f'marker contains invalid characters \x22{marker[cursor:]}\x22')

        return cls(tokens, 0, len(tokens))

    __slots__ = (\x22_tokens\x22, \x22_start\x22, \x22_stop\x22, \x22_cursor\x22)

    def __init__(self, tokens: list[Token], start: int, stop: int) -> None:
        assert 0 <= start <= stop <= len(tokens)
        self._tokens = tokens
        self._start = start
        self._stop = stop
        self._cursor = start
        self._step_over_spacing()

    def _step_over_spacing(self) -> None:
        \x22\x22\x22
        Step over spacing so that current position either is at end of string or
        points to a non-space token. This method should be invoked whenever the
        current position has been advanced, notably from within `next()`, but
        also from within the constructor and from within `parenthesized()`.
        \x22\x22\x22
        cursor = self._cursor
        stop = self._stop
        tokens = self._tokens

        while cursor < stop and tokens[cursor].tag is T.BLANK:
            cursor += 1
        self._cursor = cursor

    def has_next(self) -> bool:
        \x22\x22\x22
        Determine whether the current position points to a token. Code using
        this class must check this method before invoking `peek()` or `next()`.
        \x22\x22\x22
        return self._cursor < self._stop

    def peek(self) -> Token:
        \x22\x22\x22Return the next token without consuming it.\x22\x22\x22
        return self._tokens[self._cursor]

    def next(self) -> Token:
        \x22\x22\x22
        Return the next token and advance the current position to the next
        non-space token thereafter.
        \x22\x22\x22
        token = self._tokens[self._cursor]
        self._cursor += 1
        self._step_over_spacing()
        return token

    def parenthesized(self) -> \x22TokenString\x22:
        \x22\x22\x22
        Return the parenthesized expression starting at the current position.
        This method returns a token string that shares the same token buffer as
        this token string but has its start (also current) and stop indices set
        to the first and last token of the parenthesized expression (i.e., sans
        parentheses). It also updates this string's current position to the
        first non-space token after the closing parenthesis. The scan for the
        closing parenthesis correctly accounts for nested parentheses.
        \x22\x22\x22
        tokens = self._tokens
        cursor = self._cursor
        assert tokens[cursor].tag is T.OPEN

        nesting = 0
        for index in range(cursor + 1, self._stop):
            token = tokens[index]
            match token.tag:
                case T.CLOSE if nesting == 0:
                    string = TokenString(tokens, cursor + 1, index)
                    self._cursor = index + 1
                    self._step_over_spacing()
                    return string
                case T.OPEN:
                    nesting += 1
                case T.CLOSE:
                    nesting -= 1

        raise SyntaxError(f\x22opening parenthesis without closing one in '{self}'\x22)

    def __str__(self) -> str:
        return \x22\x22.join(t.content for t in self._tokens[self._cursor : self._stop])


class TokenStack:
    \x22\x22\x22
    A token stack. While distilling a marker to its (hopefully) only extra, the
    `distill_extra()` function uses a token stack as the primary mutable state.
    Methods draw on familiar parser terminology and techniques because marker
    evaluation *is* marker parsing.
    \x22\x22\x22

    def __init__(self) -> None:
        self._stack: list[Token] = []

    def __len__(self) -> int:
        return len(self._stack)

    def stringify(self, count: int) -> str:
        \x22\x22\x22Convert the top count tokens into a left-to-right readable string.\x22\x22\x22
        assert count <= len(self._stack)

        parts = []
        for index, token in enumerate(self._stack.__reversed__()):
            if index == count:
                break
            parts.append(token.content)
        return \x22 \x22.join(parts)

    def unwrap(self) -> Token:
        \x22\x22\x22Return the only token left on this stack.\x22\x22\x22
        assert len(self._stack) == 1
        return self._stack[0]

    def shift(self, *tokens: Token) -> None:
        \x22\x22\x22Shift the given tokens, in order, onto this stack.\x22\x22\x22
        self._stack.extend(tokens)

    def is_reducible(
        self,
        operator_tag: TypTok,
        operator_content: None | str = None,
        *operand_tags: TypTok,
    ) -> bool:
        \x22\x22\x22
        Determine whether this stack is reducible because it has at least three
        tokens with the given operator tag, operator content, and operand tags.
        \x22\x22\x22
        stack = self._stack
        return (
            len(stack) >= 3
            and operator_tag is stack[-2].tag
            and (operator_content is None or operator_content == stack[-2].content)
            and stack[-1].tag is not T.OPEN
            and (len(operand_tags) == 0 or (
                stack[-1].tag in operand_tags and stack[-3].tag in operand_tags
            ))
        )

    def reduce_with(self, reducer: Callable[[Token, Token, Token], Token]) -> None:
        \x22\x22\x22Reduce this stack's top three tokens to one with the given function.\x22\x22\x22
        stack = self._stack
        right = stack.pop()
        op = stack.pop()
        left = stack.pop()
        stack.append(reducer(left, op, right))


def distill_extra(tokens: TokenString) -> Token:
    \x22\x22\x22
    Distill the given token string down to a single extra or not-extra token.
    This function parses the token string while tracking whether terms contain
    extra or not. This function accepts only terms that restrict extra to equal
    some literal name, e.g., `\x22<name>\x22 == extra`, but not with other operators
    or more than one name per marker. This function signals errors as
    `SyntaxError`.
    \x22\x22\x22
    stack = TokenStack()

    # An actual LR parser for marker expressions would require an explicit state
    # machine with 16 distinct states (really, I generated one first). The
    # following implementation is much simpler and hence nicer thanks to (1)
    # careful interface design for TokenString and TokenStack, (2) very careful
    # ordering of shift/reduce operations, (3) the dynamic inspection of the
    # token stack with `is_reducible()`, and (4) the recursive invocation of
    # `distill_extra()` for parenthesized expressions. Of course, it still helps
    # that the marker expression syntax is very simple.

    while True:
        # Shift an operand onto the stack
        if tokens.has_next():
            if tokens.peek().tag is T.OPEN:
                parenthesized = tokens.parenthesized()
                stack.shift(distill_extra(parenthesized))
            elif tokens.peek().tag in (T.VAR, T.LIT):
                stack.shift(tokens.next())
            else:
                raise SyntaxError(f'expected operand, found \x22{tokens}\x22')
        # Try to reduce a comparison
        if stack.is_reducible(T.COMP):
            stack.reduce_with(apply_operator)
        # Try to reduce a conjunction. Top of stack mustn't be variable or literal.
        if stack.is_reducible(T.BOOL, 'and', T.EXTRA, T.NOT_EXTRA):
            stack.reduce_with(apply_operator)
        # Shift an operator onto the stack and restart cascade.
        if tokens.has_next():
            if tokens.peek().tag in (T.COMP, T.BOOL):
                stack.shift(tokens.next())
            else:
                raise SyntaxError(f'expected operator, found \x22{tokens}\x22')
            continue
        # All tokens have been consumed. All comparisons and conjunctions have
        # been reduced. That should leave only disjunctions.
        if len(stack) > 1 and not stack.is_reducible(T.BOOL, \x22or\x22):
            raise SyntaxError('expected operand but marker ended already')
        break

    # Reduce disjunctions until the stack has only one token. That's our result.
    while len(stack) > 1:
        assert stack.is_reducible(T.BOOL, \x22or\x22)
        stack.reduce_with(apply_operator)

    return stack.unwrap()


def extract_extra(marker: str) -> None | str:
    \x22\x22\x22
    Extract the extra name from an environment marker. If the marker contains a
    term constraining extra like `\x22<name>\x22 == extra`, this function returns that
    name. It treats operators other than `==` or the presence of more than one
    extra name as errors. This function signals errors as `ValueError`.
    \x22\x22\x22
    try:
        token = distill_extra(TokenString.from_string(marker))
    except SyntaxError:
        raise ValueError(f\x22malformed marker '{marker}'\x22)
    else:
        match token.tag:
            case T.EXTRA:
                return token.content
            case T.NOT_EXTRA:
                return None
            case _:
                raise ValueError(f\x22malformed marker '{marker}'\x22)
""",
# ------------------------------------------------------------------------------
"cargo/name.py":
b"""import datetime
import re


__all__ = ('canonicalized', 'split_hash', 'today_as_version')


_DASHING = re.compile(r'[-_.]+')


def canonicalize(name: str, separator: str = '-') -> str:
    \x22\x22\x22Canonicalize the distribution, package, or package extra name.\x22\x22\x22
    return _DASHING.sub(separator, name).lower()


def split_hash(url: str) -> None | tuple[str, str, str]:
    \x22\x22\x22Remove the URL's anchor, which identifies the resource's hash value.\x22\x22\x22
    url, _, hash = url.partition('#')
    if len(hash) == 0:
        return None

    algo, _, value = hash.partition('=')
    if len(algo) == 0 or len(value) == 0:
        return None

    return url, algo, value


def today_as_version() -> str:
    return '.'.join(str(part) for part in datetime.date.today().isocalendar())
""",
# ------------------------------------------------------------------------------
"cargo/requirement.py":
b"""from collections.abc import Iterator
import re
from typing import NamedTuple

from .marker import extract_extra
from .name import canonicalize


__all__ = ('Requirement',)

PARTS: re.Pattern[str] = re.compile(
    r\x22\x22\x22
        ^
               (?P<package>   [^[(;\\s]+    )    [ ]*
        (?: \\[ (?P<extras>    [^]]+        ) \\] [ ]* )?
        (?: \\( (?P<versions1> [^)]*        ) \\) [ ]* )?
        (?:    (?P<versions2> [<!=>~][^;]* )    [ ]* )?
        (?:  ; (?P<marker>    .*           )         )?
        $
    \x22\x22\x22,
    re.VERBOSE)


class Requirement(NamedTuple):
    \x22\x22\x22
    Preliminary, rough representation of a requirement. Clearly, this class is
    not the final word, but it turns one huge problem into several smaller ones.
    \x22\x22\x22

    package: str
    extras: tuple[str,...]
    versions: tuple[str,...]
    extra: None | str

    @classmethod
    def from_string(cls, requirement: str) -> 'Requirement':
        if (parts := PARTS.match(requirement)) is None:
            raise ValueError(f'invalid requirement \x22{requirement}')

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
""",
# ------------------------------------------------------------------------------
"cargo/rules.txt":
b"""pre-releases:
    only consider as candidate if
      * already installed;
      * there is no matching final or post;

V must not contain local unless explicitly allowed. Candidate's local must be ignored


~= V.N  =>  >= V.N, == V.*

    No local
    ignore pre, post, or dev part on prefix match
        eg  ~= V.N.post  becomes >= V.N.post, == V.*


== V

    strict equality with zero padding on C and V
    if V public, ignore C.local
    if V local, C.local must be string equal

== V.*

    no dev, no local
    ignore C.local

!= is just negation

<=, >=

    just order
    no V.local

>, <

    similar but exclude pre, post, and local of V  --> hence:

    >V  does NOT match V.post  unless it's >V.post
    >V  does NOT match V.local

    <V  does NOT match V.pre  unless < V.pre

    no V.local

====

    string equality
""",
# ------------------------------------------------------------------------------
"cargo/version.py":
b"""\x22\x22\x22
Support for version identifiers compatible with [PEP
440](https://peps.python.org/pep-0440/).

This module implements largely the same functionality as packaging's [version
module](https://github.com/pypa/packaging/blob/main/src/packaging/version.py) in
a fairly similar manner. In particular, this module also represents each version
with two tuples, `Data` and `Key`. While both tuples have the same named fields,
they differ in types and contents, with `Data` optimized for accessing
individual segments and `Key` optimized for implementing a total ordering of
versions. The `Version` class combines the two into a coherent interface.

Otherwise, the two implementations differ significantly:

  * Where packaging spreads the implementation over several modules, this module
    is purposefully designed to stand on its own. It has *no* dependencies
    besides `itertools`, `re`, and `typing` from the standard library.
  * Where packaging treats its data and key tuples as implementation details,
    this module provides most functionality though the `Data` tuple because that
    enables simpler and more efficient implementation of higher level features.
  * Its `Version` class nonetheless exposes much of the same interface through
    Python's `__getattr__()` fallback method. It relies on a separate interface
    declaration (in `version.pyi`) to enable static typing just as well.
  * Where packaging has `public` and `base_version` properties that, bizarrely,
    return strings, this module has `public_version` and `base_version`
    properties that return version objects.
  * `Data.release_components()` returns the release with a desired precision,
    i.e., number of components. It adds and removes least significant components
    as necessary. Newly added components are, of course, zero.
  * The implementation gets by just fine with `-1` and `float('inf')`. In
    contrast, packaging defines two classes for objects that are smaller and
    larger than all other Python objects, which strikes me as plainly
    overdesigned.

Both packaging and this module convert version identifiers to their canonical
representation while parsing and thus do not retain any information about their
original notation. Both also retain trailing zero components for release
segments. While such components have no impact on version equality and ordering,
they do impact the evaluation of the `~=` compatibility operator.
\x22\x22\x22

import itertools as it
import re
from typing import Any, Callable, cast, Literal, NamedTuple


__all__ = (\x22Data\x22, \x22Key\x22, \x22Version\x22, \x22Specifier\x22)

INFINITY = float('inf')
NOT_A_LABEL = '\xe2\x98\x85'
OPERATOR = re.compile('<=?|==|>=?|~=|!=')
STATUS_LABELS = {
    \x22a\x22: \x22a\x22,
    \x22alpha\x22: \x22a\x22,
    \x22b\x22: \x22b\x22,
    \x22beta\x22: \x22b\x22,
    \x22c\x22: \x22rc\x22,
    \x22pre\x22: \x22rc\x22,
    \x22preview\x22: \x22rc\x22,
    \x22rc\x22: \x22rc\x22,
    \x22post\x22: \x22post\x22,
    \x22r\x22: \x22post\x22,
    \x22rev\x22: \x22post\x22,
    \x22dev\x22: \x22dev\x22,
}
SEPARATOR = re.compile(r'[._-]')
SPACING = re.compile('\\s+')
SYNTAX = re.compile(
    r\x22\x22\x22
        [v]?
        (?:(?P<epoch>[0-9]+)[!])?
        (?P<release>[0-9]+(?:[.][0-9]+)*)
        (?:
            [._-]?     (?P<pre_label>   a(?:lpha)?|b(?:eta)?|c|pre(?:view)?|rc)
            (?: [._-]? (?P<pre_number>  [0-9]+) )?
        )?
        (?:
            (?: [-] (?P<post_simple> [0-9]+) )
            |
            [._-]?     (?P<post_label>  post|r(?:ev)?)
            (?: [._-]? (?P<post_number> [0-9]+) )?
        )?
        (?:
            [._-]?     (?P<dev_label>   dev)
            (?: [._-]? (?P<dev_number>  [0-9]+) )?
        )?
        (?:
            [+]        (?P<local>       [a-z0-9]+(?:[._-][a-z0-9]+)*)
        )?
    \x22\x22\x22,
    re.X | re.I,
)


class Key(NamedTuple):
    \x22\x22\x22A version key for implementing a total order of version identifiers.\x22\x22\x22

    epoch: int
    release: tuple[int, ...]
    status: Literal[\x22a\x22, \x22b\x22, \x22rc\x22, \x22\xe2\x98\x85\x22]
    pre: int | float
    post: int
    dev: int | float
    local: tuple[tuple[int, str], ...]


class Data(NamedTuple):
    \x22\x22\x22
    The individual segments of a version identifier. A `None` value indicates
    that the corresponding segment is not present. The `status` and `pre` fields
    must both be either `None` or have a value. The `local` field preserves the
    local segment as written, which is required for determining compatibility.
    However, for ordering, `Key` contains a parsed representation that breaks
    the string into components separated by `.`, `_`, or `-` and, if possible,
    parsed as integers.
    \x22\x22\x22

    epoch: int
    release: tuple[int, ...]
    status: None | Literal[\x22a\x22, \x22b\x22, \x22rc\x22]
    pre: None | int
    post: None | int
    dev: None | int
    local: None | str

    @classmethod
    def from_string(cls, version: str) -> 'Data':
        \x22\x22\x22Parse the given version identifier.\x22\x22\x22

        segments = SYNTAX.match(version.strip().lower())
        if segments is None:
            raise ValueError(f'not a version string \x22{version}\x22')

        def parse(
            label: None | str, value: None | str
        ) -> tuple[None | str, None | int]:
            return (
                (None, None)
                if label is None
                else (STATUS_LABELS[label], 0 if value is None else int(value))
            )

        epoch = cast(int, segments.group(\x22epoch\x22)) or 0
        release = tuple(int(p) for p in segments.group(\x22release\x22).split(\x22.\x22))
        status, pre = parse(segments.group('pre_label'), segments.group('pre_number'))
        if (simple_post := segments.group(\x22post_simple\x22)) is not None:
            post: None | int = int(simple_post)
        else:
            _, post = parse(segments.group(\x22post_label\x22), segments.group(\x22post_number\x22))
        _, dev = parse(segments.group(\x22dev_label\x22), segments.group(\x22dev_number\x22))
        local = segments.group(\x22local\x22)

        status = cast(None | Literal['a', 'b', 'rc'], status)
        return cls(epoch, release, status, pre, post, dev, local)

    def release_components(self, precision: int) -> tuple[int, ...]:
        \x22\x22\x22Return the release components with the given precision.\x22\x22\x22
        return tuple(it.islice(it.chain(self.release, it.repeat(0)), precision))

    def release_text(self) -> str:
        \x22\x22\x22Return the release components as a string.\x22\x22\x22
        return '.'.join(str(n) for n in self.release)

    def release_is_prefix(
        self,
        candidate: 'Data',
        *,
        ignore_last: bool = False,
    ) -> bool:
        \x22\x22\x22
        Determine whether this version data's release is a prefix of the
        candidate's release. If `ignore_last` is `True`, this method does not
        include the prefix's last and therefore least significant component in
        the comparison.
        \x22\x22\x22
        prefix = self.release
        prefix_length = len(prefix)
        if ignore_last and prefix_length <= 1 or not ignore_last and prefix_length == 0:
            raise ValueError(f'release has too few components ({prefix_length})')
        if ignore_last:
            prefix, prefix_length = prefix[:-1], prefix_length - 1

        release = candidate.release
        release_length = len(release)

        if prefix_length > release_length:
            return (
                prefix[:release_length] == release
                and all(c == 0 for c in prefix[release_length:])
            )
        elif prefix_length == release_length:
            return prefix == release
        else:
            return prefix == release[:prefix_length]

    def has_pre(self) -> bool:
        \x22\x22\x22Determine whether this version has a pre segment.\x22\x22\x22
        return self.pre is not None

    def has_post(self) -> bool:
        \x22\x22\x22Determine whether this version has a post segment.\x22\x22\x22
        return self.post is not None

    def has_dev(self) -> bool:
        \x22\x22\x22Determine whether this version has a dev segment.\x22\x22\x22
        return self.dev is not None

    def has_local(self) -> bool:
        \x22\x22\x22Determine whether this version has a local segment.\x22\x22\x22
        return self.local is not None

    def is_prerelease(self) -> bool:
        \x22\x22\x22
        Determine whether this version is a prerelease, i.e., has either a pre
        or a dev segment.
        \x22\x22\x22
        return self.pre is not None or self.dev is not None

    def only_public(self) -> 'Data':
        \x22\x22\x22Return the same version but without a local segment.\x22\x22\x22
        if self.local is None:
            return self
        return self.__class__(
            self.epoch, self.release, self.status, self.pre, self.post, self.dev, None
        )

    def only_epoch_and_release(self) -> 'Data':
        \x22\x22\x22Return the same version but with only epoch and release segments.\x22\x22\x22
        if (
            self.pre is None
            and self.post is None
            and self.dev is None
            and self.local is None
        ):
            return self
        return self.__class__(self.epoch, self.release, None, None, None, None, None)

    def to_key(self) -> Key:
        \x22\x22\x22Compute the key for this version.\x22\x22\x22
        release = tuple(
            reversed(list(it.dropwhile(lambda v: v == 0, reversed(self.release))))
        )

        if self.pre is None and self.post is None and self.dev is not None:
            pre: float = -1
        elif self.pre is None:
            pre = INFINITY
        else:
            pre = self.pre

        if self.post is None:
            post: int = -1
        else:
            post = self.post

        if self.dev is None:
            dev: float = INFINITY
        else:
            dev = self.dev

        if self.local is None:
            local: tuple[tuple[int, str], ...] = ()
        else:
            local = tuple(
                (i, '') if isinstance(i, int) else (-1, i)
                for i in SEPARATOR.split(self.local)
            )

        return Key(self.epoch, release, self.status or \x22\xe2\x98\x85\x22, pre, post, dev, local)

    def __repr__(self) -> str:
        return f\x22VersionData({', '.join(f'{f!r}' for f in self)})\x22

    def __str__(self) -> str:
        fragments = []

        if (epoch := self.epoch) > 0:
            fragments.append(f'{epoch}!')
        fragments.append(self.release_text())
        if (status := self.status) is not None:
            fragments.append(f'{status}{self.pre}')
        if (post := self.post) is not None:
            fragments.append(f'.post{post}')
        if (dev := self.dev) is not None:
            fragments.append(f'.dev{dev}')
        if (local := self.local) is not None:
            fragments.append(f'+{local}')

        return ''.join(fragments)


class Version:
    \x22\x22\x22
    A parsed version identifier.

    This class combines a `Data` and `Key` instance to provide a fully-featured
    interface. Even though it does not re-implement `Data`'s properties and
    methods for accessing version segments, it nonetheless exposes them through
    its `__getattr__()` method. The static types for those properties and
    methods are defined in a separate interface file, `version.pyi`.
    \x22\x22\x22

    __slots__ = ('_data', '_key')

    def __init__(self, version: str | Data, key: None | Key = None) -> None:
        if isinstance(version, str):
            version = Data.from_string(version)
        if key is None:
            key = version.to_key()

        self._data = version
        self._key = key

    @property
    def data(self) -> Data:
        \x22\x22\x22Return the version data.\x22\x22\x22
        return self._data

    @property
    def public_version(self) -> 'Version':
        \x22\x22\x22Return the same version but without a local segment.\x22\x22\x22
        if self._data.local is None:
            return self
        return Version(self._data.only_public())

    @property
    def base_version(self) -> 'Version':
        \x22\x22\x22Return the same version but with only epoch and release segments.\x22\x22\x22
        data = self._data
        if (
            data.pre is None
            and data.post is None
            and data.dev is None
            and data.local is None
        ):
            return self

        return Version(data.only_epoch_and_release())

    def is_exact_match(self, candidate: 'Version') -> bool:
        \x22\x22\x22Determine whether the candidate is an exact match for this version.\x22\x22\x22
        return (
            self.public_version == candidate.public_version
            and (not self.has_local() or self.local == candidate.local)
        )

    def is_prefix_match(self, candidate: 'Version', ignore_last: bool = False) -> bool:
        \x22\x22\x22Determine whether the candidate is a prefix match for this version.\x22\x22\x22
        d1, d2 = self.data, candidate.data
        return (
            d1.epoch == d2.epoch
            and d1.release_is_prefix(d2, ignore_last=ignore_last)
            and (not d1.has_pre() or d1.status == d2.status and d1.pre == d2.pre)
            and (not d1.has_post() or d1.post == d2.post)
        )

    def is_greater_match(self, candidate: 'Version') -> bool:
        \x22\x22\x22Determine whether the candidate is a greater match for this version.\x22\x22\x22
        return (
            not candidate.has_local()
            and candidate > self
            and (self.has_post() or candidate.base_version != self.base_version)
        )

    def is_lesser_match(self, candidate: 'Version') -> bool:
        \x22\x22\x22Determine whether the candidate is a lesser match for this version.\x22\x22\x22
        return (
            not candidate.has_local()
            and candidate < self
            and (self.has_pre() or candidate.base_version != self.base_version)
        )

    def is_compatible_match(self, candidate: 'Version') -> bool:
        \x22\x22\x22Determine whether the candidate is a compatible match for this version.\x22\x22\x22
        candidate = candidate.public_version
        return (
            self <= candidate
            and self.base_version.is_prefix_match(candidate, ignore_last=True)
        )

    def __lt__(self, other: object) -> bool:
        if isinstance(other, Version):
            return self._key < other._key
        return NotImplemented

    def __le__(self, other: object) -> bool:
        if isinstance(other, Version):
            return self._key <= other._key
        return NotImplemented

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Version):
            return self._key == other._key
        return NotImplemented

    def __ge__(self, other: object) -> bool:
        if isinstance(other, Version):
            return self._key >= other._key
        return NotImplemented

    def __gt__(self, other: object) -> bool:
        if isinstance(other, Version):
            return self._key > other._key
        return NotImplemented

    def __getattr__(self, name: str) -> Any:  # type: ignore[misc]
        return getattr(self._data, name)

    def __repr__(self) -> str:
        return f\x22Version({', '.join(f'{f!r}' for f in self._data)})\x22

    def __str__(self) -> str:
        return str(self._data)


class Specifier:
    \x22\x22\x22Representation of a version specifier.\x22\x22\x22

    __slots__ = ('_text', '_predicate')

    def __init__(self, specifier: str) -> None:
        specifier = specifier.strip()
        is_prefix_match = specifier.endswith('.*')
        if (op_match := OPERATOR.match(specifier)) is None:
            raise ValueError(f'unknown operator in version specifier \x22{specifier}\x22')
        operator = op_match.group()

        version_start = len(operator)
        version_stop = -2 if is_prefix_match else len(specifier)
        version = Version(specifier[version_start:version_stop])
        self._text = f'{operator} {version}{\x22.*\x22 if is_prefix_match else \x22\x22}'

        if operator != '==' and operator != '!=' and version.has_local():
            raise ValueError(f'operator {operator} cannot be used with local version')
        if is_prefix_match and version.has_dev():
            raise ValueError(f'prefix match cannot be used with dev version')

        match operator:
            case '<':
                predicate = lambda candidate: version.is_lesser_match(candidate)
            case '<=':
                predicate = lambda candidate: candidate <= version
            case '==' if is_prefix_match:
                predicate = lambda candidate: version.is_prefix_match(candidate)
            case '==':
                predicate = lambda candidate: version.is_exact_match(candidate)
            case '~=':
                predicate = lambda candidate: version.is_compatible_match(candidate)
            case '!=' if is_prefix_match:
                predicate = lambda candidate: not version.is_prefix_match(candidate)
            case '!=':
                predicate = lambda candidate: not version.is_exact_match(candidate)
            case '>=':
                predicate = lambda candidate: candidate >= version
            case '>':
                predicate = lambda candidate: version.is_greater_match(candidate)

        self._predicate: Callable[[object], bool] = predicate

    @property
    def __name__(self) -> str:
        return self._text

    def __call__(self, candidate: Version) -> bool:
        return self._predicate(candidate)

    def __str__(self) -> str:
        return self._text
""",
# ------------------------------------------------------------------------------
"tsutsumu/__main__.py":
b"""from argparse import ArgumentParser, HelpFormatter, RawTextHelpFormatter
from dataclasses import dataclass, field
import os
import sys
from textwrap import dedent
import traceback

from .maker import BundleMaker


def parser() -> ArgumentParser:
    try:
        width = min(os.get_terminal_size()[0], 70)
    except:
        width = 70

    def width_limited_formatter(prog: str) -> HelpFormatter:
        return RawTextHelpFormatter(prog, width=width)

    parser = ArgumentParser('tsutsumu',
        description=dedent(\x22\x22\x22
            Combine Python modules and related resources into a single,
            self-contained file.

            Tsutsumu automatically determines which files to include in a bundle
            by tracing a main package's dependencies at the granularity of
            packages and their extras. That means that either all of a package's
            or extra's files are included in a bundle or none of them. While
            that may end up bundling files that aren't really needed, it also is
            more robust because it follows the same recipe as package building
            and similar tools.

            Tsutsumu supports two different bundle formats. It defaults to its
            own, textual bundle format, which is particularly suitable to use
            cases, where trust is lacking and a bundle's source code should be
            readily inspectable before execution or where the runtime
            environment is resource-constrained. For use under less stringent
            requirements, Tsutsumu also targets the `zipapp` format included in
            Python's standard library, which is a bit more resource-intensive
            but also produces smaller bundles. Please use `-f`/`--format` to
            explicitly select the bundle's format.

            Tsutsumu includes the code for bootstrapping and executing the code
            in a bundle with the bundle for its own, textual format. That isn't
            necessary for the `zipapp` format, which has been supported by
            Python's standard library since version 3.5. In either case, bundles
            execute some main module's code very much like \x22python -m\x22 does. If
            the bundled modules include exactly one __main__ module, Tsutsumu
            automatically selects that module. If there are no or several such
            modules or you want to execute another, non-main module, please use
            the `-m`/`--main` option to specify the module name. Use the
            `-b`/`--bundle-only` option to omit the runtime code from Tsutsumu's
            textual format.

            Tsutsumu is \xc2\xa9 2023 Robert Grimm. It is licensed under Apache 2.0.
            The source repository is <https://github.com/apparebit/tsutsumu>
        \x22\x22\x22),
        formatter_class=width_limited_formatter)
    parser.add_argument(
        '-b', '--bundle-only',
        action='store_true',
        help='emit only bundled files and their manifest,\\nno runtime code')
    parser.add_argument(
        '-f', '--format',
        choices=('text', 'zipapp'),
        help=\x22select Tsutsumu's textual bundle format or\\nzipapp's more \x22
        \x22compact, binary one\x22)
    parser.add_argument(
        '-m', '--main',
        metavar='MODULE',
        help=\x22if a package, execute its __main__ module;\\n\x22
        \x22if a module, execute this module\x22)
    parser.add_argument(
        '-o', '--output',
        metavar='FILENAME',
        help='write bundle to this file')
    parser.add_argument(
        '-r', '--repackage',
        action='store_true',
        help='repackage runtime as \x22tsutsumu.bundle.Bundle\x22')
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='enable verbose output')
    parser.add_argument(
        'roots',
        metavar='PKGROOT', nargs='+',
        help=\x22include all Python modules reachable from\\nthe package's root directory\x22)
    return parser


@dataclass
class ToolOptions:
    bundle_only: bool = False
    main: 'None | str' = None
    output: 'None | str' = None
    repackage: bool = False
    verbose: bool = False
    roots: 'list[str]' = field(default_factory=list)


def main() -> None:
    options = parser().parse_args(namespace=ToolOptions())

    try:
        if options.bundle_only and (options.main or options.repackage):
            raise ValueError('--bundle is incompatible with --main/--repackage')

        BundleMaker(
            options.roots,
            bundle_only=options.bundle_only,
            main=options.main,
            output=options.output,
            repackage=options.repackage,
        ).run()
    except Exception as x:
        if options.verbose:
            traceback.print_exception(x)
        else:
            print(f'Error: {x}')
        sys.exit(1)


if __name__ == '__main__':
    main()
""",
# ------------------------------------------------------------------------------
"tsutsumu/debug.py":
b"""from pathlib import Path
import sys

from tsutsumu.bundle import Toolbox


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: python -m tsutsumu <path-to-bundle>')
        sys.exit(1)

    bundle = Path(sys.argv[1])
    if bundle.suffix != '.py':
        print(f'Error: bundle \x22{bundle}\x22 does not appear to be Python source code')
        sys.exit(1)

    try:
        version, manifest = Toolbox.load_meta_data(bundle)
    except Exception as x:
        print(f\x22Error: unable to load meta data ({x})\x22)
        sys.exit(1)

    for key, (kind, offset, length) in manifest.items():
        if length == 0:
            print(f'bundled file \x22{key}\x22 is empty')
            continue

        try:
            data = Toolbox.load_from_bundle(bundle, kind, offset, length)
            print(f'bundled file \x22{key}\x22 has {len(data)} bytes')
        except Exception as x:
            print(f'Error: bundled file \x22{key}\x22 is malformed ({x}):')
            with open(bundle, mode='rb') as file:
                file.seek(offset)
                raw_data = file.read(length)
            for line in raw_data.splitlines():
                print(f'    {line!r}')
            print()
""",
# ------------------------------------------------------------------------------
"tsutsumu/maker.py":
b"""import base64
from contextlib import nullcontext
from enum import Enum
from keyword import iskeyword
import os.path
from pathlib import Path
import sys
from typing import NamedTuple, TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Sequence
    from contextlib import AbstractContextManager
    from importlib.abc import Loader
    from importlib.machinery import ModuleSpec
    from typing import Callable, Protocol

    class Writable(Protocol):
        def write(self, data: 'bytes | bytearray') -> int:
            ...

from tsutsumu import __version__
from tsutsumu.bundle import Toolbox

# --------------------------------------------------------------------------------------
# File names and extensions acceptable for bundling

_BINARY_EXTENSIONS = (
    '.jpg',
    '.png',
)

_BINARY_FILES = ()

_TEXT_EXTENSIONS = (
    '.cfg',
    '.json',
    '.md',
    '.py',
    '.rst',
    '.toml',
    '.txt',

    '.patch',

    '.css',
    '.html',
    '.js',
    '.svg',
)

_TEXT_FILES = (
    '.editorconfig',
    '.gitattributes',
    '.gitignore',
    'LICENSE',
    'Makefile',
    'py.typed',
)

# --------------------------------------------------------------------------------------
# Bundle code snippets

_BANNER = (
    b'#!/usr/bin/env python3\\n'
    b'# -*- coding: utf-8 -*-\\n'
    b'# DO NOT EDIT! This script was automatically generated\\n'
    b'# by Tsutsumu <https://github.com/apparebit/tsutsumu>.\\n'
    b'# Manual edits may just break it.\\n\\n')

# Both bundle starts must have the same length
_BUNDLE_START = b'if False: {\\n'
_BUNDLE_STOP = b'}\\n\\n'
_EMPTY_LINE = b'\\n'

_MAIN = \x22\x22\x22\\
if __name__ == \x22__main__\x22:
    import runpy

    # Don't load modules from current directory
    Toolbox.restrict_sys_path()

    # Install the bundle
    bundle = Bundle.install(__file__, __version__, __manifest__)

    # This script does not exist. It never ran!
    {repackage}

    # Run equivalent of \x22python -m {main}\x22
    runpy.run_module(\x22{main}\x22, run_name=\x22__main__\x22, alter_sys=True)
\x22\x22\x22

# --------------------------------------------------------------------------------------

class FileKind(Enum):
    BINARY = 'b'
    TEXT = 't'
    VALUE = 'v'


class BundledFile(NamedTuple):
    \x22\x22\x22The local path and the platform-independent key for a bundled file.\x22\x22\x22
    kind: FileKind
    path: Path
    key: str


class BundleMaker:
    \x22\x22\x22
    Class to create Python bundles, i.e., Python scripts that contains the source
    code for several modules and supporting files.
    \x22\x22\x22

    def __init__(
        self,
        directories: 'Sequence[str | Path]',
        *,
        bundle_only: bool = False,
        binary_extensions: 'tuple[str, ...]' = _BINARY_EXTENSIONS,
        binary_files: 'tuple[str, ...]' = _BINARY_FILES,
        text_extensions: 'tuple[str, ...]' = _TEXT_EXTENSIONS,
        text_files: 'tuple[str, ...]' = _TEXT_FILES,
        main: 'None | str' = None,
        output: 'None | str | Path' = None,
        repackage: bool = False,
    ) -> None:
        self._directories = directories
        self._bundle_only = bundle_only
        self._main = main
        self._output = output
        self._repackage = repackage

        self._binary_extensions = set(binary_extensions)
        self._binary_files = set(binary_files)
        self._text_extensions = set(text_extensions)
        self._text_files = set(text_files)

        self._ranges: 'list[tuple[FileKind, str, int, int, int]]' = []
        self._repr: 'None | str' = None

    def __repr__(self) -> str:
        if self._repr is None:
            roots = ', '.join(str(directory) for directory in self._directories)
            self._repr = f'<tsutsumu-maker {roots}>'
        return self._repr

    # ----------------------------------------------------------------------------------

    def run(self) -> None:
        files = sorted(self.list_files(), key=lambda f: f.key)
        main = None if self._bundle_only else self.select_main(files)

        # context's type annotation is based on the observation that open()'s
        # result is a BufferedWriter is an AbstractContextManager[BufferedWriter].
        # The nullcontext prevents closing of stdout's binary stream when done.
        context: 'AbstractContextManager[Writable]'
        if self._output is None:
            context = nullcontext(sys.stdout.buffer)
        else:
            context = open(self._output, mode='wb')

        with context as script:
            BundleMaker.writeall(_BANNER.splitlines(keepends=True), script)
            BundleMaker.writeall(self.emit_bundle(files), script)
            BundleMaker.writeall(self.emit_meta_data(), script)
            if not self._bundle_only:
                assert main is not None
                BundleMaker.writeall(self.emit_runtime(main), script)

    # ----------------------------------------------------------------------------------

    def list_files(self) -> 'Iterator[BundledFile]':
        # Since names of directories (and stems of Python files) are module
        # names, traversal MUST NOT resolve symbolic links!
        for directory in self._directories:
            root = Path(directory).absolute()
            pending = list(root.iterdir())
            while pending:
                item = pending.pop().absolute()
                if item.is_file() and BundleMaker.is_module_name(item.stem):
                    kind = self.classify_kind(item)
                    if kind is None:
                        continue
                    key = str(item.relative_to(root.parent)).replace('\\\\', '/')
                    if not self.is_excluded_key(key):
                        yield BundledFile(kind, item, key)
                elif item.is_dir() and BundleMaker.is_module_name(item.name):
                    pending.extend(item.iterdir())

    @staticmethod
    def is_module_name(name: str) -> bool:
        return name.isidentifier() and not iskeyword(name)

    def classify_kind(self, path: Path) -> 'None | FileKind':
        if path.suffix in self._binary_extensions or path.name in self._binary_files:
            return FileKind.BINARY
        elif path.suffix in self._text_extensions or path.name in self._text_files:
            return FileKind.TEXT
        else:
            return None

    def is_excluded_key(self, key: str) -> bool:
        return (
            self._repackage
            and key in ('tsutsumu/__init__.py', 'tsutsumu/bundle.py')
        )

    # ----------------------------------------------------------------------------------

    def select_main(self, files: 'list[BundledFile]') -> str:
        if self._main is not None:
            base = self._main.replace('.', '/')
            if any(f'{base}/__main__.py' == file.key for file in files):
                return self._main
            if any(f'{base}.py' == file.key for file in files):
                return self._main
            raise ValueError(
                f'no package with __main__ module or module {self._main} in bundle')

        main_modules = [file.key for file in files if file.key.endswith('/__main__.py')]
        module_count = len(main_modules)
        if module_count == 0:
            raise ValueError('bundle has no __main__ module')
        if module_count == 1:
            self._main = main_modules[0][:-12].replace('/', '.')
            return self._main
        raise ValueError(
                'bundle has more than one __main__ module; '
                'use -m/--main option to select one')

    # ----------------------------------------------------------------------------------

    def emit_bundle(
        self,
        files: 'list[BundledFile]',
    ) -> 'Iterator[bytes]':
        yield from _BUNDLE_START.splitlines(keepends=True)
        for file in files:
            yield from self.emit_file(file.kind, file.path, file.key)
        yield from _BUNDLE_STOP.splitlines(keepends=True)

    def emit_file(self, kind: 'FileKind', path: Path, key: str) -> 'Iterator[bytes]':
        if kind is FileKind.TEXT:
            lines = [
                line                      # Split bytestring into lines,
                .decode('iso8859-1')      # convert each byte 1:1 to code point,
                .encode('unicode_escape') # convert to bytes, escaping non-ASCII values
                .replace(b'\x22', b'\\\\x22')  # and escape double quotes.
                for line in path.read_bytes().splitlines()
            ]
        else:
            lines = base64.a85encode(path.read_bytes(), wrapcol=76).splitlines()

        line_count = len(lines)
        byte_length = sum(len(line) for line in lines) + line_count

        if line_count == 0:
            assert byte_length == 0
            self.record_range(kind, key, 0, 0, 0)
            return

        prefix = b'\x22' + key.encode('utf8') + b'\x22:'
        offset = len(Toolbox.PLAIN_RULE) + len(prefix) + 1

        yield Toolbox.PLAIN_RULE

        if line_count == 1:
            if kind is FileKind.TEXT:
                self.record_range(kind, key, offset, byte_length + 4, 2)
            else:
                self.record_range(kind, key, offset + 2, byte_length + 1, 3)

            yield prefix + b' b\x22' + lines[0] + b'\\\\n\x22,\\n'
        else:
            if kind is FileKind.TEXT:
                self.record_range(kind, key, offset, byte_length + 7, 2)
                first_line = b'b\x22\x22\x22' + lines[0]
            else:
                self.record_range(kind, key, offset + 4, byte_length + 1, 5)
                prefix += b' b\x22\x22\x22'
                first_line = lines[0]

            yield prefix + b'\\n'
            yield first_line + b'\\n'
            for line in lines[1:]:
                yield line + b'\\n'
            yield b'\x22\x22\x22,\\n'

    def record_range(
        self,
        kind: 'FileKind',
        name: str,
        prefix: int,
        data: int,
        suffix: int,
    ) -> None:
        self._ranges.append((kind, name, prefix, data, suffix))

    # ----------------------------------------------------------------------------------

    def emit_meta_data(self) -> 'Iterator[bytes]':
        yield Toolbox.HEAVY_RULE
        yield from self.emit_version()
        yield _EMPTY_LINE
        yield from self.emit_manifest()

    def emit_version(self) -> 'Iterator[bytes]':
        yield f\x22__version__ = '{__version__}'\\n\x22.encode('ascii')

    def list_manifest_entries(
        self
    ) -> 'Iterator[tuple[str, tuple[FileKind, int, int]]]':
        offset = len(_BANNER) + len(_BUNDLE_START)
        for kind, key, prefix, data, suffix in self._ranges:
            yield key, ((kind, 0, 0) if data == 0 else (kind, offset + prefix, data))
            offset += prefix + data + suffix

    def emit_manifest(self) -> 'Iterator[bytes]':
        yield b'__manifest__ = {\\n'
        for key, (kind, offset, length) in self.list_manifest_entries():
            entry = f'    \x22{key}\x22: (\x22{kind.value}\x22, {offset:_d}, {length:_d}),\\n'
            yield entry.encode('utf8')
        yield b'}\\n'

    # ----------------------------------------------------------------------------------

    def emit_runtime(
        self,
        main: str,
    ) -> 'Iterator[bytes]':
        yield _EMPTY_LINE
        yield Toolbox.HEAVY_RULE
        try:
            yield from self.emit_tsutsumu_bundle()
        except Exception as x:
            import traceback
            traceback.print_exception(x)

        yield Toolbox.HEAVY_RULE
        repackage = 'bundle.repackage()\\n    ' if self._repackage else ''
        repackage += \x22del sys.modules['__main__']\x22

        main_block = _MAIN.format(main=main, repackage=repackage)
        yield from main_block.encode('utf8').splitlines(keepends=True)

    def emit_tsutsumu_bundle(self) -> 'Iterator[bytes]':
        import tsutsumu
        spec: 'None | ModuleSpec' = getattr(tsutsumu, '__spec__', None)
        loader: 'None | Loader' = getattr(spec, 'loader', None)
        get_data: 'None | Callable[[str], bytes]' = getattr(loader, 'get_data', None)

        if get_data is not None:
            assert len(tsutsumu.__path__) == 1, 'tsutsumu is a regular package'
            mod_bundle = get_data(os.path.join(tsutsumu.__path__[0], 'bundle.py'))
        else:
            import warnings
            if loader is None:
                warnings.warn(\x22tsutsumu has no module loader\x22)
            else:
                warnings.warn(f\x22tsutsumu's loader ({type(loader)}) has no get_data()\x22)

            try:
                mod_bundle_path = Path(__file__).parent / 'bundle.py'
            except AttributeError:
                raise ValueError(f\x22unable to get tsutsumu.bundle's source code\x22)
            else:
                with open(mod_bundle_path, mode='rb') as file:
                    mod_bundle = file.read()

        yield from mod_bundle.splitlines(keepends=True)
        yield _EMPTY_LINE

    # ----------------------------------------------------------------------------------

    @staticmethod
    def writeall(
        lines: 'Iterable[bytes]',
        writable: 'None | Writable' = None,
    ) -> None:
        if writable is None:
            for line in lines:
                print(line.decode('utf8'), end='')
        else:
            for line in lines:
                writable.write(line)
""",
}

# ==============================================================================

__version__ = '0.2.0'

__manifest__ = {
    "cargo/__init__.py": ("t", 0, 0),
    "cargo/distinfo.py": ("t", 306, 11_371),
    "cargo/index.py": ("t", 11_778, 12_201),
    "cargo/marker.py": ("t", 24_081, 15_169),
    "cargo/name.py": ("t", 39_350, 814),
    "cargo/py.typed": ("t", 0, 0),
    "cargo/requirement.py": ("t", 40_271, 1_948),
    "cargo/rules.txt": ("t", 42_321, 843),
    "cargo/version.py": ("t", 43_267, 17_866),
    "tsutsumu/__main__.py": ("t", 61_240, 4_920),
    "tsutsumu/debug.py": ("t", 66_264, 1_229),
    "tsutsumu/maker.py": ("t", 67_597, 13_439),
    "tsutsumu/py.typed": ("t", 0, 0),
}

# ==============================================================================

import base64
from importlib.abc import Loader
from importlib.machinery import ModuleSpec
import importlib.util
import os
import sys
from typing import cast, TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path
    from types import CodeType, ModuleType
    from typing import TypeAlias

    ManifestType: TypeAlias = dict[str, tuple[str, int, int]]


class Toolbox:
    HEAVY_RULE = b"# " + b"=" * 78 + b"\n\n"
    PLAIN_RULE = b"# " + b"-" * 78 + b"\n"

    @staticmethod
    def create_module_spec(
        name: str, loader: "Loader", path: str, pkgdir: "None | str"
    ) -> ModuleSpec:
        spec = ModuleSpec(name, loader, origin=path, is_package=bool(pkgdir))
        if pkgdir:
            if spec.submodule_search_locations is None:
                raise AssertionError(f"module spec for {name} is not for package")
            spec.submodule_search_locations.append(pkgdir)
        return spec

    @staticmethod
    def create_module(
        name: str, loader: "Loader", path: str, pkgdir: "None | str"
    ) -> "ModuleType":
        spec = Toolbox.create_module_spec(name, loader, path, pkgdir)
        module = importlib.util.module_from_spec(spec)
        setattr(module, "__file__", path)
        sys.modules[name] = module
        return module

    @staticmethod
    def find_section_offsets(bundle: bytes) -> tuple[int, int, int]:
        # Search from back is safe and if bundled data > this module, also faster.
        index3 = bundle.rfind(Toolbox.HEAVY_RULE)
        index2 = bundle.rfind(Toolbox.HEAVY_RULE, 0, index3 - 1)
        index1 = bundle.rfind(Toolbox.HEAVY_RULE, 0, index2 - 1)
        return index1, index2, index3

    @staticmethod
    def load_meta_data(path: "str | Path") -> "tuple[str, ManifestType]":
        with open(path, mode="rb") as file:
            content = file.read()

        start, stop, _ = Toolbox.find_section_offsets(content)
        bindings: "dict[str, object]" = {}
        exec(content[start + len(Toolbox.HEAVY_RULE) : stop], bindings)
        version = cast(str, bindings["__version__"])
        # cast() would require backwards-compatible type value; comment seems simpler.
        manifest: "ManifestType" = bindings["__manifest__"]  # type: ignore[assignment]
        return version, manifest

    @staticmethod
    def load_from_bundle(
        path: "str | Path", kind: str, offset: int, length: int
    ) -> bytes:
        data = Toolbox.read(path, offset, length)
        if kind == "t":
            return cast(bytes, eval(data))
        elif kind == "b":
            return base64.a85decode(data)
        elif kind == "v":
            return data
        else:
            raise ValueError(f'invalid kind "{kind}" for manifest entry')

    @staticmethod
    def read(path: "str | Path", offset: int, length: int) -> bytes:
        if length == 0:
            return b""
        with open(path, mode="rb") as file:
            file.seek(offset)
            data = file.read(length)
        if len(data) != length:
            raise AssertionError(f"actual length {len(data):,} is not {length:,}")
        return data

    @staticmethod
    def restrict_sys_path() -> None:
        # TODO: Remove virtual environment paths, too!
        cwd = os.getcwd()
        bad_paths = {"", cwd}

        main = sys.modules["__main__"]
        if hasattr(main, "__file__"):
            bad_paths.add(os.path.dirname(cast(str, main.__file__)))

        index = 0
        while index < len(sys.path):
            path = sys.path[index]
            if path in bad_paths:
                del sys.path[index]
            else:
                index += 1


class Bundle(Loader):
    """
    Representation of a bundle. Each instance serves as meta path finder and
    module loader for a particular bundle script.
    """

    @classmethod
    def install_from_file(
        cls,
        path: "str | Path",
    ) -> "Bundle":
        version, manifest = Toolbox.load_meta_data(path)
        return cls.install(path, version, manifest)

    @classmethod
    def install(
        cls,
        script: "str | Path",
        version: str,
        manifest: "ManifestType",
    ) -> "Bundle":
        bundle = cls(script, version, manifest)
        if bundle in sys.meta_path:
            raise ImportError(f'bundle for "{bundle._script}" already installed')
        sys.meta_path.insert(0, bundle)
        return bundle

    def __init__(
        self,
        script: "str | Path",
        version: str,
        manifest: "ManifestType",
    ) -> None:
        script = str(script)
        if not os.path.isabs(script):
            script = os.path.abspath(script)
        if script.endswith("/") or script.endswith(os.sep):
            raise ValueError('path to bundle script "{script}" ends in path separator')

        def intern(path: str) -> str:
            local_path = path.replace("/", os.sep)
            if os.path.isabs(local_path):
                raise ValueError(f'manifest path "{path}" is absolute')
            return os.path.join(script, local_path)

        self._script = script
        self._version = version
        self._manifest = {intern(k): v for k, v in manifest.items()}

    def __hash__(self) -> int:
        return hash(self._script) + hash(self._manifest)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Bundle):
            return False
        return (
            self._script == other._script
            and self._version == other._version
            and self._manifest == other._manifest
        )

    def __repr__(self) -> str:
        return f"<tsutsumu {self._script}>"

    def __contains__(self, key: str) -> bool:
        return key in self._manifest

    def __getitem__(self, key: str) -> bytes:
        if not key in self._manifest:
            raise ImportError(f'unknown path "{key}"')
        kind, offset, length = self._manifest[key]
        return Toolbox.load_from_bundle(self._script, kind, offset, length)

    def _locate(
        self,
        fullname: str,
        search_paths: "None | Sequence[str]" = None,
    ) -> "tuple[str, None | str]":
        if search_paths is None:
            base_paths = [os.path.join(self._script, fullname.replace(".", os.sep))]
        else:
            modname = fullname.rpartition(".")[2]
            base_paths = [os.path.join(path, modname) for path in search_paths]

        for suffix, is_pkg in (
            (os.sep + "__init__.py", True),
            (".py", False),
        ):
            for base_path in base_paths:
                full_path = base_path + suffix
                if full_path in self._manifest:
                    return full_path, (base_path if is_pkg else None)

        # It's not a regular module or package, but could be a namespace package
        # (see https://github.com/python/cpython/blob/3.11/Lib/zipimport.py#L171)

        for base_path in base_paths:
            prefix = base_path + os.sep
            for key in self._manifest:
                if key.startswith(prefix):
                    return base_path, base_path

        raise ImportError(f"No such module {fullname} in bundle {self._script}")

    def find_spec(
        self,
        fullname: str,
        search_paths: "None | Sequence[str]" = None,
        target: "None | ModuleType" = None,
    ) -> "None | ModuleSpec":
        try:
            return Toolbox.create_module_spec(
                fullname, self, *self._locate(fullname, search_paths)
            )
        except ImportError:
            return None

    def create_module(self, spec: ModuleSpec) -> "None | ModuleType":
        return None

    def exec_module(self, module: "ModuleType") -> None:
        assert module.__spec__ is not None, "module must have spec"
        exec(self.get_code(module.__spec__.name), module.__dict__)

    def is_package(self, fullname: str) -> bool:
        return self._locate(fullname)[1] is not None

    def get_code(self, fullname: str) -> "CodeType":
        fullpath = self.get_filename(fullname)
        source = importlib.util.decode_source(self[fullpath])
        return compile(source, fullpath, "exec", dont_inherit=True)

    def get_source(self, fullname: str) -> str:
        return importlib.util.decode_source(self[self.get_filename(fullname)])

    def get_data(self, path: "str | Path") -> bytes:
        return self[str(path)]

    def get_filename(self, fullname: str) -> str:
        return self._locate(fullname)[0]

    def repackage(self) -> None:
        # Check sys.modules and self._manifest to prevent duplicates
        if "tsutsumu" in sys.modules or "tsutsumu.bundle" in sys.modules:
            raise ValueError("unable to repackage() already existing modules")

        pkgdir = os.path.join(self._script, "tsutsumu")
        paths = [os.path.join(pkgdir, file) for file in ("__init__.py", "bundle.py")]
        if any(path in self._manifest for path in paths):
            raise ValueError("unable to repackage() modules already in manifest")

        # Recreate modules and add them to manifest
        tsutsumu = Toolbox.create_module("tsutsumu", self, paths[0], pkgdir)
        tsutsumu_bundle = Toolbox.create_module("tsutsumu.bundle", self, paths[1], None)

        setattr(tsutsumu, "__version__", self._version)
        setattr(tsutsumu, "bundle", tsutsumu_bundle)
        setattr(tsutsumu_bundle, "Toolbox", Toolbox)
        setattr(tsutsumu_bundle, "Bundle", Bundle)
        Bundle.__module__ = Toolbox.__module__ = "tsutsumu.bundle"

        self._repackage_add_to_manifest(tsutsumu, tsutsumu_bundle)

    def _repackage_add_to_manifest(
        self,
        tsutsumu: "ModuleType",
        tsutsumu_bundle: "ModuleType",
    ) -> None:
        with open(self._script, mode="rb") as file:
            content = file.read()

        section1, section2, section3 = Toolbox.find_section_offsets(content)

        module_offset = section1 + len(Toolbox.HEAVY_RULE)
        module_length = content.find(b"\n", module_offset) + 1 - module_offset
        assert tsutsumu.__file__ is not None
        self._manifest[tsutsumu.__file__] = ("v", module_offset, module_length)

        module_offset = section2 + len(Toolbox.HEAVY_RULE)
        module_length = section3 - 1 - module_offset
        assert tsutsumu_bundle.__file__ is not None
        self._manifest[tsutsumu_bundle.__file__] = ("v", module_offset, module_length)

    def uninstall(self) -> None:
        sys.meta_path.remove(self)

# ==============================================================================

if __name__ == "__main__":
    import runpy

    # Don't load modules from current directory
    Toolbox.restrict_sys_path()

    # Install the bundle
    bundle = Bundle.install(__file__, __version__, __manifest__)

    # This script does not exist. It never ran!
    bundle.repackage()
    del sys.modules['__main__']

    # Run equivalent of "python -m tsutsumu"
    runpy.run_module("tsutsumu", run_name="__main__", alter_sys=True)
