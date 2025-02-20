"""Main module for business logic of the Harmony Metadata Annotator."""


def annotate_granule(
    input_file_name: str, output_file_name: str, varinfo_config_file: str
) -> None:
    """Top level of abstraction to do the annotation."""
    # TODO
    # 1) Parse file using earthdata-varinfo
    # 2) check is there are any metadata overrides in the configuration file
    # 3) If so, apply them
    # 4) Done
