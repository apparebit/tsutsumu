from argparse import ArgumentParser, HelpFormatter
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

    parser = ArgumentParser('tsutsumu',
        description=dedent("""
            Combine Python modules into a single, self-contained script that
            executes a __main__ module just like \"python -m package\" does. If
            the bundled modules include only one __main__ module, that module is
            automatically selected. If they include more than one __main__
            module, please use the -p/--package option to specify the package
            name.\u2029

            This tool writes to standard out by default. Use the -o/--output
            option to name a file instead. To omit bundle runtime and bootstrap
            code, use the -b/--bundle-only option. That way, you can break your
            application into several bundles.
        """),
        formatter_class=lambda prog: HelpFormatter(prog, width=width))
    parser.add_argument(
        '-b', '--bundle-only',
        action='store_true',
        help='emit only bundled files and their manifest, no runtime code')
    parser.add_argument(
        '-p', '--package',
        metavar='PACKAGE',
        help='on startup, run the __main__ module for this package')
    parser.add_argument(
        '-o', '--output',
        metavar='FILENAME',
        help='write the bundle script to the file')
    parser.add_argument(
        '-r', '--repackage',
        action='store_true',
        help='repackage the Bundle class in a fresh "tsutsumu.bundle" module')
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='enable verbose output')
    parser.add_argument(
        'roots',
        metavar='DIRECTORY', nargs='+',
        help='include all Python modules reachable from the directory')
    options = parser.parse_args()

    try:
        if options.bundle_only and (options.package or options.repackage):
            raise ValueError('--bundle is incompatible with --package/--repackage')

        maker = BundleMaker(
            options.roots,
            bundle_only=options.bundle_only,
            package=options.package,
            repackage=options.repackage
        )
        if options.output is None:
            maker.run()
        else:
            maker.write(options.output)
    except Exception as x:
        if options.verbose:
            traceback.print_exception(x)
        else:
            print(f'Error: {x}')
        sys.exit(1)
