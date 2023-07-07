from contextlib import nullcontext
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
    b'#!/usr/bin/env python3\n'
    b'# -*- coding: utf-8 -*-\n'
    b'# DO NOT EDIT! This script was automatically generated\n'
    b'# by Tsutsumu <https://github.com/apparebit/tsutsumu>.\n'
    b'# Manual edits may just break it.\n\n')

# Both bundle starts must have the same length
_BUNDLE_START_IFFY = b'if False: {\n'
_BUNDLE_START_DICT = b'BUNDLE  = {\n'
_BUNDLE_STOP = b'}\n\n'

_EXTENSIONS = ('.css', '.html', '.js', '.md', '.py', '.rst', '.txt')

_MAIN = """
if __name__ == "__main__":
    import runpy

    # Don't load modules from current directory
    Bundle.restrict_sys_path()

    # Install the bundle
    bundle = Bundle.install(__file__, __manifest__, __version__)

    # This script does not exist. It never ran!
    {repackage}

    # Run equivalent of "python -m {main}"
    runpy.run_module("{main}", run_name="__main__", alter_sys=True)
"""

_SEPARATOR_HEAVY = (
    b'# ======================================='
    b'=======================================\n')
_SEPARATOR = (
    b'# ---------------------------------------'
    b'---------------------------------------\n')


class BundledFile(NamedTuple):
    """The local path and the platform-independent key for a bundled file."""
    path: Path
    key: str


class BundleMaker:
    """
    Class to create Python bundles, i.e., Python scripts that contains the source
    code for several modules and supporting files.
    """

    def __init__(
        self,
        directories: 'Sequence[str | Path]',
        *,
        bundle_only: bool = False,
        extensions: 'tuple[str, ...]' = _EXTENSIONS,
        main: 'None | str' = None,
        output: 'None | str | Path' = None,
        repackage: bool = False,
    ) -> None:
        self._directories = directories
        self._bundle_only = bundle_only
        self._extensions = extensions
        self._main = main
        self._output = output
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
                if self.is_text_file(item) and BundleMaker.is_module_name(item.stem):
                    key = str(item.relative_to(root.parent)).replace('\\', '/')
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
            yield from self.emit_text_file(file.path, file.key)

        yield from _BUNDLE_STOP.splitlines(keepends=True)
        yield from self.emit_manifest()
        yield from self.emit_version()

    def emit_text_file(self, path: Path, key: str) -> 'Iterator[bytes]':
        lines = [
            line                      # Split bytestring into lines,
            .decode('iso8859-1')      # convert each byte 1:1 to code point,
            .encode('unicode_escape') # convert to bytes with non-ASCII values escaped,
            .replace(b'"', b'\\x22')  # and escape double quotes.
            for line in path.read_bytes().splitlines()
        ]

        line_count = len(lines)
        byte_length = sum(len(line) for line in lines) + line_count

        prefix = b'"' + key.encode('utf8') + b'":'
        offset = len(_SEPARATOR) + len(prefix) + 1

        if line_count == 0:
            assert byte_length == 0
            self.record_range(key, 0, 0, 0)
        elif line_count == 1:
            self.record_range(key, offset, byte_length + 4, 2)
            yield _SEPARATOR
            yield prefix + b' b"' + lines[0] + b'\\n",\n'
        else:
            self.record_range(key, offset, byte_length + 7, 2)
            yield _SEPARATOR
            yield prefix + b'\n'
            yield b'b"""' + lines[0] + b'\n'
            for line in lines[1:]:
                yield line + b'\n'
            yield b'""",\n'

    def record_range(self, name: str, prefix: int, data: int, suffix: int) -> None:
        self._ranges.append((name, prefix, data, suffix))

    def list_manifest_entries(self) -> 'Iterator[tuple[str, tuple[int, int]]]':
        offset = len(_BANNER) + len(_BUNDLE_START_IFFY)
        for key, prefix, data, suffix in self._ranges:
            yield key, ((0, 0) if data == 0 else (offset + prefix, data))
            offset += prefix + data + suffix

    def emit_manifest(self) -> 'Iterator[bytes]':
        yield _SEPARATOR_HEAVY
        yield b'\n'
        yield b'__manifest__ = {\n'
        for key, (offset, length) in self.list_manifest_entries():
            yield f'    "{key}": ({offset:_d}, {length:_d}),\n'.encode('utf8')
        yield b'}\n'

    def emit_version(self) -> 'Iterator[bytes]':
        yield b'\n'
        yield f"__version__ = '{__version__}'\n".encode('ascii')

    # ----------------------------------------------------------------------------------

    def emit_runtime(
        self,
        main: str,
    ) -> 'Iterator[bytes]':
        yield b'\n'
        yield _SEPARATOR_HEAVY
        yield b'\n'
        yield from self.emit_tsutsumu_bundle()

        yield _SEPARATOR_HEAVY
        if self._repackage:
            repackage = "bundle.repackage()"
        else:
            repackage = "del sys.modules['__main__']"

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
                warnings.warn("tsutsumu has no module loader")
            else:
                warnings.warn(f"tsutsumu's loader ({type(loader)}) has no get_data()")

            try:
                mod_bundle_path = Path(__file__).parent / 'bundle.py'
            except AttributeError:
                raise ValueError(f"unable to get tsutsumu.bundle's source code")
            else:
                with open(mod_bundle_path, mode='rb') as file:
                    mod_bundle = file.read()

        yield from mod_bundle.splitlines(keepends=True)
        yield b'\n'

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
