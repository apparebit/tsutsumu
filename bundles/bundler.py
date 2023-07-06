#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# DO NOT EDIT! This script was automatically generated
# by Tsutsumu <https://github.io/apparebit/tsutsumu>.
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


if __name__ == '__main__':
    try:
        width = min(os.get_terminal_size()[0], 70)
    except:
        width = 70

    def width_limited_formatter(prog: str) -> HelpFormatter:
        return RawTextHelpFormatter(prog, width=width)

    @dataclass
    class ToolOptions:
        bundle_only: bool = False
        output: 'None | str' = None
        package: 'None | str' = None
        repackage: bool = False
        verbose: bool = False
        roots: 'list[str]' = field(default_factory=list)

    parser = ArgumentParser('tsutsumu',
        description=dedent(\x22\x22\x22
            Combine Python modules and related resources into a single,
            self-contained script. To determine which files to include in the
            bundle, this tool traverses the given directories and their
            subdirectories. Since module resolution is based on path names, this
            tool skips directories and files that do not have valid Python
            module names.

            By default, the bundle script executes a __main__ module just like
            \x22python -m package\x22 does. If the bundled modules include exactly one
            such __main__ module, that module is automatically selected.
            Otherwise, please use the -p/--package option to specify the package
            name.

            Use the -b/--bundle-only option to omit the bundle runtime and
            bootstrap code. That way, you can break your application into
            several bundles.

            By default, the bundle script is written to standard out, which may
            break the bundle script since Python's standard out is a character
            instead of a byte stream. Use the -o/--output option to write to a
            file directly.
        \x22\x22\x22),
        formatter_class=width_limited_formatter)
    parser.add_argument(
        '-b', '--bundle-only',
        action='store_true',
        help='emit only bundled files and their manifest,\\nno runtime code')
    parser.add_argument(
        '-o', '--output',
        metavar='FILENAME',
        help='write bundle script to this file')
    parser.add_argument(
        '-p', '--package',
        metavar='PACKAGE',
        help=\x22execute this package's __main__ module\x22)
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
    options = parser.parse_args(namespace=ToolOptions())

    try:
        if options.bundle_only and (options.package or options.repackage):
            raise ValueError('--bundle is incompatible with --package/--repackage')

        BundleMaker(
            options.roots,
            bundle_only=options.bundle_only,
            output=options.output,
            package=options.package,
            repackage=options.repackage,
        ).run()
    except Exception as x:
        if options.verbose:
            traceback.print_exception(x)
        else:
            print(f'Error: {x}')
        sys.exit(1)
""",
# ------------------------------------------------------------------------------
"tsutsumu/maker.py":
b"""from contextlib import nullcontext
from keyword import iskeyword
from operator import attrgetter
import os.path
from pathlib import Path
from typing import NamedTuple, TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from contextlib import AbstractContextManager
    from importlib.abc import Loader
    from importlib.machinery import ModuleSpec
    from io import BufferedWriter
    from typing import Callable


_BANNER = (
    b'#!/usr/bin/env python3\\n'
    b'# -*- coding: utf-8 -*-\\n'
    b'# DO NOT EDIT! This script was automatically generated\\n'
    b'# by Tsutsumu <https://github.io/apparebit/tsutsumu>.\\n'
    b'# Manual edits may just break it.\\n\\n')

# Both bundle starts must have the same length
_BUNDLE_START_IFFY = b'if False: {\\n'
_BUNDLE_START_DICT = b'BUNDLE  = {\\n'
_BUNDLE_STOP = b'}\\n\\n'

_EXTENSIONS = ('.css', '.html', '.js', '.md', '.py', '.rst', '.txt')

_MAIN = \x22\x22\x22
if __name__ == \x22__main__\x22:
    import runpy

    # Don't load modules from current directory
    Bundle.restrict_sys_path()

    # Install the bundle
    bundle = Bundle.install(__file__, MANIFEST)

    # This script does not exist. It never ran!
    {repackage}

    # Run equivalent of \x22python -m {package}\x22
    runpy.run_module(\x22{package}\x22, run_name=\x22__main__\x22, alter_sys=True)
\x22\x22\x22

_SEPARATOR_HEAVY = (
    b'# ======================================='
    b'=======================================\\n')
_SEPARATOR = (
    b'# ---------------------------------------'
    b'---------------------------------------\\n')


class BundledFile(NamedTuple):
    \x22\x22\x22The local path and the platform-independent key for a bundled file.\x22\x22\x22
    path: Path
    key: str


class BundleMaker:
    \x22\x22\x22
    The bundle maker combines the contents of several files into one Python
    script. By default, the script only has a single variable, MANIFEST, which
    is a dictionary mapping (relative) paths to byte offsets and lengths within
    the bundle script. Optionally, it also includes the Bundle class, which
    imports modules from the bundle script, and the corresponding bootstrap
    code. Most methods of the bundle maker are generator methods yielding the
    ines of the bundle script as newline-terminated bytestrings.
    \x22\x22\x22

    def __init__(
        self,
        directories: 'Sequence[str | Path]',
        *,
        bundle_only: bool = False,
        extensions: 'tuple[str, ...]' = _EXTENSIONS,
        output: 'None | str | Path' = None,
        package: 'None | str' = None,
        repackage: bool = False,
    ) -> None:
        self._directories = directories
        self._bundle_only = bundle_only
        self._extensions = extensions
        self._output = output
        self._package = package
        self._repackage = repackage

        self._ranges: 'list[tuple[str, int, int, int]]' = []
        self._repr: 'None | str' = None

    def __repr__(self) -> str:
        if self._repr is None:
            roots = ', '.join(str(directory) for directory in self._directories)
            self._repr = f'<tsutsumu-maker {roots}>'
        return self._repr

    # ----------------------------------------------------------------------------------

    def run(self) -> None:
        files = sorted(self.list_files(), key=attrgetter('key'))
        package = None if self._bundle_only else self.main_package(files)

        # Surprise, nullcontext[None] and BufferedWriter unify thusly:
        context: 'AbstractContextManager[None | BufferedWriter]'
        if self._output is None:
            context = nullcontext()
        else:
            context = open(self._output, mode='wb')

        with context as script:
            BundleMaker.writeall(self.emit_bundle(files), script)
            if not self._bundle_only:
                assert package is not None
                BundleMaker.writeall(self.emit_runtime(package), script)

    # ----------------------------------------------------------------------------------

    def list_files(self) -> 'Iterator[BundledFile]':
        # Since names of directories (and stems of Python files) are module
        # names, traversal MUST NOT resolve symbolic links!
        for directory in self._directories:
            root = Path(directory).absolute()
            pending = list(root.iterdir())
            while pending:
                item = pending.pop().absolute()
                if self.is_text_file(item) and BundleMaker.is_module_name(item.stem):
                    key = str(item.relative_to(root.parent)).replace('\\\\', '/')
                    if not self.is_excluded_key(key):
                        yield BundledFile(item, key)
                elif item.is_dir() and BundleMaker.is_module_name(item.name):
                    pending.extend(item.iterdir())

    def is_text_file(self, item: Path) -> bool:
        return item.is_file() and item.suffix in self._extensions

    @staticmethod
    def is_module_name(name: str) -> bool:
        return name.isidentifier() and not iskeyword(name)

    def is_excluded_key(self, key: str) -> bool:
        return (
            self._repackage
            and key in ('tsutsumu/__init__.py', 'tsutsumu/bundle.py')
        )

    # ----------------------------------------------------------------------------------

    def main_package(self, files: 'list[BundledFile]') -> str:
        if self._package is not None:
            key = f'{self._package.replace(\x22.\x22, \x22/\x22)}/__ main__.py'
            if not any(key == file.key for file in files):
                raise ValueError(
                    f'package {self._package} has no __main__ module in bundle')
            return self._package

        main_modules = [file.key for file in files if file.key.endswith('/__main__.py')]
        module_count = len(main_modules)

        if module_count == 0:
            raise ValueError('bundle has no __main__ module')
        elif module_count == 1:
            self._package = main_modules[0][:-12].replace('/', '.')
            return self._package
        else:
            raise ValueError(
                'bundle has several __main__ modules; '
                'use -p/--package option to select one')

    # ----------------------------------------------------------------------------------

    def emit_bundle(
        self,
        files: 'list[BundledFile]',
    ) -> 'Iterator[bytes]':
        yield from _BANNER.splitlines(keepends=True)
        yield from _BUNDLE_START_IFFY.splitlines(keepends=True)

        for file in files:
            yield from self.emit_text_file(file.path, file.key)

        yield from _BUNDLE_STOP.splitlines(keepends=True)
        yield from self.emit_manifest()

    def emit_text_file(self, path: Path, key: str) -> 'Iterator[bytes]':
        lines = [
            line                      # Split bytestring into lines,
            .decode('iso8859-1')      # convert each byte 1:1 to code point,
            .encode('unicode_escape') # convert to bytes with non-ASCII values escaped,
            .replace(b'\x22', b'\\\\x22')  # and escape double quotes.
            for line in path.read_bytes().splitlines()
        ]

        yield _SEPARATOR

        line_count = len(lines)
        byte_length = sum(len(line) for line in lines) + line_count

        prefix = b'\x22' + key.encode('utf8') + b'\x22:'
        offset = len(_SEPARATOR) + len(prefix) + 1

        if line_count == 0:
            assert byte_length == 0
            self.record_range(key, 0, 0, 0)
        elif line_count == 1:
            self.record_range(key, offset, byte_length + 4, 2)
            yield prefix + b' b\x22' + lines[0] + b'\\\\n\x22,\\n'
        else:
            self.record_range(key, offset, byte_length + 7, 2)
            yield prefix + b'\\n'
            yield b'b\x22\x22\x22' + lines[0] + b'\\n'
            for line in lines[1:]:
                yield line + b'\\n'
            yield b'\x22\x22\x22,\\n'

    def record_range(self, name: str, prefix: int, data: int, suffix: int) -> None:
        self._ranges.append((name, prefix, data, suffix))

    def manifest_entries(self) -> 'Iterator[tuple[str, tuple[int, int]]]':
        offset = len(_BANNER) + len(_BUNDLE_START_IFFY)
        for key, prefix, data, suffix in self._ranges:
            yield key, ((0, 0) if data == 0 else (offset + prefix, data))
            offset += prefix + data + suffix

    def emit_manifest(self) -> 'Iterator[bytes]':
        yield _SEPARATOR_HEAVY
        yield b'\\n'
        yield b'MANIFEST = {\\n'
        for key, (offset, length) in self.manifest_entries():
            yield f'    \x22{key}\x22: ({offset:_d}, {length:_d}),\\n'.encode('utf8')
        yield b'}\\n'

    # ----------------------------------------------------------------------------------

    def emit_runtime(
        self,
        package: str,
    ) -> 'Iterator[bytes]':
        yield b'\\n'
        yield _SEPARATOR_HEAVY
        yield b'\\n'
        yield from self.emit_tsutsumu_bundle()

        yield _SEPARATOR_HEAVY
        if self._repackage:
            repackage = b'bundle.repackage()'
        else:
            repackage = b'del sys.modules[\x22__main__\x22]'

        main = _MAIN.format(package=package, repackage=repackage)
        yield from main.encode('utf8').splitlines(keepends=True)

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
        file: 'None | BufferedWriter' = None,
    ) -> None:
        if file is None:
            for line in lines:
                print(line.decode('utf8'), end='')
        else:
            for line in lines:
                file.write(line)
