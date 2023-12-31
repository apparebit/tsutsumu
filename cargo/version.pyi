from typing import Literal

class Version:
    """
    The extended interface for Version.

    While the properties and methods below are implemented through one of
    Python's more dynamic features, the __getattr__() fallback method, this
    interface declaration suffices for enabling static typing for code using
    Version.
    """

    @property
    def epoch(self) -> int: ...
    @property
    def release(self) -> tuple[int,...]: ...
    @property
    def status(self) -> None | Literal["a", "b", "rc"]: ...
    @property
    def pre(self) -> None | int: ...
    @property
    def post(self) -> None | int: ...
    @property
    def dev(self) -> None | int: ...
    @property
    def local(self) -> None | str: ...
    def has_pre(self) -> bool: ...
    def has_post(self) -> bool: ...
    def has_dev(self) -> bool: ...
    def has_local(self) -> bool: ...
    def is_prerelease(self) -> bool: ...
