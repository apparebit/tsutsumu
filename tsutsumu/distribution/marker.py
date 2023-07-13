from collections.abc import Iterator
from dataclasses import dataclass
from enum import auto, Enum
import re
from typing import Callable, cast, NoReturn

from .util import canonicalize


__all__ = ('extract_extra',)


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
    re.VERBOSE)


VARIABLE_NAMES = set([
    'python_version', 'python_full_version', 'os_name', 'sys_platform',
    'platform_release', 'platform_system', 'platform_version', 'platform_machine',
    'platform_python_implementation','implementation_name', 'implementation_version',
    'extra',
])


class TypTok(Enum):
    """A class identifying the type of a token."""

    WS = auto()         # whitespace, dropped early

    LIT = auto()        # string literals, incl. their quotes
    VAR = auto()        # variables incl. extra
    COMP = auto()       # comparison operators, which combine LIT and VAR
    BOOL = auto()       # boolean and/or, which combine COMP-triples
    OPEN = auto()       # open parenthesis
    CLOSE = auto()      # close parenthesis

    EXTRA = auto()      # an "extra == 'tag'" expression
    NOT_EXTRA = auto()  # any combination of well-formed expressions without extra


@dataclass(frozen=True, slots=True)
class Token:
    tag: TypTok
    content: str


# The canonical not-extra token
ELIDED = Token(TypTok.NOT_EXTRA, '')


# ======================================================================================

def invalid_syntax(*tokens: str | Token) -> NoReturn:
    fragment = ' '.join(t.content if isinstance(t, Token) else t for t in tokens)
    raise ValueError(f'invalid syntax in marker "{fragment}"')

def tokenize(marker: str) -> Iterator[Token]:
    marker = marker.lower()
    cursor = 0
    while (t := MARKER_SYNTAX.match(marker, cursor)):
        cursor = t.end()
        tag_name = cast(str, t.lastgroup)
        if tag_name == 'WS':
            continue
        tag_content = t.group()
        if tag_name == 'VAR' and tag_content not in VARIABLE_NAMES:
            raise ValueError(f'marker contains unknown variable "{tag_content}"')
        yield Token(TypTok[tag_name], tag_content)
    if cursor < len(marker):
        invalid_syntax(marker[cursor:])

def do_apply_comparison(var: Token, op: Token, lit: Token) -> Token:
    if lit.tag is not TypTok.LIT:
        invalid_syntax(var, op, lit)
    if var.content == 'extra':
        if op.content != '==' or len(lit.content) < 3:
            invalid_syntax(var, op, lit)
        return Token(TypTok.EXTRA, canonicalize(lit.content[1:-1]))
    return ELIDED

def apply_comparison(left: Token, op: Token, right: Token) -> Token:
    if op.tag is TypTok.COMP:
        if left.tag is TypTok.VAR:
            return do_apply_comparison(left, op, right)
        elif right.tag is TypTok.VAR:
            return do_apply_comparison(right, op, left)
    invalid_syntax(left, op, right)

def apply_junction(left: Token, op: Token, right: Token) -> Token:
    if op.tag is not TypTok.BOOL:
        invalid_syntax(left, op, right)
    if left.tag is TypTok.EXTRA:
        if right.tag is TypTok.EXTRA and left.content == right.content:
            return left
        if right.tag is TypTok.NOT_EXTRA and op.content == 'and':
            return left
    elif right.tag is TypTok.EXTRA:
        if left.tag is TypTok.NOT_EXTRA and op.content == 'and':
            return right
    elif left.tag is TypTok.NOT_EXTRA and right.tag is TypTok.NOT_EXTRA:
        return ELIDED
    invalid_syntax(left, op, right)

def distill_extra(tokens: list[Token]) -> Token:
    cursor = 0
    length = len(tokens)
    stack: list[Token] = []

    def shift_onto_stack(token: Token) -> None:
        stack.append(token)

    def reduce_stack_with(reducer: Callable[[Token, Token, Token], Token]) -> None:
        right = stack.pop()
        op = stack.pop()
        left = stack.pop()
        stack.append(reducer(left, op, right))

    def is_junction_on_stack(content: str, offset: int = 0) -> bool:
        if len(stack) < offset + 3:
            return False
        token = stack[-offset-2]
        return token.tag is TypTok.BOOL and token.content == content

    def peek_token() -> Token:
        return tokens[cursor]

    def has_tokens(count: int = 1) -> bool:
        return cursor + count - 1 < length

    def next_token() -> Token:
        nonlocal cursor
        token = tokens[cursor]
        cursor += 1
        return token

    def find_close_token() -> int:
        nesting = 0
        for index in range(cursor + 1, length):
            token = tokens[index]
            if nesting == 0 and token.tag is TypTok.CLOSE:
                return index
            if token.tag is TypTok.OPEN:
                nesting += 1
            elif token.tag is TypTok.CLOSE:
                if nesting == 0:
                    invalid_syntax(*tokens[index:])
                nesting -= 1
        raise ValueError(f'opening parenthesis without closing one')

    while True:
        if has_tokens() and peek_token().tag is TypTok.OPEN:
            close = find_close_token()
            shift_onto_stack(distill_extra(tokens[1 : close]))
            tokens[0 : close + 1] = []
        elif has_tokens(3):
            result = apply_comparison(next_token(), next_token(), next_token())
            shift_onto_stack(result)
        if is_junction_on_stack('and'):
            reduce_stack_with(apply_junction)
        if not has_tokens():
            break
        shift_onto_stack(next_token())

    while len(stack) > 1:
        if not is_junction_on_stack('or'):
            invalid_syntax(*tokens)
        reduce_stack_with(apply_junction)

    return stack[0]

def extract_extra(marker: str) -> None | str:
    try:
        tokens = [*tokenize(marker)]
        token = distill_extra(tokens)
    except ValueError:
        raise ValueError(f'malformed marker "{marker}"')
    else:
        if token.tag is TypTok.NOT_EXTRA:
            return None
        if token.tag is TypTok.EXTRA:
            return token.content
        raise ValueError(f'malformed marker "{marker}"')
