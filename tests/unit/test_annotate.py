"""Tests for metadata_annotator.annotate.py."""

import numpy as np
import pytest
import xarray as xr
from freezegun import freeze_time
from varinfo import VarInfoFromNetCDF4

from metadata_annotator.annotate import (
    PROGRAM,
    VERSION,
    annotate_granule,
    create_new_variables,
    get_dimension_variables,
    get_geotransform_config,
    get_grid_start_index,
    get_matching_groups_and_variables,
    get_spatial_dimension_type,
    get_spatial_dimension_variables,
    get_start_index_from_row_col_variable,
    is_exact_path,
    update_dimension_names,
    update_dimension_variable,
    update_group_and_variable_attributes,
    update_history_metadata,
    update_metadata_attributes,
    update_metadata_attributes_for_data_array,
    update_spatial_dimension_values,
)
from metadata_annotator.exceptions import (
    InvalidDimensionAttribute,
    InvalidGridMappingReference,
    InvalidSubsetIndexShape,
    MissingDimensionAttribute,
    MissingStartIndexConfiguration,
    MissingSubsetIndexReference,
)


def test_is_exact_path_is_exact():
    """Returns True when the input is a path with no regular expression syntax."""
    assert is_exact_path('/path/one')


def test_is_exact_path_wild_card():
    """Returns False when the input has '.*' to match multiple characters."""
    assert not is_exact_path('/path/.*')


def test_is_exact_path_alternates():
    """Returns False when the input has '(one|two)', indicating alternates."""
    assert not is_exact_path('/(path_one|path_two)/variable')


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
            == f'2000-01-02T03:04:05+00:00 {PROGRAM} {VERSION}'
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
            f'2000-01-02T03:04:05+00:00 {PROGRAM} {VERSION}'
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
            f'2000-01-02T03:04:05+00:00 {PROGRAM} {VERSION}'
        )


def test_update_metadata_attributes_variable(sample_netcdf4_file, sample_varinfo):
    """Check that attributes are added and updated."""
    with xr.open_datatree(sample_netcdf4_file, decode_times=False) as test_datatree:
        # First call the function under test:
        update_metadata_attributes(test_datatree, '/variable_one', sample_varinfo)

        # Check outputs from the function:
        assert set(test_datatree['/variable_one'].attrs.keys()) == set(
            ['coordinates', 'grid_mapping', 'units']
        )

        # The units had no overrides, so should be unchanged.
        assert (
            test_datatree['/variable_one'].attrs['units']
            == 'seconds since 2000-00-00T12:34:56'
        )

        # The coordinates was updated, so should be the value in the configuration file
        assert (
            test_datatree['/variable_one'].attrs['coordinates']
            == 'time latitude longitude'
        )

        # grid_mapping is a new attribute added due to the configuration file
        assert (
            test_datatree['/variable_one'].attrs['grid_mapping']
            == '/EASE2_north_polar_projection_36km'
        )


def test_update_metadata_attributes_deletion(sample_netcdf4_file, sample_varinfo):
    """Check that an existing attribute can be deleted.

    Also ensure that no error is raised when trying to delete an attribute that does
    not exist. This tests also ensures that the function can handle nested
    variables.

    The `decode_coords` kwarg has been used to ensure `xarray` doesn't remove
    the `coordinates` metadata attribute and use it to define internal `xarray`
    objects instead.

    """
    with xr.open_datatree(
        sample_netcdf4_file, decode_times=False, decode_coords=False
    ) as test_datatree:
        # First call the function under test:
        update_metadata_attributes(
            test_datatree, '/sub_group/variable_two', sample_varinfo
        )

        # Check outputs from the function:
        # Only coordinates should remain as "delete" should have been removed
        assert set(test_datatree['/sub_group/variable_two'].attrs.keys()) == set(
            ['coordinates']
        )

        # coordinates had no overrides, so should be unchanged
        assert (
            test_datatree['/sub_group/variable_two'].attrs['coordinates']
            == 'time latitude longitude'
        )


