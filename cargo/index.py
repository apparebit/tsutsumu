"""
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
"""

import email.message
from html.parser import HTMLParser
import json
import logging
import re
import sys
import time
from typing import cast, Literal, NamedTuple, NotRequired, TypedDict

import requests
from packaging.version import Version as PackagingVersion


from .name import canonicalize, split_hash


__all__ = ()

logger = logging.getLogger("cargo.index")


PACKAGE_INDEX = "https://pypi.org/simple"
ACCEPTABLE_CONTENT = (
    "application/vnd.pypi.simple.latest+json",
    "application/vnd.pypi.simple.latest+html;q=0.2",
    # 'text/html;q=0.01', # pfui!
)

HEADERS = {
    "user-agent": "Tsutsumu (https://github.com/apparebit/tsutsumu)",
    "accept": ", ".join(ACCEPTABLE_CONTENT),
}

PYPI_CONTENT_TYPES = re.compile(
    r"application/vnd.pypi.simple.v(?P<version>\d+)\+(?P<format>html|json)"
)

ANCHOR_ATTRIBUTES = {
    "href": "url",
    "data-requires-python": "requires-python",
    "data-core-metadata": "core-metadata",  # previously data-dist-info-metadata
}

JSON_ATTRIBUTES = set(
    [
        "url",
        "requires-python",
        "core-metadata",
        "hashes",
    ]
)

# --------------------------------------------------------------------------------------


class HashValue(TypedDict):
    sha256: str

ReleaseMetadata = TypedDict('ReleaseMetadata', {
    'filename': str,
    'name': str,
    'version': str | PackagingVersion,
    'url': NotRequired[str],
    'hashes': NotRequired[HashValue],
    'core-metadata': NotRequired[Literal[False] | HashValue],
    'requires-python': NotRequired[str],
    'api-version': NotRequired[str],
})


# --------------------------------------------------------------------------------------


def determine_format(content_type_header: str) -> tuple[None | str, None | str]:
    """
    Parse the content type and, if it is one of the application/vnd.pypi.simple
    types, determine the version and the format.
    """
    message = email.message.Message()
    message["content-type"] = content_type_header
    normalized_content_type = message.get_content_type()
    if (pypi_format := PYPI_CONTENT_TYPES.match(normalized_content_type)) is None:
        return None, None
    return cast(tuple[str, str], pypi_format.groups())


def retrieve_metadata(name: str) -> None | ReleaseMetadata:
    """Retrieve metadata about the most recent wheel-based release."""
    name = canonicalize(name)

    # Fetch project JSON or page
    logger.debug('fetching package metadata for "%s"', name)
    response = requests.get(f"{PACKAGE_INDEX}/{name}/", headers=HEADERS)
    response.raise_for_status()

    content_type = response.headers.get("content-type", "")
    format = determine_format(content_type)[1]
    info: None | ReleaseMetadata
    match format:
        case "json":
            info = ingest_json(response.json())
        case "html":
            info = ingest_html(response.text)
        case _:
            raise ValueError(
                f'unrecognized content type "{content_type}" for package "{name}"'
            )

    if info is None:
        logger.warning('Unable to ingest metadata from %s for %s', format, name)
    else:
        info["version"] = str(info["version"])
        pep658 = "✅" if "core-metadata" in info else "❌"
        logger.info("%s %s v%s:", pep658, name, info["version"])
        logger.info("    requires-pathon=%s", info["requires-python"])
        logger.info("    filename=%s", info["filename"])
        logger.info("    href=%s", info["url"])
    return info


# --------------------------------------------------------------------------------------


def ingest_json(data: dict[str, object]) -> None | ReleaseMetadata:
    """Process the JSON result from PyPI' Simple Repository API."""
    api_version = None
    if "meta" in data and isinstance(data["meta"], dict):
        api_version = data["meta"].get("api-version")

    files = cast(list[ReleaseMetadata], data["files"])
    latest: None | ReleaseMetadata = None

    for file in files:
        maybe_latest = find_latest_release(file["filename"], latest)
        if maybe_latest is None:
            continue

        latest = maybe_latest
        for key, value in file.items():
            if key == "hashes":
                latest["hashes"] = cast(HashValue, value).copy()
            if key == "core-metadata" and isinstance(value, dict):
                latest["core-metadata"] = cast(HashValue, value).copy()
            elif key in JSON_ATTRIBUTES:
                latest[key] = value  # type: ignore[literal-required]

    if api_version is not None and latest is not None:
        latest["api-version"] = api_version
    return latest


# --------------------------------------------------------------------------------------


def ingest_html(html: str) -> None | ReleaseMetadata:
    """Process the HTML result from PyPI' Simple Repository API."""
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

        url = latest["url"]
        if isinstance(url, str) and (split := split_hash(url)) is not None:
            url, algo, value = split
            latest["hashes"] = {algo: value}  # type: ignore[misc]
            latest["url"] = url

    if api_version is not None and latest is not None:
        latest["api-version"] = api_version
    return latest


class Anchor(NamedTuple):
    """The scraped information about a release."""
    filename: str
    attributes: list[tuple[str, None | str]]


class LinkParser(HTMLParser):
    """A parser for the project pages of PyPI's Simple Repository API."""

    __slots__ = (
        "_api_version",
        "_handling_anchor",
        "_current_attrs",
        "_anchor_text",
        "_anchors",
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
        if tag == "meta":
            self.handle_meta(attrs)
            return
        if tag != "a":
            return

        assert not self._handling_anchor
        self._handling_anchor = True
        self._current_attrs = attrs

    def handle_endtag(self, tag: str) -> None:
        if tag != "a":
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
            content = "".join(self._anchor_text)
        assert self._current_attrs is not None
        self._anchors.append(Anchor(content, self._current_attrs))
        self._anchor_text.clear()
        self._current_attrs = None

    def handle_meta(self, attrs: list[tuple[str, None | str]]) -> None:
        is_version = False
        version = None

        for key, value in attrs:
            if key == "name" and value == "pypi:repository-version":
                is_version = True
            elif key == "content":
                version = value

        if is_version and version is not None:
            self._api_version = version


# --------------------------------------------------------------------------------------


def parse_filename(filename: str) -> None | tuple[str, str, str]:
    filename = filename.strip()
    if filename.endswith(".whl"):
        kind = "wheel"
        stem = filename[:-4]
    elif filename.endswith(".tar.gz"):
        kind = "sdist"
        stem = filename[:-7]
    elif filename.endswith(".egg"):
        kind = "egg"
        stem = filename[:-4]
    else:
        return None

    name, version, *_ = stem.split("-", maxsplit=2)
    return kind, name, version


def find_latest_release(
    filename: str, latest_so_far: None | ReleaseMetadata
) -> None | ReleaseMetadata:
    if (parse := parse_filename(filename)) is None:
        logger.warning('Unknown distribution format "%s"', filename)
        return None

    kind, name, version = parse
    if kind != "wheel":
        logger.debug('Ignoring distribution in "%s" format', kind)
        return None

    assert version is not None
    version_object = PackagingVersion(version)  # FIXME: replace with cargo's version
    if (
        latest_so_far is not None and
        version_object < latest_so_far["version"] # type: ignore[operator]
    ) :
        logger.debug("Skipping wheel %s < %s", version, latest_so_far["version"])
        return None

    return {"filename": filename, "name": name, "version": version_object}


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
