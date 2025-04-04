"""Main module for business logic of the Harmony Metadata Annotator."""

import re
from datetime import UTC, datetime
from shutil import copy

import xarray as xr
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
    granule_varinfo = VarInfoFromNetCDF4(
        input_file_name,
        short_name=collection_short_name,
        config_file=varinfo_config_file,
    )

    if len(granule_varinfo.cf_config.metadata_overrides):
        # There are metadata overrides applicable to the granule's collection:
        amend_in_file_metadata(input_file_name, output_file_name, granule_varinfo)
    else:
        # There are no updates required, so copy the input file as-is:
        copy(input_file_name, output_file_name)


def amend_in_file_metadata(
    input_file_name: str, output_file_name: str, granule_varinfo: VarInfoFromNetCDF4
) -> None:
    """Update metadata attributes according to known rules.

    First, identify the variables or groups needing to be updated, or variables
    that need to be created. Next create any missing, attribute only, variables.
    Update the metadata attributes of all variables listed in overrides, or
    removing any attributes with an overriding value of None. Lastly, update
    the `history` global attribute.

    When opening the file as a DataTree, attempts to decode times, coordinates
    and other CF-Convention metadata are disabled, to allow updates to be made
    to the metadata attributes without impacting `xarray` internal concepts such
    as `xr.Coordinates`.

    """
    items_to_update, variables_to_create = get_matching_groups_and_variables(
        granule_varinfo,
    )

    with xr.open_datatree(
        input_file_name,
        decode_times=False,
        decode_coords=False,
        decode_cf=False,
        mask_and_scale=False,
    ) as datatree:
        # First create missing variables (such as CRS definitions)
        for variable_path in variables_to_create:
            datatree[variable_path] = xr.DataArray(data=b'')
            update_metadata_attributes(
                datatree,
                variable_path,
                granule_varinfo,
            )

        # Update all pre-existing variables or groups with metadata overrides
        for item_to_update in items_to_update:
            update_metadata_attributes(
                datatree,
                item_to_update,
                granule_varinfo,
            )

        update_history_metadata(datatree)

        # Future improvement: It is memory intensive to try and write out the
        # whole `xarray.DataTree` in one operation. Making this write variables
        # and group separately reduces the memory usage, but makes the
        # operation slower. (See Harmony SMAP L2 Gridder implementation)
        datatree.to_netcdf(output_file_name)


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
    datatree: xr.DataTree,
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

    datatree[group_or_variable_path].attrs.update(attributes_to_update)

    for attribute in attributes_to_delete:
        try:
            del datatree[group_or_variable_path].attrs[attribute]
        except KeyError:
            # Trying to delete a non-existent attribute should not fail
            pass


def update_history_metadata(datatree: xr.DataTree) -> None:
    """Update the history global attribute of the DataTree.

    If either an existing History or history global attribute exists, append
    information as a new line to the existing value. Otherwise create a new
    attribute called "history".

    """
    new_history_line = ' '.join(
        [
            datetime.now(UTC).isoformat(),
            PROGRAM,
            VERSION,
        ]
    )

    if 'History' in datatree.attrs:
        history_attribute_name = 'History'
        existing_history = datatree.attrs['History']
    elif 'history' in datatree.attrs:
        history_attribute_name = 'history'
        existing_history = datatree.attrs['history']
    else:
        history_attribute_name = 'history'
        existing_history = None

    datatree.attrs[history_attribute_name] = '\n'.join(
        filter(None, [existing_history, new_history_line])
    )