def test_get_matching_groups_and_variables(sample_varinfo):
    """Ensure variables matching the override rules, and missing variables are found."""
    matching_items, missing_variables = get_matching_groups_and_variables(
        sample_varinfo
    )

    # Each of the following matches a rule from the configuration file, trying
    # to check: the root group, a sub group, a variable in the root group and
    # a nested variable.
    assert matching_items == set(
        ['/', '/sub_group', '/variable_one', '/sub_group/variable_two']
    )

    # The /EASE2_north_polar_projection_36km variable is specifically included in the
    # configuration file to test missing variable behaviour.
    assert missing_variables == set(
        [
            '/EASE2_north_polar_projection_36km',
        ]
    )


@freeze_time('2000-01-02T03:04:05+00:00')
def test_annotate_granule(
    sample_netcdf4_file,
    expected_output_netcdf4_file,
    temp_output_file_path,
    varinfo_config_file,
    mocker,
):
    """Confirm that a granule has all metadata updated as expected.

    This test uses the "TEST01" collection short name to ensure that all rules
    in the configuration file are applied to the input granule, and metadata
    attributes are either added, updated or deleted.

    """
    get_spatial_dimension_variables_mock = mocker.patch(
        'metadata_annotator.annotate.get_spatial_dimension_variables'
    )
    get_spatial_dimension_variables_mock.return_value = set()

    annotate_granule(
        sample_netcdf4_file, temp_output_file_path, varinfo_config_file, 'TEST01'
    )

    with (
        xr.open_datatree(temp_output_file_path, decode_times=False) as results_datatree,
        xr.open_datatree(
            expected_output_netcdf4_file, decode_times=False
        ) as expected_datatree,
    ):
        assert results_datatree.identical(expected_datatree)


def test_annotate_granule_no_changes(
    sample_netcdf4_file,
    temp_output_file_path,
    varinfo_config_file,
):
    """Confirm that a granule is unchanged if there are no overrides for it.

    The collection short name is set to something that will not match any of
    the configuration file overrides.

    """
    annotate_granule(
        sample_netcdf4_file,
        temp_output_file_path,
        varinfo_config_file,
        'OTHER_SHORT_NAME',
    )

    with (
        xr.open_datatree(sample_netcdf4_file, decode_times=False) as expected_datatree,
        xr.open_datatree(temp_output_file_path, decode_times=False) as results_datatree,
    ):
        assert results_datatree.identical(expected_datatree)


def test_update_group_and_variable_attributes() -> None:
    """Confirm the attributes are updated for existing variables.

    This is based on configuration including pseudo dimension variables.

    """
    with xr.open_datatree('tests/data/SC_SPL3FTP_spatially_subsetted.nc4') as datatree:
        items_to_update = [
            '/Freeze_Thaw_Retrieval_Data_Global/surface_flag',
        ]

        granule_varinfo = VarInfoFromNetCDF4(
            'tests/data/SC_SPL3FTP_spatially_subsetted.nc4',
            short_name='SPL3FTP',
            config_file='metadata_annotator/earthdata_varinfo_config.json',
        )
        update_group_and_variable_attributes(datatree, items_to_update, granule_varinfo)

        # Check attributes expected are added.
        assert all(
            item
            in datatree['/Freeze_Thaw_Retrieval_Data_Global/surface_flag'].attrs.keys()
            for item in ['grid_mapping', 'dimensions']
        )

        # Check dimension renames are as expected.
        assert set(
            datatree['/Freeze_Thaw_Retrieval_Data_Global/surface_flag'].dims
        ) == set(['am_pm', 'y', 'x'])


