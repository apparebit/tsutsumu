#!.venv/bin/python

# mypy: disallow_any_expr = false

from dataclasses import dataclass
import doctest
from importlib import import_module
from pathlib import Path
import subprocess
import shutil
import sys

from test.console import Console


# ======================================================================================


@dataclass
class Options:
    test_runner: str
    console: Console
    module_name: str = ''
    verbose: bool = False

    def make_verbose(self) -> None:
        self.verbose = True
        self.console.verbose = True

    def test_command(self) -> list[str]:
        command = [sys.executable, self.test_runner]
        if self.verbose:
            command.append('-v')
        return command


def run_tests(options: Options) -> int:
    console = options.console
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

    console.info('Running unit tests...')

    for module in (
        'test.cargo_version',
        'test.cargo_extra',
    ):
        console.detail(f'╭──── {module}')
        subprocess.run([*options.test_command(), 'run-test-module', module], check=True)
        console.detail('╰─╼')

    # ----------------------------------------------------------------------------------

    console.info('Testing ingestion from pyproject.toml...')
    from cargo.distinfo import DistInfo

    pyproject_path = Path('pyproject.toml').absolute()
    distinfo = DistInfo.from_pyproject(pyproject_path)
    for key, expected in (
        ('name', 'tsutsumu'),
        ('extras', ()),
        ('version', tsutsumu.__version__),
        ('summary', 'Simple, flexible module bundling for Python'),
        ('homepage', 'https://github.com/apparebit/tsutsumu'),
        ('required_python', '>=3.7'),
        ('required_packages', ('packaging',)),
        ('provenance', str(pyproject_path)),
    ):
        actual = getattr(distinfo, key)
        message = f'distinfo.{key} is {actual} instead of {expected}'
        assert actual == expected, message

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
            'tsutsumu', 'cargo',
        ],
        check=True
    )
    console.detail('Rebuilt bundles/bundler.py')

    # ----------------------------------------------------------------------------------

    console.info('Running documentation tests...')

    try:
        sys.argv.remove('-v')
    except:
        pass

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
        raise SystemExit(1)

    # ----------------------------------------------------------------------------------

    console.info('Comparing repackaged Tsutsumu modules to originals...')
    completion = subprocess.run([*options.test_command(), 'run-repackaged-module-test'])
    if completion.returncode != 0:
        console.error('Repackaged modules differ from originals!')
        sys.exit(1)

    # ----------------------------------------------------------------------------------

    console.success('W00t! All tests passed!')

    shutil.rmtree(tmpdir)
    return 0

# ======================================================================================

def run_module_test(options: Options) -> int:
    console = options.console
    module = import_module(options.module_name)

    errors = 0
    for key in dir(module):
        if not key.startswith('test_'):
            continue
        value = getattr(module, key)
        if not callable(value):
            continue

        console.detail(f'├─ {value.__name__}')
        with console.new_prefix('│   '):
            try:
                    value(options.console)
            except Exception as x:
                console.exception(x)
                errors += 1

    return bool(errors + console.failed_assertions)

# --------------------------------------------------------------------------------------

def run_repackaged_module_test(options: Options) -> int:
    console = options.console

    # We cannot import Bundle and Toolbox without also importing tsutsumu's
    # __init__ and bundle modules, which breaks repackage(). At the same time,
    # we can still read, compile, and exec the bundle module.

    # mypy: Expression type contains "Any" (has type "type[Path]") — Huh??
    cwd = Path.cwd().absolute()

    mod_bundle_path = cwd / 'tsutsumu' / 'bundle.py'
    mod_bundle_binary = compile(
        mod_bundle_path.read_bytes(),
        mod_bundle_path,
        'exec',
        dont_inherit=True,
    )
    mod_bundle_bindings: dict[str, object] = dict()
    exec(mod_bundle_binary, mod_bundle_bindings)
    Toolbox = mod_bundle_bindings['Toolbox']
    Bundle = mod_bundle_bindings['Bundle']

    repackaged_path = cwd / 'tmp' / 'repackaged-bundler.py'
    version, manifest = (
        Toolbox.load_meta_data(repackaged_path)) # type: ignore[attr-defined]
    bundle = (Bundle.install( # type: ignore[attr-defined]
        repackaged_path, version, manifest))
    bundle.repackage()

    # Compare repackaged modules to their originals.
    package_path = cwd / 'tsutsumu'
    bundled_package_path = repackaged_path / 'tsutsumu'

    is_different = False
    for module in ('__init__.py', 'bundle.py'):
        original = (package_path / module).read_bytes()
        repackaged = bundle[str(bundled_package_path / module)]
        if original == repackaged:
            console.detail(f'Repackaged "tsutsumu/{module}" matched original')
        else:
            console.error(f'Repackaged "tsutsumu/{module}" did NOT match original:')
            console.detail(f'{repackaged!r}')
            is_different = True

    return is_different

# --------------------------------------------------------------------------------------

if __name__ == '__main__':
    try:
        options = Options(sys.argv[0], Console(sys.stdout))
        console = options.console

        fn = run_tests
        module = None
        for arg in sys.argv[1:]:
            if arg == '-v':
                options.make_verbose()
            elif arg == 'run-test-module':
                fn = run_module_test
            elif arg == 'run-repackaged-module-test':
                fn = run_repackaged_module_test
            elif fn == run_module_test and options.module_name == '':
                options.module_name = arg
            else:
                raise SystemExit(f'unrecognized command line argument "{arg}"')

        if fn == run_module_test and options.module_name == '':
            raise SystemExit('can\'t "run-test-module" without module name')

        sys.exit(fn(options))

    except SystemExit as x:
        if isinstance(x.args[0], str):
            console.error(x.args[0])
            code = 1
        elif isinstance(x.args[0], int):
            code = x.args[0]
        sys.exit(code)

    except subprocess.CalledProcessError as x:
        cmd = list(x.cmd)
        if (Path('.') / '.venv/bin/python').samefile(cmd[0]):
            cmd[0] = 'python'
        console.info(
            f'command "{" ".join(cmd)}" failed with exit status {x.returncode}')

    except Exception as x:
        console.exception(x)
        sys.exit(1)
