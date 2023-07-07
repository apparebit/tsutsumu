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
            # If the offset's sign is negative, the module is repackaged and its
            # source is not embedded in a bytestring literal.
            file.seek(offset if offset >= 0 else -offset)
            data = file.read(length)
            assert len(data) == length
            return data if offset < 0 else cast(bytes, eval(data))

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
        self._manifest[tsutsumu.__file__] = (-init_start, init_length)

        assert tsutsumu_bundle.__file__ is not None
        self._manifest[tsutsumu_bundle.__file__] = (-bundle_start, bundle_length)

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
