"""Tests for metadata_annotator.geotransform.py."""

import numpy as np
import pytest

from metadata_annotator.exceptions import InvalidSpatialDimensionType
from metadata_annotator.geotransform import (
    Geotransform,
    compute_dimension_scale,
    geotransform_from_config,
)


def test_geotransform():
    """Test basic geotransformation computations."""
    gt = Geotransform(-2000.0, 1000.0, 0.0, 0.0, 0.0, -1000.0)
    x, y = gt.col_row_to_xy(0, 0)
    assert np.isclose(x, -1500.0)
    assert np.isclose(y, -500.0)
    x2, y2 = gt.col_row_to_xy(1, 1)
    assert np.isclose(x2, -500.0)
    assert np.isclose(y2, -1500.0)


def test_geotransform_from_config():
    """Tests geotransform config info will be parsed for a geotransform."""
    sample_geotransform_config = [-9000000, 36000, 0, 9000000, 0, -36000]
    gt = geotransform_from_config(sample_geotransform_config)
    assert isinstance(gt, Geotransform)
    assert np.isclose(gt.top_left_x, -9000000.0)
    assert np.isclose(gt.top_left_y, 9000000.0)
    assert np.isclose(gt.row_rotation, 0.0)
    assert np.isclose(gt.column_rotation, 0.0)
    assert np.isclose(gt.pixel_width, 36000.0)
    assert np.isclose(gt.pixel_height, -36000.0)


def test_compute_dimension_scale_x():
    """Tests dimension scale is computed correctly."""
    result = compute_dimension_scale(
        0, 3, 'x', 'float64', [-9000000, 36000, 0, 9000000, 0, -36000]
    )
    expected_result = np.array([-8982000.0, -8946000.0, -8910000.0], dtype=np.float64)
    assert np.allclose(result, expected_result)


def test_compute_dimension_scale_y():
    """Tests dimension scale is computed correctly."""
    result = compute_dimension_scale(
        0, 3, 'y', 'float64', [-9000000, 36000, 0, 9000000, 0, -36000]
    )
    expected_result = np.array([8982000.0, 8946000.0, 8910000.0], dtype=np.float64)
    assert np.allclose(result, expected_result)


def test_compute_dimension_scale_raises_invalid_spatial_dimension_type():
    """Tests dimension scale is computed correctly."""
    with pytest.raises(InvalidSpatialDimensionType):
        compute_dimension_scale(
            0, 3, 'am_pm', 'float64', [-9000000, 36000, 0, 9000000, 0, -36000]
        )
