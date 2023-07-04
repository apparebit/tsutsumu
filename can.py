#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# DO NOT EDIT! This script was automatically generated
# by Tsutsumu <https://github.io/apparebit/tsutsumu>.
# Manual edits may just break it.

if False: {
# ------------------------------------------------------------------------------
"spam/__init__.py": b"print('spam/__init__.py')\n",
# ------------------------------------------------------------------------------
"spam/__main__.py":
b"""print('spam/__main__.py')
import spam.bacon

print('also:', __file__)
""",
# ------------------------------------------------------------------------------
"spam/bacon.py": b"print('spam/bacon.py')\n",
# ------------------------------------------------------------------------------
"spam/ham.html":
b"""<!doctype html>
<html lang=en>
<meta charset=utf-8>
<title>Ham?</title>
<style>
* {
    margin: 0;
    padding: 0;
}
html {
    height: 100%;
}
body {
    min-height: 100%;
    display: grid;
    justify-content: center;
    align-content: center;
}
p {
    font-family: system-ui, sans-serif;
    font-size: calc(32vmin + 4vmax);
    font-weight: bolder;
}
</style>
<p>Ham!
""",
}

# ==============================================================================

MANIFEST = {
    "spam/__init__.py": (304, 30),
    "spam/__main__.py": (437, 77),
    "spam/bacon.py": (614, 27),
    "spam/ham.html": (741, 382),
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

    # Run equivalent of "python -m spam"
    runpy.run_module("spam", run_name="__main__", alter_sys=True)
