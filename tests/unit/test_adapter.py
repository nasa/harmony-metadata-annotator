"""Tests for metadata_annotator.annotate.py.

harmony_serivce.adapter is imported as adapter to enable mocking of the
VARINFO_CONFIG_FILE global variable.

"""

from os.path import basename

import pytest
import xarray as xr
from freezegun import freeze_time
from harmony_service_lib.util import config

import harmony_service.adapter as adapter
from harmony_service.adapter import MetadataAnnotatorAdapter


@freeze_time('2000-01-02T03:04:05')
def test_process_item(
    sample_netcdf4_file,
    downloaded_netcdf4_file,
    expected_output_netcdf4_file,
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

    # Override creation of dimension_index_map
    get_dimension_index_map_mock = mocker.patch(
        'metadata_annotator.annotate.get_dimension_index_map'
    )
    get_dimension_index_map_mock.return_value = None

    # Use the sample NetCDF-4 fixture as the downloaded file
    download_mock = mocker.patch('harmony_service.adapter.download')
    download_mock.return_value = downloaded_netcdf4_file

    stage_mock = mocker.patch('harmony_service.adapter.stage')
    stage_mock.return_value = 's3://bucketname/staged-location'

    get_spatial_dimension_variables_mock = mocker.patch(
        'metadata_annotator.annotate.get_spatial_dimension_variables'
    )
    get_spatial_dimension_variables_mock.return_value = set()

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
    with (
        xr.open_dataset(sample_netcdf4_file, decode_times=False) as results_datatree,
        xr.open_dataset(
            expected_output_netcdf4_file, decode_times=False
        ) as expected_datatree,
    ):
        assert results_datatree.identical(expected_datatree)


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
