from argparse import ArgumentParser, HelpFormatter, RawTextHelpFormatter
from dataclasses import dataclass, field
import os
import sys
from textwrap import dedent
import traceback

from .maker import BundleMaker


if __name__ == '__main__':
    try:
        width = min(os.get_terminal_size()[0], 70)
    except:
        width = 70

    def width_limited_formatter(prog: str) -> HelpFormatter:
        return RawTextHelpFormatter(prog, width=width)

    @dataclass
    class ToolOptions:
        bundle_only: bool = False
        output: 'None | str' = None
        package: 'None | str' = None
        repackage: bool = False
        verbose: bool = False
        roots: 'list[str]' = field(default_factory=list)

    parser = ArgumentParser('tsutsumu',
        description=dedent("""
            Combine Python modules and related resources into a single,
            self-contained script. To determine which files to include in the
            bundle, this tool traverses the given directories and their
            subdirectories. Since module resolution is based on path names, this
            tool skips directories and files that do not have valid Python
            module names.

            By default, the bundle script executes a __main__ module just like
            "python -m package" does. If the bundled modules include exactly one
            such __main__ module, that module is automatically selected.
            Otherwise, please use the -p/--package option to specify the package
            name.

            Use the -b/--bundle-only option to omit the bundle runtime and
            bootstrap code. That way, you can break your application into
            several bundles.

            By default, the bundle script is written to standard out, which may
            break the bundle script since Python's standard out is a character
            instead of a byte stream. Use the -o/--output option to write to a
            file directly.
        """),
        formatter_class=width_limited_formatter)
    parser.add_argument(
        '-b', '--bundle-only',
        action='store_true',
        help='emit only bundled files and their manifest,\nno runtime code')
    parser.add_argument(
        '-o', '--output',
        metavar='FILENAME',
        help='write bundle script to this file')
    parser.add_argument(
        '-p', '--package',
        metavar='PACKAGE',
        help="execute this package's __main__ module")
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
    options = parser.parse_args(namespace=ToolOptions())

    try:
        if options.bundle_only and (options.package or options.repackage):
            raise ValueError('--bundle is incompatible with --package/--repackage')

        BundleMaker(
            options.roots,
            bundle_only=options.bundle_only,
            output=options.output,
            package=options.package,
            repackage=options.repackage,
        ).run()
    except Exception as x:
        if options.verbose:
            traceback.print_exception(x)
        else:
            print(f'Error: {x}')
        sys.exit(1)
