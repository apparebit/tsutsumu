"""Support for package metadata in form of .dist-info files."""

from collections.abc import Iterable
from dataclasses import dataclass, field, KW_ONLY
import datetime
import importlib
import importlib.metadata as md
import itertools
from pathlib import Path
import tomllib
from typing import cast, Literal, overload, TypeVar

from . import requirement


_T = TypeVar('_T')

def today_as_version() -> str:
    return '.'.join(str(part) for part in datetime.date.today().isocalendar())


@dataclass(frozen=True, slots=True)
class DistInfo:
    name: str
    version: None | str = None
    _: KW_ONLY
    effective_version: str = field(init=False)
    summary: None | str = None
    homepage: None | str = None
    required_python: None | str = None
    required_packages: None | tuple[str, ...] = None
    provenance: None | str = None

    @classmethod
    def from_pyproject(cls, path: str | Path) -> 'DistInfo':
        with open(path, mode='rb') as file:
            metadata = cast(dict[str, object], tomllib.load(file))
        if not isinstance(project_metadata := metadata.get('project'), dict):
            raise ValueError(f'"{path}" lacks "project" section')

        @overload
        def property(key: str, typ: type[_T], is_optional: Literal[False]) -> _T:
            ...
        @overload
        def property(key: str, typ: type[_T], is_optional: Literal[True]) -> None | _T:
            ...
        def property(key: str, typ: type[_T], is_optional: bool) -> None | _T:
            value = project_metadata.get(key)
            if value is None and is_optional:
                return value
            elif isinstance(value, typ):
                return value
            elif value is None:
                raise ValueError(f'"{path}" has no "{key}" entry in "project" section')
            else:
                raise ValueError(f'"{path}" has non-{typ.__name__} "{key}" entry')

        name = requirement.canonicalize(property('name', str, False))
        version = property('version', str, True)
        summary = property('description', str, True)
        required_python = property('requires-python', str, True)

        required_packages: None | tuple[str, ...] = None
        raw_requirements = property('dependencies', list, True)
        if raw_requirements:
            if any(not isinstance(p, str) for p in raw_requirements):
                raise ValueError(f'"{path}" has non-str item in "dependencies"')
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
                raise ValueError(f'"{path}" has non-str value in "urls"')

        if version is None:
            # pyproject.toml may omit version if it is dynamic.
            if 'version' in (property('dynamic', list, True) or ()):
                package = importlib.import_module(name)
                version = getattr(package, '__version__')
                assert isinstance(version, str) # type: ignore[misc]  # due to Any
            else:
                raise ValueError(f'"{path}" has no "version" in "project" section')

        return cls(
            name,
            version=version,
            summary=summary,
            homepage=homepage,
            required_python=required_python,
            required_packages=required_packages,
            provenance=str(Path(path).absolute()),
        )

    @classmethod
    def from_installation(cls, name: str, version: None | str = None) -> 'DistInfo':
        name = requirement.canonicalize(name)

        if version is None:
            try:
                distribution = md.distribution(name)
            except ModuleNotFoundError:
                return cls(name)

        version = distribution.version
        summary = distribution.metadata['Summary']
        homepage = distribution.metadata['Home-page']
        required_python = distribution.metadata['Requires-Python']

        required_packages = None
        raw_requirements = distribution.requires
        if raw_requirements is not None:
            required_packages = tuple(raw_requirements)

        provenance = None
        if hasattr(distribution, '_path'):
            provenance = str(cast(Path, getattr(distribution, '_path')))

        return cls(
            name,
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
        for requirement in self.required_packages or ():
            lines.append('Requires-Dist: ' + requirement)

        return metadata_path, '\n'.join(lines) + '\n'

    def record_path_content(self, files: Iterable[str]) -> tuple[str, str]:
        prefix = f'{self.name}-{self.effective_version}.dist-info/'
        record_path = prefix + 'RECORD'
        all_files = itertools.chain((prefix + 'METADATA', record_path), files)
        content = ',,\n'.join(f'"{f}"' if ',' in f else f for f in all_files) + ',,\n'
        return record_path, content