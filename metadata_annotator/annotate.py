"""Main module for business logic of the Harmony Metadata Annotator."""

import os
import re
from shutil import copy

import numpy as np
import xarray as xr
from varinfo import VarInfoFromNetCDF4

from metadata_annotator.exceptions import (
    InvalidDimensionAttribute,
    InvalidDimensionsConfiguration,
    InvalidGridMappingReference,
    InvalidSubsetIndexShape,
    MissingDimensionAttribute,
    MissingDimensionVariable,
    MissingStartIndexConfiguration,
    MissingSubsetIndexReference,
)
from metadata_annotator.geotransform import compute_dimension_scale
from metadata_annotator.history_functions import (
    get_dimension_index_map,
    get_start_index_from_history,
    update_history_metadata,
)


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

        if variables_to_create:
            # Find candidate variables that might be in our configuration for creation,
            # and get the references to those variables. Such variables without
            # references, should not be created. Currently, we only support creating
            # "empty" variables with attributes, thus only grid_mapping and
            # ancillary_variables.
            candidate_reference_attributes = ['grid_mapping', 'ancillary_variables']
            candidate_referenced_variables = get_referenced_variables(
                granule_varinfo, candidate_reference_attributes
            )
            referenced_variables_to_create = (
                variables_to_create & candidate_referenced_variables
            )
            for variable_path in referenced_variables_to_create:
                create_new_variable(datatree, variable_path, granule_varinfo)

            dimension_variables = get_dimension_variables(datatree)
            dimension_variables_to_create = variables_to_create & dimension_variables
            if dimension_variables_to_create:
                update_dimension_variables(
                    datatree, dimension_variables, granule_varinfo
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

    temp_attributes = {
        attribute_name: attribute_value
        for attribute_name, attribute_value in matching_overrides.items()
        if is_temporary_attribute(attribute_name)
    }

    attributes_to_update = {
        attribute_name: attribute_value
        for attribute_name, attribute_value in matching_overrides.items()
        if not is_temporary_attribute(attribute_name) and attribute_value is not None
    }

    attributes_to_delete = (
        set(matching_overrides.keys())
        - set(attributes_to_update.keys())
        - set(temp_attributes.keys())
    )

    datatree[group_or_variable_path].attrs.update(attributes_to_update)

    for attribute in attributes_to_delete:
        try:
            del datatree[group_or_variable_path].attrs[attribute]
        except KeyError:
            # Trying to delete a non-existent attribute should not fail
            pass


def is_temporary_attribute(attribute_name: str) -> bool:
    """Determine if an attribute is temporary.

    Temporary attributes are attributes defined in earthdata-varinfo that are intended
    to be used by the metadata-annotator, but not written to the output file. The prefix
    '_*' is used to indicate whether an attribute is temporary or not.
    """
    return attribute_name.startswith('_*') and len(attribute_name) > 2


def update_group_and_variable_attributes(
    datatree: xr.DataTree,
    items_to_update: set[str],
    granule_varinfo: VarInfoFromNetCDF4,
) -> None:
    """Update attributes for existing variables and groups based on configuration."""
    for item_to_update in items_to_update:
        update_metadata_attributes(
            datatree,
            item_to_update,
            granule_varinfo,
        )
        # If dimensions override attribute exists, rename the pseudo dimension names.
        if datatree[item_to_update].attrs.get('dimensions', ''):
            update_dimension_names(datatree, item_to_update)


def update_dimension_names(datatree: xr.DataTree, variable_to_update: str) -> None:
    """Update the dimension names."""
    data_array = datatree[variable_to_update]
    rename_dim_list = data_array.attrs.get('dimensions', '').split()

    # The list exists so renaming is required.
    if rename_dim_list:
        if len(data_array.dims) != len(rename_dim_list):
            raise InvalidDimensionsConfiguration(
                variable_to_update, len(rename_dim_list), len(data_array.dims)
            )

        # Rename from source data dimension names to VarInfo dimension names
        # and limit to the number of dimensions given in rename list.
        source_dims = data_array.dims[: len(rename_dim_list)]
        rename_dict = dict(zip(source_dims, rename_dim_list))
        datatree[variable_to_update] = data_array.rename(rename_dict)


def create_new_variable(
    datatree: xr.DataTree, variable_path: str, granule_varinfo: VarInfoFromNetCDF4
) -> None:
    """Create a new variable in the datatree as configured in the json file."""
    datatree[variable_path] = xr.DataArray(data=b'')
    update_metadata_attributes(
        datatree,
        variable_path,
        granule_varinfo,
    )


def get_dimension_variables(datatree: xr.DataTree) -> set[str]:
    """Return distinct dimensions as dimension-variable names with full path.

    This is excluding dimensions defined in ancestor nodes (not datatree.dims)
    and assuming all dimension variables are at the group level
    (not up-level, not root level)
    ToDo: resolve for shared up-level or root-level dimensions
    """
    dimension_variables = set()

    for node in datatree.subtree:
        node_ds = node.dataset

        for data_var in node_ds.data_vars:
            dimension_variables.update(
                [f'{node.path}/{dim}' for dim in node_ds[data_var].dims]
            )

    return dimension_variables


def update_dimension_variables(
    datatree: xr.DataTree,
    dimension_variables: set[str],
    granule_varinfo: VarInfoFromNetCDF4,
) -> None:
    """Update the attributes and data values (spatial only) for dimension variables."""
    for dimension in dimension_variables:
        update_dimension_variable_attributes(datatree, dimension, granule_varinfo)

    spatial_dimension_variables = get_spatial_dimension_variables(
        datatree, dimension_variables
    )
    if spatial_dimension_variables:
        dimension_index_map = get_dimension_index_map(
            datatree, dimension_variables, granule_varinfo
        )
        update_spatial_dimension_values(
            datatree,
            spatial_dimension_variables,
            granule_varinfo,
            dimension_index_map,
        )


def update_dimension_variable_attributes(
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
        if not is_temporary_attribute(attribute_name) and attribute_value is not None
    }

    data_array.attrs.update(attributes_to_update)


def get_spatial_dimension_variables(
    datatree: xr.DataTree, variables: set[str] = None
) -> set[str]:
    """Return a set of identified spatial dimension variables."""
    valid_dim_standard_names = ('projection_x_coordinate', 'projection_y_coordinate')
    return set(
        variable_path
        for variable_path in variables
        if datatree[variable_path].attrs.get('standard_name', None)
        in valid_dim_standard_names
    )


def update_spatial_dimension_values(
    datatree: xr.DataTree,
    dimension_variables: set[str],
    granule_varinfo: VarInfoFromNetCDF4,
    dimension_index_map: dict[str, int] = None,
) -> None:
    """Update the spatial dimension variable values to the computed dimension scale."""
    for variable_path in dimension_variables:
        try:
            dim_data_array = datatree[variable_path]
        except KeyError as e:
            raise MissingDimensionVariable(variable_path) from e

        grid_start_index = get_grid_start_index(
            datatree, dimension_index_map, variable_path, granule_varinfo
        )

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
    datatree: xr.DataTree,
    dimension_index_map: dict[str, int],
    dimension_variable_path: str,
    granule_varinfo: VarInfoFromNetCDF4,
) -> tuple[int, int]:
    """Determine the grid offset for a given dimension.

    The method used to determine the grid offset index is determined based off the
    dimension's attributes configured in earthdata-varinfo.

    """
    var_attributes = granule_varinfo.get_missing_variable_attributes(
        dimension_variable_path
    )
    subset_index_reference = var_attributes.get('_*subset_index_reference', None)
    if subset_index_reference:
        return get_start_index_from_row_col_variable(datatree, subset_index_reference)

    if (
        var_attributes.get('_*corner_point_offsets', None)
        == 'history_subset_index_ranges'
    ):
        return get_start_index_from_history(
            dimension_index_map, dimension_variable_path
        )

    raise MissingStartIndexConfiguration(dimension_variable_path)


