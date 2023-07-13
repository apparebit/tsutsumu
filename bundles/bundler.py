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
            self-contained script. To determine which files to include in the
            bundle, this tool traverses the given directories and their
            subdirectories. Since module resolution is based on path names, this
            tool skips directories and files that do not have valid Python
            module names.

            By default, the generated script includes code for importing modules
            from the bundle and for executing one of its modules, very much like
            \x22python -m\x22 does. If the bundled modules include exactly one
            __main__ module, Tsutsumu automatically selects that module. If
            there are no or several such modules or you want to execute another
            module, please use the -m/--main option to specify the module name.

            You can use the -b/--bundle-only option to omit the bundle runtime
            and bootstrap code from the generated script. That way, you can
            break your application into several bundles. Though you probably
            want to include that code with your application's primary bundle.
            The application can then use `Bundle.exec_install()` to load and
            install such secondary bundles and `Bundle.uninstall()` to uninstall
            them again.

            Tsutsumu always generates the bundle script in binary format.
            Re-encoding its output or even changing the line endings will likely
            break the generated script! By default, the script is written to
            standard out. Please use the -o/--output option to write to a file
            instead.

            Tsutsumu is \xc2\xa9 2023 Robert Grimm. It is licensed under Apache 2.0.
            The source repository is <https://github.com/apparebit/tsutsumu>
        \x22\x22\x22),
        formatter_class=width_limited_formatter)
    parser.add_argument(
        '-b', '--bundle-only',
        action='store_true',
        help='emit only bundled files and their manifest,\\nno runtime code')
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

from .requirement import parse_requirement
from .util import canonicalize, today_as_version


__all__ = ('collect_dependencies', 'DistInfo')


def collect_dependencies(pkgname: str, *pkgextras: str) -> 'dict[str, DistInfo]':
    \x22\x22\x22
    Determine the package dependencies of the given package, the dependencies of
    those packages, and so on. This function determines the transitive closure
    of package dependencies through a breadth-first search of the dependency
    graph. This function does expect
    \x22\x22\x22

    pyproject_path = Path.cwd() / 'pyproject.toml' # type: ignore[misc]
    if pyproject_path.exists():
        distribution = DistInfo.from_pyproject(pyproject_path)
    else:
        distribution = DistInfo.from_installation(pkgname,pkgextras)

    # Breadth-first search requires a queue
    pending: deque[tuple[str, tuple[str, ...], str]] = (
        deque((pkgname, pkgextras, req) for req in distribution.required_packages))
    distributions = {pkgname: distribution}

    while len(pending) > 0:
        # Resolve the requirement to a distribution
        pkgname, pkgextras, requirement = pending.pop()
        dependency, dep_extras, _, only_for_extra = parse_requirement(requirement)
        if only_for_extra is not None and only_for_extra not in pkgextras:
            continue # since requirement is for unused package extra
        if dependency in distributions:
            continue
        dist = DistInfo.from_installation(dependency, dep_extras)
        distributions[dependency] = dist
        pending.extend(
            (dist.name, dist.extras, req) for req in dist.required_packages)

    return distributions


