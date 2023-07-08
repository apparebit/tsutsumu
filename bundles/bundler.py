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
b"""import base64
from pathlib import Path
import sys
from typing import cast

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: python -m tsutsumu <path-to-bundle>')
        sys.exit(1)

    bundle = Path(sys.argv[1])
    if bundle.suffix != '.py':
        print(f'Error: bundle \x22{bundle}\x22 does not appear to be Python source code')
        sys.exit(1)

    bindings: 'dict[str, object]' = {}
    exec(bundle.read_bytes(), bindings)

    if '__manifest__' not in bindings:
        print(f'Error: bundle \x22{bundle}\x22 does include __manifest__')
        sys.exit(1)

    manifest = cast(dict[str, tuple[int, int]], bindings['__manifest__'])
    for key, (kind, offset, length) in manifest.items():
        if length == 0:
            print(f'bundled file \x22{key}\x22 is empty')
            continue

        try:
            with open(bundle, mode='rb') as file:
                file.seek(offset)
                data = file.read(length)

            if kind == 'b':
                data = base64.a85decode(eval(data))
            elif kind == 't':
                data = eval(data)
            elif kind == 'v':
                data = data
            else:
                print(f'manifest entry with invalid kind \x22{kind}\x22')
                continue

            print(f'bundled file \x22{key}\x22 has {len(data)} bytes')

        except Exception as x:
            print(f'bundled file \x22{key}\x22 is malformed:')
            print(f'    {x}')
            print()
            for line in data.splitlines():
                print(f'    {line!r}')
            print()
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
    from collections.abc import Iterator, Sequence
    from contextlib import AbstractContextManager
    from importlib.abc import Loader
    from importlib.machinery import ModuleSpec
    from typing import Callable, Protocol

    class Writable(Protocol):
        def write(self, data: 'bytes | bytearray') -> int:
            ...

from tsutsumu import __version__


_BANNER = (
    b'#!/usr/bin/env python3\\n'
    b'# -*- coding: utf-8 -*-\\n'
    b'# DO NOT EDIT! This script was automatically generated\\n'
    b'# by Tsutsumu <https://github.com/apparebit/tsutsumu>.\\n'
    b'# Manual edits may just break it.\\n\\n')

# Both bundle starts must have the same length
_BUNDLE_START_IFFY = b'if False: {\\n'
_BUNDLE_START_DICT = b'BUNDLE  = {\\n'
_BUNDLE_STOP = b'}\\n\\n'

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

_MAIN = \x22\x22\x22
if __name__ == \x22__main__\x22:
    import runpy

    # Don't load modules from current directory
    Bundle.restrict_sys_path()

    # Install the bundle
    bundle = Bundle.install(__file__, __manifest__, __version__)

    # This script does not exist. It never ran!
    {repackage}

    # Run equivalent of \x22python -m {main}\x22
    runpy.run_module(\x22{main}\x22, run_name=\x22__main__\x22, alter_sys=True)
\x22\x22\x22

_SEPARATOR_HEAVY = (
    b'# ======================================='
    b'=======================================\\n')
_SEPARATOR = (
    b'# ---------------------------------------'
    b'---------------------------------------\\n')


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
            BundleMaker.writeall(self.emit_bundle(files), script)
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
        yield from _BANNER.splitlines(keepends=True)
        yield from _BUNDLE_START_IFFY.splitlines(keepends=True)

        for file in files:
            yield from self.emit_file(file.kind, file.path, file.key)

        yield from _BUNDLE_STOP.splitlines(keepends=True)
        yield from self.emit_manifest()
        yield from self.emit_version()

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
        offset = len(_SEPARATOR) + len(prefix) + 1

        yield _SEPARATOR

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

    def list_manifest_entries(self) -> 'Iterator[tuple[str, tuple[str, int, int]]]':
        offset = len(_BANNER) + len(_BUNDLE_START_IFFY)
        for kind, key, prefix, data, suffix in self._ranges:
            yield key, ((kind, 0, 0) if data == 0 else (kind, offset + prefix, data))
            offset += prefix + data + suffix

    def emit_manifest(self) -> 'Iterator[bytes]':
        yield _SEPARATOR_HEAVY
        yield b'\\n'
        yield b'__manifest__ = {\\n'
        for key, (kind, offset, length) in self.list_manifest_entries():
            entry = f'    \x22{key}\x22: (\x22{kind.value}\x22, {offset:_d}, {length:_d}),\\n'
            yield entry.encode('utf8')
        yield b'}\\n'

    def emit_version(self) -> 'Iterator[bytes]':
        yield b'\\n'
        yield f\x22__version__ = '{__version__}'\\n\x22.encode('ascii')

    # ----------------------------------------------------------------------------------

    def emit_runtime(
        self,
        main: str,
    ) -> 'Iterator[bytes]':
        yield b'\\n'
        yield _SEPARATOR_HEAVY
        yield b'\\n'
        yield from self.emit_tsutsumu_bundle()

        yield _SEPARATOR_HEAVY
        if self._repackage:
            repackage = \x22bundle.repackage()\x22
        else:
            repackage = \x22del sys.modules['__main__']\x22

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
        yield b'\\n'

    # ----------------------------------------------------------------------------------

    @staticmethod
    def writeall(
        lines: 'Iterator[bytes]',
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

__manifest__ = {
    "tsutsumu/__main__.py": ("t", 309, 4_319),
    "tsutsumu/debug.py": ("t", 4_732, 1_617),
    "tsutsumu/maker.py": ("t", 6_453, 13_000),
}

__version__ = '0.1.0'

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


class Bundle(Loader):
    """
    Representation of a bundle. Each instance serves as meta path finder and
    module loader for a particular bundle script.
    """

    @classmethod
    def exec_install(
        cls,
        path: 'str | Path',
    ) -> 'Bundle':
        with open(path, mode='rb') as file:
            content = file.read()

        if (
            content.find(b'\nif False: {\n')
            or content.find(b'=\n\n__manifest__ = {') == -1
            or content.find(b'}\n\n__version__ = "') == -1
        ):
            raise ValueError(f'"{path}" does not appear to be a bundle')

        bindings: 'dict[str, object]' = {}
        exec(content, bindings)
        # cast() would require backwards-compatible type value; comment seems simpler.
        manifest: 'dict[str, tuple[int, int]]' = (
            bindings['__manifest__']) # type: ignore[assignment]
        version = cast(str, bindings['__version__'])

        return cls.install(path, manifest, version)

    @classmethod
    def install(
        cls,
        script: 'str | Path',
        manifest: 'dict[str, tuple[str, int, int]]',
        version: str,
    ) -> 'Bundle':
        bundle = Bundle(script, manifest, version)
        for finder in sys.meta_path:
            if bundle == finder:
                raise ImportError(
                    f'bind "{bundle._script}" is already installed')
        sys.meta_path.insert(0, bundle)
        return bundle

    def __init__(
        self,
        script: 'str | Path',
        manifest: 'dict[str, tuple[str, int, int]]',
        version: str,
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
        self._manifest = {intern(k): v for k, v in manifest.items()}
        self._version = version

    def __hash__(self) -> int:
        return hash(self._script) + hash(self._manifest)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Bundle):
            return False
        return (
            self._script == other._script
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

        # The bundle dictionary does not include empty files
        if length == 0:
            return b''

        with open(self._script, mode='rb') as file:
            file.seek(offset)
            data = file.read(length)
            assert len(data) == length

            if kind == 't':
                return eval(data)
            elif kind == 'b':
                return base64.a85decode(eval(data))
            elif kind == 'v':
                return data
            else:
                raise ValueError(f'invalid kind "{kind}" for manifest entry')

    def _locate(
        self,
        fullname: str,
        paths: 'None | Sequence[str]' = None,
    ) -> 'tuple[str, None | str]':
        if paths is None:
            prefixes = [os.path.join(
                self._script,
                fullname.replace('.', os.sep)
            )]
        else:
            modname = fullname.rpartition('.')[2]
            prefixes = [os.path.join(path, modname) for path in paths]

        for suffix, is_pkg in (
            (os.sep + '__init__.py', True),
            ('.py', False),
        ):
            for prefix in prefixes:
                fullpath = prefix + suffix
                if fullpath in self._manifest:
                    return fullpath, (prefix if is_pkg else None)

        raise ImportError(
            f'No such module {fullname} in bundle {self._script}')

    def find_spec(
        self,
        fullname: str,
        path: 'None | Sequence[str]' = None,
        target: 'None | ModuleType' = None,
    ) -> 'None | ModuleSpec':
        try:
            fullpath, modpath = self._locate(fullname, path)
        except ImportError:
            return None

        spec = ModuleSpec(fullname, self, origin=fullpath, is_package=bool(modpath))
        if modpath:
            assert spec.submodule_search_locations is not None
            spec.submodule_search_locations.append(modpath)
        return spec

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
        # Do not repackage if modules exist or their paths are listed in manifest!
        if 'tsutsumu' in sys.modules or 'tsutsumu.bundle' in sys.modules:
            raise ValueError('unable to repackage() already existing modules')

        pkg_path = os.path.join(self._script, 'tsutsumu')
        paths = [os.path.join(pkg_path, file) for file in ('__init__.py', 'bundle.py')]
        if paths[0] in self._manifest or paths[1] in self._manifest:
            raise ValueError('unable to repackage() modules already in manifest')

        # Repackage: Create modules, add attributes, add to manifest.
        package, bundle = self._repackage_create_modules(pkg_path, paths[0], paths[1])
        self._repackage_add_attributes(package, bundle)
        self._repackage_add_to_manifest(package, bundle)

        # If running as __main__ module, remove module.
        if __name__ == '__main__':
            del sys.modules['__main__']

    def _repackage_create_modules(
        self,
        pkg_path: str,
        init_path: str,
        bundle_path: str,
    ) -> 'tuple[ModuleType, ModuleType]':
        for name, path, pkgdir in (
            ('tsutsumu', init_path, pkg_path),
            ('tsutsumu.bundle', bundle_path, None),
        ):
            spec = ModuleSpec(name, self, origin=path, is_package=bool(pkgdir))
            if pkgdir:
                assert spec.submodule_search_locations is not None
                spec.submodule_search_locations.append(pkgdir)
            module = importlib.util.module_from_spec(spec)
            setattr(module, '__file__', path)
            sys.modules[name] = module

        return sys.modules['tsutsumu'], sys.modules['tsutsumu.bundle']

    def _repackage_add_attributes(
        self,
        tsutsumu: 'ModuleType',
        tsutsumu_bundle: 'ModuleType',
    ) -> None:
        for obj, attr, value in (
            (tsutsumu, '__version__', self._version),
            (tsutsumu, 'bundle', tsutsumu_bundle),
            (tsutsumu_bundle, 'Bundle', Bundle),
            (Bundle, '__module__', 'tsutsumu.bundle'),
        ):
            setattr(obj, attr, value)

    def _repackage_add_to_manifest(
        self,
        tsutsumu: 'ModuleType',
        tsutsumu_bundle: 'ModuleType',
    ) -> None:
        hr = b'# ' + b'=' * 78 + b'\n'
        with open(self._script, mode='rb') as file:
            content = file.read()
        index = content.find(hr)
        index = content.find(hr, index + len(hr))
        init_start = content.rfind(b'__version__', 0, index)
        init_length = index - 1 - init_start
        bundle_start = index + len(hr) + 1
        bundle_length = content.find(hr, bundle_start) - 1 - bundle_start

        assert tsutsumu.__file__ is not None
        self._manifest[tsutsumu.__file__] = ('v', init_start, init_length)

        assert tsutsumu_bundle.__file__ is not None
        self._manifest[tsutsumu_bundle.__file__] = ('v', bundle_start, bundle_length)

    def uninstall(self) -> None:
        index = 0
        while index < len(sys.meta_path):
            if self == sys.meta_path[index]:
                del sys.meta_path[index]
            else:
                index += 1

    @staticmethod
    def restrict_sys_path() -> None:
        # FIXME: Maybe, we should disable venv paths, too?!
        cwd = os.getcwd()

        index = 0
        while index < len(sys.path):
            path = sys.path[index]
            if path == '' or path == cwd:
                del sys.path[index]
            else:
                index += 1

    @staticmethod
    def warn(message: str) -> None:
        # Assuming that warnings are infrequent, delay import until use.
        import warnings
        warnings.warn(message)

# ==============================================================================

if __name__ == "__main__":
    import runpy

    # Don't load modules from current directory
    Bundle.restrict_sys_path()

    # Install the bundle
    bundle = Bundle.install(__file__, __manifest__, __version__)

    # This script does not exist. It never ran!
    bundle.repackage()

    # Run equivalent of "python -m tsutsumu"
    runpy.run_module("tsutsumu", run_name="__main__", alter_sys=True)
