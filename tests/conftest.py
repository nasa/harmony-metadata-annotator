"""Set up fixtures for unit tests."""

from datetime import datetime
from os.path import join as path_join
from shutil import copy, move, rmtree
from tempfile import mkdtemp

import numpy as np
import xarray as xr
from harmony_service_lib.message import Message as HarmonyMessage
from harmony_service_lib.util import bbox_to_geometry
from pystac import Asset, Catalog, Item
from pytest import fixture
from varinfo import VarInfoFromNetCDF4

from metadata_annotator.history_functions import PROGRAM, get_semantic_version


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

    sample_datatree = xr.DataTree(
        dataset=xr.Dataset(
            attrs={
                'short_name': 'TEST01',
                'update': 'original value',
                'delete': 'attribute should not exist',
            },
            data_vars={
                'variable_one': xr.DataArray(
                    np.array([]),
                    attrs={
                        '_FillValue': -9999.0,
                        'coordinates': 'original_value',
                        'units': 'seconds since 2000-00-00T12:34:56',
                    },
                ),
                'variable_three': xr.DataArray(
                    np.array([]),
                    attrs={
                        '_FillValue': -9999.0,
                        'coordinates': 'time latitude longitude',
                        'notes': 'this variable does not match any override rules',
                    },
                ),
            },
        ),
    )

    sample_datatree['/sub_group'] = xr.Dataset(
        attrs={
            'delete': 'attribute should not exist',
            'update': 'original value',
        },
        data_vars={
            'variable_two': xr.DataArray(
                np.array([]),
                attrs={
                    '_FillValue': -9999.0,
                    'coordinates': 'time latitude longitude',
                    'delete': 'attribute needs to be deleted',
                },
            )
        },
    )
    sample_datatree.to_netcdf(file_name, encoding=None)
    return file_name


@fixture(scope='function')
def expected_output_netcdf4_file(temp_dir) -> str:
    """NetCDF-4 file with metadata updated per earthdata-varinfo config file."""
    file_name = path_join(temp_dir, 'expected_output.nc')

    sample_datatree = xr.DataTree(
        dataset=xr.Dataset(
            attrs={
                'short_name': 'TEST01',
                'update': 'corrected root group value',
                'addition': 'new root group value',
                'history': f'2000-01-02T03:04:05+00:00 {PROGRAM} '
                f'{get_semantic_version()}',
            },
            data_vars={
                'EASE2_north_polar_projection_36km': xr.DataArray(
                    b'',
                    attrs={
                        'false_easting': 0.0,
                        'false_northing': 0.0,
                        'grid_mapping_name': 'lambert_azimuthal_equal_area',
                        'latitude_of_projection_origin': 90.0,
                        'longitude_of_projection_origin': 0.0,
                        'master_geotransform': [-9000000, 36000, 0, 9000000, 0, -36000],
                    },
                ),
                'variable_one': xr.DataArray(
                    np.array([]),
                    attrs={
                        '_FillValue': -9999.0,
                        'coordinates': 'time latitude longitude',
                        'grid_mapping': '/EASE2_north_polar_projection_36km',
                        'units': 'seconds since 2000-00-00T12:34:56',
                    },
                ),
                'variable_three': xr.DataArray(
                    np.array([]),
                    attrs={
                        '_FillValue': -9999.0,
                        'coordinates': 'time latitude longitude',
                        'notes': 'this variable does not match any override rules',
                    },
                ),
            },
        ),
    )

    sample_datatree['/sub_group'] = xr.Dataset(
        attrs={
            'update': 'corrected subgroup value',
            'nested_addition': 'new subgroup value',
        },
        data_vars={
            'variable_two': xr.DataArray(
                np.array([]),
                attrs={
                    '_FillValue': -9999.0,
                    'coordinates': 'time latitude longitude',
                },
            )
        },
    )
    sample_datatree.to_netcdf(file_name, encoding=None)
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