T = TypeVar('T')

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
    def from_pyproject(cls, path: str | Path) -> 'DistInfo':
        with open(path, mode='rb') as file:
            metadata = cast(dict[str, object], tomllib.load(file))
        if not isinstance(project_metadata := metadata.get('project'), dict):
            raise ValueError(f'\x22{path}\x22 lacks \x22project\x22 section')

        @overload
        def property(key: str, typ: type[T], is_optional: Literal[False]) -> T:
            ...
        @overload
        def property(key: str, typ: type[T], is_optional: Literal[True]) -> None | T:
            ...
        def property(key: str, typ: type[T], is_optional: bool) -> None | T:
            value = project_metadata.get(key)
            if value is None and is_optional:
                return value
            elif isinstance(value, typ):
                return value
            elif value is None:
                raise ValueError(f'\x22{path}\x22 has no \x22{key}\x22 entry in \x22project\x22 section')
            else:
                raise ValueError(f'\x22{path}\x22 has non-{typ.__name__} \x22{key}\x22 entry')

        name = canonicalize(property('name', str, False))
        version = property('version', str, True)
        summary = property('description', str, True)
        required_python = property('requires-python', str, True)

        required_packages: tuple[str, ...] = ()
        raw_requirements = property('dependencies', list, True)
        if raw_requirements:
            if any(not isinstance(p, str) for p in raw_requirements):
                raise ValueError(f'\x22{path}\x22 has non-str item in \x22dependencies\x22')
            else:
                required_packages = tuple(raw_requirements)

        homepage: None | str = None
        urls = property('urls', dict, True)
        if urls is not None:
            for location in ('homepage', 'repository', 'documentation'):
                if location not in urls:
                    continue
                url = urls[location]
                if isinstance(url, str):
                    homepage = url
                    break
                raise ValueError(f'\x22{path}\x22 has non-str value in \x22urls\x22')

        if version is None:
            # pyproject.toml may omit version if it is dynamic.
            if 'version' in (property('dynamic', list, True) or ()):
                package = importlib.import_module(name)
                version = getattr(package, '__version__')
                assert isinstance(version, str) # type: ignore[misc]  # due to Any
            else:
                raise ValueError(f'\x22{path}\x22 has no \x22version\x22 in \x22project\x22 section')

        return cls(
            name,
            (),
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
    ) -> 'DistInfo':
        name = canonicalize(name)

        if version is None:
            try:
                distribution = md.distribution(name)
            except ModuleNotFoundError:
                return cls(name, tuple(extras))

        version = distribution.version
        summary = distribution.metadata['Summary']
        homepage = distribution.metadata['Home-page']
        required_python = distribution.metadata['Requires-Python']

        required_packages: tuple[str, ...] = ()
        raw_requirements = distribution.requires
        if raw_requirements is not None:
            required_packages = tuple(raw_requirements)

        provenance = None
        if hasattr(distribution, '_path'):
            provenance = str(cast(Path, getattr(distribution, '_path')).absolute())

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
        object.__setattr__(self, 'effective_version', version)

    def __hash__(self) -> int:
        return hash(self.name) + hash(self.version)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DistInfo):
            return NotImplemented
        return self.name == other.name and self.version == other.version

    def __repr__(self) -> str:
        version = '?.?' if self.version is None else self.version
        return f'<DistInfo {self.name} {version}>'

    def metadata_path_content(self) -> tuple[str, str]:
        metadata_path = f'{self.name}-{self.effective_version}.dist-info/METADATA'
        lines = [
            'Metadata-Version: 2.1',
            'Name: ' + self.name,
            'Version: ' + self.effective_version
        ]

        if self.summary:
            lines.append('Summary: ' + self.summary)
        if self.homepage:
            lines.append('Home-page: ' + self.homepage)
        if self.required_python:
            lines.append('Requires-Python: ' + self.required_python)
        for requirement in self.required_packages:
            lines.append('Requires-Dist: ' + requirement)

        return metadata_path, '\\n'.join(lines) + '\\n'

    def record_path_content(self, files: Iterable[str]) -> tuple[str, str]:
        prefix = f'{self.name}-{self.effective_version}.dist-info/'
        record_path = prefix + 'RECORD'
        all_files = itertools.chain((prefix + 'METADATA', record_path), files)
        content = ',,\\n'.join(f'\x22{f}\x22' if ',' in f else f for f in all_files) + ',,\\n'
        return record_path, content
""",
# ------------------------------------------------------------------------------
"tsutsumu/distribution/marker.py":
b"""from collections.abc import Iterator
from dataclasses import dataclass
from enum import auto, Enum
import re
from typing import Callable, cast, NoReturn

from .util import canonicalize


__all__ = ('extract_extra',)


