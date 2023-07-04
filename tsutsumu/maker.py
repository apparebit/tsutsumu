import os.path
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from importlib.abc import Loader
    from types import ModuleType


_BANNER = (
    b'#!/usr/bin/env python3\n'
    b'# -*- coding: utf-8 -*-\n'
    b'# DO NOT EDIT! This script was automatically generated\n'
    b'# by Tsutsumu <https://github.io/apparebit/tsutsumu>.\n'
    b'# Manual edits may just break it.\n\n')

# Both bundle starts must have the same length
_BUNDLE_START_IFFY = b'if False: {\n'
_BUNDLE_START_DICT = b'BUNDLE  = {\n'
_BUNDLE_STOP = b'}\n\n'

_EXTENSIONS = ('.html', '.md', '.py', '.rst', '.txt')

_MAIN = """
if __name__ == "__main__":
    import runpy

    # Don't load modules from current directory
    if sys.path[0] == "" or os.path.samefile(".", sys.path[0]):
        del sys.path[0]

    # Install the bundle
    bundle = Bundle.install(__file__, MANIFEST)

    # This script does not exist. It never ran!
    {repackage}

    # Run equivalent of "python -m {package}"
    runpy.run_module("{package}", run_name="__main__", alter_sys=True)
"""

_SEPARATOR_HEAVY = (
    b'# ======================================='
    b'=======================================\n')
_SEPARATOR = (
    b'# ---------------------------------------'
    b'---------------------------------------\n')


class BundleMaker:
    """
    The bundle maker combines the contents of one or more directories with the
    code for running a package's __main__ module while importing modules and
    resource from the bundle. Its `run()` method yields the bundle script, line
    by line but without line endings. The manifest counts one byte per line
    ending, which should be just `\\n`.
    """

    def __init__(
        self,
        directories: 'Sequence[str | Path]',
        *,
        bundle_only: bool = False,
        extensions: tuple[str, ...] = _EXTENSIONS,
        package: None | str = None,
        repackage: bool = False,
        skip_dot: bool = True,
    ) -> None:
        self._directories = directories
        self._bundle_only = bundle_only
        self._extensions = extensions
        self._package = package
        self._repackage = repackage
        self._skip_dot = skip_dot

        self._ranges: list[tuple[str, int, int, int]] = []
        self._repr: None | str = None

    def __repr__(self) -> str:
        if self._repr is None:
            roots = ', '.join(str(directory) for directory in self._directories)
            self._repr = f'<tsutsumu-maker {roots}>'
        return self._repr

    def write(self, path: str | Path) -> None:
        files = sorted(self.list_files(), key=lambda f: f[1])
        with open(path, mode='wb') as file:
            for line in self.emit_script(files):
                file.write(line)

    def run(self) -> None:
        files = sorted(self.list_files(), key=lambda f: f[1])
        for line in self.emit_script(files):
            print(line.decode('utf8'), end='')

    def list_files(self) -> 'Iterator[tuple[Path, str]]':
        for root in self._directories:
            if isinstance(root, str):
                root = Path(root).resolve()
            if not root.is_dir():
                raise ValueError(f'path "{root}" is not a directory')

            pending = list(root.iterdir())
            while pending:
                item = pending.pop().resolve()
                if self._skip_dot and item.name.startswith('.'):
                    continue
                elif item.is_file() and item.suffix in self._extensions:
                    key = str(item.relative_to(root.parent)).replace('\\', '/')
                    if not self.exclude_file(key):
                        yield item, key
                elif item.is_dir():
                    pending.extend(item.iterdir())

    def exclude_file(self, key: str) -> bool:
        return (
            self._repackage
            and key in ('tsutsumu/__init__.py', 'tsutsumu/bundle.py')
        )

    def emit_script(self, files: list[tuple[Path, str]]) -> 'Iterator[bytes]':
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
        yield b'\n'
        yield from self.emit_mod_bundle()

        yield _SEPARATOR_HEAVY
        if self._repackage:
            repackage = b'bundle.repackage_script(__file__)'
        else:
            repackage = b'del sys.modules["__main__"]'

        main = _MAIN.format(package=package, repackage=repackage)
        yield from main.encode('utf8').splitlines(keepends=True)

    def main_package(self, files: list[tuple[Path, str]]) -> str:
        if self._package is not None:
            key = f'{self._package.replace(".", "/")}/__ main__.py'
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
            .replace(b'"', b'\\x22')  # and escape double quotes.
            for line in path.read_bytes().splitlines()
        ]

        yield _SEPARATOR

        line_count = len(lines)
        byte_length = sum(len(line) for line in lines) + line_count

        prefix = b'"' + key.encode('utf8') + b'":'
        offset = len(_SEPARATOR) + len(prefix) + 1

        if line_count == 0:
            assert byte_length == 0
            self.record_range(key, 0, 0, 0)
        elif line_count == 1:
            self.record_range(key, offset, byte_length + 4, 2)
            yield prefix + b' b"' + lines[0] + b'\\n",\n'
        else:
            self.record_range(key, offset, byte_length + 7, 2)
            yield prefix + b'\n'
            yield b'b"""' + lines[0] + b'\n'
            for line in lines[1:]:
                yield line + b'\n'
            yield b'""",\n'

    def record_range(self, name: str, prefix: int, data: int, suffix: int) -> None:
        self._ranges.append((name, prefix, data, suffix))

    def manifest_entries(self) -> 'Iterator[tuple[str, tuple[int, int]]]':
        offset = len(_BANNER) + len(_BUNDLE_START_IFFY)
        for key, prefix, data, suffix in self._ranges:
            yield key, (offset + prefix, data)
            offset += prefix + data + suffix

    def emit_manifest(self) -> 'Iterator[bytes]':
        yield _SEPARATOR_HEAVY
        yield b'\n'
        yield b'MANIFEST = {\n'
        for key, (offset, length) in self.manifest_entries():
            yield f'    "{key}": ({offset:_d}, {length:_d}),\n'.encode('utf8')
        yield b'}\n'
        yield b'\n'

    def emit_mod_bundle(self) -> 'Iterator[bytes]':
        # Why would anyone ever load modules from place other than the file system?
        import tsutsumu
        loader = self.get_loader(tsutsumu)
        get_data = getattr(loader, 'get_data', None)
        if get_data is not None:
            assert len(tsutsumu.__path__) == 1, 'tsutsumu is a regular package'
            mod_bundle = get_data(os.path.join(tsutsumu.__path__[0], 'bundle.py'))
        else:
            import warnings
            if loader is None:
                warnings.warn("tsutsumu's module has no loader")
            else:
                warnings.warn(f"tsutsumu's loader {loader} has no get_data()")

            try:
                mod_bundle_path = Path(__file__).parent / 'bundle.py'
            except AttributeError:
                raise ValueError(f"unable to get tsutsumu.bundle's source code")
            else:
                with open(mod_bundle_path, mode='rb') as file:
                    mod_bundle = file.read()

        yield from mod_bundle.splitlines(keepends=True)
        yield b'\n'

    def get_loader(self, module: 'ModuleType') -> 'None | Loader':
        spec = getattr(module, '__spec__', None)
        loader = getattr(spec, 'loader', None)
        if loader is not None:
            return loader

        # Module.__loader__ is deprecated, to be removed in Python 3.14. Meanwhile...
        return getattr(module, '__loader__', None)
