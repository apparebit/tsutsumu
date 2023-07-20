"""Support for package metadata in form of .dist-info files."""

from collections import deque
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, KW_ONLY
import importlib
import importlib.metadata as md
import itertools
from pathlib import Path
import tomllib
from typing import cast, Literal, overload, TypeVar

from packaging.markers import Marker as PackagingMarker
from packaging.requirements import Requirement as PackagingRequirement

from .name import canonicalize, today_as_version
from .requirement import Requirement


# class Person(NamedTuple):
#     name: str
#     email: None | str
#     url: None | str


# class DistInfoData(NamedTuple):
#     name: str
#     version: None | str = None
#     summary: None | str = None
#     homepage: None | str = None
#     download_url: None | str = None
#     project_url: None | str = None
#     keywords: tuple[str, ...] = ()
#     classifiers: tuple[str, ...] = ()
#     platforms: tuple[str, ...] = ()
#     author: None | Person = None
#     maintainer: None | Person = None
#     license: None | str = None
#     required_python: None | str = None
#     required_dists: tuple[str, ...] = ()
#     required_resources: tuple[str, ...] = ()
#     provided_dists: tuple[str, ...] = ()
#     provided_extras: tuple[str, ...] = ()
#     obsoleted_dists: tuple[str,...] = ()
#     provenance: tuple[str, ...] = ()

__all__ = ("collect_dependencies", "DistInfo")


def collect_dependencies(
    pkgname: str, *pkgextras: str
) -> "tuple[dict[str, DistInfo], dict[str, PackagingMarker]]":
    """
    Determine the transitive closure of package dependencies via a breadth-first
    search of locally installed packages. This function not only returns a
    dictionary of resolved dependencies, but also one of dependencies that were
    never installed in the first place due to their marker evaluating to false.
    """

    pyproject_path = Path.cwd() / "pyproject.toml"
    if pyproject_path.exists():
        distribution = DistInfo.from_pyproject(pyproject_path, pkgextras)
    else:
        distribution = DistInfo.from_installation(pkgname, pkgextras)

    # Breadth-first search requires a queue
    pending: deque[tuple[str, tuple[str, ...], str]] = deque(
        (pkgname, pkgextras, req) for req in distribution.required_packages
    )
    distributions = {pkgname: distribution}
    not_installed: dict[str, PackagingMarker] = {}

    while len(pending) > 0:
        # Resolve the requirement to a distribution. We first use Tsutsumu's
        # lossy parser to determine if the requirement is scoped to an extra.
        # Next, we also evaluate the marker with packaging's precise machinery,
        # since the package may not be installed at all due to a version
        # constraint on the operating system or Python runtime.

        pkgname, pkgextras, requirement = pending.pop()
        dependency, dep_extras, _, only_for_extra = Requirement.from_string(requirement)

        req = PackagingRequirement(requirement)
        if req.marker is not None:
            env = {} if only_for_extra is None else {"extra": only_for_extra}
            if not req.marker.evaluate(env):
                not_installed[pkgname] = req.marker
                continue  # since dependency hasn't been installed
        if only_for_extra is not None and only_for_extra not in pkgextras:
            continue  # since requirement is for unused package
        if dependency in distributions:
            continue  # since dependency has already been processed

        dist = DistInfo.from_installation(dependency, dep_extras)
        distributions[dependency] = dist
        pending.extend((dist.name, dist.extras, req) for req in dist.required_packages)

    return distributions, not_installed


