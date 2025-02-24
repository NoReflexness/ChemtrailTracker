import logging
import numpy as np
import svgwrite

logger = logging.getLogger('FlightAnalyzer')

def generate_individual_svg(coords, pattern_type, output_path):
    logger.debug(f"Generating SVG for {output_path}")
    dwg = svgwrite.Drawing(output_path, size=('400px', '300px'))
    dwg.add(dwg.rect(insert=(0, 0), size=('100%', '100%'), fill='white'))
    coords = np.array(coords)
    lats, lons = coords[:, 0], coords[:, 1]
    lat_min, lat_max = min(lats), max(lats)
    lon_min, lon_max = min(lons), max(lons)

    def scale_coord(lat, lon):
        x = 20 + (lon - lon_min) / (lon_max - lon_min) * 360 if lon_max != lon_min else 200
        y = 280 - (lat - lat_min) / (lat_max - lat_min) * 260 if lat_max != lat_min else 150
        return x, y

    colors = {'Commercial': 'blue', 'Survey': 'green', 'Agricultural': 'purple', 'Firefighting': 'red', 'Chemtrail': 'orange'}
    points = [scale_coord(lat, lon) for lat, lon in coords]
    dwg.add(dwg.polyline(points, stroke=colors.get(pattern_type, 'black'), fill='none', stroke_width=2))
    dwg.save()
    return output_path