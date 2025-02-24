import pytest
import os
from flight_analyzer.utils import generate_individual_svg

def test_generate_individual_svg(tmp_path, sample_coords):
    svg_path = str(tmp_path / "test.svg")
    generate_individual_svg(sample_coords, 'Commercial', svg_path)
    assert os.path.exists(svg_path)
    with open(svg_path, 'r') as f:
        content = f.read()
        assert 'polyline' in content
        assert 'stroke="blue"' in content