T = TypeVar("T")


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
    def from_pyproject(
        cls, path: str | Path, extras: tuple[str, ...] = ()
    ) -> "DistInfo":
        with open(path, mode="rb") as file:
            metadata = cast(dict[str, object], tomllib.load(file))
        if not isinstance(project_metadata := metadata.get("project"), dict):
            raise ValueError(f'"{path}" lacks "project" section')

        @overload
        def property(key: str, typ: type[list[str]], is_optional: bool) -> list[str]:
            ...

        @overload
        def property(key: str, typ: type[T], is_optional: Literal[False]) -> T:
            ...

        @overload
        def property(key: str, typ: type[T], is_optional: Literal[True]) -> None | T:
            ...

        def property(key: str, typ: type[T], is_optional: bool) -> None | T:
            value = project_metadata.get(key)
            if isinstance(value, typ):
                return value
            if value is None:
                if typ is list:
                    return cast(T, [])
                if is_optional:
                    return None
            if value is None:
                raise ValueError(f'"{path}" has no "{key}" entry in "project" section')
            else:
                raise ValueError(f'"{path}" has non-{typ.__name__} "{key}" entry')

        name = canonicalize(property("name", str, False))
        version = property("version", str, True)
        summary = property("description", str, True)
        required_python = property("requires-python", str, True)

        raw_requirements = property("dependencies", list, True)
        if any(not isinstance(p, str) for p in raw_requirements):
            raise ValueError(f'"{path}" has non-str item in "dependencies"')
        optional_dependencies = cast(
            dict[str, list[str]], property("optional-dependencies", dict, True)
        ) or cast(dict[str, list[str]], {})
        for extra in extras:
            if extra in optional_dependencies:
                for dependency in optional_dependencies[extra]:
                    raw_requirements.append(f'{dependency} ; extra == "{extra}"')
        required_packages = tuple(raw_requirements)

        homepage: None | str = None
        urls = property("urls", dict, True)
        if urls is not None:
            for location in ("homepage", "repository", "documentation"):
                if location not in urls:
                    continue
                url = urls[location]
                if isinstance(url, str):
                    homepage = url
                    break
                raise ValueError(f'"{path}" has non-str value in "urls"')

        if version is None:
            # pyproject.toml may omit version if it is dynamic.
            if "version" in property("dynamic", list, True):
                package = importlib.import_module(name)
                version = getattr(package, "__version__")
                assert isinstance(version, str)
            else:
                raise ValueError(f'"{path}" has no "version" in "project" section')

        return cls(
            name,
            extras,
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
    ) -> "DistInfo":
        name = canonicalize(name)

        if version is None:
            try:
                distribution = md.distribution(name)
            except ModuleNotFoundError:
                return cls(name, tuple(extras))

        # Distribution's implementation reads and parses the metadata file on
        # every access to its metadata property. Since its other properties
        # internally use the metadata property as well, it's really easy to read
        # and parse the same file over and over again.
        metadata = distribution.metadata

        version = metadata["Version"]
        summary = metadata["Summary"]
        homepage = metadata["Home-page"]
        required_python = metadata["Requires-Python"]
        required_packages = tuple(
            cast(
                list[str],
                metadata.get_all("Requires-Dist", failobj=cast(list[str], [])),
            )
        )
        # provided_extras = metadata.get_all('Provides-Extra')
        # provided_distributions = metadata.get_all('Provides-Dist')

        provenance = None
        if hasattr(distribution, "_path"):
            provenance = str(cast(Path, getattr(distribution, "_path")).absolute())

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
        object.__setattr__(self, "effective_version", version)

    def __hash__(self) -> int:
        return hash(self.name) + hash(self.version)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DistInfo):
            return NotImplemented
        return self.name == other.name and self.version == other.version

    def __repr__(self) -> str:
        version = "?.?" if self.version is None else self.version
        return f"<DistInfo {self.name} {version}>"

    def metadata_path_content(self) -> tuple[str, str]:
        metadata_path = f"{self.name}-{self.effective_version}.dist-info/METADATA"
        lines = [
            "Metadata-Version: 2.1",
            "Name: " + self.name,
            "Version: " + self.effective_version,
        ]

        if self.summary:
            lines.append("Summary: " + self.summary)
        if self.homepage:
            lines.append("Home-page: " + self.homepage)
        if self.required_python:
            lines.append("Requires-Python: " + self.required_python)
        for requirement in self.required_packages:
            lines.append("Requires-Dist: " + requirement)

        return metadata_path, "\n".join(lines) + "\n"

    def record_path_content(self, files: Iterable[str]) -> tuple[str, str]:
        prefix = f"{self.name}-{self.effective_version}.dist-info/"
        record_path = prefix + "RECORD"
        all_files = itertools.chain((prefix + "METADATA", record_path), files)
        content = ",,\n".join(f'"{f}"' if "," in f else f for f in all_files) + ",,\n"
        return record_path, content
