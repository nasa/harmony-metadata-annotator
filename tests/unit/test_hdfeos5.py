"""Tests for metadata_annotator hdfeos5."""

from os.path import join as path_join

import numpy as np
import pytest
import xarray as xr

from metadata_annotator.annotate import annotate_granule
from metadata_annotator.exceptions import (
    InvalidHDFEOS5GridDefinition,
    UnexpectedCoordinateValues,
)
from metadata_annotator.hdfeos5 import (
    get_grid_definition,
    get_struct_metadata,
    set_cell_center_values,
    set_center_registration,
)

CONFIG_FILE = 'metadata_annotator/earthdata_varinfo_config.json'
GRID_NAME = 'MOD_Grid_Seaice_1km'
GRID_PATH = f'/HDFEOS/GRIDS/{GRID_NAME}'
# StructMetadata of MOD29P1D.A2025237.h04v08.007.2026196115719.h5,
# which stores pixel upper-left corners in XDim and YDim.
STRUCT_METADATA = (
    'GROUP=SwathStructure\nEND_GROUP=SwathStructure\nGROUP=GridStructure\n'
    '\tGROUP=GRID_1\n'
    '\t\tGridName="MOD_Grid_Seaice_1km"\n'
    '\t\tXDim=951\n'
    '\t\tYDim=951\n'
    '\t\tUpperLeftPointMtrs=(-5244627.580500,1430352.976500)\n'
    '\t\tLowerRightMtrs=(-4291058.929500,476784.325500)\n'
    '\t\tGridOrigin=HE5_HDFE_GD_UL\n'
    '\t\tProjection=HE5_GCTP_LAMAZ\n'
    '\t\tProjParams=(6371228,0,0,0,0,90000000,0,0,0,0,0,0,0)\n'
    '\t\tSphereCode=-1\n'
    '\t\tGROUP=Dimension\n\t\tEND_GROUP=Dimension\n'
    '\t\tGROUP=DataField\n\t\tEND_GROUP=DataField\n'
    '\tEND_GROUP=GRID_1\nEND_GROUP=GridStructure\nEND\n'
)


def with_registration(value: str) -> str:
    """Return the sample StructMetadata declaring a pixel registration."""
    return STRUCT_METADATA.replace(
        '\t\tSphereCode=-1\n', f'\t\tSphereCode=-1\n\t\tPixelRegistration={value}\n'
    )


def build_datatree(struct_metadata: str, offset: float = 0.0) -> xr.DataTree:
    """Return an HDF-EOS5 style DataTree; offset 0.0 gives corners, 0.5 centers."""
    grid = get_grid_definition(struct_metadata, GRID_NAME)
    values = []
    for axis, name in enumerate(('XDim', 'YDim')):
        first = grid['UpperLeftPointMtrs'][axis]
        step = (grid['LowerRightMtrs'][axis] - first) / grid[name]
        values.append(first + (np.arange(grid[name]) + offset) * step)

    return xr.DataTree.from_dict(
        {
            '/HDFEOS INFORMATION': xr.Dataset(
                {'StructMetadata.0': ((), np.bytes_(struct_metadata.encode('ascii')))}
            ),
            GRID_PATH: xr.Dataset(
                coords={
                    'XDim': (
                        'XDim',
                        values[0],
                        {'standard_name': 'projection_x_coordinate', 'units': 'm'},
                    ),
                    'YDim': (
                        'YDim',
                        values[1],
                        {'standard_name': 'projection_y_coordinate', 'units': 'm'},
                    ),
                }
            ),
            f'{GRID_PATH}/Data Fields': xr.Dataset(
                {
                    'Ice_Surface_Temperature': (
                        ('YDim', 'XDim'),
                        np.zeros((values[1].size, values[0].size), dtype=np.uint16),
                    )
                }
            ),
        }
    )


@pytest.fixture(name='sample_hdfeos5_file')
def fixture_sample_hdfeos5_file(temp_dir) -> str:
    """Write a MOD29P1D style granule holding corner-valued XDim and YDim."""
    file_path = path_join(temp_dir, 'MOD29P1D_sample.h5')
    build_datatree(STRUCT_METADATA).to_netcdf(file_path, engine='h5netcdf')
    return file_path


def test_get_grid_definition():
    """Grid settings are parsed from StructMetadata."""
    assert get_grid_definition(STRUCT_METADATA, GRID_NAME) == {
        'XDim': 951,
        'YDim': 951,
        'UpperLeftPointMtrs': (-5244627.5805, 1430352.9765),
        'LowerRightMtrs': (-4291058.9295, 476784.3255),
        'PixelRegistration': None,
    }


