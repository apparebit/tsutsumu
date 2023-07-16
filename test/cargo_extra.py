from tsutsumu.distribution.requirement import parse_requirement

for requirement, expected_result in (
    ('spam', ('spam', [], [], None)),
    ('spam [ can ,label]', ('spam', ['can', 'label'], [], None)),
    ('spam >6.6.5, < 6.6.6', ('spam', [], ['>6.6.5', '<6.6.6'], None)),
    ('spam ; extra == "can"', ('spam', [], [], 'can')),
    ('spam; "can"==  extra', ('spam', [], [], 'can')),
    ('spam[bacon](==2.0)', ('spam', ['bacon'], ['==2.0'], None)),
    ('spam; os_name != "bacon" and os_name != "ham" and extra == "tofu"',
        ('spam', [], [], 'tofu')),
    ('spam; extra == "bacon" or "bacon" == extra', ('spam', [], [], 'bacon')),
):
    requirement_quadruple = parse_requirement(requirement)
    print(f'    {requirement_quadruple}')
    assert requirement_quadruple == expected_result
