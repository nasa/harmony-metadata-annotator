"""Tests for metadata_annotator.history_functions.py."""

import pytest
import xarray as xr
from freezegun import freeze_time
from varinfo import VarInfoFromNetCDF4

from metadata_annotator.exceptions import MissingDimensionVariable
from metadata_annotator.history_functions import (
    PROGRAM,
    get_dim_index_from_var_dim_map,
    get_dimension_index_map,
    get_index_range_substring,
    get_semantic_version,
    get_start_index_from_history,
    get_variable_dimension_map,
    parse_start_indices_from_history_attr,
    update_history_metadata,
)


@freeze_time('2000-01-02T03:04:05')
def test_update_history_metadata_no_input_history(sample_netcdf4_file):
    """A new history attribute should be created."""
    with xr.open_datatree(sample_netcdf4_file, decode_times=False) as test_datatree:
        # Invoke the function under test:
        update_history_metadata(test_datatree)

        # Check output from the function:
        assert 'history' in test_datatree.attrs
        assert 'History' not in test_datatree.attrs
        assert (
            test_datatree.attrs['history']
            == f'2000-01-02T03:04:05+00:00 {PROGRAM} {get_semantic_version()}'
        )


@freeze_time('2000-01-02T03:04:05+00:00')
def test_update_history_metadata_append_to_existing(sample_netcdf4_file):
    """An existing history attribute should have a new line added."""
    with xr.open_datatree(sample_netcdf4_file, decode_times=False) as test_datatree:
        # First add a pre-existing history metadata attribute:
        test_datatree.attrs['history'] = '1999-01-01T00 File creation v1'

        # Now invoke the function under test:
        update_history_metadata(test_datatree)

        # Check output from the function:
        assert 'history' in test_datatree.attrs
        assert 'History' not in test_datatree.attrs
        assert test_datatree.attrs['history'] == (
            '1999-01-01T00 File creation v1\n'
            f'2000-01-02T03:04:05+00:00 {PROGRAM} {get_semantic_version()}'
        )


@freeze_time('2000-01-02T03:04:05+00:00')
def test_update_history_metadata_existing_uppercase(sample_netcdf4_file):
    """If History exists instead of history, that should be used."""
    with xr.open_datatree(sample_netcdf4_file, decode_times=False) as test_datatree:
        # First add a history metadata attribute:
        test_datatree.attrs['History'] = '1999-01-01T00 File creation v1'

        # Now invoke the function under test:
        update_history_metadata(test_datatree)

        # Check output from the function:
        assert 'History' in test_datatree.attrs
        assert 'history' not in test_datatree.attrs
        assert test_datatree.attrs['History'] == (
            '1999-01-01T00 File creation v1\n'
            f'2000-01-02T03:04:05+00:00 {PROGRAM} {get_semantic_version()}'
        )


def test_get_index_range_substring() -> None:
    """Ensure that the index range substring is parsed correctly from variable name."""
    # Test a normal order 3D index range.
    idxrange = '/Freeze_Thaw_Retrieval_Data_Global/surface_flag[][16:44][227:278]'
    variable_name, index_ranges = get_index_range_substring(idxrange)
    assert variable_name == '/Freeze_Thaw_Retrieval_Data_Global/surface_flag'
    assert index_ranges == ['', '16:44', '227:278']

    # Test a 2D index range.
    idxrange = '/Freeze_Thaw_Retrieval_Data_Global/transition_direction[16:44][227:278]'
    variable_name, index_ranges = get_index_range_substring(idxrange)
    assert variable_name == '/Freeze_Thaw_Retrieval_Data_Global/transition_direction'
    assert index_ranges == ['16:44', '227:278']

    # Test a 3D not nominal order index range
    idxrange = '/Soil_Moisture_Retrieval_Data_AM/landcover_class[0:26][294:455][]'
    variable_name, index_ranges = get_index_range_substring(idxrange)
    assert variable_name == '/Soil_Moisture_Retrieval_Data_AM/landcover_class'
    assert index_ranges == ['0:26', '294:455', '']

    # Empty string
    idxrange = ''
    variable_name, index_ranges = get_index_range_substring(idxrange)
    assert variable_name == ''
    assert index_ranges == []

    # Invalid format string
    idxrange = 'This is a test for invalid index string format'
    variable_name, index_ranges = get_index_range_substring(idxrange)
    assert variable_name == ''
    assert index_ranges == []