MARKER_SYNTAX = re.compile(
    r\x22\x22\x22
        (?P<WS> \\s+)
        | (?P<OPEN> [(])
        | (?P<CLOSE> [)])
        | (?P<COMP> <=? | != | ===? | >=? | ~= | not\\s+in | in)
        | (?P<BOOL> and | or)
        | (?P<LIT> '[^']*' | \x22[^\x22]*\x22)
        | (?P<VAR>  [a-z] (?: [a-z_]* [a-z])?)
    \x22\x22\x22,
    re.VERBOSE)


VARIABLE_NAMES = set([
    'python_version', 'python_full_version', 'os_name', 'sys_platform',
    'platform_release', 'platform_system', 'platform_version', 'platform_machine',
    'platform_python_implementation','implementation_name', 'implementation_version',
    'extra',
])


class TypTok(Enum):
    \x22\x22\x22A class identifying the type of a token.\x22\x22\x22

    WS = auto()         # whitespace, dropped early

    LIT = auto()        # string literals, incl. their quotes
    VAR = auto()        # variables incl. extra
    COMP = auto()       # comparison operators, which combine LIT and VAR
    BOOL = auto()       # boolean and/or, which combine COMP-triples
    OPEN = auto()       # open parenthesis
    CLOSE = auto()      # close parenthesis

    EXTRA = auto()      # an \x22extra == 'tag'\x22 expression
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
    raise ValueError(f'invalid syntax in marker \x22{fragment}\x22')

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
            raise ValueError(f'marker contains unknown variable \x22{tag_content}\x22')
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
        raise ValueError(f'malformed marker \x22{marker}\x22')
    else:
        if token.tag is TypTok.NOT_EXTRA:
            return None
        if token.tag is TypTok.EXTRA:
            return token.content
        raise ValueError(f'malformed marker \x22{marker}\x22')
""",
# ------------------------------------------------------------------------------
"tsutsumu/distribution/requirement.py":
b"""import re
from typing import cast

from .marker import extract_extra
from .util import canonicalize


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
from typing import NamedTuple

from .distinfo import collect_dependencies, DistInfo


class FileType(Enum):
    BINARY = 'b'
    METADATA = 'm'
    TEXT = 't'
    VALUE = 'v'


class FileRef(NamedTuple):
    tag: FileType
    path: Path
    key: str


def python_file_fraction(path: str | Path) -> float:
    path = Path(path)
    if not path.exists() or not path.is_dir():
        return 0
    all_files = python_files = 0
    for item in path.iterdir():
        if not item.is_file():
            continue
        all_files += 1
        python_files += (item.suffix == '.py')
    return python_files / all_files


def locate_module_root(distinfo: DistInfo) -> Path:
    if distinfo.provenance is None:
        raise ValueError(
            f'lack of provenance for \x22{distinfo.name}\x22 prevents enumeration of files')

    distpath = Path(distinfo.provenance)
    if distpath.suffix == '.dist-info' and distpath.is_dir():
        modpath = distpath.parent
        if python_file_fraction(modpath) > 0.6:
            return modpath

    if distpath.name == 'pyproject.toml' and distpath.is_file():
        modpath = distpath.parent / distinfo.name
        if python_file_fraction(modpath) > 0.6:
            return modpath
        modpath = distpath.parent / 'src', distinfo.name
        if python_file_fraction(modpath) > 0.6:
            return modpath

    raise ValueError(f'unable to determine module root for \x22{distinfo.name}\x22')


dependencies = collect_dependencies('tsutsumu', 'dev')
for name, distinfo in dependencies.items():
    print(name, locate_module_root(distinfo))

""",
# ------------------------------------------------------------------------------
"tsutsumu/distribution/util.py":
b"""import datetime
import re

__all__ = ('canonicalize', 'today_as_version')

_DASHING = re.compile(r'[-_.]+')

