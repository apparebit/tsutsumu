"""
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
"""

import itertools as it
import re
from typing import Any, Callable, cast, Literal, NamedTuple


__all__ = ("Data", "Key", "Version", "Specifier")

INFINITY = float('inf')
NOT_A_LABEL = '★'
OPERATOR = re.compile('<=?|==|>=?|~=|!=')
STATUS_LABELS = {
    "a": "a",
    "alpha": "a",
    "b": "b",
    "beta": "b",
    "c": "rc",
    "pre": "rc",
    "preview": "rc",
    "rc": "rc",
    "post": "post",
    "r": "post",
    "rev": "post",
    "dev": "dev",
}
SEPARATOR = re.compile(r'[._-]')
SPACING = re.compile('\s+')
SYNTAX = re.compile(
    r"""
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
    """,
    re.X | re.I,
)


class Key(NamedTuple):
    """A version key for implementing a total order of version identifiers."""

    epoch: int
    release: tuple[int, ...]
    status: Literal["a", "b", "rc", "★"]
    pre: int | float
    post: int
    dev: int | float
    local: tuple[tuple[int, str], ...]


class Data(NamedTuple):
    """
    The individual segments of a version identifier. A `None` value indicates
    that the corresponding segment is not present. The `status` and `pre` fields
    must both be either `None` or have a value. The `local` field preserves the
    local segment as written, which is required for determining compatibility.
    However, for ordering, `Key` contains a parsed representation that breaks
    the string into components separated by `.`, `_`, or `-` and, if possible,
    parsed as integers.
    """

    epoch: int
    release: tuple[int, ...]
    status: None | Literal["a", "b", "rc"]
    pre: None | int
    post: None | int
    dev: None | int
    local: None | str

    @classmethod
    def from_string(cls, version: str) -> 'Data':
        """Parse the given version identifier."""

        segments = SYNTAX.match(version.strip().lower())
        if segments is None:
            raise ValueError(f'not a version string "{version}"')

        def parse(
            label: None | str, value: None | str
        ) -> tuple[None | str, None | int]:
            return (
                (None, None)
                if label is None
                else (STATUS_LABELS[label], 0 if value is None else int(value))
            )

        epoch = cast(int, segments.group("epoch")) or 0
        release = tuple(int(p) for p in segments.group("release").split("."))
        status, pre = parse(segments.group('pre_label'), segments.group('pre_number'))
        if (simple_post := segments.group("post_simple")) is not None:
            post: None | int = int(simple_post)
        else:
            _, post = parse(segments.group("post_label"), segments.group("post_number"))
        _, dev = parse(segments.group("dev_label"), segments.group("dev_number"))
        local = segments.group("local")

        status = cast(None | Literal['a', 'b', 'rc'], status)
        return cls(epoch, release, status, pre, post, dev, local)

    def release_components(self, precision: int) -> tuple[int, ...]:
        """Return the release components with the given precision."""
        return tuple(it.islice(it.chain(self.release, it.repeat(0)), precision))

    def release_text(self) -> str:
        """Return the release components as a string."""
        return '.'.join(str(n) for n in self.release)

    def release_is_prefix(
        self,
        candidate: 'Data',
        *,
        ignore_last: bool = False,
    ) -> bool:
        """
        Determine whether this version data's release is a prefix of the
        candidate's release. If `ignore_last` is `True`, this method does not
        include the prefix's last and therefore least significant component in
        the comparison.
        """
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
        """Determine whether this version has a pre segment."""
        return self.pre is not None

    def has_post(self) -> bool:
        """Determine whether this version has a post segment."""
        return self.post is not None

    def has_dev(self) -> bool:
        """Determine whether this version has a dev segment."""
        return self.dev is not None

    def has_local(self) -> bool:
        """Determine whether this version has a local segment."""
        return self.local is not None

    def is_prerelease(self) -> bool:
        """
        Determine whether this version is a prerelease, i.e., has either a pre
        or a dev segment.
        """
        return self.pre is not None or self.dev is not None

    def only_public(self) -> 'Data':
        """Return the same version but without a local segment."""
        if self.local is None:
            return self
        return self.__class__(
            self.epoch, self.release, self.status, self.pre, self.post, self.dev, None
        )

    def only_epoch_and_release(self) -> 'Data':
        """Return the same version but with only epoch and release segments."""
        if (
            self.pre is None
            and self.post is None
            and self.dev is None
            and self.local is None
        ):
            return self
        return self.__class__(self.epoch, self.release, None, None, None, None, None)

    def to_key(self) -> Key:
        """Compute the key for this version."""
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

        return Key(self.epoch, release, self.status or "★", pre, post, dev, local)

    def __repr__(self) -> str:
        return f"VersionData({', '.join(f'{f!r}' for f in self)})"

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
    """
    A parsed version identifier.

    This class combines a `Data` and `Key` instance to provide a fully-featured
    interface. Even though it does not re-implement `Data`'s properties and
    methods for accessing version segments, it nonetheless exposes them through
    its `__getattr__()` method. The static types for those properties and
    methods are defined in a separate interface file, `version.pyi`.
    """

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
        """Return the version data."""
        return self._data

    @property
    def public_version(self) -> 'Version':
        """Return the same version but without a local segment."""
        if self._data.local is None:
            return self
        return Version(self._data.only_public())

    @property
    def base_version(self) -> 'Version':
        """Return the same version but with only epoch and release segments."""
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
        """Determine whether the candidate is an exact match for this version."""
        return (
            self.public_version == candidate.public_version
            and (not self.has_local() or self.local == candidate.local)
        )

    def is_prefix_match(self, candidate: 'Version', ignore_last: bool = False) -> bool:
        """Determine whether the candidate is a prefix match for this version."""
        d1, d2 = self.data, candidate.data
        return (
            d1.epoch == d2.epoch
            and d1.release_is_prefix(d2, ignore_last=ignore_last)
            and (not d1.has_pre() or d1.status == d2.status and d1.pre == d2.pre)
            and (not d1.has_post() or d1.post == d2.post)
        )

    def is_greater_match(self, candidate: 'Version') -> bool:
        """Determine whether the candidate is a greater match for this version."""
        return (
            not candidate.has_local()
            and candidate > self
            and (self.has_post() or candidate.base_version != self.base_version)
        )

    def is_lesser_match(self, candidate: 'Version') -> bool:
        """Determine whether the candidate is a lesser match for this version."""
        return (
            not candidate.has_local()
            and candidate < self
            and (self.has_pre() or candidate.base_version != self.base_version)
        )

    def is_compatible_match(self, candidate: 'Version') -> bool:
        """Determine whether the candidate is a compatible match for this version."""
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
        return f"Version({', '.join(f'{f!r}' for f in self._data)})"

    def __str__(self) -> str:
        return str(self._data)


class Specifier:
    """Representation of a version specifier."""

    __slots__ = ('_text', '_predicate')

    def __init__(self, specifier: str) -> None:
        specifier = specifier.strip()
        is_prefix_match = specifier.endswith('.*')
        if (op_match := OPERATOR.match(specifier)) is None:
            raise ValueError(f'unknown operator in version specifier "{specifier}"')
        operator = op_match.group()

        version_start = len(operator)
        version_stop = -2 if is_prefix_match else len(specifier)
        version = Version(specifier[version_start:version_stop])
        self._text = f'{operator} {version}{".*" if is_prefix_match else ""}'

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
