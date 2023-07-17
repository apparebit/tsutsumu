import itertools as it
import math
import re
from typing import cast, Literal, NamedTuple


# mypy: disallow_any_expr = false

__all__ = ("Version",)

VERSION_SYNTAX = re.compile(
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

LABELS = {
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

NOT_A_LABEL = '★'

SEPARATOR = re.compile(r'[._-]')


class VersionData(NamedTuple):
    epoch: int
    release: tuple[int, ...]
    status: None | Literal["a", "b", "rc"]
    pre: None | int
    post: None | int
    dev: None | int
    local: None | str

    @classmethod
    def from_string(cls, version: str) -> 'VersionData':
        segments = VERSION_SYNTAX.match(version.strip().lower())
        if segments is None:
            raise ValueError(f'not a version string "{version}"')

        def parse(
            label: None | str, value: None | str
        ) -> tuple[None | str, None | int]:
            return (
                (None, None)
                if label is None
                else (LABELS[label], 0 if value is None else int(value))
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
        return tuple(it.islice(it.chain(self.release, it.repeat(0)), precision))

    def release_text(self) -> str:
        return '.'.join(str(n) for n in self.release)

    def to_key(
        self,
    ) -> tuple[
        int, tuple[int, ...], str, float, int, float, tuple[tuple[int, str], ...]
    ]:
        release = tuple(
            reversed(list(it.dropwhile(lambda v: v == 0, reversed(self.release))))
        )

        if self.pre is None and self.post is None and self.dev is not None:
            pre: float = -1
        elif self.pre is None:
            pre = math.inf
        else:
            pre = self.pre

        if self.post is None:
            post: int = -1
        else:
            post = self.post

        if self.dev is None:
            dev: float = math.inf
        else:
            dev = self.dev

        if self.local is None:
            local: tuple[tuple[int, str], ...] = ()
        else:
            local = tuple(
                (i, '') if isinstance(i, int) else (-1, i)
                for i in SEPARATOR.split(self.local)
            )

        return self.epoch, release, self.status or "★", pre, post, dev, local


class Version:
    __slots__ = ('_version', '_key', '_text')

    def __init__(self, version: str) -> None:
        self._version = VersionData.from_string(version)
        self._key = self._version.to_key()
        self._text: None | str = None

    @property
    def epoch(self) -> int:
        return self._version.epoch

    @property
    def release(self) -> tuple[int, ...]:
        return self._version.release

    @property
    def is_prerelease(self) -> bool:
        return self._version.status is not None

    @property
    def status(self) -> None | Literal['a', 'b', 'rc']:
        return self._version.status

    @property
    def pre(self) -> None | int:
        return self._version.pre

    @property
    def is_postrelease(self) -> bool:
        return self._version.post is not None

    @property
    def post(self) -> None | int:
        return self._version.post

    @property
    def is_devrelease(self) -> bool:
        return self.dev is not None

    @property
    def dev(self) -> None | int:
        return self._version.dev

    @property
    def local(self) -> None | str:
        return self._version.local

    def astuple(self) -> VersionData:
        return self._version

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

    def __str__(self) -> str:
        if self._text is not None:
            return self._text

        data = self._version
        fragments = []

        if (epoch := data.epoch) > 0:
            fragments.append(f'{epoch}!')
        fragments.append(data.release_text())
        if (status := data.status) is not None:
            fragments.append(f'{status}{data.pre}')
        if (post := data.post) is not None:
            fragments.append(f'.post{post}')
        if (dev := data.dev) is not None:
            fragments.append(f'.dev{dev}')
        if (local := data.local) is not None:
            fragments.append(f'+{local}')

        self._text = text = ''.join(fragments)
        return text

    def __repr__(self) -> str:
        return f"Version({', '.join(f'{f!r}' for f in self._version)})"
