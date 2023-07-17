#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# DO NOT EDIT! This script was automatically generated
# by Tsutsumu <https://github.com/apparebit/tsutsumu>.
# Manual edits may just break it.

if False: {
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
"tsutsumu/distribution/__init__.py":
b"""from .requirement import parse_requirement
from .distinfo import collect_dependencies, DistInfo
""",
# ------------------------------------------------------------------------------
"tsutsumu/distribution/distinfo.py":
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

from cargo.name import canonicalize

from .requirement import parse_requirement
from .util import today_as_version


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

    pyproject_path = Path.cwd() / \x22pyproject.toml\x22  # type: ignore[misc]
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
        dependency, dep_extras, _, only_for_extra = parse_requirement(requirement)

        req = PackagingRequirement(requirement)
        if req.marker is not None:
            env = {} if only_for_extra is None else {\x22extra\x22: only_for_extra}
            if not req.marker.evaluate(env):
                not_installed[pkgname] = req.marker
                continue  # since dependency hasn't been installed
        if only_for_extra is not None and only_for_extra not in pkgextras:
            continue  # since requirement is for unused package extra
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
                assert isinstance(version, str)  # type: ignore[misc]  # due to Any
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
"tsutsumu/distribution/marker.py":
b"""from dataclasses import dataclass
from enum import auto, Enum
import re
from typing import Callable, cast, NoReturn

from cargo.name import canonicalize


__all__ = (\x22extract_extra\x22,)


MARKER_SYNTAX = re.compile(
    r\x22\x22\x22
        (?P<WS> \\s+)
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
    \x22\x22\x22A class identifying the type of a token.\x22\x22\x22

    WS = auto()  # whitespace, dropped early

    LIT = auto()  # string literals, incl. their quotes
    VAR = auto()  # variables incl. extra
    COMP = auto()  # comparison operators, which combine LIT and VAR
    BOOL = auto()  # boolean and/or, which combine COMP-triples
    OPEN = auto()  # open parenthesis
    CLOSE = auto()  # close parenthesis

    EXTRA = auto()  # an \x22extra == 'tag'\x22 expression
    NOT_EXTRA = auto()  # any combination of well-formed expressions without extra


T = TypTok


@dataclass(frozen=True, slots=True)
class Token:
    tag: TypTok
    content: str


# The canonical not-extra token
ELIDED = Token(T.NOT_EXTRA, \x22\x22)


# ======================================================================================


def invalid_syntax(*tokens: str | Token) -> NoReturn:
    fragment = \x22\x22.join(t.content if isinstance(t, Token) else t for t in tokens)
    raise ValueError(f\x22invalid syntax in marker '{fragment}'\x22)


def _do_apply_comparison(left: Token, op: Token, right: Token) -> Token:
    match left.content, op.content, right.content:
        case \x22extra\x22, \x22==\x22, content if len(content) >= 3:
            return Token(T.EXTRA, canonicalize(content[1:-1]))
        case \x22extra\x22, _, _:
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
        case T.EXTRA, T.BOOL, T.NOT_EXTRA if op.content == \x22and\x22:
            return left
        case T.NOT_EXTRA, T.BOOL, T.EXTRA if op.content == \x22and\x22:
            return right
        case T.NOT_EXTRA, T.BOOL, T.NOT_EXTRA:
            return ELIDED

    invalid_syntax(left, op, right)


class TokenString:
    \x22\x22\x22
    A token string. This class represents the input for marker evaluation. It is
    consumed in strictly linear order from the front, but optimizes the
    recursive evaluation of (parenthesized) substrings through buffer sharing.
    \x22\x22\x22

    @classmethod
    def parse(cls, marker: str) -> \x22TokenString\x22:
        tokens = []
        cursor = 0
        while t := MARKER_SYNTAX.match(marker, cursor):
            cursor = t.end()
            tag = cast(str, t.lastgroup)
            content = t.group()
            if tag == \x22VAR\x22 and content not in VARIABLE_NAMES:
                raise ValueError(f\x22marker contains unknown variable '{content}'\x22)
            tokens.append(Token(TypTok[tag], content))

        if cursor < len(marker):
            raise ValueError(f\x22marker contains invalid syntax '{marker[cursor:]}'\x22)

        return cls(tokens, 0, len(tokens))

    __slots__ = (\x22_tokens\x22, \x22_start\x22, \x22_stop\x22, \x22_cursor\x22)

    def __init__(self, tokens: list[Token], start: int, stop: int) -> None:
        assert 0 <= start <= stop <= len(tokens)
        self._tokens = tokens
        self._start = start
        self._stop = stop
        self._cursor = start

    def __str__(self) -> str:
        return \x22\x22.join(t.content for t in self._tokens[self._cursor : self._stop])

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

    def parenthesized(self) -> \x22TokenString\x22:
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

        raise ValueError(f\x22opening parenthesis without closing one in '{self}'\x22)


class TokenStack:
    \x22\x22\x22
    A token stack. This class captures the incremental execution state during
    marker evaluation. It draws on familiar parser terminology and techniques
    because marker evaluation *is* marker parsing.
    \x22\x22\x22

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
        return \x22 \x22.join(parts)

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
                raise ValueError(f\x22expected comparison, found '{stack.stringify(3)}'\x22)
            stack.reduce_with(apply_operator)
        if stack.has_triple(T.BOOL, \x22and\x22):
            stack.reduce_with(apply_operator)
        if not tokens.has_next():
            break
        stack.shift(tokens.next())

    # Reduce disjunctions until the stack has only one token. That's our result.
    while len(stack) > 1:
        assert stack.has_triple(T.BOOL, \x22or\x22)
        stack.reduce_with(apply_operator)

    return stack.unwrap()


def extract_extra(marker: str) -> None | str:
    try:
        token = distill_extra(TokenString.parse(marker))
    except ValueError:
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
"tsutsumu/distribution/requirement.py":
b"""import re
from typing import cast

from .marker import extract_extra
from cargo.name import canonicalize


__all__ = ('parse_requirement',)


REQUIREMENT_PARTS: re.Pattern[str] = re.compile(
    r\x22\x22\x22
        ^
               (?P<package>  [^[(;\\s]+    )    [ ]*
        (?: \\[ (?P<extras>   [^]]+        ) \\] [ ]* )?
        (?: \\( (?P<version1> [^)]*        ) \\) [ ]* )?
        (?:    (?P<version2> [<!=>~][^;]* )    [ ]* )?
        (?:  ; (?P<marker>   .*           )         )?
        $
    \x22\x22\x22,
    re.VERBOSE)

def parse_requirement(
    requirement: str
) -> tuple[str, list[str], list[str], None | str]:
    if (parts := REQUIREMENT_PARTS.match(requirement)) is None:
        raise ValueError(f'requirement \x22{requirement} is malformed')

    package = canonicalize(cast(str, parts.group('package')).strip())

    extras = []
    if (extras_text := cast(str, parts['extras'])):
        extras = [canonicalize(extra.strip()) for extra in extras_text.split(',')]

    versions = []
    if (version_text := parts['version1'] or parts['version2']): # type: ignore[misc]
        versions = [
            v.strip().replace(' ', '') for v in cast(str, version_text).split(',')]

    marker = None
    marker_text = cast(str, parts['marker'])
    if marker_text is not None:
        marker = extract_extra(marker_text.strip())

    return package, extras, versions, marker

""",
# ------------------------------------------------------------------------------
"tsutsumu/distribution/storage.py":
b"""from collections.abc import Iterator
from enum import Enum
from pathlib import Path
import stat
from typing import NamedTuple
import zipfile

from .distinfo import collect_dependencies, DistInfo


class FileType(Enum):
    BINARY = 'b'     # Binary file using Base85 in Tsutsumu's text format
    METADATA = 'm'   # .dist-info files: METADATA and RECORD
    TEXT = 't'       # Text file using Unicode escapes in text format
    VALUE = 'v'      # Bundled runtime code for tsutsumu.__init__ and tsutsumu.bundle


class FileRef(NamedTuple):
    tag: FileType
    path: Path      # Absolute path mounted on local file system, platform-specific
    key: str        # Relative path serving as unique key, using forward slashes


def python_file_fraction(path: str | Path) -> float:
    path = Path(path)
    if not path.exists() or not path.is_dir():
        return 0
    all_files = python_files = all_bytes = python_bytes = 0
    for item in path.iterdir():
        if not item.is_file():
            continue

        size = item.stat().st_size
        all_files += 1
        all_bytes += size
        if item.suffix == '.py':
            python_files += 1
            python_bytes += size

    return python_files / all_files, python_bytes / all_bytes


def locate_module_root(distinfo: DistInfo) -> None | Path:
    if distinfo.provenance is None:
        raise ValueError(
            f'unable to enumerate files for \x22{distinfo.name}\x22 without provenance')

    distpath = Path(distinfo.provenance)
    if distpath.suffix == '.dist-info' and distpath.is_dir():
        modpath = distpath.parent
        if python_file_fraction(modpath)[0] > 0.3:
            return modpath

    if distpath.name == 'pyproject.toml' and distpath.is_file():
        modpath = distpath.parent / distinfo.name
        if python_file_fraction(modpath)[0] > 0.3:
            return modpath

        modpath = distpath.parent / 'src', distinfo.name
        if python_file_fraction(modpath)[0] > 0.3:
            return modpath

    raise ValueError(f'unable to determine module root for \x22{distinfo.name}\x22')


dependencies = collect_dependencies('tsutsumu', 'dev')
for name in dependencies:
    print(name)
print()

for name, distinfo in dependencies.items():
    module_root = locate_module_root(distinfo)
    if module_root is None:
        continue
    print(f'{name:<10}: {module_root}')
    file_fraction, byte_fraction = python_file_fraction(module_root)
    print(f'          : {file_fraction * 100:5.2f}%  {byte_fraction * 100:5.2f}%')


def create_zipapp(
    bundle_path: str | Path,
    shebang_command: str,
    compressed: bool,
    files: Iterator[FileRef]
) -> None:
    # .pyz file
    with open(bundle_path, mode='wb') as fd:
        # consider platform encoding on Unix
        shebang_line = b'#!' + shebang_command.encode('utf8') + b'\\n'
        fd.write(shebang_line)

        compression = (
            zipfile.ZIP_DEFLATED if compressed else zipfile.ZIP_STORED)
        with zipfile.ZipFile(fd, 'w', compression=compression) as zf:
            for file in files:
                zf.write(file.read_bytes(), file.key)

        if not hasattr(fd, 'write'):
            fd.chmod(fd.stat().st_mode | stat.S_IEXEC)
""",
# ------------------------------------------------------------------------------
"tsutsumu/distribution/util.py":
b"""import datetime
import re

__all__ = ('today_as_version')

def today_as_version() -> str:
    return '.'.join(str(part) for part in datetime.date.today().isocalendar())
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
        files = sorted(self.list_files(), key=lambda f: f.key) # type: ignore[misc]
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
    "tsutsumu/__main__.py": ("t", 309, 4_920),
    "tsutsumu/debug.py": ("t", 5_333, 1_229),
    "tsutsumu/distribution/__init__.py": ("t", 6_682, 103),
    "tsutsumu/distribution/distinfo.py": ("t", 6_905, 10_618),
    "tsutsumu/distribution/marker.py": ("t", 17_641, 9_018),
    "tsutsumu/distribution/requirement.py": ("t", 26_782, 1_407),
    "tsutsumu/distribution/storage.py": ("t", 28_308, 3_229),
    "tsutsumu/distribution/util.py": ("t", 31_653, 176),
    "tsutsumu/maker.py": ("t", 31_933, 13_460),
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
        exec(self.get_code(module.__spec__.name), module.__dict__)  # type: ignore[misc]

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