def test_parse_start_indices_from_history_attr(sample_netcdf4_file) -> None:
    """Ensure that the index range from history attribute are retrieved correctly."""
    with xr.open_datatree('tests/data/SC_SPL3FTP_spatially_subsetted.nc4') as datatree:
        idxdict = parse_start_indices_from_history_attr(datatree)
        assert idxdict['/Freeze_Thaw_Retrieval_Data_Global/surface_flag'] == [
            0,
            16,
            227,
        ]
        assert idxdict['/Freeze_Thaw_Retrieval_Data_Global/transition_direction'] == [
            16,
            227,
        ]

    with xr.open_datatree(sample_netcdf4_file, decode_times=False) as test_datatree:
        idxdict = parse_start_indices_from_history_attr(test_datatree)
        assert not idxdict

        test_datatree.attrs['history'] = 'This is a history attribute to test'
        idxdict = parse_start_indices_from_history_attr(test_datatree)
        assert not idxdict


def test_get_variable_dimension_map() -> None:
    """Ensure that the correct dimensions list is returned for requested variables."""
    # with xr.open_datatree('tests/data/SC_SPL3FTP_spatially_subsetted.nc4') as dtree:
    granule_varinfo = VarInfoFromNetCDF4(
        'tests/data/SC_SPL3FTP_spatially_subsetted.nc4',
        short_name='SPL3FTP',
        config_file='metadata_annotator/earthdata_varinfo_config.json',
    )
    variable_dimensions_dict = get_variable_dimension_map(granule_varinfo)
    expected_dimensions = tuple(
        [
            '/Freeze_Thaw_Retrieval_Data_Global/am_pm',
            '/Freeze_Thaw_Retrieval_Data_Global/y',
            '/Freeze_Thaw_Retrieval_Data_Global/x',
        ]
    )

    expected_variables = {
        '/Freeze_Thaw_Retrieval_Data_Global/latitude',
        '/Freeze_Thaw_Retrieval_Data_Global/longitude',
        '/Freeze_Thaw_Retrieval_Data_Global/surface_flag',
    }

    assert variable_dimensions_dict[expected_dimensions] in expected_variables


def test_get_dimension_index_map() -> None:
    """Ensure that the dimensions are returned with the correct subset indices."""
    with xr.open_datatree('tests/data/SC_SPL3FTP_spatially_subsetted.nc4') as datatree:
        granule_varinfo = VarInfoFromNetCDF4(
            'tests/data/SC_SPL3FTP_spatially_subsetted.nc4',
            short_name='SPL3FTP',
            config_file='metadata_annotator/earthdata_varinfo_config.json',
        )
        # Setup the test to make sure it has the updated configuration
        data_set = xr.Dataset(datatree['/Freeze_Thaw_Retrieval_Data_Global'])
        renamed_da = datatree['/Freeze_Thaw_Retrieval_Data_Global/surface_flag'].rename(
            {'dim0': 'am_pm', 'dim1': 'y', 'dim2': 'x'}
        )
        datatree['/Freeze_Thaw_Retrieval_Data_Global/surface_flag'] = renamed_da

        renamed_da = datatree[
            '/Freeze_Thaw_Retrieval_Data_Global/transition_direction'
        ].rename({'dim1': 'y', 'dim2': 'x'})
        datatree['/Freeze_Thaw_Retrieval_Data_Global/transition_direction'] = renamed_da

        data_set = xr.Dataset(datatree['/Freeze_Thaw_Retrieval_Data_Global'])
        data_array = data_set['am_pm']
        datatree['/Freeze_Thaw_Retrieval_Data_Global/am_pm'] = data_array

        data_array = data_set['y'].assign_attrs(
            corner_point_offsets='history_subset_index_ranges'
        )
        datatree['/Freeze_Thaw_Retrieval_Data_Global/y'] = data_array

        data_array = data_set['x'].assign_attrs(
            corner_point_offsets='history_subset_index_ranges'
        )
        datatree['/Freeze_Thaw_Retrieval_Data_Global/x'] = data_array

        dim_dict = get_dimension_index_map(
            datatree,
            [
                '/Freeze_Thaw_Retrieval_Data_Global/am_pm',
                '/Freeze_Thaw_Retrieval_Data_Global/y',
                '/Freeze_Thaw_Retrieval_Data_Global/x',
            ],
            granule_varinfo,
        )

        assert dim_dict['/Freeze_Thaw_Retrieval_Data_Global/am_pm'] == 0
        assert dim_dict['/Freeze_Thaw_Retrieval_Data_Global/y'] == 16
        assert dim_dict['/Freeze_Thaw_Retrieval_Data_Global/x'] == 227

        # If the dimension is not there, it will be a Key Error
        with pytest.raises(MissingDimensionVariable):
            dim_dict = get_dimension_index_map(
                datatree,
                [
                    '/Freeze_Thaw_Retrieval_Data_Global/dim0',
                ],
                granule_varinfo,
            )
        # If the configuration is not there, it will return None
        dim_dict = get_dimension_index_map(
            datatree,
            [
                '/Freeze_Thaw_Retrieval_Data_Global/am_pm',
            ],
            granule_varinfo,
        )
        assert dim_dict is None


