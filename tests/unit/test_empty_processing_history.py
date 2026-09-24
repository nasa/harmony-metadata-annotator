"""Regression coverage for empty processing-history record lists."""

import json

import numpy as np
import pytest
import xarray as xr
from netCDF4 import Dataset

from metadata_annotator.annotate import annotate_granule
from metadata_annotator.history_functions import (
    PROGRAM,
    get_request_url_attribute,
    read_history_json_attrs,
    update_history_metadata,
)


@pytest.mark.parametrize('serialized', ['[]', '[ ]', '[\n]'])
def test_empty_history_uses_input_filename(serialized):
    """An empty record list has no source URL to override the fallback."""
    tree = xr.DataTree(xr.Dataset(attrs={'history_json': serialized}))
    assert read_history_json_attrs(tree) == []
    assert get_request_url_attribute('input.nc', tree) == 'input.nc'
    assert tree.attrs['history_json'] == serialized


@pytest.mark.parametrize('history_name', ['history', 'History'])
def test_empty_history_gets_its_first_processing_record(history_name):
    """Append provenance without losing the existing textual history."""
    tree = xr.DataTree(
        xr.Dataset(
            attrs={
                'history_json': '[]',
                history_name: 'original processing',
            }
        )
    )
    update_history_metadata('input.nc', tree)
    records = json.loads(tree.attrs['history_json'])
    assert len(records) == 1
    assert records[0]['program'] == PROGRAM
    assert records[0]['derived_from'] == 'input.nc'
    assert tree.attrs[history_name].startswith('original processing\n')
    update_history_metadata('input.nc', tree)
    updated = json.loads(tree.attrs['history_json'])
    assert len(updated) == 2
    assert updated[0] == records[0]
    assert updated[1]['derived_from'] == 'input.nc'


@pytest.mark.parametrize(
    'record',
    [
        {},
        {'parameters': {'request_url': 'https://example.test/input.nc'}},
        {'parameters': [{'request_url': 'https://example.test/input.nc?subset=value'}]},
    ],
)
@pytest.mark.parametrize('as_list', [False, True])
def test_nonempty_history_preserves_source_selection(record, as_list):
    """Retain dictionary/list history and parameter representations."""
    tree = xr.DataTree(
        xr.Dataset(
            attrs={
                'history_json': json.dumps([record] if as_list else record),
            }
        )
    )
    expected = 'https://example.test/input.nc' if record else 'input.nc'
    assert get_request_url_attribute('input.nc', tree) == expected


def test_malformed_history_still_raises():
    """Do not hide JSON corruption while handling an empty valid array."""
    tree = xr.DataTree(xr.Dataset(attrs={'history_json': '[invalid'}))
    with pytest.raises(json.JSONDecodeError):
        get_request_url_attribute('input.nc', tree)


@pytest.mark.parametrize('serialized', ['[]', None, '{}', '[{}]'])
def test_full_netcdf_annotation_retains_data(serialized, tmp_path):
    """Apply a real metadata override and reopen the resulting NetCDF file."""
    source = tmp_path / 'input.nc'
    output = tmp_path / 'output.nc'
    config_path = tmp_path / 'overrides.json'
    config_path.write_text(
        json.dumps(
            {
                'Mission': {'LOCAL_TEST': 'LOCAL'},
                'CollectionShortNamePath': ['short_name'],
                'MetadataOverrides': [
                    {
                        'Applicability': {
                            'Mission': 'LOCAL',
                            'ShortNamePath': 'LOCAL_TEST',
                            'VariablePattern': '/measurement$',
                        },
                        'Attributes': [
                            {'Name': 'long_name', 'Value': 'Annotated measurement'}
                        ],
                    }
                ],
            }
        ),
        encoding='utf-8',
    )
    values = np.array([1.25, 2.5, np.nan])
    attrs = {
        'title': 'preserved collection',
        'history': 'original processing',
        'short_name': 'LOCAL_TEST',
    }
    if serialized is not None:
        attrs['history_json'] = serialized
    tree = xr.DataTree(
        xr.Dataset(
            data_vars={'measurement': ('sample', values)},
            attrs=attrs,
        )
    )
    tree['/details'] = xr.Dataset(data_vars={'quality': ('sample', [0, 1, 2])})
    tree.to_netcdf(source, engine='h5netcdf')
    tree.close()

    annotate_granule(str(source), str(output), str(config_path), 'LOCAL_TEST')
    with Dataset(output) as dataset:
        assert dataset.title == 'preserved collection'
        assert dataset['measurement'].long_name == 'Annotated measurement'
        np.testing.assert_array_equal(dataset['measurement'][:].filled(np.nan), values)
        np.testing.assert_array_equal(dataset['details/quality'][:], [0, 1, 2])
        records = json.loads(dataset.history_json)
        assert len(records) == (2 if serialized in ('{}', '[{}]') else 1)
        assert records[-1]['program'] == PROGRAM
        assert records[-1]['derived_from'] == str(source)
    with Dataset(source) as dataset:
        assert 'long_name' not in dataset['measurement'].ncattrs()
        if serialized is not None:
            assert dataset.history_json == serialized
