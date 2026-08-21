"""Unit and regression tests for the service configuration."""

from os.path import join as path_join

import numpy as np
import xarray as xr
from pytest import fixture
from varinfo import VarInfoFromNetCDF4

SERVICE_CONFIG_FILE = 'metadata_annotator/earthdata_varinfo_config.json'


@fixture(scope='function')
def sample_spl3smp_file(temp_dir) -> str:
    """Create a minimal SPL3SMP-shaped NetCDF-4 file with UTC time strings.

    The arrays are two-dimensional because the SMAP MetadataOverrides
    configure a `y x` dimension layout for these variables.
    """
    file_name = path_join(temp_dir, 'spl3smp_input.nc')

    sample_datatree = xr.DataTree(xr.Dataset())
    sample_datatree['/Soil_Moisture_Retrieval_Data_AM'] = xr.Dataset(
        data_vars={
            'tb_time_utc': xr.DataArray(np.array([['t1', 't2'], ['t3', 't4']])),
            'soil_moisture': xr.DataArray(np.ones((2, 2))),
        },
    )
    sample_datatree['/Soil_Moisture_Retrieval_Data_PM'] = xr.Dataset(
        data_vars={
            'tb_time_utc_pm': xr.DataArray(np.array([['t1', 't2'], ['t3', 't4']])),
            'soil_moisture_pm': xr.DataArray(np.ones((2, 2))),
        },
    )

    sample_datatree.to_netcdf(file_name, encoding=None)
    return file_name


def test_smap_time_utc_variables_not_excluded(sample_spl3smp_file):
    """UTC time string variables must not be excluded for SMAP collections.

    The annotator therefore retains them in its output.
    """
    granule_varinfo = VarInfoFromNetCDF4(
        sample_spl3smp_file,
        config_file=SERVICE_CONFIG_FILE,
        short_name='SPL3SMP',
    )

    excluded_variables = granule_varinfo.get_excluded_science_variables()
    time_utc_excluded = {
        variable for variable in excluded_variables if 'time_utc' in variable
    }
    assert time_utc_excluded == set()
