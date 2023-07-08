import base64
from pathlib import Path
import sys
from typing import cast

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: python -m tsutsumu <path-to-bundle>')
        sys.exit(1)

    bundle = Path(sys.argv[1])
    if bundle.suffix != '.py':
        print(f'Error: bundle "{bundle}" does not appear to be Python source code')
        sys.exit(1)

    bindings: 'dict[str, object]' = {}
    exec(bundle.read_bytes(), bindings)

    if '__manifest__' not in bindings:
        print(f'Error: bundle "{bundle}" does include __manifest__')
        sys.exit(1)

    manifest = cast(dict[str, tuple[int, int]], bindings['__manifest__'])
    for key, (kind, offset, length) in manifest.items():
        if length == 0:
            print(f'bundled file "{key}" is empty')
            continue

        try:
            with open(bundle, mode='rb') as file:
                file.seek(offset)
                data = file.read(length)

            if kind == 'b':
                data = base64.a85decode(eval(data))
            elif kind == 't':
                data = eval(data)
            elif kind == 'v':
                data = data
            else:
                print(f'manifest entry with invalid kind "{kind}"')
                continue

            print(f'bundled file "{key}" has {len(data)} bytes')

        except Exception as x:
            print(f'bundled file "{key}" is malformed:')
            print(f'    {x}')
            print()
            for line in data.splitlines():
                print(f'    {line!r}')
            print()