def test_get_grid_definition_geographic_grid():
    """Geographic grids are rejected."""
    struct_metadata = STRUCT_METADATA.replace('HE5_GCTP_LAMAZ', 'HE5_GCTP_GEO')
    with pytest.raises(InvalidHDFEOS5GridDefinition):
        get_grid_definition(struct_metadata, GRID_NAME)


@pytest.mark.parametrize(
    'variable_name, expected_first, expected_last',
    [
        ('XDim', -5244126.2300, -4291560.2800),
        ('YDim', 1429851.6260, 477285.6760),
    ],
)
def test_set_cell_center_values(variable_name, expected_first, expected_last):
    """Corner values become cell centers; dtype and attributes are kept."""
    datatree = build_datatree(STRUCT_METADATA)
    variable_path = f'{GRID_PATH}/{variable_name}'
    attributes = dict(datatree[variable_path].attrs)

    set_cell_center_values(datatree, variable_path)

    values = datatree[variable_path].values
    assert values[0] == pytest.approx(expected_first, abs=1e-4)
    assert values[-1] == pytest.approx(expected_last, abs=1e-4)
    assert values.dtype == np.float64
    assert datatree[variable_path].attrs == attributes
    child_values = datatree[f'{GRID_PATH}/Data Fields'].coords[variable_name]
    np.testing.assert_array_equal(child_values.values, values)


def test_set_cell_center_values_already_centers():
    """Cell-center values are left unchanged."""
    datatree = build_datatree(STRUCT_METADATA, 0.5)
    expected = datatree[f'{GRID_PATH}/XDim'].values.copy()

    set_cell_center_values(datatree, f'{GRID_PATH}/XDim')

    np.testing.assert_array_equal(datatree[f'{GRID_PATH}/XDim'].values, expected)


def test_set_cell_center_values_corner_registration():
    """Corner values are rewritten and corner registration becomes center."""
    datatree = build_datatree(with_registration('HE5_HDFE_CORNER'))

    set_cell_center_values(datatree, f'{GRID_PATH}/XDim')

    assert datatree[f'{GRID_PATH}/XDim'].values[0] == pytest.approx(
        -5244126.2300, abs=1e-4
    )
    assert get_struct_metadata(datatree) == with_registration('HE5_HDFE_CENTER')


def test_set_center_registration_split_parts():
    """A value spanning two StructMetadata parts is replaced in both."""
    struct_metadata = with_registration('HE5_HDFE_CORNER')
    split = struct_metadata.index('HE5_HDFE_CORNER') + 10
    datatree = build_datatree(struct_metadata)
    datatree['/HDFEOS INFORMATION'] = xr.Dataset(
        {
            'StructMetadata.0': ((), np.str_(struct_metadata[:split])),
            'StructMetadata.1': ((), np.str_(struct_metadata[split:])),
        }
    )

    set_center_registration(datatree, GRID_NAME)

    group = datatree['/HDFEOS INFORMATION']
    assert group['StructMetadata.0'].values.dtype == np.dtype(f'<U{split}')
    assert get_struct_metadata(datatree) == with_registration('HE5_HDFE_CENTER')


def test_set_cell_center_values_unexpected_values():
    """Values matching neither corners nor centers raise an exception."""
    datatree = build_datatree(STRUCT_METADATA, 0.25)
    with pytest.raises(UnexpectedCoordinateValues):
        set_cell_center_values(datatree, f'{GRID_PATH}/XDim')


def test_annotate_granule_hdfeos5_cell_centers(
    sample_hdfeos5_file, temp_output_file_path
):
    """The annotated output holds cell centers and no temporary attribute."""
    annotate_granule(
        sample_hdfeos5_file, temp_output_file_path, CONFIG_FILE, 'MOD29P1D'
    )

    with xr.open_datatree(
        temp_output_file_path, decode_coords=False, engine='h5netcdf'
    ) as output:
        x_values = output[f'{GRID_PATH}/XDim']
        assert float(x_values[0]) == pytest.approx(-5244126.2300, abs=1e-4)
        assert float(output[f'{GRID_PATH}/YDim'][0]) == pytest.approx(
            1429851.6260, abs=1e-4
        )
        assert '_*hdfeos5_cell_centers' not in x_values.attrs
