import math

import pytest

from hex2tile import compute_hex_center


def test_compute_hex_center_flat_top_axial():
    hex_width = 20.0
    hex_height = hex_width * (math.sqrt(3)/2)

    x0, y0 = compute_hex_center(0, 0, hex_width)
    assert x0 == 0.0
    assert y0 == 0.0

    x1, y1 = compute_hex_center(1, 0, hex_width)
    assert x1 == 0.0
    assert y1 == pytest.approx(hex_height)

    x2, y2 = compute_hex_center(0, 1, hex_width)
    assert x2 == math.sqrt(3)/2 * hex_height
    assert y2 == pytest.approx(hex_height/2)

    x3, y3 = compute_hex_center(0, 2, hex_width)
    assert x3 == math.sqrt(3)/2 * hex_height * 2
    assert y3 == pytest.approx(hex_height)
