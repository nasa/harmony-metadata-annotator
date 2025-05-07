"""Main module for business logic of the Harmony Metadata Annotator."""

import os
import re
from datetime import UTC, datetime
from shutil import copy

import numpy as np
import xarray as xr
from varinfo import VarInfoFromNetCDF4

from metadata_annotator.exceptions import (
    InvalidDimensionAttribute,
    InvalidGridMappingReference,
    InvalidSubsetIndexShape,
    MissingDimensionAttribute,
    MissingStartIndexConfiguration,
    MissingSubsetIndexReference,
)
from metadata_annotator.geotransform import compute_dimension_scale

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
        # Update all pre-existing variables or groups with metadata overrides including
        # dimension renaming where applicable.
        update_group_and_variable_attributes(datatree, items_to_update, granule_varinfo)

        # get all the dimension variables
        dimension_variables = get_dimension_variables(datatree)

        # create variables or update dimensions
        for variable_path in variables_to_create:
            if variable_path not in dimension_variables:
                create_new_variables(datatree, variable_path, granule_varinfo)
            else:
                update_dimension_variable(datatree, variable_path, granule_varinfo)

        spatial_dimension_variables = get_spatial_dimension_variables(
            datatree, dimension_variables
        )
        update_spatial_dimension_values(
            datatree, spatial_dimension_variables, granule_varinfo
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


def update_group_and_variable_attributes(
    datatree: xr.DataTree, items_to_update: str, granule_varinfo: VarInfoFromNetCDF4
) -> None:
    """Update attributes for existing variables and groups based on configuration."""
    for item_to_update in items_to_update:
        update_metadata_attributes(
            datatree,
            item_to_update,
            granule_varinfo,
        )
        # rename the pseudo dimension names
        update_dimension_names(datatree, item_to_update)


def update_dimension_names(data_tree: xr.DataTree, variable_to_update: str) -> None:
    """Update the dimension names."""
    data_array = data_tree[variable_to_update]
    attrs = data_array.attrs
    # If dimension attribute exists for variable to update,
    # get target dimension names.
    rename_dim_list = attrs.get('dimensions', '').split()

    # The list exists so renaming is required.
    if rename_dim_list:
        if len(data_array.dims) != len(rename_dim_list):
            raise Exception(f'Incorrect configured dimensions for {variable_to_update}')

        # Rename from source data dimension names to VarInfo dimension names
        # and limit to the number of dimensions given in rename list.
        source_dims = data_array.dims[: len(rename_dim_list)]
        rename_dict = dict(zip(source_dims, rename_dim_list))
        data_tree[variable_to_update] = data_array.rename(rename_dict)


def create_new_variables(
    datatree: xr.DataTree, variable_path: str, granule_varinfo: VarInfoFromNetCDF4
) -> None:
    """Create new variables in the data tree as configured in the json file."""
    datatree[variable_path] = xr.DataArray(data=b'')
    update_metadata_attributes(
        datatree,
        variable_path,
        granule_varinfo,
    )


def get_dimension_variables(
    data_tree: xr.DataTree, dimension_variables: set[str] = None
) -> set[str]:
    """Return dimension variables."""
    if dimension_variables is None:
        dimension_variables = set()
    for name, node in data_tree.children.items():
        dt = data_tree[name]
        if dt.dims:
            dt_dim_dict = dict(dt.dims)
            dimension_variables.update(f'/{name}/{dim}' for dim in dt_dim_dict.keys())
        if node.children:
            get_dimension_variables(node, dimension_variables)

    return dimension_variables


def update_dimension_variable(
    datatree: xr.DataTree, variable_path: str, granule_varinfo: VarInfoFromNetCDF4
) -> None:
    """Update attributes of a dimension variable based on json configuration."""
    group_path, dimension_name = os.path.split(variable_path)
    dt_group = datatree[group_path]
    dataset = xr.Dataset(dt_group)
    data_array = dataset[dimension_name]
    update_metadata_attributes_for_data_array(
        data_array, variable_path, granule_varinfo
    )
    dataset[dimension_name] = data_array
    datatree[group_path] = dt_group.assign(dataset)


def update_metadata_attributes_for_data_array(
    data_array: xr.DataArray,
    group_or_variable_path: str,
    granule_varinfo: VarInfoFromNetCDF4,
) -> None:
    """Update the metadata attributes on the supplied group or variable.

    The attributes are updated on the data array based on the metadata
    overrides matched by earthdata-varinfo for the requested path.

    """
    matching_overrides = granule_varinfo.cf_config.get_metadata_overrides(
        group_or_variable_path,
    )

    attributes_to_update = {
        attribute_name: attribute_value
        for attribute_name, attribute_value in matching_overrides.items()
        if attribute_value is not None
    }

    data_array.attrs.update(attributes_to_update)


def get_spatial_dimension_variables(
    data_tree: xr.DataTree, variables: set[str] = None
) -> set[str]:
    """Return a set of identified spatial dimension variables."""
    spatial_dimension_variables = set()
    valid_dim_standard_names = ('projection_x_coordinate', 'projection_y_coordinate')
    for variable_path in variables:
        standard_name = data_tree[variable_path].attrs.get('standard_name', None)
        if standard_name in valid_dim_standard_names:
            spatial_dimension_variables.add(variable_path)

    return spatial_dimension_variables


def update_spatial_dimension_values(
    datatree: xr.DataTree,
    dimension_variables: set[str],
    granule_varinfo: VarInfoFromNetCDF4,
) -> None:
    """Update the spatial dimension variable values to the computed dimension scale."""
    for variable_path in dimension_variables:
        dim_data_array = datatree[variable_path]

        grid_start_index = get_grid_start_index(datatree, dim_data_array)
        dimension_size = len(dim_data_array)
        spatial_dimension_type = get_spatial_dimension_type(dim_data_array)

        data_array_attributes = granule_varinfo.get_missing_variable_attributes(
            variable_path
        )
        dimension_value_dtype = data_array_attributes.get('type', np.float64)

        geotransform_config = get_geotransform_config(dim_data_array, granule_varinfo)

        dimension_scale = compute_dimension_scale(
            grid_start_index,
            dimension_size,
            spatial_dimension_type,
            dimension_value_dtype,
            geotransform_config,
        )

        datatree[variable_path] = dim_data_array.copy(data=dimension_scale)


def get_grid_start_index(
    datatree: xr.DataTree, dim_data_array: xr.DataArray
) -> tuple[int, int]:
    """Determine the grid offset for a given dimension.

    The method used to determine the grid offset index is determined based off the
    dimension's attributes configured in earthdata-varinfo.

    """
    subset_index_reference = dim_data_array.attrs.get('subset_index_reference', None)
    if subset_index_reference:
        return get_start_index_from_row_col_variable(datatree, subset_index_reference)
    raise MissingStartIndexConfiguration(dim_data_array.name)


def get_start_index_from_row_col_variable(
    datatree: xr.DataTree, subset_index_reference: str
) -> tuple[int, int]:
    """Return the grid start index from a row or column index variable.

    The subset_index_reference must correspond to a variable in the datatree that
    has at least two dimensions. The value at the [0, 0] position in the last two
    dimensions (assumed to be y, x) is returned as the grid start index.
    """
    try:
        row_col_variable = datatree[subset_index_reference]
    except KeyError as e:
        raise MissingSubsetIndexReference(subset_index_reference) from e

    if row_col_variable.ndim < 2:
        raise InvalidSubsetIndexShape(subset_index_reference)

    return row_col_variable.values[..., 0, 0].item()


def get_spatial_dimension_type(data_array: xr.DataArray) -> str:
    """Return whether the given spatial dimension variable is 'x' or 'y'."""
    standard_name = data_array.attrs.get('standard_name', None)

    if not standard_name:
        raise MissingDimensionAttribute(data_array.name, 'standard_name')
    if standard_name == 'projection_x_coordinate':
        return 'x'
    if standard_name == 'projection_y_coordinate':
        return 'y'
    raise InvalidDimensionAttribute(data_array.name, 'standard_name', standard_name)


def get_geotransform_config(
    data_array: xr.DataArray, granule_varinfo: VarInfoFromNetCDF4
) -> list[int]:
    """Get the geotransform configuration from the variable's grid mapping reference."""
    grid_mapping_reference = data_array.attrs.get('grid_mapping')
    if not grid_mapping_reference:
        raise MissingDimensionAttribute(data_array.name, 'grid_mapping')

    grid_mapping_attributes = granule_varinfo.get_missing_variable_attributes(
        grid_mapping_reference
    )
    if not grid_mapping_attributes:
        raise InvalidGridMappingReference(grid_mapping_reference)

    geotransform_config = grid_mapping_attributes.get('master_geotransform', None)
    if not geotransform_config:
        raise MissingDimensionAttribute(data_array.name, 'master_geotransform')

    return geotransform_config
