#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# DO NOT EDIT! This script was automatically generated
# by Tsutsumu <https://github.io/apparebit/tsutsumu>.
# Manual edits may just break it.

if False: {
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
"tsutsumu/__main__.py":
b"""from argparse import ArgumentParser, HelpFormatter
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
        return HelpFormatter(prog, width=width)

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
            Combine Python modules into a single, self-contained script that
            executes a __main__ module just like \\\x22python -m package\\\x22 does. If
            the bundled modules include only one __main__ module, that module is
            automatically selected. If they include more than one __main__
            module, please use the -p/--package option to specify the package
            name.

            This tool writes to standard out by default. Use the -o/--output
            option to name a file instead. To omit bundle runtime and bootstrap
            code, use the -b/--bundle-only option. That way, you can break your
            application into several bundles.
        \x22\x22\x22),
        formatter_class=width_limited_formatter)
    parser.add_argument(
        '-b', '--bundle-only',
        action='store_true',
        help='emit only bundled files and their manifest, no runtime code')
    parser.add_argument(
        '-o', '--output',
        metavar='FILENAME',
        help='write the bundle script to the file')
    parser.add_argument(
        '-p', '--package',
        metavar='PACKAGE',
        help='on startup, run the __main__ module for this package')
    parser.add_argument(
        '-r', '--repackage',
        action='store_true',
        help='repackage the Bundle class in a fresh \x22tsutsumu.bundle\x22 module')
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='enable verbose output')
    parser.add_argument(
        'roots',
        metavar='DIRECTORY', nargs='+',
        help='include all Python modules reachable from the directory')
    options = parser.parse_args(namespace=ToolOptions())

    try:
        if options.bundle_only and (options.package or options.repackage):
            raise ValueError('--bundle is incompatible with --package/--repackage')

        maker = BundleMaker(
            options.roots,
            bundle_only=options.bundle_only,
            package=options.package,
            repackage=options.repackage
        )
        if options.output is None:
            maker.run()
        else:
            maker.write(options.output)
    except Exception as x:
        if options.verbose:
            traceback.print_exception(x)
        else:
            print(f'Error: {x}')
        sys.exit(1)
""",
# ------------------------------------------------------------------------------
"tsutsumu/bundle.py":
b"""from importlib.abc import Loader
from importlib.machinery import ModuleSpec
import importlib.util
import os
import sys
from typing import cast, TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from types import CodeType, ModuleType


class Bundle(Loader):
    \x22\x22\x22
    Representation of a bundle. Each instance serves as meta path finder and
    module loader for a particular bundle script.
    \x22\x22\x22

    @classmethod
    def install(
        cls,
        script: str,
        manifest: 'dict[str, tuple[int, int]]',
    ) -> 'Bundle':
        bundle = Bundle(script, manifest)
        for finder in sys.meta_path:
            if bundle == finder:
                raise ImportError(
                    f'bind \x22{bundle._script}\x22 is already installed')
        sys.meta_path.insert(0, bundle)
        return bundle

    def __init__(
        self,
        script: str,
        manifest: 'dict[str, tuple[int, int]]',
    ) -> None:
        if len(script) == 0:
            raise ValueError('path to bundle script is empty')
        if script.endswith('/') or script.endswith(os.sep):
            raise ValueError(
                'path to bundle script \x22{script}\x22 ends in path separator')

        def intern(path: str) -> str:
            local_path = path.replace('/', os.sep)
            if os.path.isabs(local_path):
                raise ValueError(f'manifest path \x22{path}\x22 is absolute')
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
            raise ImportError(f'unknown path \x22{key}\x22')
        offset, length = self._manifest[key]

        # Entirely empty files aren't included in the file dictionary.
        if offset == 0 and length == 0:
            return b''

        with open(self._script, mode='rb') as file:
            file.seek(offset)
            data = file.read(length)
            assert len(data) == length
            # The source code for tsutsumu/bundle.py isn't a bytestring.
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

    def get_data(self, path: str) -> bytes:
        return self[path]

    def get_filename(self, fullname: str) -> str:
        return self._locate(fullname)[0]

    def repackage_script(self, script: str) -> None:
        if __name__ != '__main__':
            Bundle.warn('attempt to repackage outside bundle script')
            return

        tsutsumu, tsutsumu_bundle = self.recreate_modules(script)
        self.add_attributes(tsutsumu, tsutsumu_bundle)
        self.add_to_manifest(tsutsumu, tsutsumu_bundle)

        del sys.modules['__main__']

    @staticmethod
    def warn(message: str) -> None:
        import warnings
        warnings.warn(message)

    def recreate_modules(self, path: str) -> 'tuple[ModuleType, ModuleType]':
        pkgdir = os.path.join(path, 'tsutsumu')

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

    def add_attributes(
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
                    Bundle.warn(f\x22{obj}.{attr} is {actual} instead of {old}\x22)
                    continue
            setattr(obj, attr, new)

    def add_to_manifest(
        self,
        tsutsumu: 'ModuleType',
        tsutsumu_bundle: 'ModuleType',
    ) -> None:
        if tsutsumu.__file__ in self._manifest:
            Bundle.warn(f'manifest already includes \x22{tsutsumu.__file__}\x22')
        else:
            assert tsutsumu.__file__ is not None
            self._manifest[tsutsumu.__file__] = (0, 0)

        if tsutsumu_bundle.__file__ in self._manifest:
            Bundle.warn(f'manifest already includes \x22{tsutsumu_bundle.__file__}\x22')
        else:
            hr = b'# ' + b'=' * 78 + b'\\n'
            with open(self._script, mode='rb') as file:
                content = file.read()
            start = content.find(hr)
            start = content.find(hr, start + len(hr)) + len(hr)
            stop = content.find(hr, start)

            assert tsutsumu_bundle.__file__ is not None
            self._mod_bundle = tsutsumu_bundle.__file__
            self._manifest[self._mod_bundle] = (start, stop - start)
""",
# ------------------------------------------------------------------------------
"tsutsumu/maker.py":
b"""import os.path
from pathlib import Path
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from importlib.abc import Loader
    from importlib.machinery import ModuleSpec
    from types import ModuleType


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
    if sys.path[0] == \x22\x22 or os.path.samefile(\x22.\x22, sys.path[0]):
        del sys.path[0]

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


class BundleMaker:
    \x22\x22\x22
    The bundle maker combines the contents of one or more directories with the
    code for running a package's __main__ module while importing modules and
    resource from the bundle. Its `run()` method yields the bundle script, line
    by line but without line endings. The manifest counts one byte per line
    ending, which should be just `\\\\n`.
    \x22\x22\x22

    def __init__(
        self,
        directories: 'Sequence[str | Path]',
        *,
        bundle_only: bool = False,
        extensions: 'tuple[str, ...]' = _EXTENSIONS,
        package: 'None | str' = None,
        repackage: bool = False,
        skip_dot: bool = True,
    ) -> None:
        self._directories = directories
        self._bundle_only = bundle_only
        self._extensions = extensions
        self._package = package
        self._repackage = repackage
        self._skip_dot = skip_dot

        self._ranges: 'list[tuple[str, int, int, int]]' = []
        self._repr: 'None | str' = None

    def __repr__(self) -> str:
        if self._repr is None:
            roots = ', '.join(str(directory) for directory in self._directories)
            self._repr = f'<tsutsumu-maker {roots}>'
        return self._repr

    def write(self, path: 'str | Path') -> None:
        files = sorted(self.list_files(), key=BundleMaker.file_ordering)
        with open(path, mode='wb') as file:
            for line in self.emit_script(files):
                file.write(line)

    def run(self) -> None:
        files = sorted(self.list_files(), key=BundleMaker.file_ordering)
        for line in self.emit_script(files):
            print(line.decode('utf8'), end='')

    @staticmethod
    def file_ordering(file: 'tuple[Path, str]') -> str:
        return file[1]

    def list_files(self) -> 'Iterator[tuple[Path, str]]':
        for root in self._directories:
            if isinstance(root, str):
                root = Path(root).resolve()
            if not root.is_dir():
                raise ValueError(f'path \x22{root}\x22 is not a directory')

            pending = list(root.iterdir())
            while pending:
                item = pending.pop().resolve()
                if self._skip_dot and item.name.startswith('.'):
                    continue
                elif item.is_file() and item.suffix in self._extensions:
                    key = str(item.relative_to(root.parent)).replace('\\\\', '/')
                    if not self.exclude_file(key):
                        yield item, key
                elif item.is_dir():
                    pending.extend(item.iterdir())

    def exclude_file(self, key: str) -> bool:
        return (
            self._repackage
            and key in ('tsutsumu/__init__.py', 'tsutsumu/bundle.py')
        )

    def emit_script(self, files: 'list[tuple[Path, str]]') -> 'Iterator[bytes]':
        package = self.main_package(files)

        yield from _BANNER.splitlines(keepends=True)
        yield from _BUNDLE_START_IFFY.splitlines(keepends=True)

        for path, key in files:
            yield from self.emit_text_file(path, key)

        yield from _BUNDLE_STOP.splitlines(keepends=True)
        yield from self.emit_manifest()

        if self._bundle_only:
            return

        yield _SEPARATOR_HEAVY
        yield b'\\n'
        yield from self.emit_mod_bundle()

        yield _SEPARATOR_HEAVY
        if self._repackage:
            repackage = b'bundle.repackage_script(__file__)'
        else:
            repackage = b'del sys.modules[\x22__main__\x22]'

        main = _MAIN.format(package=package, repackage=repackage)
        yield from main.encode('utf8').splitlines(keepends=True)

    def main_package(self, files: 'list[tuple[Path, str]]') -> str:
        if self._package is not None:
            key = f'{self._package.replace(\x22.\x22, \x22/\x22)}/__ main__.py'
            if not any(key == file[1] for file in files):
                raise ValueError(
                    f'package {self._package} has no __main__ module in bundle')
            return self._package

        main_modules = [file[1] for file in files if file[1].endswith('/__main__.py')]
        module_count = len(main_modules)

        if module_count == 0:
            raise ValueError('bundle has no __main__ module')
        elif module_count == 1:
            self._package = main_modules[0][:-12].replace('/', '.')
            return self._package
        else:
            raise ValueError('bundle has several __main__ modules')

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
            yield key, (offset + prefix, data)
            offset += prefix + data + suffix

    def emit_manifest(self) -> 'Iterator[bytes]':
        yield _SEPARATOR_HEAVY
        yield b'\\n'
        yield b'MANIFEST = {\\n'
        for key, (offset, length) in self.manifest_entries():
            yield f'    \x22{key}\x22: ({offset:_d}, {length:_d}),\\n'.encode('utf8')
        yield b'}\\n'
        yield b'\\n'

    def emit_mod_bundle(self) -> 'Iterator[bytes]':
        # Why would anyone ever load modules from place other than the file system?
        import tsutsumu
        loader = self.get_loader(tsutsumu)
        get_data: 'None | Callable[[str], bytes]' = getattr(loader, 'get_data', None)
        if get_data is not None:
            assert len(tsutsumu.__path__) == 1, 'tsutsumu is a regular package'
            mod_bundle = get_data(os.path.join(tsutsumu.__path__[0], 'bundle.py'))
        else:
            import warnings
            if loader is None:
                warnings.warn(\x22tsutsumu's module has no loader\x22)
            else:
                warnings.warn(f\x22tsutsumu's loader {loader} has no get_data()\x22)

            try:
                mod_bundle_path = Path(__file__).parent / 'bundle.py'
            except AttributeError:
                raise ValueError(f\x22unable to get tsutsumu.bundle's source code\x22)
            else:
                with open(mod_bundle_path, mode='rb') as file:
                    mod_bundle = file.read()

        yield from mod_bundle.splitlines(keepends=True)
        yield b'\\n'

    def get_loader(self, module: 'ModuleType') -> 'None | Loader':
        spec: 'None | ModuleSpec' = getattr(module, '__spec__', None)
        loader: 'None | Loader' = getattr(spec, 'loader', None)
        if loader is not None:
            return loader

        # Module.__loader__ is deprecated, to be removed in Python 3.14. Meanwhile...
        loader2: 'None | Loader' = getattr(module, '__loader__', None)
        return loader2
""",
}

