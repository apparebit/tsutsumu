from argparse import ArgumentParser, HelpFormatter, RawTextHelpFormatter
from dataclasses import dataclass, field
import os
import sys
from textwrap import dedent
import traceback

from .maker import BundleMaker


def parser() -> ArgumentParser:
    try:
        width = min(os.get_terminal_size()[0], 70)
    except:
        width = 70

    def width_limited_formatter(prog: str) -> HelpFormatter:
        return RawTextHelpFormatter(prog, width=width)

    parser = ArgumentParser('tsutsumu',
        description=dedent("""
            Combine Python modules and related resources into a single,
            self-contained script. To determine which files to include in the
            bundle, this tool traverses the given directories and their
            subdirectories. Since module resolution is based on path names, this
            tool skips directories and files that do not have valid Python
            module names.

            By default, the generated script includes code for importing modules
            from the bundle and for executing one of its modules, very much like
            "python -m" does. If the bundled modules include exactly one
            __main__ module, Tsutsumu automatically selects that module. If
            there are no or several such modules or you want to execute another
            module, please use the -m/--main option to specify the module name.

            You can use the -b/--bundle-only option to omit the bundle runtime
            and bootstrap code from the generated script. That way, you can
            break your application into several bundles. Though you probably
            want to include that code with your application's primary bundle.
            The application can then use `Bundle.exec_install()` to load and
            install such secondary bundles and `Bundle.uninstall()` to uninstall
            them again.

            Tsutsumu always generates the bundle script in binary format.
            Re-encoding its output or even changing the line endings will likely
            break the generated script! By default, the script is written to
            standard out. Please use the -o/--output option to write to a file
            instead.

            Tsutsumu is © 2023 Robert Grimm. It is licensed under Apache 2.0.
            The source repository is <https://github.com/apparebit/tsutsumu>
        """),
        formatter_class=width_limited_formatter)
    parser.add_argument(
        '-b', '--bundle-only',
        action='store_true',
        help='emit only bundled files and their manifest,\nno runtime code')
    parser.add_argument(
        '-m', '--main',
        metavar='MODULE',
        help="if a package, execute its __main__ module;\n"
        "if a module, execute this module")
    parser.add_argument(
        '-o', '--output',
        metavar='FILENAME',
        help='write bundle to this file')
    parser.add_argument(
        '-r', '--repackage',
        action='store_true',
        help='repackage runtime as "tsutsumu.bundle.Bundle"')
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='enable verbose output')
    parser.add_argument(
        'roots',
        metavar='PKGROOT', nargs='+',
        help="include all Python modules reachable from\nthe package's root directory")
    return parser


@dataclass
class ToolOptions:
    bundle_only: bool = False
    main: 'None | str' = None
    output: 'None | str' = None
    repackage: bool = False
    verbose: bool = False
    roots: 'list[str]' = field(default_factory=list)


def main() -> None:
    options = parser().parse_args(namespace=ToolOptions())

    try:
        if options.bundle_only and (options.main or options.repackage):
            raise ValueError('--bundle is incompatible with --main/--repackage')

        BundleMaker(
            options.roots,
            bundle_only=options.bundle_only,
            main=options.main,
            output=options.output,
            repackage=options.repackage,
        ).run()
    except Exception as x:
        if options.verbose:
            traceback.print_exception(x)
        else:
            print(f'Error: {x}')
        sys.exit(1)


if __name__ == '__main__':
    main()
