"""Test functions in harmony_service.utilities."""

from harmony_service.utilities import get_mimetype


def test_get_mimetype_known():
    """Test using type known to `mimetypes.guess_type`."""
    assert get_mimetype('/path/to/data.h5') == 'application/x-hdf5'


def test_get_mimetype_netcdf4():
    """Test for .nc4, which `mimetypes.guess_type` doesn't not."""
    assert get_mimetype('/path/to/data.nc4') == 'application/x-netcdf'


def test_get_mimetype_unknown():
    """Default of application/octet-stream when completely unknown."""
    assert get_mimetype('file.unknown') == 'application/octet-stream'
