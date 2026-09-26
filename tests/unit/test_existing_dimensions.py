"""Exercise dimension-only annotation without creating missing variables."""

import json
from pathlib import Path

import numpy as np
import pytest
import xarray as xr
from varinfo import VarInfoFromNetCDF4

from metadata_annotator.annotate import (
    annotate_granule,
    get_matching_groups_and_variables,
)
from metadata_annotator.exceptions import InvalidDimensionsConfiguration


def make_input_and_config(
    tmp_path: Path,
    group: str,
    new_dims: tuple[str, ...],
    coordinates: bool,
    dimension_override: str | None,
) -> tuple[Path, Path, str, np.ndarray]:
    """Write real input and rules that reference only pre-existing variables."""
    old_dims = tuple(f'old_{index}' for index in range(len(new_dims)))
    shape = (3,) if len(new_dims) == 1 else (2, 3)
    data = np.arange(np.prod(shape), dtype=np.int16).reshape(shape)
    science = xr.DataArray(
        data, dims=old_dims, attrs={'units': 'original', 'notes': 'keep'}
    )
    science.encoding.update({'zlib': True, 'complevel': 2, '_FillValue': -9999})
    dataset = xr.Dataset({'science': science, 'untouched': (('other',), [7, 8])})
    if coordinates:
        dataset = dataset.assign_coords(
            {
                name: np.arange(size) + 10
                for name, size in zip(new_dims, shape, strict=True)
            }
        )
    tree = xr.DataTree(dataset=dataset) if group == '/' else xr.DataTree()
    if group != '/':
        tree[group] = dataset
    tree.attrs['short_name'] = 'TEST01'
    tree.attrs['keep'] = 'root metadata'
    input_path = tmp_path / 'input.nc4'
    tree.to_netcdf(input_path, engine='h5netcdf')
    variable = f'{group.rstrip("/")}/science'
    attributes = [{'Name': 'units', 'Value': 'updated'}]
    if dimension_override is not None:
        attributes.append({'Name': 'dimensions', 'Value': dimension_override})
    config = {
        'Identification': 'Regression configuration',
        'Version': 1,
        'CollectionShortNamePath': ['short_name'],
        'Mission': {'TEST01': 'TEST_MISSION'},
        'MetadataOverrides': [
            {
                'Applicability': {
                    'Mission': 'TEST_MISSION',
                    'ShortNamePath': 'TEST01',
                    'VariablePattern': variable,
                },
                'Attributes': attributes,
            }
        ],
    }
    config_path = tmp_path / 'config.json'
    config_path.write_text(json.dumps(config), encoding='utf-8')
    return input_path, config_path, variable, data


@pytest.mark.parametrize('group', ['/', '/group'])
@pytest.mark.parametrize('new_dims', [('sample',), ('y', 'x')])
@pytest.mark.parametrize('coordinates', [False, True])
def test_dimension_only_rules_rename_existing_variables(
    tmp_path: Path,
    group: str,
    new_dims: tuple[str, ...],
    coordinates: bool,
) -> None:
    """Renaming must not depend on an unrelated variable-creation rule."""
    input_path, config, variable, values = make_input_and_config(
        tmp_path, group, new_dims, coordinates, ' '.join(new_dims)
    )
    before = input_path.read_bytes()
    varinfo = VarInfoFromNetCDF4(
        str(input_path), config_file=str(config), short_name='TEST01'
    )
    matched, missing = get_matching_groups_and_variables(varinfo)
    assert matched == {variable}
    assert missing == set()
    output = tmp_path / 'output.nc4'
    annotate_granule(str(input_path), str(output), str(config), 'TEST01')
    with xr.open_datatree(output, decode_cf=False, engine='h5netcdf') as result:
        actual = result[variable]
        assert actual.dims == new_dims
        assert actual.dtype == np.dtype('int16')
        np.testing.assert_array_equal(actual.values, values)
        assert actual.attrs['units'] == 'updated'
        assert actual.attrs['notes'] == 'keep'
        assert actual.attrs['_FillValue'] == -9999
        assert actual.encoding['zlib'] is True
        assert actual.encoding['complevel'] == 2
        np.testing.assert_array_equal(result[group]['untouched'], [7, 8])
        assert result[group]['untouched'].dims == ('other',)
        assert result.attrs['keep'] == 'root metadata'
        assert 'history_json' in result.attrs
        if coordinates:
            for dimension, size in zip(new_dims, values.shape, strict=True):
                np.testing.assert_array_equal(
                    result[group][dimension], np.arange(size) + 10
                )
    assert input_path.read_bytes() == before


def test_invalid_dimension_only_rule_is_rejected(tmp_path: Path) -> None:
    """The existing dimension-count validation must also run in this path."""
    input_path, config, _, _ = make_input_and_config(
        tmp_path, '/', ('y', 'x'), False, 'one_dimension'
    )
    with pytest.raises(InvalidDimensionsConfiguration):
        annotate_granule(
            str(input_path), str(tmp_path / 'output.nc4'), str(config), 'TEST01'
        )


def test_metadata_only_rule_preserves_dimensions(tmp_path: Path) -> None:
    """A rule with no dimension override keeps its existing behavior."""
    input_path, config, variable, values = make_input_and_config(
        tmp_path, '/group', ('y', 'x'), False, None
    )
    output = tmp_path / 'output.nc4'
    annotate_granule(str(input_path), str(output), str(config), 'TEST01')
    with xr.open_datatree(output, decode_cf=False, engine='h5netcdf') as result:
        assert result[variable].dims == ('old_0', 'old_1')
        assert result[variable].attrs['units'] == 'updated'
        np.testing.assert_array_equal(result[variable].values, values)