@fixture(scope='function')
def sample_netcdf4_file_test02(temp_dir) -> str:
    """Create a sample NetCDF-4 file."""
    file_name = path_join(temp_dir, 'test_input_02.nc')

    sample_datatree = xr.DataTree(
        dataset=xr.Dataset(
            attrs={
                'short_name': 'TEST02',
            },
            data_vars={
                'x': xr.DataArray(
                    np.array([0, 1, 2]),
                    attrs={
                        'standard_name': 'projection_x_coordinate',
                        'subset_index_reference': 'EASE_column_index',
                        'grid_mapping': '/EASE2_north_polar_projection_36km',
                    },
                    dims=['x'],
                ),
                'y': xr.DataArray(
                    np.array([0, 1, 2]),
                    attrs={
                        'standard_name': 'projection_y_coordinate',
                        'subset_index_reference': 'EASE_row_index',
                        'grid_mapping': '/EASE2_north_polar_projection_36km',
                    },
                    dims=['y'],
                ),
                'variable_one': xr.DataArray(
                    np.ones((3, 3)),
                    attrs={
                        'standard_name': 'invalid_standard_name',
                        'grid_mapping': '/EASE2_variable_missing_geotransform',
                    },
                    dims=['y', 'x'],
                ),
                'variable_two': xr.DataArray(
                    np.ones((3, 3)),
                    attrs={},
                    dims=['y', 'x'],
                ),
                'EASE_column_index': xr.DataArray(
                    np.array([[5, 6, 7], [5, 6, 7], [5, 6, 7]]),
                    attrs={},
                    dims=['y', 'x'],
                ),
                'EASE_row_index': xr.DataArray(
                    np.array([[5, 6, 7], [5, 6, 7], [5, 6, 7]]),
                    attrs={},
                    dims=['y', 'x'],
                ),
            },
        ),
    )

    sample_datatree.to_netcdf(file_name, encoding=None)
    return file_name


@fixture(scope='function')
def sample_varinfo_test02(
    sample_netcdf4_file_test02, varinfo_config_file
) -> VarInfoFromNetCDF4:
    """Create sample VarInfoFromNetCDF4 instance."""
    return VarInfoFromNetCDF4(
        sample_netcdf4_file_test02, config_file=varinfo_config_file, short_name='TEST02'
    )


@fixture(scope='function')
def sample_netcdf4_file_test03(temp_dir) -> str:
    """Create a sample NetCDF-4 file to test index ranges from history."""
    file_name = path_join(temp_dir, 'test_input_03.nc')

    sample_datatree = xr.DataTree(
        dataset=xr.Dataset(
            attrs={
                'short_name': 'TEST03',
            },
            data_vars={
                'x': xr.DataArray(
                    np.array([0, 1, 2]),
                    attrs={
                        'standard_name': 'projection_x_coordinate',
                        'corner_point_offsets': 'history_subset_index_ranges',
                        'grid_mapping': '/EASE2_north_polar_projection_36km',
                    },
                    dims=['x'],
                ),
                'y': xr.DataArray(
                    np.array([0, 1, 2]),
                    attrs={
                        'standard_name': 'projection_y_coordinate',
                        'corner_point_offsets': 'history_subset_index_ranges',
                        'grid_mapping': '/EASE2_north_polar_projection_36km',
                    },
                    dims=['y'],
                ),
                'test_variable': xr.DataArray(
                    np.ones((3, 3)),
                    attrs={},
                    dims=['y', 'x'],
                ),
            },
        ),
    )

    sample_datatree.to_netcdf(file_name, encoding=None)
    return file_name


@fixture(scope='function')
def sample_varinfo_test03(
    sample_netcdf4_file, varinfo_config_file
) -> VarInfoFromNetCDF4:
    """Create sample VarInfoFromNetCDF4 instance."""
    return VarInfoFromNetCDF4(
        sample_netcdf4_file, config_file=varinfo_config_file, short_name='TEST03'
    )


@fixture(scope='function')
def sample_netcdf4_file_test04(temp_dir) -> str:
    """Create a sample NetCDF-4 file for testing updating dimension variables."""
    file_name = path_join(temp_dir, 'test_input_04.nc')

    sample_datatree = xr.DataTree(xr.Dataset())

    sample_datatree['/sub_group'] = xr.Dataset(
        attrs={'short_name': 'TEST04'},
        data_vars={
            'x': xr.DataArray(np.array([0, 1, 2]), attrs={}, dims=['x']),
            'y': xr.DataArray(np.array([0, 1, 2]), attrs={}, dims=['y']),
            'variable_one': xr.DataArray(
                np.ones((3, 3)),
                attrs={},
                dims=['y', 'x'],
            ),
        },
    )

    sample_datatree.to_netcdf(file_name, encoding=None)
    return file_name


@fixture(scope='function')
def sample_varinfo_test04(
    sample_netcdf4_file, varinfo_config_file
) -> VarInfoFromNetCDF4:
    """Create sample VarInfoFromNetCDF4 instance."""
    return VarInfoFromNetCDF4(
        sample_netcdf4_file, config_file=varinfo_config_file, short_name='TEST04'
    )
