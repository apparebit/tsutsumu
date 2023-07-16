from dataclasses import dataclass
from enum import auto, Enum
import re
from typing import Callable, cast, NoReturn

from cargo.name import canonicalize


__all__ = ("extract_extra",)


MARKER_SYNTAX = re.compile(
    r"""
        (?P<WS> \s+)
        | (?P<OPEN> [(])
        | (?P<CLOSE> [)])
        | (?P<COMP> <=? | != | ===? | >=? | ~= | not\s+in | in)
        | (?P<BOOL> and | or)
        | (?P<LIT> '[^']*' | "[^"]*")
        | (?P<VAR>  [a-z] (?: [a-z_]* [a-z])?)
    """,
    re.VERBOSE,
)


VARIABLE_NAMES = set(
    [
        "python_version",
        "python_full_version",
        "os_name",
        "sys_platform",
        "platform_release",
        "platform_system",
        "platform_version",
        "platform_machine",
        "platform_python_implementation",
        "implementation_name",
        "implementation_version",
        "extra",
    ]
)


class TypTok(Enum):
    """A class identifying the type of a token."""

    WS = auto()  # whitespace, dropped early

    LIT = auto()  # string literals, incl. their quotes
    VAR = auto()  # variables incl. extra
    COMP = auto()  # comparison operators, which combine LIT and VAR
    BOOL = auto()  # boolean and/or, which combine COMP-triples
    OPEN = auto()  # open parenthesis
    CLOSE = auto()  # close parenthesis

    EXTRA = auto()  # an "extra == 'tag'" expression
    NOT_EXTRA = auto()  # any combination of well-formed expressions without extra


T = TypTok


@dataclass(frozen=True, slots=True)
class Token:
    tag: TypTok
    content: str


# The canonical not-extra token
ELIDED = Token(T.NOT_EXTRA, "")


# ======================================================================================


def invalid_syntax(*tokens: str | Token) -> NoReturn:
    fragment = "".join(t.content if isinstance(t, Token) else t for t in tokens)
    raise ValueError(f"invalid syntax in marker '{fragment}'")


def _do_apply_comparison(left: Token, op: Token, right: Token) -> Token:
    match left.content, op.content, right.content:
        case "extra", "==", content if len(content) >= 3:
            return Token(T.EXTRA, canonicalize(content[1:-1]))
        case "extra", _, _:
            invalid_syntax(left, op, right)

    return ELIDED


def apply_operator(left: Token, op: Token, right: Token) -> Token:
    match left.tag, op.tag, right.tag:
        case T.VAR, T.COMP, T.LIT:
            return _do_apply_comparison(left, op, right)
        case T.LIT, T.COMP, T.VAR:
            return _do_apply_comparison(right, op, left)
        case T.EXTRA, T.BOOL, T.EXTRA if left.content == right.content:
            return left
        case T.EXTRA, T.BOOL, T.NOT_EXTRA if op.content == "and":
            return left
        case T.NOT_EXTRA, T.BOOL, T.EXTRA if op.content == "and":
            return right
        case T.NOT_EXTRA, T.BOOL, T.NOT_EXTRA:
            return ELIDED

    invalid_syntax(left, op, right)


