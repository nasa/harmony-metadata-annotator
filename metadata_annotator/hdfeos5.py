"""Rewrite HDF-EOS5 grid XDim and YDim coordinates as cell centers.

Some HDF-EOS5 granules store pixel upper-left corners in XDim and YDim, which
can incorrectly be interpreted as cell centers. To avoid that, variables configured
with `_*hdfeos5_cell_centers` are rewritten as cell centers, and if exists,
PixelRegistration is changed to center too.

"""

import re

import numpy as np
import xarray as xr
from varinfo import VarInfoFromNetCDF4

from metadata_annotator.exceptions import (
    InvalidHDFEOS5GridDefinition,
    UnexpectedCoordinateValues,
)

CELL_CENTERS_ATTRIBUTE = '_*hdfeos5_cell_centers'
STRUCT_METADATA_GROUP = '/HDFEOS INFORMATION'
COORDINATE_AXES = {'XDim': 0, 'YDim': 1}
# See HDF-EOS5_REF.pdf in HDFEOS5_1.16 branch at
# https://git.earthdata.nasa.gov/scm/das/hdfeos5.git
CORNER_REGISTRATION = 'HE5_HDFE_CORNER'
CENTER_REGISTRATION = 'HE5_HDFE_CENTER'
GEOGRAPHIC_PROJECTION = 'HE5_GCTP_GEO'


def update_hdfeos5_cell_centers(
    datatree: xr.DataTree,
    items_to_update: set[str],
    granule_varinfo: VarInfoFromNetCDF4,
) -> None:
    """Rewrite configured XDim and YDim variables as cell centers."""
    for variable_path in sorted(items_to_update):
        overrides = granule_varinfo.cf_config.get_metadata_overrides(variable_path)
        if str(overrides.get(CELL_CENTERS_ATTRIBUTE, '')).lower() == 'true':
            set_cell_center_values(datatree, variable_path)


def set_cell_center_values(datatree: xr.DataTree, variable_path: str) -> None:
    """Replace pixel-corner XDim or YDim values with pixel centers.

    Center values are left unchanged, and values matching neither raise
    UnexpectedCoordinateValues. A predefined corner registration attribute
    is also changed to center.

    """
    grid_path, variable_name = variable_path.rsplit('/', 1)
    grid_name = grid_path.rsplit('/', 1)[-1]
    if variable_name not in COORDINATE_AXES:
        raise InvalidHDFEOS5GridDefinition(
            variable_path, 'only XDim and YDim can be rewritten as cell centers'
        )

    grid = get_grid_definition(get_struct_metadata(datatree), grid_name)
    corners, centers = get_corner_and_center_values(grid, variable_name)
    values = datatree[variable_path].values
    tolerance = 1e-3 * abs(corners[1] - corners[0]) if corners.size > 1 else 1e-6

    if not is_close(values, centers, tolerance):
        if not is_close(values, corners, tolerance):
            raise UnexpectedCoordinateValues(variable_path)

        datatree[variable_path] = datatree[variable_path].copy(
            data=centers.astype(values.dtype)
        )

    if grid['PixelRegistration'] == CORNER_REGISTRATION:
        set_center_registration(datatree, grid_name)


def set_center_registration(datatree: xr.DataTree, grid_name: str) -> None:
    """Change a grid's declared PixelRegistration from corner to center."""
    part_names = get_struct_metadata_part_names(datatree)
    group = datatree[STRUCT_METADATA_GROUP]
    part_texts = [decode_text(group[name].values) for name in part_names]
    start = find_corner_registration(''.join(part_texts), grid_name)
    if start is None:
        return

    # There is a chance that the corner registration is split across two
    # StructMetadata parts, so we should detect and modify both involved parts.
    end = start + len(CENTER_REGISTRATION)
    part_start = 0
    for name, part_text in zip(part_names, part_texts):
        part_end = part_start + len(part_text)
        first, last = max(start, part_start), min(end, part_end)
        if first < last:
            datatree[f'{STRUCT_METADATA_GROUP}/{name}'] = group[name].copy(
                data=replace_text(
                    group[name].values,
                    first - part_start,
                    CENTER_REGISTRATION[first - start : last - start],
                )
            )
        part_start = part_end


def find_corner_registration(struct_metadata: str, grid_name: str) -> int | None:
    """Return the position of a grid's corner registration value, or None."""
    settings_start, settings_text = find_grid_settings(struct_metadata, grid_name)
    match = re.search(
        rf'^\s*PixelRegistration=({CORNER_REGISTRATION})\s*$',
        settings_text,
        flags=re.MULTILINE,
    )
    return settings_start + match.start(1) if match else None


