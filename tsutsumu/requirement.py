from collections.abc import Iterator
from dataclasses import dataclass
from enum import auto, Enum
import re
from typing import cast, ClassVar, overload


_DASHING = re.compile(r'[-_.]+')

_REQUIREMENT_PARTS: re.Pattern[str] = re.compile(
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

_MARKER_TOKEN: re.Pattern[str] = re.compile(
    r"""
        (?P<WS> \s+)
        | (?P<OPEN> [(])
        | (?P<CLOSE> [)])
        | (?P<COMP> <=? | != | ===? | >=? | ~= | not\s+in | in)
        | (?P<BOOL> and | or)
        | (?P<LIT> '[^']*' | "[^"]*")
        | (?P<VAR>  python_ (?: full_)? version | os_name | sys_platform
            | platform_ (?: release | system | version| machine | python_implementation)
            | implementation[._] (?: name | version)
            | extra )
    """,
    re.VERBOSE)


# ======================================================================================


def canonicalize(name: str, separator: str = '-') -> str:
    """Convert the package or extra name to its canonical form."""
    return _DASHING.sub(separator, name).lower()


def parse_requirement(
    requirement: str
) -> tuple[str, None | list[str], None| list[str], None | str]:
    """
    Parse the package requirement. Unlike the equivalent functionality in the
    `packaging` package, this function extracts all information needed for
    making sense of packages and their extras but without assuming a specific
    Python runtime and host computer. This function returns the name of the
    required package, the optional list of extras for the required package, the
    optional list of version constraints for the required package, and the
    optional extra for the current package. If the latter is present, the
    package that has this requirement scopes the requirement to that extra.
    All returned package name and extra names are in canonical form.
    """

    if (parts := _REQUIREMENT_PARTS.match(requirement)) is None:
        raise ValueError(f'requirement "{requirement} is malformed')

    package = canonicalize(cast(str, parts.group('package')).strip())

    extras = None
    if (extras_text := cast(str, parts['extras'])):
        extras = [canonicalize(extra.strip()) for extra in extras_text.split(',')]

    versions = None
    if (version_text := parts['version1'] or parts['version2']): # type: ignore[misc]
        versions = [v.strip() for v in cast(str, version_text).split(',')]

    marker = None
    marker_text = cast(str, parts['marker'])
    if marker_text is not None:
        marker_tokens = [t for t in _tokenize(marker_text) if t.type is not _TypTok.WS]
        raw_marker = _Simplifier().extract_extra(marker_tokens)
        marker = None if raw_marker is None else canonicalize(raw_marker)

    return package, extras, versions, marker


# ======================================================================================


class _TypTok(Enum):
    """
    Not a type token but rather a token type or tag. `WS` tokens probably are
    dropped early on. `EXTRA` and `ELIDED` tokens probably shouldn't be
    generated during lexing; they help analyze markers without fully parsing
    them.
    """
    WS = auto()

    OPEN = auto()
    CLOSE = auto()
    COMP = auto()
    BOOL = auto()
    LIT = auto()
    VAR = auto()

    EXTRA = auto()
    ELIDED = auto()


@dataclass(frozen=True, slots=True)
class _Token:
    ELIDED_VALUE: 'ClassVar[_Token]'

    type: _TypTok
    content: str

    @classmethod
    def extra(cls, literal: str) -> '_Token':
        return cls(_TypTok.EXTRA, canonicalize(literal[1:-1]))

_Token.ELIDED_VALUE = _Token(_TypTok.ELIDED, '')


def _tokenize(marker: str) -> Iterator[_Token]:
    cursor = 0
    while (t := _MARKER_TOKEN.match(marker, cursor)) is not None:
        cursor = t.end()
        yield _Token(_TypTok[cast(str, t.lastgroup)], t.group())
    if cursor < len(marker):
        raise ValueError(f'unrecognized "{marker[cursor:]}" in marker "{marker}"')


class _Simplifier:
    """
    Simplifier of marker tokens. This class takes a sequence of marker tokens
    and iteratively reduces semantically well-formed token groups until only one
    token remains. This process is purposefully inaccurate in that it seeks to
    extract an `EXTRA` token only. All other expressions reduce to the `ELIDED`
    token. Both tokens are synthetic tokens without corresponding surface
    syntax. By extracting a requirement's extra constraint this way, this class
    can support most of the expressivity of markers, while also ensuring
    correctness by design. The `Marker` class in
    [packaging](https://github.com/pypa/packaging/tree/main) fully parses and
    evaluates markers. But that also makes the result specific to the current
    Python runtime and its host. Instead `Simplifier` serves as an accurate
    cross-platform oracle for extras, which are critical for completely
    resolving package dependencies.
    """

    def __init__(self) -> None:
        self._token_stack: list[list[_Token]] = []

    # ----------------------------------------------------------------------------------

    def start(self, tokens: list[_Token]) -> None:
        self._token_stack.append(tokens)

    def done(self) -> _Token:
        assert len(self._token_stack) > 0
        assert len(self._token_stack[-1]) == 1
        return self._token_stack.pop()[0]

    @overload
    def __getitem__(self, index: int) -> _Token:
        ...
    @overload
    def __getitem__(self, index: slice) -> list[_Token]:
        ...
    def __getitem__(self, index: int | slice) -> _Token | list[_Token]:
        return self._token_stack[-1][index]

    def __len__(self) -> int:
        return len(self._token_stack[-1])

    def type(self, index: int) -> _TypTok:
        return self[index].type

    def content(self, index: int) -> str:
        return self[index].content

    # ----------------------------------------------------------------------------------

    def find(self, type: _TypTok) -> int:
        for index, token in enumerate(self._token_stack[-1]):
            if token.type == type:
                return index
        return -1

    def match(self, *patterns: None | str | _TypTok | _Token, start: int = 0) -> bool:
        for index, pattern in enumerate(patterns):
            if pattern is None:
                continue
            if isinstance(pattern, _TypTok):
                if self[start + index].type == pattern:
                    continue
                return False
            if isinstance(pattern, str):
                if self[start + index].content == pattern:
                    continue
                return False
            assert isinstance(pattern, _Token)
            if self[start + index] == pattern:
                continue
            return False
        return True

    # ----------------------------------------------------------------------------------

    def reduce(self, start: int, stop: int, value: _Token) -> None:
        self._token_stack[-1][start: stop] = [value]

    def apply(self, tokens: list[_Token]) -> _Token:
        self.start(tokens)
        tp = _TypTok

        def elide3(start: int) -> None:
            self.reduce(start, start + 3, _Token.ELIDED_VALUE)

        def handle_comp(var: int, lit: int) -> None:
            assert self.type(lit) is tp.LIT
            if self.content(var) != 'extra':
                elide3(min(var, lit))
                return
            assert self.content(1) == '=='
            start = min(var, lit)
            self.reduce(start, start + 3, _Token.extra(self[lit].content))

        while len(self) > 1:
            # Recurse on parentheses
            if self.match(tp.OPEN):
                close = self.find(tp.CLOSE)
                assert close >= 0
                value = self.apply(self[1 : close])
                self.reduce(0, close + 1, value)
                continue

            # Handle comparisons, which include extra clauses
            if self.match(None, tp.COMP):
                if self.match(tp.VAR):
                    handle_comp(0, 2)
                    continue
                if self.match(None, None, tp.VAR):
                    handle_comp(2, 0)
                    continue
                if self.match(tp.LIT, None, tp.LIT):
                    elide3(0)
                    continue
                assert False

            # Process conjunctions before disjunctions
            assert self.match(None, tp.BOOL)
            if self.match(None, 'and'):
                if self.match(tp.ELIDED, 'and', tp.ELIDED):
                    elide3(0)
                elif self.match(tp.EXTRA, 'and', tp.ELIDED):
                    self.reduce(0, 3, self[0])
                elif self.match(tp.ELIDED, 'and', tp.EXTRA):
                    self.reduce(0, 3, self[2])
                elif self.match(tp.EXTRA, 'and', tp.EXTRA):
                    assert self.content(0) == self.content(2)
                    self.reduce(0, 3, self[0])
                continue

            # Reduce disjunction only if 2nd argument also is a single token
            assert self.content(1) == 'or'
            if len(self) == 3 or self[3].type == tp.BOOL and self[3].content == 'or':
                if self.match(tp.ELIDED, None, tp.ELIDED):
                    elide3(0)
                elif self.match(tp.EXTRA, None, tp.EXTRA):
                    # In theory, we could combine unequal extras into set.
                    # In practice, the entire marker syntax is far too expressive.
                    assert self.content(0) == self.content(2)
                    self.reduce(0, 3, self[0])
                else:
                    assert False
                continue

            # Recurse on span to the next disjunction
            paren_level = 0
            cursor = 4

            while cursor < len(self):
                ct = self.type(cursor)
                if ct is tp.OPEN:
                    paren_level += 1
                elif ct is tp.CLOSE:
                    assert paren_level > 0
                    paren_level -= 1
                elif ct in (tp.COMP, tp.LIT, tp.VAR):
                    pass
                elif ct is tp.BOOL:
                    if self.content(cursor) == 'or':
                        break
                else:
                    assert False

            assert paren_level == 0
            self.reduce(2, cursor, self.apply(self[2:cursor]))

        return self.done()

    # ----------------------------------------------------------------------------------

    def extract_extra(self, tokens: list[_Token]) -> None | str:
        token = self.apply(tokens)
        if token.type is _TypTok.ELIDED:
            return None
        if token.type is _TypTok.EXTRA:
            return token.content
        assert False
