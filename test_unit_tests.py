"""Test script to test unit tests
"""
import xarray as xr
from metadata_annotator.annotate import (
    update_dimension_names, 
    update_dimension_variables, 
    update_metadata_attributes_for_data_array,

)
from varinfo import VarInfoFromNetCDF4


def get_dimension_variables(data_tree: xr.DataTree, dimension_variables: set[str]):
    """Return dimension variables."""
    for name, node in data_tree.children.items():
        dt = data_tree[name]
        if dt.dims:
            dt_dim_dict = dict(dt.dims)
            dimension_variables.update(f'/{name}/{dim}' for dim in dt_dim_dict.keys())
        if node.children:
            get_dimension_variables(node, dimension_variables)

    return dimension_variables

input_file = "harmony-metadata-annotator/tests/data/SC_SPL3FTP_spatially_subsetted.nc4"
with xr.open_datatree(input_file) as datatree:
    for name, node in datatree.children.items():
        print(name)
    for group in datatree.groups:
        print(group)
            
    dimension_variables = get_dimension_variables(datatree, set())
    assert dimension_variables == set(
            [
                '/Freeze_Thaw_Retrieval_Data_Global/dim0',
                '/Freeze_Thaw_Retrieval_Data_Global/dim1',
                '/Freeze_Thaw_Retrieval_Data_Global/dim2',
            ]
        )


with xr.open_datatree('harmony-metadata-annotator/tests/data/SC_SPL3FTP_spatially_subsetted.nc4') as datatree:
        granule_varinfo = VarInfoFromNetCDF4(
            'harmony-metadata-annotator/tests/data/SC_SPL3FTP_spatially_subsetted.nc4',
            short_name='SPL3FTP',
            config_file='harmony-metadata-annotator/metadata_annotator/earthdata_varinfo_config.json',
        )
        # rename the dim variables
        da = datatree['/Freeze_Thaw_Retrieval_Data_Global/surface_flag']
        renamed_da = da.rename({'dim0': 'am_pm', 'dim1': 'y', 'dim2': 'x'})
        datatree['/Freeze_Thaw_Retrieval_Data_Global/surface_flag'] = renamed_da
        ds = xr.Dataset(datatree['/Freeze_Thaw_Retrieval_Data_Global'])
        da_dim = ds['x']
        update_metadata_attributes_for_data_array(
            da_dim, '/Freeze_Thaw_Retrieval_Data_Global/x', granule_varinfo
        )
        assert set(da_dim.attrs) == set(
            [
                'axis',
                'dimensions',
                'grid_mapping',
                'long_name',
                'standard_name',
                'type',
                'units',
            ]
        )


with xr.open_datatree('harmony-metadata-annotator/tests/data/SC_SPL3FTP_spatially_subsetted.nc4') as datatree:
        granule_varinfo = VarInfoFromNetCDF4(
            'harmony-metadata-annotator/tests/data/SC_SPL3FTP_spatially_subsetted.nc4',
            short_name='SPL3FTP',
            config_file='harmony-metadata-annotator/metadata_annotator/earthdata_varinfo_config.json',
        )
        #rename the dim variables
        da = datatree['/Freeze_Thaw_Retrieval_Data_Global/surface_flag']
        renamed_da = da.rename({'dim0':'am_pm', 'dim1':'y', 'dim2':'x'})
        datatree['/Freeze_Thaw_Retrieval_Data_Global/surface_flag'] = renamed_da
        
        update_dimension_variables(
            datatree, '/Freeze_Thaw_Retrieval_Data_Global/y', granule_varinfo
        )

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
            ]
        )


with xr.open_datatree('harmony-metadata-annotator/tests/data/SC_SPL3FTP_spatially_subsetted.nc4') as datatree:
        variable_to_update = '/Freeze_Thaw_Retrieval_Data_Global/transition_direction'

        datatree[variable_to_update] = datatree[variable_to_update].assign_attrs(dimensions='y x')

        update_dimension_names(datatree, variable_to_update)

        # check dimension renames
        assert set(
            datatree['/Freeze_Thaw_Retrieval_Data_Global/transition_direction'].dims
        ) == set(['y', 'x'])