class TokenString:
    """
    A token string. This class represents the input for marker evaluation. It is
    consumed in strictly linear order from the front, but optimizes the
    recursive evaluation of (parenthesized) substrings through buffer sharing.
    """

    @classmethod
    def parse(cls, marker: str) -> "TokenString":
        tokens = []
        cursor = 0
        while t := MARKER_SYNTAX.match(marker, cursor):
            cursor = t.end()
            tag = cast(str, t.lastgroup)
            content = t.group()
            if tag == "VAR" and content not in VARIABLE_NAMES:
                raise ValueError(f"marker contains unknown variable '{content}'")
            tokens.append(Token(TypTok[tag], content))

        if cursor < len(marker):
            raise ValueError(f"marker contains invalid syntax '{marker[cursor:]}'")

        return cls(tokens, 0, len(tokens))

    __slots__ = ("_tokens", "_start", "_stop", "_cursor")

    def __init__(self, tokens: list[Token], start: int, stop: int) -> None:
        assert 0 <= start <= stop <= len(tokens)
        self._tokens = tokens
        self._start = start
        self._stop = stop
        self._cursor = start

    def __str__(self) -> str:
        return "".join(t.content for t in self._tokens[self._cursor : self._stop])

    def has_next(self, count: int = 1) -> bool:
        return self._cursor + count - 1 < self._stop

    def has_triple_with(self, tag: TypTok, content: None | str = None) -> bool:
        tokens = self._tokens
        if self._cursor + 2 < self._stop:
            return False
        token = tokens[self._cursor + 1]
        return token.tag is tag and (content is None or content == token.content)

    def peek(self) -> Token:
        return self._tokens[self._cursor]

    def next(self) -> Token:
        tokens = self._tokens
        cursor = self._cursor
        stop = self._stop

        token = tokens[cursor]
        while True:
            cursor += 1
            if cursor == stop or tokens[cursor].tag is not T.WS:
                break

        self._cursor = cursor
        return token

    def parenthesized(self) -> "TokenString":
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
                    return string
                case T.OPEN:
                    nesting += 1
                case T.CLOSE:
                    nesting -= 1

        raise ValueError(f"opening parenthesis without closing one in '{self}'")


class TokenStack:
    """
    A token stack. This class captures the incremental execution state during
    marker evaluation. It draws on familiar parser terminology and techniques
    because marker evaluation *is* marker parsing.
    """

    def __init__(self) -> None:
        self._stack: list[Token] = []

    def __len__(self) -> int:
        return len(self._stack)

    def stringify(self, count: int) -> str:
        assert count <= len(self._stack)

        parts = []
        for index, token in enumerate(self._stack.__reversed__()):
            if index == count:
                break
            parts.append(token.content)
        return " ".join(parts)

    def unwrap(self) -> Token:
        assert len(self._stack) == 1
        return self._stack[0]

    def shift(self, *tokens: Token) -> None:
        self._stack.extend(tokens)

    def reduce_with(self, reducer: Callable[[Token, Token, Token], Token]) -> None:
        stack = self._stack
        right = stack.pop()
        op = stack.pop()
        left = stack.pop()
        stack.append(reducer(left, op, right))

    def has_triple(self, tag: TypTok, content: None | str = None) -> bool:
        stack = self._stack
        if len(stack) < 3:
            return False
        token = stack[-2]
        if token.tag is not tag or (content is not None and content != token.content):
            return False
        token = stack[-1]
        return token.tag is not T.OPEN


def distill_extra(tokens: TokenString) -> Token:
    stack = TokenStack()

    # Compute the fixed point of parenthesized, comparsion, and conjunctive
    # expressions. Once all of them have been reduced, handle disjunctions.
    while True:
        if tokens.has_next() and tokens.peek().tag is T.OPEN:
            parenthesized = tokens.parenthesized()
            stack.shift(distill_extra(parenthesized))
        elif tokens.has_next(3):
            stack.shift(tokens.next(), tokens.next(), tokens.next())
            if not stack.has_triple(T.COMP):
                raise ValueError(f"expected comparison, found '{stack.stringify(3)}'")
            stack.reduce_with(apply_operator)
        if stack.has_triple(T.BOOL, "and"):
            stack.reduce_with(apply_operator)
        if not tokens.has_next():
            break
        stack.shift(tokens.next())

    # Reduce disjunctions until the stack has only one token. That's our result.
    while len(stack) > 1:
        assert stack.has_triple(T.BOOL, "or")
        stack.reduce_with(apply_operator)

    return stack.unwrap()


def extract_extra(marker: str) -> None | str:
    try:
        token = distill_extra(TokenString.parse(marker))
    except ValueError:
        raise ValueError(f"malformed marker '{marker}'")
    else:
        match token.tag:
            case T.EXTRA:
                return token.content
            case T.NOT_EXTRA:
                return None
            case _:
                raise ValueError(f"malformed marker '{marker}'")
