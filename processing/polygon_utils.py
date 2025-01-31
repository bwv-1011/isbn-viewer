import numpy as np
import geojson
from scipy.ndimage import convolve
from shapely import Polygon, simplify
from shapely.ops import polylabel
from shapely.ops import unary_union
from collections import defaultdict

from utils import hilbert_rectangle_projection

def simplify_polygon(points):
    def is_collinear(p1, p2, p3):
        return (p2[1] - p1[1]) * (p3[0] - p2[0]) == (p3[1] - p1[1]) * (p2[0] - p1[0])

    simplified = [points[0]]

    for i in range(1, len(points) - 1):
        if not is_collinear(simplified[-1], points[i], points[i + 1]):
            simplified.append(points[i])

    if not is_collinear(simplified[-1], points[-1], simplified[0]):
        simplified.append(points[-1])

    return simplified


def find_outline(points):
    x_min = int(points[:, 0].min())
    x_max = int(points[:, 0].max())
    y_min = int(points[:, 1].min())
    y_max = int(points[:, 1].max())

    # binary grid
    grid = np.zeros((x_max - x_min + 3, y_max - y_min + 3), dtype=int)
    for x, y in points:
        grid[x - x_min + 1, y - y_min + 1] = 1

    # convolution kernel for the 8 neighbors
    kernel = np.array([[1, 1, 1], [1, 0, 1], [1, 1, 1]])

    neighbor_count = convolve(grid, kernel, mode="constant", cval=0)

    # boundary points have fewer than 8 neighbors
    boundary_mask = (grid == 1) & (neighbor_count < 8)

    boundary_points = np.argwhere(boundary_mask)
    return boundary_points + np.array([x_min - 1, y_min - 1])


def order_polygon_points(points):
    n = len(points)

    ordered_points = np.zeros_like(points)
    ordered_points[0] = points[0]

    used = np.zeros(n, dtype=bool)
    used[0] = True

    current_point = points[0]

    for i in range(1, n):
        distances = np.linalg.norm(points[~used] - current_point, axis=1)

        closest_idx = np.argmin(distances)

        actual_idx = np.arange(n)[~used][closest_idx]

        ordered_points[i] = points[actual_idx]

        used[actual_idx] = True

        current_point = points[actual_idx]

    return ordered_points


def isbn_position_range_to_polygon(range_start: int, range_end: int):
    positions = range(range_start, range_end + 1)
    locs = hilbert_rectangle_projection(positions)

    # expand area to 'enclose' all pixels
    shifts = np.array([[0, 0], [0, 1], [1, 0], [1, 1]], dtype=np.uint64)
    all_points = (locs[:, None, :] + shifts).reshape(-1, 2)

    outline = find_outline(all_points)

    ordered_boundary_points = order_polygon_points(outline)

    simplified_polygon = simplify_polygon(ordered_boundary_points)

    # close polygon
    simplified_polygon.append(simplified_polygon[0])

    return [[int(x), int(y)] for x, y in simplified_polygon]


def calculate_polygon_label_position(polygon_points):
    polygon = Polygon(polygon_points)

    p1 = polylabel(polygon)
    p2 = polylabel(simplify(polygon, tolerance=1))

    x1, y1 = p1.coords[0]
    x2, y2 = p2.coords[0]
    xm = (x1 * 2 + x2) / 3
    ym = (y1 * 2 + y2) / 3
    return (xm, ym)


def merge_polygons(polygons):
    merged = unary_union(polygons)

    if merged.geom_type == "Polygon":
        return [merged]
    elif merged.geom_type == "MultiPolygon":
        return list(merged.geoms)


def merge_geojson_polygons(
    polygons: geojson.FeatureCollection,
) -> geojson.FeatureCollection:
    # merge polygons with same id and shared border

    polygons_per_id = defaultdict(lambda: [])
    for feature in polygons["features"]:
        polygons_per_id[feature.id].append(feature)

    new_feature_collection = []

    for polygon_id, features in polygons_per_id.items():
        if len(feature) > 1:
            polygons = [Polygon(x.geometry.coordinates[0]) for x in features]
            merged_polygons = merge_polygons(polygons)
            for x in merged_polygons:
                new_feature_collection.append(
                    geojson.Feature(
                        id=polygon_id,
                        geometry=geojson.Polygon(
                            [[[x, y] for x, y in (x.exterior.coords)]]
                        ),
                        properties=features[0].properties,
                    )
                )
        else:
            new_feature_collection.append(features[0])

    return geojson.FeatureCollection(new_feature_collection)
