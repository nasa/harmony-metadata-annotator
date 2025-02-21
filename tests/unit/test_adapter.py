"""Tests for metadata_annotator.annotate.py.

harmony_serivce.adapter is imported as adapter to enable mocking of the
VARINFO_CONFIG_FILE global variable.

"""

from os.path import basename

import pytest
from freezegun import freeze_time
from harmony_service_lib.util import config
from netCDF4 import Dataset

import harmony_service.adapter as adapter
from harmony_service.adapter import MetadataAnnotatorAdapter
from metadata_annotator.annotate import PROGRAM, VERSION


@freeze_time('2000-01-02T03:04:05')
def test_process_item(
    sample_netcdf4_file,
    downloaded_netcdf4_file,
    sample_stac,
    stac_asset_href,
    sample_harmony_message,
    varinfo_config_file,
    temp_dir,
    mocker,
):
    """Confirm normal processing occurs."""
    # Override the working directory with temporary test directory
    temp_dir_mock = mocker.patch('harmony_service.adapter.TemporaryDirectory')
    temp_dir_mock.return_value.__enter__.return_value = temp_dir

    # Override the configuration file with the test configuration file
    mocker.patch.object(adapter, 'VARINFO_CONFIG_FILE', varinfo_config_file)

    # Use the sample NetCDF-4 fixture as the downloaded file
    download_mock = mocker.patch('harmony_service.adapter.download')
    download_mock.return_value = downloaded_netcdf4_file

    stage_mock = mocker.patch('harmony_service.adapter.stage')
    stage_mock.return_value = 's3://bucketname/staged-location'

    # Create and run the service
    harmony_config = config(validate=False)

    metadata_annotator = MetadataAnnotatorAdapter(
        sample_harmony_message, config=harmony_config, catalog=sample_stac
    )
    _, output_stac = metadata_annotator.invoke()

    # Ensure mocked functions to download input and stage output were called
    download_mock.assert_called_once_with(
        stac_asset_href,
        temp_dir,
        logger=mocker.ANY,
        cfg=harmony_config,
        access_token=sample_harmony_message.accessToken,
    )

    stage_mock.asset_called_once_with(
        sample_netcdf4_file,
        basename(sample_netcdf4_file),
        'application/x-netcdf',
        location=sample_harmony_message.stagingLocation,
        logger=mocker.ANY,
        cfg=harmony_config,
    )

    # Check output STAC
    output_items = list(output_stac.get_items(recursive=True))
    assert len(output_items) == 1
    assert output_items[0].to_dict()['assets'] == {
        'data': {
            'href': 's3://bucketname/staged-location',
            'type': 'application/x-netcdf',
            'title': 'staged-location',
            'roles': ['data'],
        }
    }

    # Check output file
    with Dataset(sample_netcdf4_file, 'r') as test_results:
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


def test_process_item_exception(
    sample_stac,
    stac_asset_href,
    sample_harmony_message,
    varinfo_config_file,
    temp_dir,
    mocker,
):
    """Confirm correct exception handling occurs."""
    # Override the working directory with temporary test directory
    temp_dir_mock = mocker.patch('harmony_service.adapter.TemporaryDirectory')
    temp_dir_mock.return_value.__enter__.return_value = temp_dir

    # Override the configuration file with the test configuration file
    mocker.patch.object(adapter, 'VARINFO_CONFIG_FILE', varinfo_config_file)

    # Use the sample NetCDF-4 fixture as the downloaded file
    download_mock = mocker.patch('harmony_service.adapter.download')
    download_mock.side_effect = RuntimeError('Download went wrong')

    stage_mock = mocker.patch('harmony_service.adapter.stage')
    stage_mock.return_value = 's3://bucketname/staged-location'

    # Create and run the service
    harmony_config = config(validate=False)

    metadata_annotator = MetadataAnnotatorAdapter(
        sample_harmony_message, config=harmony_config, catalog=sample_stac
    )

    with pytest.raises(RuntimeError):
        metadata_annotator.invoke()