def test_update_dimension_names() -> None:
    """Verify that the dimension names are renamed as expected."""
    with xr.open_datatree('tests/data/SC_SPL3FTP_spatially_subsetted.nc4') as datatree:
        variable_to_update = '/Freeze_Thaw_Retrieval_Data_Global/transition_direction'
        datatree[variable_to_update] = datatree[variable_to_update].assign_attrs(
            dimensions='y x'
        )
        update_dimension_names(datatree, variable_to_update)

        # Check dimension renames are as expected.
        assert set(
            datatree['/Freeze_Thaw_Retrieval_Data_Global/transition_direction'].dims
        ) == set(['y', 'x'])


def test_create_new_variables() -> None:
    """Test if new variables are successfully created."""
    with xr.open_datatree('tests/data/SC_SPL3FTP_spatially_subsetted.nc4') as datatree:
        variable_to_create = '/EASE2_global_projection_36km'

        granule_varinfo = VarInfoFromNetCDF4(
            'tests/data/SC_SPL3FTP_spatially_subsetted.nc4',
            short_name='SPL3FTP',
            config_file='metadata_annotator/earthdata_varinfo_config.json',
        )
        create_new_variables(datatree, variable_to_create, granule_varinfo)

        # Check if the new variable is created.
        assert 'EASE2_global_projection_36km' in datatree['/'].data_vars

        # Check if attributes are updated for the variable.
        assert set(datatree['/EASE2_global_projection_36km'].attrs.keys()) == set(
            [
                'false_easting',
                'false_northing',
                'grid_mapping_name',
                'longitude_of_central_meridian',
                'master_geotransform',
                'standard_parallel',
            ]
        )


def test_get_dimension_variables() -> set[str]:
    """Ensure return of dimension variables."""
    with xr.open_datatree('tests/data/SC_SPL3FTP_spatially_subsetted.nc4') as datatree:
        dimension_variables = get_dimension_variables(datatree, set())
        assert dimension_variables == set(
            [
                '/Freeze_Thaw_Retrieval_Data_Global/dim0',
                '/Freeze_Thaw_Retrieval_Data_Global/dim1',
                '/Freeze_Thaw_Retrieval_Data_Global/dim2',
            ]
        )


def test_update_dimension_variable() -> None:
    """Ensure attributes of a dimension variable are updated as expected."""
    with xr.open_datatree('tests/data/SC_SPL3FTP_spatially_subsetted.nc4') as datatree:
        granule_varinfo = VarInfoFromNetCDF4(
            'tests/data/SC_SPL3FTP_spatially_subsetted.nc4',
            short_name='SPL3FTP',
            config_file='metadata_annotator/earthdata_varinfo_config.json',
        )
        # Rename the dim variables.
        da = datatree['/Freeze_Thaw_Retrieval_Data_Global/surface_flag']
        renamed_da = da.rename({'dim0': 'am_pm', 'dim1': 'y', 'dim2': 'x'})
        datatree['/Freeze_Thaw_Retrieval_Data_Global/surface_flag'] = renamed_da

        update_dimension_variable(
            datatree, '/Freeze_Thaw_Retrieval_Data_Global/y', granule_varinfo
        )
        # Ensure that the attributes are updated.
        assert set(
            datatree['/Freeze_Thaw_Retrieval_Data_Global'].dataset['y'].attrs
        ) == set(
            [
                'axis',
                'dimensions',
                'grid_mapping',
                'long_name',
                'standard_name',
                'type',
                'units',
                'corner_point_offsets',
            ]
        )


