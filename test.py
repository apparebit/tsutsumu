#!.venv/bin/python

import doctest
from pathlib import Path
import subprocess
import shutil
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import TextIO


class Console:
    CSI = '\x1b['
    BOLD = '1'
    REGULAR = '0'
    GREEN = '1;32'
    RED = '1;31'
    RESET = '39;0'

    def __init__(self, stream: 'TextIO') -> None:
        self._is_tty = stream.isatty()
        self._stream = stream

    def sgr(self, code: str) -> str:
        return f'{self.CSI}{code}m' if self._is_tty else ''

    def detail(self, message: str) -> None:
        self._stream.write(f'{message}\n')

    def info(self, message: str) -> None:
        self._stream.write(f'{self.sgr(self.BOLD)}{message}{self.sgr(self.REGULAR)}\n')

    def success(self, message: str) -> None:
        self._stream.write(f'{self.sgr(self.GREEN)}{message}{self.sgr(self.RESET)}\n')

    def error(self, message: str) -> None:
        self._stream.write(f'{self.sgr(self.RED)}{message}{self.sgr(self.RESET)}\n')


def main() -> None:
    console = Console(sys.stdout)

    console.info("Getting started with Tsutsumu's test suite...")
    console.detail(f'Running "{sys.executable}"')
    console.detail(f' - Python {sys.version}')

    try:
        import tsutsumu
    except ImportError:
        console.error('Unable to import tsutsumu')
        sys.exit(1)

    console.detail(f'Testing tsutsumu {tsutsumu.__version__}')

    # ----------------------------------------------------------------------------------

    console.info('Running documentation tests...')
    doc_failures, doc_tests = doctest.testfile('README.md')

    if doc_failures != 0:
        console.error(f'{doc_failures}/{doc_tests} documentation tests failed!')
        sys.exit(1)

    console.detail(f'All {doc_tests} documentation tests passed')

    # ----------------------------------------------------------------------------------

    cwd = Path('.').absolute()
    tmpdir = cwd / 'tmp'

    shutil.rmtree(tmpdir, ignore_errors=True)
    tmpdir.mkdir()

    # ----------------------------------------------------------------------------------

    console.info('Bundling tsutsumu twice...')
    subprocess.run([
            sys.executable,
            '-m', 'tsutsumu',
            '-o', str(tmpdir / 'bundler.py'),
            'tsutsumu',
        ],
        check=True
    )
    console.detail('Created tmp/bundler.py')

    subprocess.run([
            sys.executable,
            '-m', 'tsutsumu',
            '-r',
            '-o', str(tmpdir / 'repackaged_bundler.py'),
            'tsutsumu',
        ],
        check=True
    )
    console.detail('Created tmp/repackaged_bundler.py')

    # ----------------------------------------------------------------------------------

    console.info('Bundling spam thrice...')
    subprocess.run([
            sys.executable,
            '-m', 'tsutsumu',
            '-o', str(tmpdir / 'can1.py'),
            'spam'
        ],
        check=True
    )
    console.detail('Created tmp/can1.py with tsutsumu package')

    subprocess.run([
            sys.executable,
            str(tmpdir / 'bundler.py'),
            '-o', str(tmpdir / 'can2.py'),
            'spam'
        ],
        check=True
    )
    console.detail('Created tmp/can2.py with bundled tsutsumu')

    subprocess.run([
            sys.executable,
            str(tmpdir / 'repackaged_bundler.py'),
            '-o', str(tmpdir / 'can3.py'),
            'spam'
        ],
        check=True
    )
    console.detail('Created tmp/can3.py with repackaged tsutsumu')

    # ----------------------------------------------------------------------------------

    console.info('Comparing cans of spam...')
    files = [(tmpdir/ f'can{index}.py').read_bytes() for index in range(1, 4)]

    mismatch = False
    if files[0] != files[1]:
        console.detail('tmp/can1.py and tmp/can2.py differ')
        mismatch = True
    if files[0] != files[2]:
        console.detail('tmp/can1.py and tmp/can3.py differ')
        mismatch = True
    if mismatch:
        console.error(
            'Regular and bundled versions of Tsutsumu generated different bundles!')
        sys.exit(1)

    console.detail('All three cans contain the exact same spam')

    # ----------------------------------------------------------------------------------

    console.info('Checking repackaged tsutsumu modules...')
    result = subprocess.run([
            sys.executable,
            'test.py',
            'repackaged-module-test'
        ],
    )

    if result.returncode != 0:
        console.error('Repackaged modules differ from originals!')
        sys.exit(1)

    # ----------------------------------------------------------------------------------

    console.success('W00t! All tests passed!')

    shutil.rmtree(tmpdir)
    sys.exit(0)


def repackaged_module_test() -> None:
    cwd = Path('.').absolute()

    # Importing repackaged_bundler does not execute bootstrap code,
    # since it is not the __main__ module.
    import tmp.repackaged_bundler

    # Extract __manifest__, __version__, and Bundle from module.
    repackaged_bundle_path = cwd / 'tmp' / 'repackaged_bundler.py'
    manifest = tmp.repackaged_bundler.__manifest__
    version = tmp.repackaged_bundler.__version__
    Bundle = tmp.repackaged_bundler.Bundle

    # Install bundle and repackage.
    bundle = Bundle.install(repackaged_bundle_path, manifest, version)
    bundle.repackage()

    # Compare repackaged modules to their originals.
    original_path = cwd / 'tsutsumu'
    repackaged_path = repackaged_bundle_path / 'tsutsumu'

    code = 0
    for module in ('__init__.py', 'bundle.py'):
        original = (original_path / module).read_bytes()
        repackaged = bundle[str(repackaged_path / module)]
        if original == repackaged:
            print(f'Repackaged "tsutsumu/{module}" matched original')
        else:
            print(f'Repackaged "tsutsumu/{module}" did NOT match original:')
            print(f'{repackaged!r}')
            code = 1

    sys.exit(code)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'repackaged-module-test':
        repackaged_module_test()
    else:
        main()
