"""Tests for metadata_annotator.annotate.py."""

from freezegun import freeze_time
from netCDF4 import Dataset

from metadata_annotator.annotate import (
    PROGRAM,
    VERSION,
    annotate_granule,
    get_matching_groups_and_variables,
    is_exact_path,
    update_history_metadata,
    update_metadata_attributes,
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
    with Dataset(sample_netcdf4_file, 'a') as test_input:
        update_history_metadata(test_input)

    with Dataset(sample_netcdf4_file, 'r') as test_output:
        assert 'history' in test_output.ncattrs()
        assert (
            test_output.getncattr('history')
            == f'2000-01-02T03:04:05+00:00 {PROGRAM} {VERSION}'
        )


@freeze_time('2000-01-02T03:04:05+00:00')
def test_update_history_metadata_append_to_existing(sample_netcdf4_file):
    """An existing history attribute should have a new line added."""
    with Dataset(sample_netcdf4_file, 'a') as test_input:
        # First add a history metadata attribute:
        test_input.setncattr('history', '1999-01-01T00 File creation v1')

        # Now invoke the function under test:
        update_history_metadata(test_input)

    with Dataset(sample_netcdf4_file, 'r') as test_output:
        assert 'history' in test_output.ncattrs()
        assert test_output.getncattr('history') == (
            '1999-01-01T00 File creation v1\n'
            f'2000-01-02T03:04:05+00:00 {PROGRAM} {VERSION}'
        )


@freeze_time('2000-01-02T03:04:05+00:00')
def test_update_history_metadata_existing_uppercase(sample_netcdf4_file):
    """If History exists instead of history, that should be used."""
    with Dataset(sample_netcdf4_file, 'a') as test_input:
        # First add a history metadata attribute:
        test_input.setncattr('History', '1999-01-01T00 File creation v1')

        # Now invoke the function under test:
        update_history_metadata(test_input)

    with Dataset(sample_netcdf4_file, 'r') as test_output:
        assert 'History' in test_output.ncattrs()
        assert 'history' not in test_output.ncattrs()
        assert test_output.getncattr('History') == (
            '1999-01-01T00 File creation v1\n'
            f'2000-01-02T03:04:05+00:00 {PROGRAM} {VERSION}'
        )


def test_update_metadata_attributes_variable(sample_netcdf4_file, sample_varinfo):
    """Check that attributes are added and updated."""
    with Dataset(sample_netcdf4_file, 'a') as test_dataset:
        update_metadata_attributes(test_dataset, '/variable_one', sample_varinfo)

    with Dataset(sample_netcdf4_file, 'r') as test_results:
        assert set(test_results['/variable_one'].ncattrs()) == set(
            ['coordinates', 'grid_mapping', 'units']
        )

        # units had no overrides, so should be unchanged
        assert (
            test_results['/variable_one'].getncattr('units')
            == 'seconds since 2000-00-00T12:34:56'
        )

        # coordinates was updated, so should be the value in the configuration file
        assert (
            test_results['/variable_one'].getncattr('coordinates')
            == 'time latitude longitude'
        )

        # grid_mapping is a new attribute added due to the configuration file
        assert (
            test_results['/variable_one'].getncattr('grid_mapping')
            == '/EASE2_polar_projection'
        )


def test_update_metadata_attributes_deletion(sample_netcdf4_file, sample_varinfo):
    """Check that an existing attribute can be deleted.

    Also ensure that no error is raised when trying to delete an attribute that does
    not exist. This tests also ensures that the function can handle nested
    variables.

    """
    with Dataset(sample_netcdf4_file, 'a') as test_dataset:
        update_metadata_attributes(
            test_dataset, '/sub_group/variable_two', sample_varinfo
        )

    with Dataset(sample_netcdf4_file, 'r') as test_results:
        # Only coordinates should remain as "delete" should have been removed
        assert set(test_results['/sub_group/variable_two'].ncattrs()) == set(
            ['coordinates']
        )

        # coordinates had no overrides, so should be unchanged
        assert (
            test_results['/sub_group/variable_two'].getncattr('coordinates')
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

    # The /EASE2_global_projection variable is specifically included in the
    # configuration file to test missing variable behaviour.
    assert missing_variables == set(
        [
            '/EASE2_global_projection',
        ]
    )


@freeze_time('2000-01-02T03:04:05+00:00')
def test_annotate_granule(
    sample_netcdf4_file,
    temp_output_file_path,
    varinfo_config_file,
):
    """Confirm that a granule has all metadata updated as expected.

    This test uses the "TEST01" collection short name to ensure that all rules
    in the configuration file are applied to the input granule, and metadata
    attributes are either added, updated or deleted.

    """
    annotate_granule(
        sample_netcdf4_file, temp_output_file_path, varinfo_config_file, 'TEST01'
    )

    with Dataset(temp_output_file_path, 'r') as test_results:
        # Check all the expected groups and variables are present:
        assert set(test_results.groups.keys()) == set(['sub_group'])
        assert set(test_results.variables.keys()) == set(
            ['variable_one', 'variable_three', 'EASE2_global_projection']
        )
        assert set(test_results['sub_group'].variables.keys()) == set(
            [
                'variable_two',
            ]
        )

        # Check all expected metadata attributes exist with expected values.
        # "update" updated, "addition" added, "history" added, "delete" removed.
        assert test_results.__dict__ == {
            'addition': 'new root group value',
            'history': f'2000-01-02T03:04:05+00:00 {PROGRAM} {VERSION}',
            'short_name': 'TEST01',
            'update': 'corrected root group value',
        }

        # "coordinates" updated, "grid_mapping" added.
        assert test_results['/variable_one'].__dict__ == {
            'coordinates': 'time latitude longitude',
            'grid_mapping': '/EASE2_polar_projection',
            'units': 'seconds since 2000-00-00T12:34:56',
        }

        # No changes to input file.
        assert test_results['/variable_three'].__dict__ == {
            'coordinates': 'time latitude longitude',
            'notes': 'this variable does not match any override rules',
        }

        # Entirely new variable.
        assert test_results['/EASE2_global_projection'].__dict__ == {
            'false_easting': 0.0,
            'false_northing': 0.0,
            'grid_mapping_name': 'lambert_azimuthal_equal_area',
            'latitude_of_projection_origin': 90.0,
            'longitude_of_projection_origin': 0.0,
        }

        # "nested_addition" added, "update" updated, "delete" removed.
        assert test_results['/sub_group'].__dict__ == {
            'nested_addition': 'new subgroup value',
            'update': 'corrected subgroup value',
        }

        # "delete" removed.
        assert test_results['/sub_group/variable_two'].__dict__ == {
            'coordinates': 'time latitude longitude',
        }


def test_annotate_granule_no_changes(
    sample_netcdf4_file,
    temp_output_file_path,
    varinfo_config_file,
):
    """Confirm that a granule is unchanged if there are no overrides for it.

    The collection short name is set to something that will not match any of
    the configuration file overrides.

    Comparisons to expected output are made explicitly in the test, instead of
    comparing to the input file, to prevent matching against a potentially
    mutated input. That shouldn't happen, but this test ensures immunity to
    any such issues.

    """
    annotate_granule(
        sample_netcdf4_file,
        temp_output_file_path,
        varinfo_config_file,
        'OTHER_SHORT_NAME',
    )

    with Dataset(temp_output_file_path, 'r') as test_results:
        # Check all the expected groups and variables are present:
        assert set(test_results.groups.keys()) == set(['sub_group'])
        assert set(test_results.variables.keys()) == set(
            ['variable_one', 'variable_three']
        )
        assert set(test_results['sub_group'].variables.keys()) == set(
            [
                'variable_two',
            ]
        )

        # Check all expected metadata attributes exist with expected values.
        # Some will look odd, as they are the original values from the fixture,
        # most of which are designed to be updated in other tests.
        assert test_results.__dict__ == {
            'short_name': 'TEST01',
            'update': 'original value',
            'delete': 'attribute should not exist',
        }

        assert test_results['/variable_one'].__dict__ == {
            'coordinates': 'original value',
            'units': 'seconds since 2000-00-00T12:34:56',
        }

        assert test_results['/variable_three'].__dict__ == {
            'coordinates': 'time latitude longitude',
            'notes': 'this variable does not match any override rules',
        }

        assert test_results['/sub_group'].__dict__ == {
            'delete': 'attribute should not exist',
            'update': 'original value',
        }

        assert test_results['/sub_group/variable_two'].__dict__ == {
            'coordinates': 'time latitude longitude',
            'delete': 'attribute needs to be deleted',
        }
