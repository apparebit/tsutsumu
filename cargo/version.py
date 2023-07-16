import itertools as it
import re
from typing import cast, Literal, NamedTuple, TypeAlias

from ._infinity import NegativeInfinity, NegativeInfinityType, PositiveInfinity


__all__ = ("Version",)


_VERSION_SYNTAX = re.compile(
    r"""
        [v]?
        (?:(?P<epoch>[0-9]+)[!])?
        (?P<release>[0-9]+(?:[.][0-9]+)*)
        (?:
            [._-]?     (?P<pre_label>   a(?:lpha)?|b(?:eta)?|c|pre(?:view)?|rc)
            (?: [._-]? (?P<pre_number>  [0-9]+) )?
        )?
        (?:
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


_RELABEL = {
    None: None,
    "a": "a",
    "alpha": "a",
    "b": "b",
    "beta": "b",
    "c": "rc",
    "dev": "dev",
    "post": "post",
    "pre": "rc",
    "preview": "rc",
    "r": "post",
    "rc": "rc",
    "rev": "post",
}


_LOCAL_SEPARATOR = re.compile(r'[._-]')


def _ingest_segment(
    label: None | str,
    number: None | str,
) -> tuple[None | str, None | int]:
    if label is None:
        assert number is None
        return None, None
    label = _RELABEL[label.lower()]
    if number is None:
        return label, 0
    return label, int(number)


def _format_segment(segment: None | int | str) -> str:
    return "⋯" if segment is None else str(segment)


LocalT: TypeAlias = None | tuple[int|str, ...] | NegativeInfinityType


class VersionData(NamedTuple):
    epoch: int
    release: tuple[int, ...]
    prelabel: None | Literal["", "a", "b", "rc"]
    pre: None | int
    post: None | int
    dev: None | int
    local: LocalT

    def to_key(self) -> 'VersionData':
        release = tuple(
            reversed(list(it.dropwhile(lambda v: v == 0, reversed(self.release)))))

        if self.prelabel is None and self.post is None and self.dev is not None:
            pre: int = NegativeInfinity
        elif self.prelabel is None:
            pre = PositiveInfinity
        else:
            pre = cast(int, self.pre)

        if self.post is None:
            post: int = NegativeInfinity
        else:
            post = self.post

        if self.dev is None:
            dev: int = PositiveInfinity
        else:
            dev = self.dev

        if self.local is None:
            local: LocalT = NegativeInfinity
        else:
            local = tuple(
                (i, '') if isinstance(i, int) else (NegativeInfinity, i)
                for i in self.local
            )

        return VersionData(self.epoch, release, '', pre, post, dev, local)


class Version:

    __slots__ = ("_ver", "_key")

    @classmethod
    def of(cls, text: str) -> "Version":
        parts = _VERSION_SYNTAX.match(text.strip())
        if parts is None:
            raise ValueError(f'not a marker "{text}"')

        epoch = cast(int, parts.group("epoch") or 0)
        release = tuple(int(p) for p in parts.group("release").split("."))
        rawprelabel, pre = _ingest_segment(
            parts.group("pre_label"), parts.group("pre_number")
        )
        prelabel = cast(None | Literal['a', 'b', 'rc'], rawprelabel)
        post = _ingest_segment(parts.group("post_label"), parts.group("post_number"))[1]
        dev = _ingest_segment(parts.group("dev_label"), parts.group("dev_number"))[1]
        local = None
        rawlocal = parts.group("local")
        if rawlocal is not None:
            local = tuple(
                p.lower() if not p.isdigit() else int(p)
                for p in _LOCAL_SEPARATOR.split(rawlocal)
            )
        return cls(epoch, release, prelabel, pre, post, dev, local)

    def __init__(
        self,
        epoch: int,
        release: tuple[int, ...],
        prelabel: None | Literal["a", "b", "rc"],
        pre: None | int,
        post: None | int,
        dev: None | int,
        local: None | tuple[int|str, ...],
    ) -> None:
        self._ver = VersionData(epoch, release, prelabel, pre, post, dev, local)
        self._key = self._ver.to_key()

    @property
    def astuple(self) -> VersionData:
        return self._ver

    @property
    def epoch(self) -> int:
        return self._ver[0]

    @property
    def release(self) -> tuple[int, ...]:
        return self._ver[1]

    @property
    def pre(self) -> None | tuple[Literal['', 'a', 'b', 'rc'], int]:
        prelabel = self._ver[2]
        if prelabel is None:
            return None
        return prelabel, cast(int, self._ver[3])

    @property
    def post(self) -> None | int:
        return self._ver[4]

    @property
    def dev(self) -> None | int:
        return self._ver[5]

    @property
    def local(self) -> None | str:
        return self._ver[6]

    @property
    def is_prerelease(self) -> bool:
        return self.pre is not None or self.dev is not None

    @property
    def is_postrelease(self) -> bool:
        return self.post is not None

    @property
    def is_devrelease(self) -> bool:
        return self.dev is not None

    def __str__(self) -> str:
        fragments = []
        if (epoch := self.epoch) != 0:
            fragments.append(f"{epoch}!")
        fragments.append(".".join(str(num) for num in self.release))
        if (pre := self.pre) is not None:
            fragments.append(f".{pre[0]}{pre[1]}")
        if (post := self.post) is not None:
            fragments.append(f".post{post}")
        if (dev := self.dev) is not None:
            fragments.append(f".dev{dev}")
        if (local := self.local) is not None:
            fragments.append(f"+{local}")
        return "".join(fragments)

    def __repr__(self) -> str:
        release = ".".join(str(num) for num in self.release)
        pre = "⋯, ⋯" if (prep := self.pre) is None else f"{prep[0]}, {prep[1]}"
        post = _format_segment(self.post)
        dev = _format_segment(self.dev)
        local = _format_segment(self.local)
        return f"Version({self.epoch}, {release}, {pre}, {post}, {dev}, {local})"

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self._key < other._key

    def __le__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self._key <= other._key

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self._key == other._key

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self._key >= other._key

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self._key > other._key