def test_update_metadata_attributes_for_data_array() -> None:
    """Update the metadata attributes on the supplied group or variable.

    The attributes are updated on the data array based on the metadata
    overrides matched by earthdata-varinfo for the requested path.

    """
    with xr.open_datatree('tests/data/SC_SPL3FTP_spatially_subsetted.nc4') as datatree:
        granule_varinfo = VarInfoFromNetCDF4(
            'tests/data/SC_SPL3FTP_spatially_subsetted.nc4',
            short_name='SPL3FTP',
            config_file='metadata_annotator/earthdata_varinfo_config.json',
        )
        # Rename the dimension variables.
        da = datatree['/Freeze_Thaw_Retrieval_Data_Global/surface_flag']
        renamed_da = da.rename({'dim0': 'am_pm', 'dim1': 'y', 'dim2': 'x'})
        datatree['/Freeze_Thaw_Retrieval_Data_Global/surface_flag'] = renamed_da
        ds = xr.Dataset(datatree['/Freeze_Thaw_Retrieval_Data_Global'])
        da_dim = ds['x']
        update_metadata_attributes_for_data_array(
            da_dim, '/Freeze_Thaw_Retrieval_Data_Global/x', granule_varinfo
        )
        # Ensure that the expected attributes are updated.
        assert set(da_dim.attrs) == set(
            [
                'axis',
                'dimensions',
                'grid_mapping',
                'long_name',
                'standard_name',
                'type',
                'units',
                'corner_point_offsets',
            ]
        )


def test_update_spatial_dimension_values(
    sample_netcdf4_file_test02, sample_varinfo_test02
) -> None:
    """Ensure spatial dimension values are updated as expected."""
    with xr.open_datatree(
        sample_netcdf4_file_test02, decode_times=False
    ) as test_datatree:
        variables = {'/x', '/y'}
        update_spatial_dimension_values(test_datatree, variables, sample_varinfo_test02)
        expected_x_result = np.array([-8802000, -8766000, -8730001], dtype=np.float64)
        expected_y_result = np.array([8802000, 8766000, 8730000], dtype=np.float64)
        assert np.allclose(test_datatree['x'], expected_x_result)
        assert np.allclose(test_datatree['y'], expected_y_result)


def test_get_spatial_dimension_variables(sample_netcdf4_file_test02) -> None:
    """Ensure only spatial variable dimensions are returned."""
    with xr.open_datatree(
        sample_netcdf4_file_test02, decode_times=False
    ) as test_datatree:
        variables = {'/x', '/y', '/am_pm'}
        assert get_spatial_dimension_variables(test_datatree, variables) == {'/x', '/y'}


def test_get_spatial_dimension_variables_no_matches(sample_netcdf4_file_test02) -> None:
    """Ensure an empty set is returned when no spatial dimensions are present."""
    with xr.open_datatree(
        sample_netcdf4_file_test02, decode_times=False
    ) as test_datatree:
        variables = {'/am_pm'}
        assert get_spatial_dimension_variables(test_datatree, variables) == set()


def test_get_grid_start_index_uses_subset_index_reference(
    sample_netcdf4_file_test02,
) -> None:
    """Ensure the expected grid start index is returned for a given dimension."""
    with xr.open_datatree(
        sample_netcdf4_file_test02, decode_times=False
    ) as test_datatree:
        assert get_grid_start_index(test_datatree, test_datatree['x']) == 5


def test_get_grid_start_index_missing_configuration(sample_netcdf4_file_test02) -> None:
    """Ensure the expected exception is raised when required configuration is missing.

    The method used to determine the grid offset index is determined based off the
    dimension's attributes configured in earthdata-varinfo. Currently, the attribute
    'subset_index_reference' is the only supported attribute. If it is missing, the
    'MissingStartIndexConfiguration' should be raised.

    """
    with xr.open_datatree(
        sample_netcdf4_file_test02, decode_times=False
    ) as test_datatree:
        with pytest.raises(MissingStartIndexConfiguration):
            get_grid_start_index(test_datatree, test_datatree['am_pm'])


def test_get_start_index_from_row_col_variable(sample_netcdf4_file_test02) -> None:
    """Ensure the expected start index is returned for a given row/col variable."""
    with xr.open_datatree(
        sample_netcdf4_file_test02, decode_times=False
    ) as test_datatree:
        assert (
            get_start_index_from_row_col_variable(test_datatree, 'EASE_column_index')
            == 5
        )


