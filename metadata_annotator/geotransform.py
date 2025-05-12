"""Info particular to creating dimension scales from a geotransform."""

from dataclasses import dataclass

import numpy as np

from metadata_annotator.exceptions import InvalidSpatialDimensionType


@dataclass
class Geotransform:
    """Class for holding a GDAL-style 6-element geotransform."""

    top_left_x: np.float64
    pixel_width: np.float64
    row_rotation: np.float64
    top_left_y: np.float64
    column_rotation: np.float64
    pixel_height: np.float64

    def col_row_to_xy(self, col: int, row: int) -> tuple[np.float64, np.float64]:
        """Convert grid cell location to x,y coordinate."""
        # Geotransform is defined from upper left corner as (0,0), so adjust
        # input value to the center of grid at (.5, .5)
        adj_col = col + 0.5
        adj_row = row + 0.5

        x = self.top_left_x + adj_col * self.pixel_width + adj_row * self.row_rotation
        y = (
            self.top_left_y
            + adj_col * self.column_rotation
            + adj_row * self.pixel_height
        )
        return x, y


def geotransform_from_config(geotransform_info: list) -> Geotransform:
    """Return a geotransform object from the geotransform configuration list.

    The geotransform configuration is a list of six elements that describe the spatial
    transformation for a grid. The elements correspond to the following values:

    GT(0) x-coordinate of the upper-left corner of the upper-left pixel.
    GT(1) w-e pixel resolution / pixel width.
    GT(2) row rotation (typically zero).
    GT(3) y-coordinate of the upper-left corner of the upper-left pixel.
    GT(4) column rotation (typically zero).
    GT(5) n-s pixel resolution / pixel height (negative value for a north-up image).

    """
    return Geotransform(
        geotransform_info[0],
        geotransform_info[1],
        geotransform_info[2],
        geotransform_info[3],
        geotransform_info[4],
        geotransform_info[5],
    )


def compute_dimension_scale(
    start_index: int,
    dim_size: int,
    spatial_dimension_type: str,
    dimension_value_dtype: str,
    geotransform_config: list,
) -> np.ndarray:
    """Compute the dimension scale from the given geotransform configuration."""
    geotransform = geotransform_from_config(geotransform_config)

    # compute the x,y locations along a column and row
    if spatial_dimension_type == 'x':
        column_dimensions = [
            geotransform.col_row_to_xy(i, 0)
            for i in range(start_index, start_index + dim_size)
        ]
        dimension_scale = np.array(
            [x for x, y in column_dimensions], dtype=np.dtype(dimension_value_dtype)
        )
    elif spatial_dimension_type == 'y':
        row_dimensions = [
            geotransform.col_row_to_xy(0, i)
            for i in range(start_index, start_index + dim_size)
        ]
        dimension_scale = np.array(
            [y for x, y in row_dimensions], dtype=np.dtype(dimension_value_dtype)
        )
    else:
        raise InvalidSpatialDimensionType(spatial_dimension_type)

    return dimension_scale