# ==============================================================================

MANIFEST = {
    "tsutsumu/__init__.py": (203, 0),
    "tsutsumu/__main__.py": (308, 3_118),
    "tsutsumu/bundle.py": (3_531, 8_313),
    "tsutsumu/maker.py": (11_948, 9_608),
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
    from types import CodeType, ModuleType


class Bundle(Loader):
    """
    Representation of a bundle. Each instance serves as meta path finder and
    module loader for a particular bundle script.
    """

    @classmethod
    def install(
        cls,
        script: str,
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
        script: str,
        manifest: 'dict[str, tuple[int, int]]',
    ) -> None:
        if len(script) == 0:
            raise ValueError('path to bundle script is empty')
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

        # Entirely empty files aren't included in the file dictionary.
        if offset == 0 and length == 0:
            return b''

        with open(self._script, mode='rb') as file:
            file.seek(offset)
            data = file.read(length)
            assert len(data) == length
            # The source code for tsutsumu/bundle.py isn't a bytestring.
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

    def get_data(self, path: str) -> bytes:
        return self[path]

    def get_filename(self, fullname: str) -> str:
        return self._locate(fullname)[0]

    def repackage_script(self, script: str) -> None:
        if __name__ != '__main__':
            Bundle.warn('attempt to repackage outside bundle script')
            return

        tsutsumu, tsutsumu_bundle = self.recreate_modules(script)
        self.add_attributes(tsutsumu, tsutsumu_bundle)
        self.add_to_manifest(tsutsumu, tsutsumu_bundle)

        del sys.modules['__main__']

    @staticmethod
    def warn(message: str) -> None:
        import warnings
        warnings.warn(message)

    def recreate_modules(self, path: str) -> 'tuple[ModuleType, ModuleType]':
        pkgdir = os.path.join(path, 'tsutsumu')

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

    def add_attributes(
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

    def add_to_manifest(
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

# ==============================================================================

if __name__ == "__main__":
    import runpy

    # Don't load modules from current directory
    if sys.path[0] == "" or os.path.samefile(".", sys.path[0]):
        del sys.path[0]

    # Install the bundle
    bundle = Bundle.install(__file__, MANIFEST)

    # This script does not exist. It never ran!
    b'del sys.modules["__main__"]'

    # Run equivalent of "python -m tsutsumu"
    runpy.run_module("tsutsumu", run_name="__main__", alter_sys=True)
