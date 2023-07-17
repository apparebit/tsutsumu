from operator import lt, le, eq, ne, ge, gt
from typing import Callable

from cargo.version import Version

OPERATOR_NAMES = {'lt':'<', 'le':'<=', 'eq':'==', 'ne':'!=', 'ge':'>=', 'gt':'>'}

def test_parse_version(logger: Callable[[str], None]) -> None:
    for input, expected in (
        ('1.2.3', (0, (1, 2, 3), None, None, None, None, None)),
        ('1.2.3a', (0, (1, 2, 3), 'a', 0, None, None, None)),
        ('1.2.3b1', (0, (1, 2, 3), 'b', 1, None, None, None)),
        ('1.2.3.b2', (0, (1, 2, 3), 'b', 2, None, None, None)),
        ('1.2.3.preview-3', (0, (1, 2, 3), 'rc', 3, None, None, None)),
        ('1.2.3.rc.4', (0, (1, 2, 3), 'rc', 4, None, None, None)),
        ('1.2.3.rc_5', (0, (1, 2, 3), 'rc', 5, None, None, None)),
        ('1.2.3post', (0, (1, 2, 3), None, None, 0, None, None)),
        ('1.2.3.r1', (0, (1, 2, 3), None, None, 1, None, None)),
        ('1.2.3.rev2', (0, (1, 2, 3), None, None, 2, None, None)),
        ('1.2.3.post_3', (0, (1, 2, 3), None, None, 3, None, None)),
        ('1.2.3.post.4', (0, (1, 2, 3), None, None, 4, None, None)),
        ('1.2.3.post-5', (0, (1, 2, 3), None, None, 5, None, None)),
        ('v1.2.3.dev', (0, (1, 2, 3), None, None, None, 0, None)),
        ('v1.2.3.dev1', (0, (1, 2, 3), None, None, None, 1, None)),
        ('v1.2.3dev2', (0, (1, 2, 3), None, None, None, 2, None)),
        ('v1.2.3.pre-4.post-5.dev-6', (0, (1, 2, 3), 'rc', 4, 5, 6, None)),
        ('1.2.3+local', (0, (1, 2, 3), None, None, None, None, 'local')),
    ):
        actual = Version(input)
        logger(f'{actual!s:>20} --- {actual!r}')
        assert actual.astuple() == expected

COMPARISONS = (
    ('1.2.3', eq, '1.2.3'),
    ('1.2.3', eq, '1.2.3.0.0'),
    ('1.2.3', ne, '1.2.2'),
    ('1.2.3a', lt, '1.2.3'),
    ('1.2.3dev', lt, '1.2.3'),
    ('1.2.3pre.dev', lt, '1.2.3pre'),
    ('1.2.3.post.dev', lt, '1.2.3.post'),
    ('1.2.3pre', lt, '1.2.3.post'),
)

def test_compare_versions(logger: Callable[[str], None]) -> None:
    for s1, op, s2 in COMPARISONS:
        v1, cp, v2 = Version(s1), OPERATOR_NAMES[op.__name__], Version(s2)
        logger(f'{str(v1):>16s} {cp:<2} {v2}')
        assert op(v1, v2)
        if cp in ('==', '!='):
            logger(f'{str(v2):>16s} {cp} {v1}')
            assert op(v2, v1)
        elif cp == '<':
            logger(f'{str(v2):>16s} >  {v1}')
            assert gt(v2, v1)
