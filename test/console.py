from collections.abc import Iterator
from contextlib import contextmanager
import itertools as it
import operator
import traceback
from typing import Any, Callable, cast, overload, Self, TextIO


def textify(v: object) -> str:
    try:
        return str(v)
    except:
        pass
    try:
        return repr(v)
    except:
        pass
    try:
        return object.__str__(v)
    except:
        return '??'


class Console:
    _CSI = '\x1b['
    _BOLD = '1'
    _GREY = '38;5;240'
    _GREEN = '1;32'
    _RED = '1;31'
    _RESET = '39;0'

    def __init__(self, stream: 'TextIO', verbose: bool = False) -> None:
        self._is_tty = stream.isatty()
        self._stream = stream
        self.verbose = verbose
        self._prefix_value = ''
        self._failed_assertions = 0

    def _sgr(self, code: str) -> str:
        return f'{self._CSI}{code}m' if self._is_tty else ''

    # ----------------------------------------------------------------------------------

    @contextmanager
    def new_prefix(self, prefix: str) -> 'Iterator[Console]':
        old_prefix = self._prefix_value
        try:
            self._prefix_value = prefix
            yield self
        finally:
            self._prefix_value = old_prefix

    def _prefix(self) -> Self:
        self._stream.write(self._prefix_value)
        return self

    def _write_in_style(self, message: str, style: str) -> Self:
        formatted = f'{self._sgr(style)}{message}{self._sgr(self._RESET)}'
        self._stream.write(formatted)
        return self

    def _write_plain(self, message: str) -> Self:
        self._stream.write(message)
        return self

    def _newline(self) -> Self:
        self._stream.write('\n')
        return self

    # ----------------------------------------------------------------------------------

    def trace(self, message: str) -> None:
        if self.verbose:
            self._prefix()._write_in_style(message, self._GREY)._newline()

    def detail(self, message: str) -> None:
        self._prefix()._write_plain(message)._newline()

    def info(self, message: str) -> None:
        self._prefix()._write_in_style(message, self._BOLD)._newline()

    def success(self, message: str) -> None:
        self._prefix()._write_in_style(message, self._GREEN)._newline()

    def error(self, message: str) -> None:
        self._prefix()._write_in_style(message, self._RED)._newline()

    def exception(self, x: Exception) -> None:
        for line in it.chain(*(f.splitlines() for f in traceback.format_exception(x))):
            if (
                line == ''
                or line.startswith(' ')
                or line.startswith('During handling')
                or line == 'Traceback (most recent call last):'
            ):
                self._prefix()._write_plain(line)._newline()
            else:
                self._prefix()._write_in_style(line, self._RED)._newline()

    # ----------------------------------------------------------------------------------

    @property
    def failed_assertions(self) -> int:
        return self._failed_assertions

    def assert_eq(self, left: object, right: object) -> None:
        self.assert_op(operator.eq, left, right)

    @overload
    def assert_op(
        self,
        op: Callable[[object], bool],
        arg: object,
        /,
        *,
        expected: bool = ...,
    ) -> None:
        ...

    @overload
    def assert_op(
        self,
        op: str | Callable[[object, object], bool],
        arg1: object,
        arg2: object,
        /,
        *,
        expected: bool = ...,
    ) -> None:
        ...

    def assert_op(
        self,
        op: str | Callable[[object], bool] | Callable[[object, object], bool],
        /,
        *args: object,
        expected: bool = True,
    ) -> None:
        fn = getattr(operator, op) if isinstance(op, str) else op
        fn_name = getattr(fn, '__name__', str(fn))

        prefix = '' if expected else 'not '
        display = f'{prefix}{fn_name}｟ {",  ".join(textify(a) for a in args)} ｠'

        failed: bool | Exception = False
        try:
            result = fn(*args)
            if expected:
                failed = not result
            else:
                failed = result
        except Exception as x:
            failed = x

        if not failed:
            self.trace(f'PASS: {display}')
            return

        self._failed_assertions += 1
        self.error(f'FAIL: {display}')
        if isinstance(failed, Exception):
            self.exception(failed)
