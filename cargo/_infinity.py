class NegativeInfinityType(int):

    __slots__ = ()

    def __repr__(self) -> str:
        return '-Infinity'

    def __hash__(self) -> int:
        return hash(665)

    def __lt__(self, other: object) -> bool:
        return True

    def __le__(self, other: object) -> bool:
        return True

    def __eq__(self, other: object) -> bool:
        return isinstance(other, self.__class__)

    def __gt__(self, other: object) -> bool:
        return False

    def __ge__(self, other: object) -> bool:
        return False


class PositiveInfinityType(int):

    __slots__ = ()

    def __repr__(self) -> str:
        return '+Infinity'

    def __hash__(self) -> int:
        return hash(667)

    def __lt__(self, other: object) -> bool:
        return False

    def __le__(self, other: object) -> bool:
        return False

    def __eq__(self, other: object) -> bool:
        return isinstance(other, self.__class__)

    def __gt__(self, other: object) -> bool:
        return True

    def __ge__(self, other: object) -> bool:
        return True

NegativeInfinity = NegativeInfinityType()
PositiveInfinity = PositiveInfinityType()
