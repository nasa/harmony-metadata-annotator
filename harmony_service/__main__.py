"""Run the Harmony Metadata Annotator service via the Harmony CLI."""

from argparse import ArgumentParser
from sys import argv

from harmony_service_lib import is_harmony_cli, run_cli, setup_cli

from harmony_service.adapter import MetadataAnnotatorAdapter
from harmony_service.exceptions import SERVICE_NAME


def main(arguments: list[str]):
    """Parse command line arguments and invoke the appropriate method."""
    parser = ArgumentParser(
        prog=SERVICE_NAME, description='Run Harmony Metadata Annotator.'
    )

    setup_cli(parser)
    harmony_arguments, _ = parser.parse_known_args(arguments[1:])

    if is_harmony_cli(harmony_arguments):
        run_cli(parser, harmony_arguments, MetadataAnnotatorAdapter)
    else:
        parser.error('Only --harmony CLIs are supported')


if __name__ == '__main__':
    main(argv)
