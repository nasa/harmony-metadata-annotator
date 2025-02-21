"""Main module for business logic of the Harmony Metadata Annotator."""

import re
from datetime import UTC, datetime
from shutil import copy

from netCDF4 import Dataset
from varinfo import VarInfoFromNetCDF4

PROGRAM = 'Harmony Metadata Annotator'
# To be improved - make dynamic based on service_version.txt
VERSION = '0.0.1'


def annotate_granule(
    input_file_name: str,
    output_file_name: str,
    varinfo_config_file: str,
    collection_short_name: str | None = None,
) -> None:
    """Top level of abstraction to do the annotation.

    Copy input file to output location, then parse it using `earthdata-varinfo`.
    See if the configuration file has any rules applicable to variables or
    groups for granules belonging to the collection the granule is from. If so,
    amend the metadata according to those rules.

    """
    copy(input_file_name, output_file_name)

    granule_varinfo = VarInfoFromNetCDF4(
        input_file_name,
        short_name=collection_short_name,
        config_file=varinfo_config_file,
    )

    if len(granule_varinfo.cf_config.metadata_overrides):
        # There are metadata overrides applicable to the granule's collection:
        amend_in_file_metadata(output_file_name, granule_varinfo)


def amend_in_file_metadata(file_name: str, granule_varinfo: VarInfoFromNetCDF4) -> None:
    """Update metadata attributes according to known rules.

    First, identify the variables or groups needing to be updated, or variables
    that need to be created. Next create any missing, attribute only, variables.
    Update the metadata attributes of all variables listed in overrides, or
    removing any attributes with an overriding value of None. Lastly, update
    the `history` global attribute.

    """
    items_to_update, variables_to_create = get_matching_groups_and_variables(
        granule_varinfo,
    )

    with Dataset(file_name, 'a') as output_dataset:
        # First create missing variables (such as CRS definitions)
        for variable_path in variables_to_create:
            output_dataset.createVariable(variable_path, 'S1')
            update_metadata_attributes(
                output_dataset,
                variable_path,
                granule_varinfo,
            )

        # Update all pre-existing variables or groups with metadata overrides
        for item_to_update in items_to_update:
            update_metadata_attributes(
                output_dataset,
                item_to_update,
                granule_varinfo,
            )

        update_history_metadata(output_dataset)


def get_matching_groups_and_variables(
    granule_varinfo: VarInfoFromNetCDF4,
) -> tuple[set[str], set[str]]:
    """Find all groups and variables that match a metadata override pattern.

    Patterns for the overrides are taken from the earthdata-varinfo configuration
    file, and are filtered to only identify overrides applicable to the
    collection the input granule belongs to. This approach is taken in
    preference to iterating through all variables in a granule for two reasons:

    1) Iterating through overrides is likely quicker, particularly for granules
       with many variables.
    2) Iterating through overrides will also identify missing variables.

    """
    matches = set()
    missing_variables = set()

    for pattern_string in granule_varinfo.cf_config.metadata_overrides:
        override_pattern = re.compile(pattern_string)
        pattern_matches = set(
            group
            for group in granule_varinfo.groups
            if override_pattern.match(group) is not None
        )
        pattern_matches.update(
            set(
                variable
                for variable in granule_varinfo.variables
                if override_pattern.match(variable) is not None
            )
        )

        matches.update(pattern_matches)

        if len(pattern_matches) == 0 and is_exact_path(pattern_string):
            missing_variables.add(pattern_string)

    return matches, missing_variables


def is_exact_path(pattern_string: str) -> bool:
    """Determine if the string is an exact path.

    Should return true for strings that only match a single path, but False
    when regular expression syntax is present allowing multiple matches.

    To be improved: If there are variable names that contain special characters
    also used in regular expressions, then this check will incorrectly assume
    that the string is a regular expression.

    """
    return re.escape(pattern_string) == pattern_string


def update_metadata_attributes(
    output_granule: Dataset,
    group_or_variable_path: str,
    granule_varinfo: VarInfoFromNetCDF4,
) -> None:
    """Update the metadata attributes on the supplied group or variable.

    This function uses the precedence rules outlined in earthdata-varinfo. If
    multiple metadata overrides apply to the same variable or group, the most
    specific is used. This is defined as the matching rule with the deepest
    specified hierarchy and the shortest specified variable basename.

    """
    matching_overrides = granule_varinfo.cf_config.get_metadata_overrides(
        group_or_variable_path,
    )

    attributes_to_update = {
        attribute_name: attribute_value
        for attribute_name, attribute_value in matching_overrides.items()
        if attribute_value is not None
    }
    attributes_to_delete = set(matching_overrides.keys()) - set(
        attributes_to_update.keys()
    )

    if group_or_variable_path == '/':
        # Using a path of '/' from the root group doesn't work.
        output_object = output_granule
    else:
        output_object = output_granule[group_or_variable_path]

    output_object.setncatts(attributes_to_update)

    for attribute in attributes_to_delete:
        try:
            output_object.delncattr(attribute)
        except RuntimeError as exception:
            # Trying to delete a non-existent attribute should not fail
            if not str(exception).endswith('Attribute not found'):
                raise


def update_history_metadata(output_dataset: Dataset) -> None:
    """Update the history global attribute of the Dataset."""
    new_history_line = ' '.join(
        [
            datetime.now(UTC).isoformat(),
            PROGRAM,
            VERSION,
        ]
    )

    existing_attributes = output_dataset.ncattrs()

    if 'History' in existing_attributes:
        history_attribute_name = 'History'
        existing_history = output_dataset.getncattr('History')
    elif 'history' in existing_attributes:
        history_attribute_name = 'history'
        existing_history = output_dataset.getncattr('history')
    else:
        history_attribute_name = 'history'
        existing_history = None

    output_history_value = '\n'.join(filter(None, [existing_history, new_history_line]))

    output_dataset = output_dataset.setncattr(
        history_attribute_name,
        output_history_value,
    )
