import argparse
import ast
import pathlib

from lazy_imports_lite._transformer import TransformModuleImports
from lazy_imports_lite._utils import unparse


def main():
    parser = argparse.ArgumentParser(
        prog="lazy-imports-lite", description="Tool for various file operations."
    )
    subparsers = parser.add_subparsers(
        title="subcommands", dest="subcommand", help="Available subcommands"
    )

    # Subcommand for preview
    preview_parser = subparsers.add_parser(
        "preview", help="Preview the contents of a file"
    )
    preview_parser.add_argument("filename", help="Name of the file to preview")

    args = parser.parse_args()

    if args.subcommand == "preview":
        transformer = TransformModuleImports()
        code = pathlib.Path(args.filename).read_text()
        tree = ast.parse(code)
        new_tree = ast.fix_missing_locations(transformer.visit(tree))
        new_code = unparse(new_tree)
        print(new_code)

    else:
        print(
            "Error: Please specify a valid subcommand. Use 'preview --help' for more information."
        )
        exit(1)


if __name__ == "__main__":
    main()
