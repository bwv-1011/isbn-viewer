from collections import defaultdict

import cv2
import geojson
import numpy as np
from shapely import Polygon, simplify
from shapely.geometry import mapping as polygon_to_geojson
from shapely.geometry import shape as geojson_to_polygon
from shapely.ops import polylabel, unary_union
from utils import hilbert_rectangle_projection


def simplify_polygon(points):
    def is_collinear(p1, p2, p3):
        area = (p2[0] - p1[0]) * (p3[1] - p1[1]) - (p2[1] - p1[1]) * (p3[0] - p1[0])
        return abs(area) < 1e-10

    simplified = [points[0]]

    for i in range(1, len(points) - 1):
        if not is_collinear(simplified[-1], points[i], points[i + 1]):
            simplified.append(points[i])

    # handle the last point
    if not is_collinear(simplified[-1], points[-1], simplified[0]):
        simplified.append(points[-1])
    else:
        if len(simplified) > 1 and is_collinear(
            simplified[0], simplified[1], points[-1]
        ):
            pass
        else:
            simplified.append(points[-1])

    # check if the first point is collinear with the last and second points
    if len(simplified) > 2 and is_collinear(
        simplified[-1], simplified[0], simplified[1]
    ):
        simplified.pop(0)

    return simplified


def find_polygon_points(points):
    # bounding box of the points
    x_min = int(points[:, 0].min())
    x_max = int(points[:, 0].max())
    y_min = int(points[:, 1].min())
    y_max = int(points[:, 1].max())

    # binary grid with a 1-pixel padding
    grid = np.zeros((x_max - x_min + 3, y_max - y_min + 3), dtype=int)
    grid[points[:, 0] - x_min + 1, points[:, 1] - y_min + 1] = 1

    grid = grid.astype(np.uint8)
    contours, _ = cv2.findContours(grid, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    boundary_points = contours[0].squeeze()
    # fix diagonal jumps, bc findContours is a 8-neighborhood tracing algorithm, not 4-neighbor
    fixed_points = []
    for i in range(len(boundary_points) - 1):
        x1, y1 = boundary_points[i]
        x2, y2 = boundary_points[i + 1]
        fixed_points.append((y1, x1))
        if abs(x1 - x2) == 1 and abs(y1 - y2) == 1:
            # there are two possibilities to fill the jump: (x1,y2) or (x2,y1), check the grid
            if grid[y2, x1] == 1:
                fixed_points.append((y2, x1))
            else:
                fixed_points.append((y1, x2))

    fixed_points.append(boundary_points[-1][::-1])
    fixed_points.append(fixed_points[0])
    fixed_boundary_points = np.array(fixed_points)
    return fixed_boundary_points + np.array([x_min - 1, y_min - 1])


def isbn_position_range_to_polygon(range_start: int, range_end: int):
    positions = range(range_start, range_end + 1)
    locs = hilbert_rectangle_projection(positions)

    # expand area to 'enclose' all pixels
    shifts = np.array([[0, 0], [0, 1], [1, 0], [1, 1]], dtype=np.uint64)
    all_points = (locs[:, None, :] + shifts).reshape(-1, 2)

    points = find_polygon_points(all_points)

    simplified_polygon = simplify_polygon(points)
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
        if len(features) > 1:
            polygons = [geojson_to_polygon(x.geometry) for x in features]
            merged_polygons = merge_polygons(polygons)
            for x in merged_polygons:
                new_feature_collection.append(
                    geojson.Feature(
                        id=polygon_id,
                        geometry=polygon_to_geojson(x),
                        properties=features[0].properties,
                    )
                )
        else:
            new_feature_collection.append(features[0])

    return geojson.FeatureCollection(new_feature_collection)