def test_get_dim_index_from_variable_dimension_map() -> None:
    """Ensure that the right indices are returned for all the dimensions."""
    variable_dimension_map = {
        (
            '/Freeze_Thaw_Retrieval_Data_Global/am_pm',
            '/Freeze_Thaw_Retrieval_Data_Global/y',
            '/Freeze_Thaw_Retrieval_Data_Global/x',
        ): '/Freeze_Thaw_Retrieval_Data_Global/surface_flag',
        (
            '/Freeze_Thaw_Retrieval_Data_Polar/am_pm',
            '/Freeze_Thaw_Retrieval_Data_Polar/y',
            '/Freeze_Thaw_Retrieval_Data_Polar/x',
        ): '/Freeze_Thaw_Retrieval_Data_Polar/latitude',
    }

    variables_with_index_ranges = {
        '/Freeze_Thaw_Retrieval_Data_Global/surface_flag': [0, 15, 224],
        '/Freeze_Thaw_Retrieval_Data_Global/transition_direction': [15, 224],
        '/Freeze_Thaw_Retrieval_Data_Global/latitude': [0, 15, 224],
        '/Freeze_Thaw_Retrieval_Data_Global/longitude': [0, 15, 224],
        '/Freeze_Thaw_Retrieval_Data_Polar/latitude': [0, 237, 128],
        '/Freeze_Thaw_Retrieval_Data_Polar/longitude': [0, 237, 128],
    }

    dim_index_map = get_dim_index_from_var_dim_map(
        variable_dimension_map, variables_with_index_ranges
    )
    assert dim_index_map['/Freeze_Thaw_Retrieval_Data_Global/y'] == 15
    assert dim_index_map['/Freeze_Thaw_Retrieval_Data_Global/x'] == 224
    assert dim_index_map['/Freeze_Thaw_Retrieval_Data_Polar/y'] == 237
    assert dim_index_map['/Freeze_Thaw_Retrieval_Data_Polar/x'] == 128


def test_get_start_index_from_history() -> None:
    """Ensure that the start index returned for the requested dimension is correct."""
    dim_index_map = {
        '/Freeze_Thaw_Retrieval_Data_Global/y': 15,
        '/Freeze_Thaw_Retrieval_Data_Global/x': 224,
        '/Freeze_Thaw_Retrieval_Data_Polar/y': 237,
        '/Freeze_Thaw_Retrieval_Data_Polar/x': 128,
    }
    assert (
        get_start_index_from_history(
            dim_index_map, '/Freeze_Thaw_Retrieval_Data_Global/x'
        )
        == 224
    )
    # Return 0 if the dimension does not exist
    assert (
        get_start_index_from_history(
            dim_index_map, '/Freeze_Thaw_Retrieval_Data_Global/am_pm'
        )
        == 0
    )
