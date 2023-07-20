from .console import Console
from cargo.marker import extract_extra
from cargo.requirement import Requirement

def test_parse_requirement(console: Console) -> None:
    for input, expected_result in (
        ('spam', ('spam', (), (), None)),
        ('spam [ can ,label]', ('spam', ('can', 'label'), (), None)),
        ('spam >6.6.5, < 6.6.6', ('spam', (), ('>6.6.5', '<6.6.6'), None)),
        ('spam ; extra == "can"', ('spam', (), (), 'can')),
        ('spam; "can"==  extra', ('spam', (), (), 'can')),
        ('spam[bacon](==2.0)', ('spam', ('bacon',), ('==2.0',), None)),
        ('spam; os_name != "bacon" and os_name != "ham" and extra == "tofu"',
            ('spam', (), (), 'tofu')),
        ('spam; extra == "bacon" or "bacon" == extra', ('spam', (), (), 'bacon')),
    ):
        output = Requirement.from_string(input)
        # The conversion to a plain tuple isn't necessary for correctness, but
        # it helps reduce the clutter in verbose mode.
        console.assert_eq(tuple(output), expected_result)

def test_extract_extra(console: Console) -> None:
    for marker in (
        'os_name != "a" and os_name != "b"',
        '(os_name != "a") and os_name != "b"',
        'os_name != "a" and (os_name != "b")',
        '(os_name != "a") and (os_name != "b")',
        '(((os_name != "a"))) and os_name != "b"',
        '(os_name != "a" and (os_name != "b"))',

    ):
        console.assert_eq(extract_extra(marker), None)
