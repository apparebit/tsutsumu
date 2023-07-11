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
    HRULE = b'# ' + b'=' * 78 + b'\n'

    @staticmethod
    def create_module_spec(
        name: str, loader: 'Loader', path: str, pkgdir: 'None | str'
    ) -> ModuleSpec:
        spec = ModuleSpec(name, loader, origin=path, is_package=bool(pkgdir))
        if pkgdir:
            assert spec.submodule_search_locations is not None
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
        index3 = bundle.rfind(Toolbox.HRULE)
        index2 = bundle.rfind(Toolbox.HRULE, 0, index3 - 1)
        index1 = bundle.rfind(Toolbox.HRULE, 0, index2 - 1)
        return index1, index2, index3

    @staticmethod
    def load_meta_data(path: 'str | Path') -> 'tuple[str, ManifestType]':
        with open(path, mode='rb') as file:
            content = file.read()

        start, stop, _ = Toolbox.find_section_offsets(content)
        bindings: 'dict[str, object]' = {}
        exec(content[start + len(Toolbox.HRULE) : stop], bindings)
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
            assert len(data) == length
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
        sys.meta_path.remove(self)
