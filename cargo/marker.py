from dataclasses import dataclass
from enum import auto, Enum
import re
from typing import Callable, cast

from .name import canonicalize


__all__ = ("extract_extra",)


SYNTAX = re.compile(
    r"""
        (?P<BLANK> \s+)
        | (?P<OPEN> [(])
        | (?P<CLOSE> [)])
        | (?P<COMP> <=? | != | ===? | >=? | ~= | not\s+in | in)
        | (?P<BOOL> and | or)
        | (?P<LIT> '[^']*' | "[^"]*")
        | (?P<VAR>  [a-z] (?: [a-z._-]* [a-z])?)
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
    """
    The type of a token.

    Tokens with the `EXTRA` or `NOT_EXTRA` type do not appear in marker
    expressions. But a marker expression is reducible to one of these tokens
    with `distill_extra()`.
    """

    BLANK = auto()  # spacing

    LIT = auto()  # string literals, incl. their quotes
    VAR = auto()  # variables incl. extra
    COMP = auto()  # comparison operators, which combine LIT and VAR
    BOOL = auto()  # boolean and/or, which combine COMP-triples
    OPEN = auto()  # open parenthesis
    CLOSE = auto()  # close parenthesis

    EXTRA = auto()  # an "extra == 'tag'" expression
    NOT_EXTRA = auto()  # any combination of well-formed expressions without extra


# The single letter version makes the code eminently more readable.
T = TypTok


@dataclass(frozen=True, slots=True)
class Token:
    """Representation of a token."""
    tag: TypTok
    content: str


# The canonical not-extra token
ELIDED = Token(T.NOT_EXTRA, "🟅")

# ======================================================================================

def apply_operator(left: Token, op: Token, right: Token) -> Token:
    """
    Apply the infix operator on its arguments. The left and right tokens must be
    a variable, literal, extra, or not-extra token. The operator token must be a
    comparison or boolean combinator.
    """
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
                raise SyntaxError(f'invalid term "extra {op.content} {right.content}"')
            else:
                return ELIDED

        case T.LIT, T.COMP, T.VAR:
            if right.content == 'extra':
                if op.content == '==' and len(left.content) >= 3:
                    return Token(T.EXTRA, canonicalize(left.content[1:-1]))
                raise SyntaxError(f'invalid term "{left.content} {op.content} extra"')
            else:
                return ELIDED

        case _, T.COMP, _:
            l, o, r = left.content, op.content, right.content
            raise SyntaxError(f'not a valid comparison "{l} {o} {r}"')

        case (T.EXTRA, T.BOOL, T.EXTRA) if left.content == right.content:
            return left
        case T.EXTRA, T.BOOL, T.EXTRA:
            l, r = left.content, right.content
            raise SyntaxError(f'marker with multiple extras "{l}" and "{r}"')

        case (T.EXTRA, T.BOOL, T.NOT_EXTRA) if op.content == "and":
            return left
        case T.EXTRA, T.BOOL, T.NOT_EXTRA:
            raise SyntaxError(f'disjunction of extra "{left.content}" and non-extra')

        case (T.NOT_EXTRA, T.BOOL, T.EXTRA) if op.content == "and":
            return right
        case T.NOT_EXTRA, T.BOOL, T.EXTRA:
            raise SyntaxError(f'disjunction of non-extra and extra "{right.content}"')

        case T.NOT_EXTRA, T.BOOL, T.NOT_EXTRA:
            return ELIDED

    raise AssertionError('unreachable')


class TokenString:
    """
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
    """

    @classmethod
    def from_string(cls, marker: str) -> "TokenString":
        """Tokenize the given character string."""
        tokens = []
        cursor = 0
        while t := SYNTAX.match(marker, cursor):
            cursor = t.end()
            tag = cast(str, t.lastgroup)
            content = t.group()
            if tag == "VAR":
                content = content.replace('-', '_').replace('.', '_')
                if content not in VARIABLE_NAMES:
                    raise SyntaxError(f'marker contains unknown variable "{content}"')
            tokens.append(Token(TypTok[tag], content))

        if cursor < len(marker):
            raise SyntaxError(f'marker contains invalid characters "{marker[cursor:]}"')

        return cls(tokens, 0, len(tokens))

    __slots__ = ("_tokens", "_start", "_stop", "_cursor")

    def __init__(self, tokens: list[Token], start: int, stop: int) -> None:
        assert 0 <= start <= stop <= len(tokens)
        self._tokens = tokens
        self._start = start
        self._stop = stop
        self._cursor = start
        self._step_over_spacing()

    def _step_over_spacing(self) -> None:
        """
        Step over spacing so that current position either is at end of string or
        points to a non-space token. This method should be invoked whenever the
        current position has been advanced, notably from within `next()`, but
        also from within the constructor and from within `parenthesized()`.
        """
        cursor = self._cursor
        stop = self._stop
        tokens = self._tokens

        while cursor < stop and tokens[cursor].tag is T.BLANK:
            cursor += 1
        self._cursor = cursor

    def has_next(self) -> bool:
        """
        Determine whether the current position points to a token. Code using
        this class must check this method before invoking `peek()` or `next()`.
        """
        return self._cursor < self._stop

    def peek(self) -> Token:
        """Return the next token without consuming it."""
        return self._tokens[self._cursor]

    def next(self) -> Token:
        """
        Return the next token and advance the current position to the next
        non-space token thereafter.
        """
        token = self._tokens[self._cursor]
        self._cursor += 1
        self._step_over_spacing()
        return token

    def parenthesized(self) -> "TokenString":
        """
        Return the parenthesized expression starting at the current position.
        This method returns a token string that shares the same token buffer as
        this token string but has its start (also current) and stop indices set
        to the first and last token of the parenthesized expression (i.e., sans
        parentheses). It also updates this string's current position to the
        first non-space token after the closing parenthesis. The scan for the
        closing parenthesis correctly accounts for nested parentheses.
        """
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

        raise SyntaxError(f"opening parenthesis without closing one in '{self}'")

    def __str__(self) -> str:
        return "".join(t.content for t in self._tokens[self._cursor : self._stop])


class TokenStack:
    """
    A token stack. While distilling a marker to its (hopefully) only extra, the
    `distill_extra()` function uses a token stack as the primary mutable state.
    Methods draw on familiar parser terminology and techniques because marker
    evaluation *is* marker parsing.
    """

    def __init__(self) -> None:
        self._stack: list[Token] = []

    def __len__(self) -> int:
        return len(self._stack)

    def stringify(self, count: int) -> str:
        """Convert the top count tokens into a left-to-right readable string."""
        assert count <= len(self._stack)

        parts = []
        for index, token in enumerate(self._stack.__reversed__()):
            if index == count:
                break
            parts.append(token.content)
        return " ".join(parts)

    def unwrap(self) -> Token:
        """Return the only token left on this stack."""
        assert len(self._stack) == 1
        return self._stack[0]

    def shift(self, *tokens: Token) -> None:
        """Shift the given tokens, in order, onto this stack."""
        self._stack.extend(tokens)

    def is_reducible(
        self,
        operator_tag: TypTok,
        operator_content: None | str = None,
        *operand_tags: TypTok,
    ) -> bool:
        """
        Determine whether this stack is reducible because it has at least three
        tokens with the given operator tag, operator content, and operand tags.
        """
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
        """Reduce this stack's top three tokens to one with the given function."""
        stack = self._stack
        right = stack.pop()
        op = stack.pop()
        left = stack.pop()
        stack.append(reducer(left, op, right))


def distill_extra(tokens: TokenString) -> Token:
    """
    Distill the given token string down to a single extra or not-extra token.
    This function parses the token string while tracking whether terms contain
    extra or not. This function accepts only terms that restrict extra to equal
    some literal name, e.g., `"<name>" == extra`, but not with other operators
    or more than one name per marker. This function signals errors as
    `SyntaxError`.
    """
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
                raise SyntaxError(f'expected operand, found "{tokens}"')
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
                raise SyntaxError(f'expected operator, found "{tokens}"')
            continue
        # All tokens have been consumed. All comparisons and conjunctions have
        # been reduced. That should leave only disjunctions.
        if len(stack) > 1 and not stack.is_reducible(T.BOOL, "or"):
            raise SyntaxError('expected operand but marker ended already')
        break

    # Reduce disjunctions until the stack has only one token. That's our result.
    while len(stack) > 1:
        assert stack.is_reducible(T.BOOL, "or")
        stack.reduce_with(apply_operator)

    return stack.unwrap()


def extract_extra(marker: str) -> None | str:
    """
    Extract the extra name from an environment marker. If the marker contains a
    term constraining extra like `"<name>" == extra`, this function returns that
    name. It treats operators other than `==` or the presence of more than one
    extra name as errors. This function signals errors as `ValueError`.
    """
    try:
        token = distill_extra(TokenString.from_string(marker))
    except SyntaxError:
        raise ValueError(f"malformed marker '{marker}'")
    else:
        match token.tag:
            case T.EXTRA:
                return token.content
            case T.NOT_EXTRA:
                return None
            case _:
                raise ValueError(f"malformed marker '{marker}'")
