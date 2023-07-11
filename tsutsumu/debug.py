from pathlib import Path
import sys

from tsutsumu.bundle import Toolbox


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: python -m tsutsumu <path-to-bundle>')
        sys.exit(1)

    bundle = Path(sys.argv[1])
    if bundle.suffix != '.py':
        print(f'Error: bundle "{bundle}" does not appear to be Python source code')
        sys.exit(1)

    try:
        version, manifest = Toolbox.load_meta_data(bundle)
    except Exception as x:
        print(f"Error: unable to load meta data ({x})")
        sys.exit(1)

    for key, (kind, offset, length) in manifest.items():
        if length == 0:
            print(f'bundled file "{key}" is empty')
            continue

        try:
            data = Toolbox.load_from_bundle(bundle, kind, offset, length)
            print(f'bundled file "{key}" has {len(data)} bytes')
        except Exception as x:
            print(f'Error: bundled file "{key}" is malformed ({x}):')
            with open(bundle, mode='rb') as file:
                file.seek(offset)
                raw_data = file.read(length)
            for line in raw_data.splitlines():
                print(f'    {line!r}')
            print()
