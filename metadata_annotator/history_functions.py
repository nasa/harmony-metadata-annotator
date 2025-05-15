"""Module with history functions."""

import os
import re
from datetime import UTC, datetime
from urllib.parse import parse_qs, unquote

import xarray as xr
from varinfo import VarInfoFromNetCDF4

from metadata_annotator.exceptions import MissingDimensionVariable

PROGRAM = 'Harmony Metadata Annotator'


def update_history_metadata(datatree: xr.DataTree) -> None:
    """Update the history global attribute of the DataTree.

    If either an existing History or history global attribute exists, append
    information as a new line to the existing value. Otherwise create a new
    attribute called "history".
    """
    history_attribute_name, existing_history = read_history_attrs(datatree)
    write_history_attrs(datatree, history_attribute_name, existing_history)


def read_history_attrs(datatree: xr.DataTree) -> tuple[str, str]:
    """Read history attribute."""
    if 'History' in datatree.attrs:
        history_attribute_name = 'History'
        existing_history = datatree.attrs['History']
    elif 'history' in datatree.attrs:
        history_attribute_name = 'history'
        existing_history = datatree.attrs['history']
    else:
        history_attribute_name = 'history'
        existing_history = None
    return history_attribute_name, existing_history


def write_history_attrs(
    datatree: xr.DataTree, history_attribute_name: str, existing_history: str
) -> None:
    """Write history attribute."""
    new_history_line = ' '.join(
        [
            datetime.now(UTC).isoformat(),
            PROGRAM,
            get_semantic_version(),
        ]
    )
    datatree.attrs[history_attribute_name] = '\n'.join(
        filter(None, [existing_history, new_history_line])
    )


def get_start_index_from_history(
    dimension_index_map: dict[str, int], dimension_variable_path: str
) -> int:
    """Return the start index from the dimension index map."""
    if dimension_variable_path in dimension_index_map.keys():
        return dimension_index_map[dimension_variable_path]
    return 0


def get_dimension_index_map(
    datatree: xr.DataTree,
    dimension_variables: list[str],
    granule_var_info: VarInfoFromNetCDF4,
) -> dict[str, int]:
    """Return dimension path to start index mapping."""
    try:
        if not any(
            datatree[dim].attrs.get('corner_point_offsets')
            == 'history_subset_index_ranges'
            for dim in dimension_variables
        ):
            return {}

    except KeyError as e:
        raise MissingDimensionVariable(str(e)) from e

    # Read history attribute and retrieve all the variables with their corresponding
    # index ranges.
    variable_start_indices_map = parse_start_indices_from_history_attr(datatree)

    # Retrieve the mapping of requested variables and the corresponding dimension paths
    variable_dimension_map = get_variable_dimension_map(granule_var_info)

    # Retrieve the mapping from the dimension variable to the start index
    dimension_index_map = get_dim_index_from_var_dim_map(
        variable_dimension_map, variable_start_indices_map
    )

    return dimension_index_map


def parse_start_indices_from_history_attr(datatree: xr.DataTree) -> dict[str, str]:
    """Return dictionary of variables with corresponding start index."""
    _, existing_history = read_history_attrs(datatree)

    if not existing_history:
        return {}

    decoded_string = unquote(existing_history)
    parsed_data = parse_qs(decoded_string)
    opendap_entry = next(iter(parsed_data.values()), ())

    if not opendap_entry:
        return {}

    index_range_entries = ((opendap_entry[0].split('=')[1]).rstrip()).split(';')
    variable_start_indices_map = {}
    for entry in index_range_entries:
        variable, dim_indices = get_index_range_substring(entry)
        start_dims = [int(dim.split(':')[0]) if dim else 0 for dim in dim_indices]
        variable_start_indices_map[variable] = start_dims
    return variable_start_indices_map


def get_variable_dimension_map(
    granule_var_info: VarInfoFromNetCDF4,
) -> dict[tuple, str]:
    """Return a mapping from dimensions list to a requested variable."""
    var_dim_map = {
        dimlist: list(varlist)[0]
        for dimlist, varlist in granule_var_info.group_variables_by_dimensions().items()
    }

    return var_dim_map


def get_dim_index_from_var_dim_map(
    variable_dimension_map: dict[tuple, str],
    variable_start_indices_map: dict[str, list[int]],
) -> dict[str, int]:
    """Returns the mapping from dimension to start index.

    This is retrieved from the variable dimension map and the variable with index map.
    """
    dimension_index_map = {}

    # variable_dimension_map has a dictionary of dimensions in a tuple with
    # a corresponding variable path name
    for variable_dimensions, variable_path in variable_dimension_map.items():
        # variable_start_indices_map has a dictionary with requested variable names
        # and corresponding subsetted start indices
        if variable_path in variable_start_indices_map:
            start_indices = variable_start_indices_map[variable_path]

            # update the map to only contain the dimension_path and start index
            dimension_index_map.update(zip(variable_dimensions, start_indices))

    return dimension_index_map


def get_index_range_substring(index_range_string: str) -> tuple[str, list]:
    """Return variable and index range."""
    variable = ''
    if not index_range_string:
        return variable, []

    start_index = -1
    end_index = -1
    start_char = '['
    end_char = ']'

    # Gets the index to the starting char '[' for the index ranges.
    for i, char in enumerate(index_range_string):
        if char == start_char:
            start_index = i
            break

    # Gets the index to the ending char ']' for the index ranges.
    for i in reversed(range(len(index_range_string))):
        if index_range_string[i] == end_char:
            end_index = i
            break

    if start_index != -1 and end_index != -1 and start_index <= end_index:
        # The variable is before the index range start.
        variable = index_range_string[0:start_index]
        # Get all the index ranges in square brackets
        index_range_dims = re.findall(
            r'\[(.*?)\]', index_range_string[start_index : end_index + 1]
        )
        return variable, index_range_dims
    return variable, []


def get_semantic_version() -> str:
    """Parse the service_version.txt to get the semantic version number."""
    current_directory = os.path.dirname(os.path.abspath('__file__'))
    path = os.path.join(current_directory, 'docker/service_version.txt')
    with open(path, encoding='utf-8') as file_handler:
        semantic_version = file_handler.read().strip()
        return semantic_version
    return 'Version not found'
