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
    for key, (offset, length) in manifest.items():
        if length == 0:
            print(f'bundled file "{key}" is empty')
            continue

        # A negative offset indicates a repackaged module file that is not
        # embedded in a binary string literal on disk.
        if offset < 0:
            print(f'bundled file "{key}" has been repackaged')

        try:
            with open(bundle, mode='rb') as file:
                file.seek(offset if offset >= 0 else -offset)
                data = file.read(length)

            if offset >= 0:
                data = eval(data)
            print(f'bundled file "{key}" has {len(data)} bytes')
        except Exception as x:
            print(f'bundled file "{key}" is malformed:')
            print(f'    {x}')
            print()
            for line in data.splitlines():
                print(f'    {line!r}')
            print()
