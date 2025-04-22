"""Tests for metadata_annotator.annotate.py."""

import xarray as xr
from freezegun import freeze_time

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

        # units had no overrides, so should be unchanged
        assert (
            test_datatree['/variable_one'].attrs['units']
            == 'seconds since 2000-00-00T12:34:56'
        )

        # coordinates was updated, so should be the value in the configuration file
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
):
    """Confirm that a granule has all metadata updated as expected.

    This test uses the "TEST01" collection short name to ensure that all rules
    in the configuration file are applied to the input granule, and metadata
    attributes are either added, updated or deleted.

    """
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