def get_start_index_from_row_col_variable(
    datatree: xr.DataTree, subset_index_reference: str
) -> tuple[int, int]:
    """Return the grid start index from a row or column index variable.

    The subset_index_reference must correspond to a 2D variable in the datatree.
    The value at the [0, 0] is returned as the grid start index.
    """
    try:
        row_col_variable = datatree[subset_index_reference]
    except KeyError as e:
        raise MissingSubsetIndexReference(subset_index_reference) from e

    # To be improved - extend to support 3D variables
    if row_col_variable.ndim != 2:
        raise InvalidSubsetIndexShape(subset_index_reference)

    return row_col_variable.values[0][0]


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

    geotransform_config = grid_mapping_attributes.get('_*master_geotransform', None)
    if not geotransform_config:
        raise MissingDimensionAttribute(data_array.name, '_*master_geotransform')

    return geotransform_config


def get_referenced_variables(
    granule_varinfo: VarInfoFromNetCDF4, reference_attributes: list[str]
) -> set[str]:
    """Return a set of variable names referenced by the given attributes."""
    referenced_variables = set()

    all_variables = granule_varinfo.get_all_variables()
    for attribute in reference_attributes:
        referenced_variables.update(
            granule_varinfo.get_references_for_attribute(all_variables, attribute)
        )

    return referenced_variables
