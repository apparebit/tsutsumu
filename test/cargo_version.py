from .console import Console
from cargo.version import Version, Specifier


def test_parse_version(console: Console) -> None:
    for input, output_text, output_data in (
        ('1.2.3', '1.2.3', (0, (1, 2, 3), None, None, None, None, None)),
        ('1.2.3a', '1.2.3a0', (0, (1, 2, 3), 'a', 0, None, None, None)),
        ('1.2.3b1', '1.2.3b1', (0, (1, 2, 3), 'b', 1, None, None, None)),
        ('1.2.3.b2', '1.2.3b2', (0, (1, 2, 3), 'b', 2, None, None, None)),
        ('1.2.3.preview-3', '1.2.3rc3', (0, (1, 2, 3), 'rc', 3, None, None, None)),
        ('1.2.3.rc.4', '1.2.3rc4', (0, (1, 2, 3), 'rc', 4, None, None, None)),
        ('1.2.3.rc_5', '1.2.3rc5', (0, (1, 2, 3), 'rc', 5, None, None, None)),
        ('1.2.3post', '1.2.3.post0', (0, (1, 2, 3), None, None, 0, None, None)),
        ('1.2.3.r1', '1.2.3.post1', (0, (1, 2, 3), None, None, 1, None, None)),
        ('1.2.3.rev2', '1.2.3.post2', (0, (1, 2, 3), None, None, 2, None, None)),
        ('1.2.3.post_3', '1.2.3.post3', (0, (1, 2, 3), None, None, 3, None, None)),
        ('1.2.3.post.4', '1.2.3.post4', (0, (1, 2, 3), None, None, 4, None, None)),
        ('1.2.3.post-5', '1.2.3.post5', (0, (1, 2, 3), None, None, 5, None, None)),
        ('v1.2.3.dev', '1.2.3.dev0', (0, (1, 2, 3), None, None, None, 0, None)),
        ('v1.2.3.dev1', '1.2.3.dev1', (0, (1, 2, 3), None, None, None, 1, None)),
        ('v1.2.3dev2', '1.2.3.dev2', (0, (1, 2, 3), None, None, None, 2, None)),
        ('v1.2.3.pre-4.post-5.dev-6',
            '1.2.3rc4.post5.dev6', (0, (1, 2, 3), 'rc', 4, 5, 6, None)),
        ('1.2.3+local', '1.2.3+local', (0, (1, 2, 3), None, None, None, None, 'local')),
    ):
        actual = Version(input)
        console.assert_eq(str(actual), output_text)
        console.assert_eq(actual.data, output_data)


def test_compare_versions(console: Console) -> None:
    for s1, op, s2 in (
        ('1.2.3', 'eq', '1.2.3'),
        ('1.2.3', 'eq', '1.2.3.0.0'),
        ('1.2.3', 'ne', '1.2.2'),
        ('1.2.3a', 'lt', '1.2.3'),
        ('1.2.3dev', 'lt', '1.2.3'),
        ('1.2.3pre.dev', 'lt', '1.2.3pre'),
        ('1.2.3.post.dev', 'lt', '1.2.3.post'),
        ('1.2.3pre', 'lt', '1.2.3.post'),
    ):
        v1, v2 = Version(s1), Version(s2)
        console.assert_op(op, v1, v2)
        if op in ('eq', 'ne'):
            console.assert_op(op, v2, v1)
        elif op == 'lt':
            console.assert_op('gt', v2, v1)


def test_apply_specifier(console: Console) -> None:
    for spec_text, version_text, result in (
        ('> 1.2.3', '1.2.3post', False),
        ('> 1.2.3', '1.2.4', True),
        ('>= 1.2.3', '1.2.3', True),
        ('>= 1.2.3', '1.2.4', True),
        ('== 1.2.3', '1.2.4', False),
        ('== 1.2.3', '1.2.3.0', True),
        ('== 1.2.3.0', '1.2.3', True),
        ('== 1.2.*', '1.2', True),
        ('== 1.2.*', '1.2.3', True),
        ('== 1.2.*', '1.2.4.rc5', True),
        ('== 1.2.*', '1.2.4.post5', True),
        ('~= 1.2.3', '1.2.2', False),
        ('~= 1.2.3', '1.2.3', True),
        ('~= 1.2.3', '1.2.9999999999999999999', True),
        ('~= 1.2.3', '1.3.0', False),
    ):
        spec = Specifier(spec_text)
        version = Version(version_text)
        console.assert_op(spec, version, expected=result)