""",
}

# ==============================================================================

MANIFEST = {
    "tsutsumu/__main__.py": (308, 3_550),
    "tsutsumu/maker.py": (3_962, 10_964),
}

# ==============================================================================

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
    def install(
        cls,
        script: 'str | Path',
        manifest: 'dict[str, tuple[int, int]]',
    ) -> 'Bundle':
        bundle = Bundle(script, manifest)
        for finder in sys.meta_path:
            if bundle == finder:
                raise ImportError(
                    f'bind "{bundle._script}" is already installed')
        sys.meta_path.insert(0, bundle)
        return bundle

    def __init__(
        self,
        script: 'str | Path',
        manifest: 'dict[str, tuple[int, int]]',
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
        self._mod_bundle: 'None | str' = None

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
        offset, length = self._manifest[key]

        # The bundle dictionary does not include empty files
        if length == 0:
            return b''

        with open(self._script, mode='rb') as file:
            file.seek(offset)
            data = file.read(length)
            assert len(data) == length
            # The source code for tsutsumu/bundle.py isn't a bytestring
            return data[1:-1] if key == self._mod_bundle else cast(bytes, eval(data))

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
        if __name__ != '__main__':
            Bundle.warn('attempt to repackage outside bundle script')
            return

        tsutsumu, tsutsumu_bundle = self._recreate_modules()
        self._add_attributes(tsutsumu, tsutsumu_bundle)
        self._add_to_manifest(tsutsumu, tsutsumu_bundle)

        del sys.modules['__main__']

    def _recreate_modules(self) -> 'tuple[ModuleType, ModuleType]':
        pkgdir = os.path.join(self._script, 'tsutsumu')

        for modname, filename, modpath in (
            ('tsutsumu', '__init__.py', pkgdir),
            ('tsutsumu.bundle', 'bundle.py', None),
        ):
            if modname in sys.modules:
                Bundle.warn(f'module {modname} already exists')
                continue

            fullpath = os.path.join(pkgdir, filename)
            spec = ModuleSpec(modname, self, origin=fullpath, is_package=bool(modpath))
            if modpath:
                assert spec.submodule_search_locations is not None
                spec.submodule_search_locations.append(modpath)
            module = importlib.util.module_from_spec(spec)
            setattr(module, '__file__', fullpath)
            sys.modules[modname] = module

        return sys.modules['tsutsumu'], sys.modules['tsutsumu.bundle']

    def _add_attributes(
        self,
        tsutsumu: 'ModuleType',
        tsutsumu_bundle: 'ModuleType',
    ) -> None:
        for obj, attr, old, new in (
            (tsutsumu, 'bundle', None, tsutsumu_bundle),
            (tsutsumu_bundle, 'Bundle', None, Bundle),
            (Bundle, '__module__', '__main__', 'tsutsumu.bundle'),
        ):
            if old is None:
                if hasattr(obj, attr):
                    Bundle.warn(f'{obj} already has attribute {attr}')
                    continue
            else:
                actual: 'None | str' = getattr(obj, attr, None)
                if actual != old:
                    Bundle.warn(f"{obj}.{attr} is {actual} instead of {old}")
                    continue
            setattr(obj, attr, new)

    def _add_to_manifest(
        self,
        tsutsumu: 'ModuleType',
        tsutsumu_bundle: 'ModuleType',
    ) -> None:
        if tsutsumu.__file__ in self._manifest:
            Bundle.warn(f'manifest already includes "{tsutsumu.__file__}"')
        else:
            assert tsutsumu.__file__ is not None
            self._manifest[tsutsumu.__file__] = (0, 0)

        if tsutsumu_bundle.__file__ in self._manifest:
            Bundle.warn(f'manifest already includes "{tsutsumu_bundle.__file__}"')
        else:
            hr = b'# ' + b'=' * 78 + b'\n'
            with open(self._script, mode='rb') as file:
                content = file.read()
            start = content.find(hr)
            start = content.find(hr, start + len(hr)) + len(hr)
            stop = content.find(hr, start)

            assert tsutsumu_bundle.__file__ is not None
            self._mod_bundle = tsutsumu_bundle.__file__
            self._manifest[self._mod_bundle] = (start, stop - start)

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
    bundle = Bundle.install(__file__, MANIFEST)

    # This script does not exist. It never ran!
    b'bundle.repackage()'

    # Run equivalent of "python -m tsutsumu"
    runpy.run_module("tsutsumu", run_name="__main__", alter_sys=True)