def test_get_start_index_from_row_col_variable_missing_reference(
    sample_netcdf4_file_test02,
) -> None:
    """Ensure the expected exception is raised when the index reference is invalid."""
    with xr.open_datatree(
        sample_netcdf4_file_test02, decode_times=False
    ) as test_datatree:
        with pytest.raises(MissingSubsetIndexReference):
            get_start_index_from_row_col_variable(test_datatree, 'missing_variable')


def test_get_start_index_from_row_col_variable_invalid_index_shape(
    sample_netcdf4_file_test02,
) -> None:
    """Ensure the expected exception is raised when index variable shape is invalid."""
    with xr.open_datatree(
        sample_netcdf4_file_test02, decode_times=False
    ) as test_datatree:
        with pytest.raises(InvalidSubsetIndexShape):
            get_start_index_from_row_col_variable(test_datatree, 'x')


def test_get_spatial_dimension_type(sample_netcdf4_file_test02) -> None:
    """Ensure the correct spatial dimension type is returned."""
    with xr.open_datatree(
        sample_netcdf4_file_test02, decode_times=False
    ) as test_datatree:
        assert get_spatial_dimension_type(test_datatree['x']) == 'x'
        assert get_spatial_dimension_type(test_datatree['y']) == 'y'


def test_get_spatial_dimension_type_invalid_standard_name(
    sample_netcdf4_file_test02,
) -> None:
    """Ensure an exception is raised when an invalid standard_name is encountered."""
    with xr.open_datatree(
        sample_netcdf4_file_test02, decode_times=False
    ) as test_datatree:
        with pytest.raises(InvalidDimensionAttribute):
            get_spatial_dimension_type(test_datatree['z'])


def test_get_spatial_dimension_type_missing_standard_name(
    sample_netcdf4_file_test02,
) -> None:
    """Ensure an exception is raised when a standard_name attribute is missing."""
    with xr.open_datatree(
        sample_netcdf4_file_test02, decode_times=False
    ) as test_datatree:
        with pytest.raises(MissingDimensionAttribute):
            get_spatial_dimension_type(test_datatree['am_pm'])


def test_get_geotransform_config(
    sample_netcdf4_file_test02, sample_varinfo_test02
) -> None:
    """Ensure the expected geotransform list is returned."""
    with xr.open_datatree(
        sample_netcdf4_file_test02, decode_times=False
    ) as test_datatree:
        expected_geotransform = [-9000000, 36000, 0, 9000000, 0, -36000]
        assert (
            get_geotransform_config(test_datatree['x'], sample_varinfo_test02)
            == expected_geotransform
        )


def test_get_geotransform_config_missing_grid_mapping_reference(
    sample_netcdf4_file_test02, sample_varinfo_test02
) -> None:
    """Ensure the expected geotransform list is returned."""
    with xr.open_datatree(
        sample_netcdf4_file_test02, decode_times=False
    ) as test_datatree:
        with pytest.raises(MissingDimensionAttribute):
            get_geotransform_config(test_datatree['am_pm'], sample_varinfo_test02)


def test_get_geotransform_config_invalid_grid_mapping_reference(
    sample_varinfo_test02,
) -> None:
    """Ensure an exception is raised when there is an invalid grid_mapping reference."""
    data_array = xr.DataArray([], attrs={'grid_mapping': 'fake_grid_mapping_variable'})
    with pytest.raises(InvalidGridMappingReference):
        get_geotransform_config(data_array, sample_varinfo_test02)


def test_get_geotransform_config_missing_master_geotransform(
    sample_netcdf4_file_test02, sample_varinfo_test02
) -> None:
    """Ensure an exception is raised when master_geotransform attribute is missing."""
    with xr.open_datatree(
        sample_netcdf4_file_test02, decode_times=False
    ) as test_datatree:
        with pytest.raises(MissingDimensionAttribute):
            get_geotransform_config(test_datatree['z'], sample_varinfo_test02)
