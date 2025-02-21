"""Set up fixtures for unit tests."""

from datetime import datetime
from os.path import join as path_join
from shutil import copy, move, rmtree
from tempfile import mkdtemp

from harmony_service_lib.message import Message as HarmonyMessage
from harmony_service_lib.util import bbox_to_geometry
from netCDF4 import Dataset
from pystac import Asset, Catalog, Item
from pytest import fixture
from varinfo import VarInfoFromNetCDF4


@fixture(scope='function')
def temp_dir() -> str:
    """A temporary directory for test isolation."""
    temp_directory = mkdtemp()
    yield temp_directory
    rmtree(temp_directory)


@fixture(scope='function')
def temp_output_file_path(temp_dir) -> str:
    """The file path for an output file in the test temporary directory."""
    return path_join(temp_dir, 'annotated_output.nc')


@fixture(scope='function')
def varinfo_config_file(temp_dir) -> str:
    """Return file path of configuration file."""
    config_path = path_join(temp_dir, 'earthdata_varinfo_test_config.json')
    copy('tests/data/earthdata_varinfo_test_config.json', config_path)
    return config_path


@fixture(scope='function')
def sample_varinfo(sample_netcdf4_file, varinfo_config_file) -> VarInfoFromNetCDF4:
    """Create sample VarInfoFromNetCDF4 instance."""
    return VarInfoFromNetCDF4(
        sample_netcdf4_file, config_file=varinfo_config_file, short_name='TEST01'
    )


@fixture(scope='function')
def sample_netcdf4_file(temp_dir) -> str:
    """Create a sample NetCDF-4 file."""
    file_name = path_join(temp_dir, 'test_input.nc')

    with Dataset(file_name, 'w') as ds:
        ds.setncatts(
            {
                'short_name': 'TEST01',
                'update': 'original value',
                'delete': 'attribute should not exist',
            }
        )

        variable_one = ds.createVariable('variable_one', 'S1')
        variable_one.setncatts(
            {
                'coordinates': 'original value',
                'units': 'seconds since 2000-00-00T12:34:56',
            }
        )

        subgroup = ds.createGroup('/sub_group')
        subgroup.setncatts(
            {
                'delete': 'attribute should not exist',
                'update': 'original value',
            }
        )

        variable_two = ds.createVariable('/sub_group/variable_two', 'S1')
        variable_two.setncatts(
            {
                'coordinates': 'time latitude longitude',
                'delete': 'attribute needs to be deleted',
            }
        )

        variable_three = ds.createVariable('/variable_three', 'S1')
        variable_three.setncatts(
            {
                'coordinates': 'time latitude longitude',
                'notes': 'this variable does not match any override rules',
            }
        )

    return file_name


@fixture(scope='function')
def downloaded_netcdf4_file(temp_dir, sample_netcdf4_file) -> str:
    """Provide a downloaded file path more like Harmony.

    This makes the downloaded filename distinct from the STAC Asset.href, so
    that errors do not occur when trying to copy the file to its own location.

    """
    downloaded_file_name = path_join(temp_dir, 'SHA256_scramble.nc')
    move(sample_netcdf4_file, downloaded_file_name)
    return downloaded_file_name


@fixture(scope='session')
def stac_asset_href() -> str:
    """Return a URL for a STAC Asset."""
    return 'https://www.example.com/test_input.nc'


@fixture(scope='session')
def sample_stac(stac_asset_href) -> Catalog:
    """Create a sample SpatioTemporal Asset Catalog (STAC).

    Spatial and temporal information is not used by the service, so default
    values are used.

    """
    catalog = Catalog(id='input catalog', description='test input')

    item = Item(
        id='input granule',
        bbox=[-180, -90, 180, 90],
        geometry=bbox_to_geometry([-180, -90, 180, 90]),
        datetime=datetime(2000, 1, 2, 3, 4, 5),
        properties={'props': 'None'},
    )

    item.add_asset(
        'input data',
        Asset(
            stac_asset_href,
            media_type='application/x-netcdf4',
            roles=['data'],
        ),
    )
    catalog.add_item(item)

    return catalog


@fixture(scope='session')
def sample_harmony_message() -> HarmonyMessage:
    """Create a sample Harmony message to send to service."""
    return HarmonyMessage(
        {
            'accessToken': 'fake_token',
            'callback': 'https://example.com/',
            'sources': [{'collection': 'C1234-EEDTEST', 'shortName': 'TEST01'}],
            'stagingLocation': 's3://bucket/staging-location',
            'user': 'fakeuser',
        }
    )
