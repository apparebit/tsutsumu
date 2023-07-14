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
            self-contained file.

            Tsutsumu automatically determines which files to include in a bundle
            by tracing a main package's dependencies at the granularity of
            packages and their extras. That means that either all of a package's
            or extra's files are included in a bundle or none of them. While
            that may end up bundling files that aren't really needed, it also is
            more robust because it follows the same recipe as package building
            and similar tools.

            Tsutsumu supports two different bundle formats. It defaults to its
            own, textual bundle format, which is particularly suitable to use
            cases, where trust is lacking and a bundle's source code should be
            readily inspectable before execution or where the runtime
            environment is resource-constrained. For use under less stringent
            requirements, Tsutsumu also targets the `zipapp` format included in
            Python's standard library, which is a bit more resource-intensive
            but also produces smaller bundles. Please use `-f`/`--format` to
            explicitly select the bundle's format.

            Tsutsumu includes the code for bootstrapping and executing the code
            in a bundle with the bundle for its own, textual format. That isn't
            necessary for the `zipapp` format, which has been supported by
            Python's standard library since version 3.5. In either case, bundles
            execute some main module's code very much like "python -m" does. If
            the bundled modules include exactly one __main__ module, Tsutsumu
            automatically selects that module. If there are no or several such
            modules or you want to execute another, non-main module, please use
            the `-m`/`--main` option to specify the module name. Use the
            `-b`/`--bundle-only` option to omit the runtime code from Tsutsumu's
            textual format.

            Tsutsumu is © 2023 Robert Grimm. It is licensed under Apache 2.0.
            The source repository is <https://github.com/apparebit/tsutsumu>
        """),
        formatter_class=width_limited_formatter)
    parser.add_argument(
        '-b', '--bundle-only',
        action='store_true',
        help='emit only bundled files and their manifest,\nno runtime code')
    parser.add_argument(
        '-f', '--format',
        choices=('text', 'zipapp'),
        help="select Tsutsumu's textual bundle format or\nzipapp's more "
        "compact, binary one")
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