def replace_text(value: np.ndarray, start: int, replacement: str) -> np.ndarray:
    """Return a StructMetadata part with text replaced, keeping its type and size."""
    if value.dtype.kind == 'S':
        raw = bytearray(value.tobytes())
        raw[start : start + len(replacement)] = replacement.encode('ascii')
        return np.frombuffer(bytes(raw), dtype=value.dtype).reshape(value.shape)

    item = value.item()
    item_text = item.decode('ascii') if isinstance(item, bytes) else item
    item_text = item_text[:start] + replacement + item_text[start + len(replacement) :]
    new_item = item_text.encode('ascii') if isinstance(item, bytes) else item_text
    return np.array(new_item, dtype=value.dtype)


def get_corner_and_center_values(
    grid: dict, variable_name: str
) -> tuple[np.ndarray, np.ndarray]:
    """Return the pixel-corner and pixel-center values of one grid axis."""
    axis = COORDINATE_AXES[variable_name]
    size = grid[variable_name]
    first_edge = grid['UpperLeftPointMtrs'][axis]
    last_edge = grid['LowerRightMtrs'][axis]
    step = (last_edge - first_edge) / size
    corners = first_edge + np.arange(size) * step
    return corners, corners + step / 2.0


def is_close(values: np.ndarray, expected: np.ndarray, tolerance: float) -> bool:
    """Return True when the values match within an absolute tolerance."""
    return values.shape == expected.shape and bool(
        np.allclose(values, expected, rtol=0.0, atol=tolerance)
    )


def get_struct_metadata(datatree: xr.DataTree) -> str:
    """Return the StructMetadata text, joining StructMetadata.N parts."""
    part_names = get_struct_metadata_part_names(datatree)
    group = datatree[STRUCT_METADATA_GROUP]
    return ''.join(decode_text(group[name].values) for name in part_names)


def get_struct_metadata_part_names(datatree: xr.DataTree) -> list:
    """Return the StructMetadata.N variable names in numeric order."""
    try:
        group = datatree[STRUCT_METADATA_GROUP]
    except KeyError as exception:
        raise InvalidHDFEOS5GridDefinition(
            STRUCT_METADATA_GROUP, 'the granule has no HDF-EOS5 StructMetadata'
        ) from exception

    part_names = sorted(
        (
            name
            for name in group.data_vars
            if re.fullmatch(r'StructMetadata\.\d+', name)
        ),
        key=lambda name: int(name.split('.')[1]),
    )
    if not part_names:
        raise InvalidHDFEOS5GridDefinition(
            STRUCT_METADATA_GROUP, 'the granule has no HDF-EOS5 StructMetadata parts'
        )

    return part_names


def decode_text(value: np.ndarray | bytes | str) -> str:
    """Decode a StructMetadata part stored as a string or character array."""
    if isinstance(value, np.ndarray):
        value = value.item() if value.ndim == 0 else b''.join(value.ravel().tolist())
    if isinstance(value, bytes):
        value = value.decode('ascii', errors='replace')
    return value.rstrip('\x00')


def get_grid_definition(struct_metadata: str, grid_name: str) -> dict:
    """Parse one grid's grid-level settings from StructMetadata."""
    _, settings_text = find_grid_settings(struct_metadata, grid_name)
    settings = dict(re.findall(r'^\s*(\w+)=(.*?)\s*$', settings_text, re.MULTILINE))
    return parse_grid_settings(settings, grid_name)


def find_grid_settings(struct_metadata: str, grid_name: str) -> tuple[int, str]:
    """Return the position and text of one grid's grid-level settings."""
    for block in re.finditer(
        r'GROUP=GRID_\d+(.*?)END_GROUP=GRID_\d+', struct_metadata, flags=re.DOTALL
    ):
        settings_text = block.group(1).split('GROUP=', 1)[0]
        settings = dict(re.findall(r'^\s*(\w+)=(.*?)\s*$', settings_text, re.MULTILINE))
        if settings.get('GridName', '').strip('"') == grid_name:
            return block.start(1), settings_text

    raise InvalidHDFEOS5GridDefinition(grid_name, 'grid not found in StructMetadata')


def parse_grid_settings(settings: dict, grid_name: str) -> dict:
    """Convert raw StructMetadata grid settings to typed values."""
    if settings.get('Projection') == GEOGRAPHIC_PROJECTION:
        raise InvalidHDFEOS5GridDefinition(
            grid_name, 'geographic grids are not supported'
        )

    try:
        return {
            'XDim': int(settings['XDim']),
            'YDim': int(settings['YDim']),
            'UpperLeftPointMtrs': parse_point(settings['UpperLeftPointMtrs']),
            'LowerRightMtrs': parse_point(settings['LowerRightMtrs']),
            'PixelRegistration': settings.get('PixelRegistration'),
        }
    except (KeyError, ValueError) as exception:
        raise InvalidHDFEOS5GridDefinition(
            grid_name, f'incomplete grid definition ({exception})'
        ) from exception


def parse_point(text: str) -> tuple[float, float]:
    """Parse an HDF-EOS5 point such as "(-5244627.580500,1430352.976500)"."""
    x_value, y_value = (float(value) for value in text.strip('()').split(','))
    return x_value, y_value
