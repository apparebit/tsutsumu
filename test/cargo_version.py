from cargo.version import Version

def test_parse_version() -> None:
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
        actual = Version.of(input)
        print(f'    {actual!s:>20} --- {actual!r}')
        assert actual == expected
