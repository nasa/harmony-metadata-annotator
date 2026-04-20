"""Module with history functions."""

import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import parse_qs, unquote

import xarray as xr
from varinfo import VarInfoFromNetCDF4

from metadata_annotator.exceptions import MissingDimensionVariable

# Values needed for history_json attribute
HISTORY_JSON_SCHEMA = (
    'https://harmony.earthdata.nasa.gov/schemas/history/0.1.0/history-v0.1.0.json'
)
PROGRAM = 'Harmony Metadata Annotator'
PROGRAM_REF = 'https://github.com/nasa/harmony-metadata-annotator'


def update_history_metadata(input_file_name: str, datatree: xr.DataTree) -> None:
    """Update the history-related metadata global attribute of the DataTree.

    This method updates two forms of history metadata:

    • The 'history_json' attribute is updated by appending a new structured
      record describing the current operation, including the
      timestamp, program name, version, request URL, and processing parameters.

    • The human‑readable `history` (or `History`) global attribute is updated
      by appending a new line summarizing the execution. If no
      history attribute exists, a new one is created.

    Parameters
    ----------
    input_file_name : str
        Path to the input NetCDF4 file
    datatree : xr.DataTree
        Allow datatree history-related metadata modification

    Returns:
    -------
    None
        This function modifies the file in place and does not return a value.

    """
    history_attribute_name, existing_history = read_history_attrs(datatree)

    request_url = get_request_url_attribute(input_file_name, datatree)

    # Create new history_json attribute and append existing_history
    new_history_json_record = create_history_json_record(request_url)

    output_history_json = read_history_json_attrs(datatree)

    # Append `history_json_record` to the existing `history_json` array:
    output_history_json.append(new_history_json_record)

    # Update existing `history_json` array:
    datatree.attrs['history_json'] = json.dumps(output_history_json)

    # Create a new history for Metadata Annotator history
    new_history_line = ' '.join(
        [
            new_history_json_record['date_time'],
            new_history_json_record['program'],
            new_history_json_record['version'],
        ]
    )

    # Append new Metadata Annotator history to existing history
    output_history = '\n'.join(filter(None, [existing_history, new_history_line]))

    # Update history attribute with new Metadata Annotator entry
    datatree.attrs[history_attribute_name] = output_history


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


def get_request_url_attribute(input_file_name: str, datatree: xr.DataTree) -> str:
    """Extract the request URL from the file's `history_json` attribute.

    This function reads the `history_json` global attribute—if present—and
    attempts to extract the `request_url` value from its `parameters` field.
    The method supports both dictionary- and list-based parameter structures.
    If a request URL is found, any query string (text after '?') is removed.
    If no valid request URL is available, the function returns the file's
    own filename as a fallback.

    Parameters
    ----------
    input_file_name : str
        Path to the input NetCDF4 file
    datatree : xr.DataTree
        Allow datatree history-related metadata modification

    Returns:
    -------
    str
        The extracted request URL without query parameters, or the file's
        filename if no request URL is present.

    """
    if 'history_json' not in datatree.attrs:
        return input_file_name

    history_json = json.loads(datatree.attrs['history_json'])

    if isinstance(history_json, list):
        history_json = history_json[0]

    parameters = history_json.get('parameters')

    if isinstance(parameters, dict):
        return parameters.get('request_url', input_file_name)

    if isinstance(parameters, list):
        for item in parameters:
            if isinstance(item, dict) and 'request_url' in item:
                request_url = item['request_url'].split('?', 1)[0]
                return request_url

    return input_file_name


def create_history_json_record(granule_url: str) -> dict:
    """Create a serializable dictionary for the `history_json` attribute.

    This function assembles a serializable dictionary capturing metadata
    about the current operation. The record includes the execution
    timestamp, program name, version, processing parameters, and the source
    granule URL.

    Parameters
    ----------
    granule_url : str
        The URL of the input granule from which the output file was derived.
        Stored in the `derived_from` field.

    Returns:
    -------
    Dict
        A fully populated dictionary representing a `history_json` record,
        ready to be serialized and written to the output file.

    """
    history_json_record = {
        '$schema': HISTORY_JSON_SCHEMA,
        'date_time': datetime.now(timezone.utc).isoformat(),
        'program': PROGRAM,
        'version': get_semantic_version(),
        'derived_from': granule_url,
        'program_ref': PROGRAM_REF,
    }

    return history_json_record


def read_history_json_attrs(datatree: xr.DataTree) -> list:
    """Retrieve and normalize the `history_json` global attribute.

    This function checks whether the file contains a `history_json`
    attribute. If present, the JSON content is parsed and returned as a
    list of history records. The attribute may contain either a single
    JSON object or a list of objects; in both cases, the return value is
    normalized to a list. If the attribute does not exist, an empty list
    is returned.

    Parameters
    ----------
    datatree : xr.DataTree
        datatree object from which the
        `history_json` attribute should be read.

    Returns:
    -------
    List
        A list of parsed `history_json` records. Returns an empty list
        when the file does not contain a `history_json` attribute.

    """
    output_history_json = []

    if 'history_json' in datatree.attrs:
        old_history_json = json.loads(datatree.attrs['history_json'])
        if isinstance(old_history_json, list):
            output_history_json = old_history_json
        else:
            # Single `history_json_record` element.
            output_history_json = [old_history_json]

    return output_history_json


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
    # Check that all dimension variables exist in the datatree
    for dim in dimension_variables:
        try:
            datatree[dim]
        except KeyError as e:
            raise MissingDimensionVariable(str(e)) from e

    if not any(
        granule_var_info.get_missing_variable_attributes(dim).get(
            '_*corner_point_offsets'
        )
        == 'history_subset_index_ranges'
        for dim in dimension_variables
    ):
        return {}

    # Read history attribute and retrieve all the variables with their corresponding
    # index ranges.
    variable_start_indices_map = parse_start_indices_from_history_attr(datatree)

    # Retrieve the mapping of requested variables and the corresponding dimension paths
    variable_dimension_map = get_variable_dimension_map(
        granule_var_info, datatree, dimension_variables
    )
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
    datatree: xr.DataTree,
    dimension_variables: set[str],
) -> dict[tuple, str]:
    """Return a mapping from dimensions list to a requested variable.

    Note that this function utilizes a temporary solution for location up-level (shared)
    dimension variables by updating the dimension map returned by the earthdata-varinfo
    method `group_variables_by_dimensions`. This should remain place until
    earthdata-varinfo supports up-level dimensions.
    """
    var_dim_map = {
        dimlist: list(varlist)[0]
        for dimlist, varlist in granule_var_info.group_variables_by_dimensions().items()
    }

    def construct_dim_path(parent_path: str, dim_name: str) -> str:
        """Construct the full path to the dimension variable."""
        return f'{parent_path}/{dim_name}' if parent_path != '/' else f'/{dim_name}'

    # Identify dimensions that have been created up-level and update map
    updated_map = {}
    for dim_list, var_path in var_dim_map.items():
        new_dim_list = []
        for dim in dim_list:
            if dim in dimension_variables:
                new_dim_list.append(dim)
                continue

            group_path, dimension_name = os.path.split(dim)
            new_dim = None
            for parent in datatree[group_path].parents:
                parent_dim_path = construct_dim_path(parent.path, dimension_name)
                if parent_dim_path in dimension_variables:
                    new_dim = parent_dim_path
                    break

            if not new_dim:
                raise MissingDimensionVariable(dim)
            new_dim_list.append(new_dim)

        updated_map[tuple(new_dim_list)] = var_path

    return updated_map


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