def canonicalize(name: str, separator: str = '-') -> str:
    \x22\x22\x22Convert a package or tag name to its canonical form.\x22\x22\x22
    return _DASHING.sub(separator, name).lower()

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
    "tsutsumu/__main__.py": ("t", 309, 4_319),
    "tsutsumu/debug.py": ("t", 4_732, 1_229),
    "tsutsumu/distribution/__init__.py": ("t", 6_081, 103),
    "tsutsumu/distribution/distinfo.py": ("t", 6_304, 8_381),
    "tsutsumu/distribution/marker.py": ("t", 14_803, 6_368),
    "tsutsumu/distribution/requirement.py": ("t", 21_294, 1_402),
    "tsutsumu/distribution/storage.py": ("t", 22_815, 1_684),
    "tsutsumu/distribution/util.py": ("t", 24_615, 415),
    "tsutsumu/maker.py": ("t", 25_134, 13_460),
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
    HEAVY_RULE = b'# ' + b'=' * 78 + b'\n\n'
    PLAIN_RULE = b'# ' + b'-' * 78 + b'\n'

    @staticmethod
    def create_module_spec(
        name: str, loader: 'Loader', path: str, pkgdir: 'None | str'
    ) -> ModuleSpec:
        spec = ModuleSpec(name, loader, origin=path, is_package=bool(pkgdir))
        if pkgdir:
            if spec.submodule_search_locations is None:
                raise AssertionError(f'module spec for {name} is not for package')
            spec.submodule_search_locations.append(pkgdir)
        return spec

    @staticmethod
    def create_module(
        name: str, loader: 'Loader', path: str, pkgdir: 'None | str'
    ) -> 'ModuleType':
        spec = Toolbox.create_module_spec(name, loader, path, pkgdir)
        module = importlib.util.module_from_spec(spec)
        setattr(module, '__file__', path)
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
    def load_meta_data(path: 'str | Path') -> 'tuple[str, ManifestType]':
        with open(path, mode='rb') as file:
            content = file.read()

        start, stop, _ = Toolbox.find_section_offsets(content)
        bindings: 'dict[str, object]' = {}
        exec(content[start + len(Toolbox.HEAVY_RULE) : stop], bindings)
        version = cast(str, bindings['__version__'])
        # cast() would require backwards-compatible type value; comment seems simpler.
        manifest: 'ManifestType' = bindings['__manifest__'] # type: ignore[assignment]
        return version, manifest

    @staticmethod
    def load_from_bundle(
        path: 'str | Path',
        kind: str,
        offset: int,
        length: int
    ) -> bytes:
        data = Toolbox.read(path, offset, length)
        if kind == 't':
            return cast(bytes, eval(data))
        elif kind == 'b':
            return base64.a85decode(data)
        elif kind == 'v':
            return data
        else:
            raise ValueError(f'invalid kind "{kind}" for manifest entry')

    @staticmethod
    def read(path: 'str | Path', offset: int, length: int) -> bytes:
        if length == 0:
            return b''
        with open(path, mode='rb') as file:
            file.seek(offset)
            data = file.read(length)
        if len(data) != length:
            raise AssertionError(f'actual length {len(data):,} is not {length:,}')
        return data

    @staticmethod
    def restrict_sys_path() -> None:
        # TODO: Remove virtual environment paths, too!
        cwd = os.getcwd()
        bad_paths = {'', cwd}

        main = sys.modules['__main__']
        if hasattr(main, '__file__'):
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
        path: 'str | Path',
    ) -> 'Bundle':
        version, manifest = Toolbox.load_meta_data(path)
        return cls.install(path, version, manifest)

    @classmethod
    def install(
        cls, script: 'str | Path', version: str, manifest: 'ManifestType',
    ) -> 'Bundle':
        bundle = cls(script, version, manifest)
        if bundle in sys.meta_path:
            raise ImportError(f'bundle for "{bundle._script}" already installed')
        sys.meta_path.insert(0, bundle)
        return bundle

    def __init__(
        self, script: 'str | Path', version: str, manifest: 'ManifestType',
    ) -> None:
        script = str(script)
        if not os.path.isabs(script):
            script = os.path.abspath(script)
        if script.endswith('/') or script.endswith(os.sep):
            raise ValueError(
                'path to bundle script "{script}" ends in path separator')

        def intern(path: str) -> str:
            local_path = path.replace('/', os.sep)
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
        return f'<tsutsumu {self._script}>'

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
        search_paths: 'None | Sequence[str]' = None,
    ) -> 'tuple[str, None | str]':
        if search_paths is None:
            base_paths = [os.path.join(
                self._script,
                fullname.replace('.', os.sep)
            )]
        else:
            modname = fullname.rpartition('.')[2]
            base_paths = [os.path.join(path, modname) for path in search_paths]

        for suffix, is_pkg in (
            (os.sep + '__init__.py', True),
            ('.py', False),
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

        raise ImportError(
            f'No such module {fullname} in bundle {self._script}')

    def find_spec(
        self,
        fullname: str,
        search_paths: 'None | Sequence[str]' = None,
        target: 'None | ModuleType' = None,
    ) -> 'None | ModuleSpec':
        try:
            return Toolbox.create_module_spec(
                fullname, self, *self._locate(fullname, search_paths))
        except ImportError:
            return None

    def create_module(self, spec: ModuleSpec) -> 'None | ModuleType':
        return None

    def exec_module(self, module: 'ModuleType') -> None:
        assert module.__spec__ is not None, 'module must have spec'
        exec(self.get_code(module.__spec__.name), module.__dict__) # type: ignore[misc]

    def is_package(self, fullname: str) -> bool:
        return self._locate(fullname)[1] is not None

    def get_code(self, fullname: str) -> 'CodeType':
        fullpath = self.get_filename(fullname)
        source = importlib.util.decode_source(self[fullpath])
        return compile(source, fullpath, 'exec', dont_inherit=True)

    def get_source(self, fullname: str) -> str:
        return importlib.util.decode_source(self[self.get_filename(fullname)])

    def get_data(self, path: 'str | Path') -> bytes:
        return self[str(path)]

    def get_filename(self, fullname: str) -> str:
        return self._locate(fullname)[0]

    def repackage(self) -> None:
        # Check sys.modules and self._manifest to prevent duplicates
        if 'tsutsumu' in sys.modules or 'tsutsumu.bundle' in sys.modules:
            raise ValueError('unable to repackage() already existing modules')

        pkgdir = os.path.join(self._script, 'tsutsumu')
        paths = [os.path.join(pkgdir, file) for file in ('__init__.py', 'bundle.py')]
        if any(path in self._manifest for path in paths):
            raise ValueError('unable to repackage() modules already in manifest')

        # Recreate modules and add them to manifest
        tsutsumu = Toolbox.create_module('tsutsumu', self, paths[0], pkgdir)
        tsutsumu_bundle = Toolbox.create_module('tsutsumu.bundle', self, paths[1], None)

        setattr(tsutsumu, '__version__', self._version)
        setattr(tsutsumu, 'bundle', tsutsumu_bundle)
        setattr(tsutsumu_bundle, 'Toolbox', Toolbox)
        setattr(tsutsumu_bundle, 'Bundle', Bundle)
        Bundle.__module__ = Toolbox.__module__ = 'tsutsumu.bundle'

        self._repackage_add_to_manifest(tsutsumu, tsutsumu_bundle)

    def _repackage_add_to_manifest(
        self,
        tsutsumu: 'ModuleType',
        tsutsumu_bundle: 'ModuleType',
    ) -> None:
        with open(self._script, mode='rb') as file:
            content = file.read()

        section1, section2, section3 = Toolbox.find_section_offsets(content)

        module_offset = section1 + len(Toolbox.HEAVY_RULE)
        module_length = content.find(b'\n', module_offset) + 1 - module_offset
        assert tsutsumu.__file__ is not None
        self._manifest[tsutsumu.__file__] = ('v', module_offset, module_length)

        module_offset = section2 + len(Toolbox.HEAVY_RULE)
        module_length = section3 - 1 - module_offset
        assert tsutsumu_bundle.__file__ is not None
        self._manifest[tsutsumu_bundle.__file__] = ('v', module_offset, module_length)

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
