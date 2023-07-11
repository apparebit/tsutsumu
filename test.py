#!.venv/bin/python

import base64
import doctest
import importlib
from pathlib import Path
import subprocess
import shutil
import sys
from typing import cast, TYPE_CHECKING

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

# ======================================================================================

def main() -> None:
    console = Console(sys.stdout)

    console.info("Getting started with Tsutsumu's test suite...")
    console.detail(f'Running "{sys.executable}"')
    console.detail(f' - Python {sys.version}')

    try:
        import tsutsumu
        from tsutsumu.bundle import Toolbox
    except ImportError:
        console.error('Unable to import tsutsumu')
        sys.exit(1)

    console.detail(f'Testing tsutsumu {tsutsumu.__version__}')

    cwd = Path('.').absolute()
    tmpdir = cwd / 'tmp'

    shutil.rmtree(tmpdir, ignore_errors=True)
    tmpdir.mkdir()

    # ----------------------------------------------------------------------------------

    console.info('Rebuilding repository bundles...')

    # This bundle must be regenerated before documentation test, which uses it.
    subprocess.run([
            sys.executable,
            '-m', 'tsutsumu',
            '-o', str(cwd / 'bundles' / 'can.py'),
            'spam'
        ],
        check=True
    )
    console.detail('Rebuilt bundles/can.py')

    subprocess.run([
            sys.executable,
            '-m', 'tsutsumu',
            '-o', str(cwd / 'bundles' / 'bundler.py'),
            '-r',
            'tsutsumu'
        ],
        check=True
    )
    console.detail('Rebuilt bundles/bundler.py')

    # ----------------------------------------------------------------------------------

    console.info('Running documentation tests...')

    # Since documentation test uses bundles/can.py, we regenerate it first.
    doc_failures, doc_tests = doctest.testfile(
        'README.md', optionflags=doctest.REPORT_NDIFF)

    if doc_failures != 0:
        console.error(f'{doc_failures}/{doc_tests} documentation tests failed!')
        sys.exit(1)

    console.detail(f'All {doc_tests} documentation tests passed')

    # ----------------------------------------------------------------------------------

    console.info('Bundling Tsutsumu without and with repackaging...')
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
            '-o', str(tmpdir / 'repackaged-bundler.py'),
            'tsutsumu',
        ],
        check=True
    )
    console.detail('Created tmp/repackaged-bundler.py')

    # ----------------------------------------------------------------------------------

    console.info('Bundling spam with regular, bundled, and repackaged Tsutsumu...')
    subprocess.run([
            sys.executable,
            '-m', 'tsutsumu',
            '-o', str(tmpdir / 'can1.py'),
            'spam'
        ],
        check=True
    )
    console.detail('Created tmp/can1.py with regular Tsutsumu')

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
            str(tmpdir / 'repackaged-bundler.py'),
            '-o', str(tmpdir / 'can3.py'),
            'spam'
        ],
        check=True
    )
    console.detail('Created tmp/can3.py with repackaged tsutsumu')

    # ----------------------------------------------------------------------------------

    console.info('Comparing cans of bundled spam...')
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

    console.detail('All three cans contain the exact same spam!')

    # ----------------------------------------------------------------------------------

    console.info('Comparing bundled binary file to original...')
    original = (cwd / 'spam' / 'bacon.jpg').read_bytes()

    err_count = 0
    for index in range(1, 4):
        filename = f'can{index}.py'
        path = tmpdir / filename

        manifest = Toolbox.load_meta_data(path)[1]
        kind, offset, length = manifest['spam/bacon.jpg']
        if kind != 'b':
            console.detail(
                f'Bundled image in "tmp/{filename}" has kind "{kind}", not "b"')
            err_count += 1

        canned_bacon = Toolbox.load_from_bundle(path, kind, offset, length)
        if original == canned_bacon:
            console.detail(f'Bundled image in "tmp/{filename}" is the same as original')
        else:
            console.detail(f'Bundled image in "tmp/{filename}" differs from original:')
            lines = Toolbox.read(path, offset, length).splitlines()
            for line in lines[:3]:
                console.detail(f'    {line!r}')
            console.detail('    ...')
            err_count += 1

    if err_count > 0:
        console.error(f'Bundling of binary files is broken!')
        sys.exit(1)

    # ----------------------------------------------------------------------------------

    console.info('Comparing repackaged Tsutsumu modules to originals...')
    result = subprocess.run([
            sys.executable,
            'test.py',
            'run-repackaged-module-test'
        ],
    )

    if result.returncode != 0:
        console.error('Repackaged modules differ from originals!')
        sys.exit(1)

    # ----------------------------------------------------------------------------------

    console.success('W00t! All tests passed!')

    shutil.rmtree(tmpdir)
    sys.exit(0)

# ======================================================================================

def repackaged_module_test() -> None:
    from tsutsumu.bundle import Bundle, Toolbox

    cwd = Path('.').absolute()
    repackaged_path = cwd / 'tmp' / 'repackaged-bundler.py'


    version, manifest = Toolbox.load_meta_data(repackaged_path)
    bundle = Bundle.install(repackaged_path, version, manifest)
    bundle.repackage()

    # Compare repackaged modules to their originals.
    package_path = cwd / 'tsutsumu'
    bundled_package_path = repackaged_path / 'tsutsumu'

    code = 0
    for module in ('__init__.py', 'bundle.py'):
        original = (package_path / module).read_bytes()
        repackaged = bundle[str(bundled_package_path / module)]
        if original == repackaged:
            print(f'Repackaged "tsutsumu/{module}" matched original')
        else:
            print(f'Repackaged "tsutsumu/{module}" did NOT match original:')
            print(f'{repackaged!r}')
            code = 1

    sys.exit(code)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'run-repackaged-module-test':
        repackaged_module_test()
    else:
        main()
