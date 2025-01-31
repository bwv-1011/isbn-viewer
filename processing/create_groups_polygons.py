from shapely import Polygon
from pathlib import Path
import geojson
from tqdm import tqdm
from polygon_utils import merge_geojson_polygons
from collections import defaultdict
import subprocess

from polygon_utils import calculate_polygon_label_position
from utils import n_prefix_to_zoom_level


def strip_properties(geojson_data):
    stripped_features = []
    for feature in geojson_data.features:
        stripped_feature = geojson.Feature(id=feature.id, geometry=feature.geometry)
        stripped_features.append(stripped_feature)

    return geojson.FeatureCollection(stripped_features)


def create_polygon_labels(feature_collection, n_prefix):
    label_features = []
    for feature in feature_collection["features"]:
        label_coordinates = calculate_polygon_label_position(
            feature.geometry.coordinates[0]
        )
        label_features.append(
            geojson.Feature(
                id=feature.id,
                geometry=geojson.Point(label_coordinates),
                properties=feature.properties,
                tippecanoe={
                    "minzoom": n_prefix_to_zoom_level(n_prefix),
                    "maxzoom": 9,
                },
            )
        )
    return geojson.FeatureCollection(label_features)


zoom_levels = {3: [0, 7], 4: [0, 7], 5: [0, 7], 6: [4, 9], 7: [6, 9]}


if __name__ == "__main__":
    output_folder = Path("output") / "groups"
    output_folder.mkdir(parents=True, exist_ok=True)

    pmtiles_folder = Path("output") / "pmtiles"
    pmtiles_folder.mkdir(parents=True, exist_ok=True)

    features = []
    for n in range(6, 11):
        with open(output_folder / f"groups{n}.geojson") as f:
            gj = geojson.load(f)
            features.extend(gj["features"])

    all_polygons = geojson.FeatureCollection(features)
    merged_polygons = merge_geojson_polygons(all_polygons)

    areas = []

    groups = defaultdict(lambda: [])

    for polygon in tqdm(merged_polygons["features"]):
        x = Polygon(polygon.geometry.coordinates[0])

        area = x.area

        if area > 6:
            groups[3].append(polygon)
        elif area > 0.58:
            groups[4].append(polygon)
        elif area > 0.058:
            groups[5].append(polygon)
        elif area > 0.0058:
            groups[6].append(polygon)
        else:
            groups[7].append(polygon)

    for n_prefix, features in groups.items():
        feature_collection = geojson.FeatureCollection(features)

        label_feature_collection = create_polygon_labels(feature_collection, n_prefix)
        label_features_filepath = output_folder / f"groups_{n_prefix}_labels.geojson"
        with open(label_features_filepath, "w") as f:
            geojson.dump(label_feature_collection, f)

        border_features_filepath = output_folder / f"groups_{n_prefix}.geojson"
        with open(border_features_filepath, "w") as f:
            geojson.dump(strip_properties(feature_collection), f)

        min_zoom, max_zoom = zoom_levels[n_prefix]

        pmtiles_filepath = pmtiles_folder / f"groups_{n_prefix}.pmtiles"

        subprocess.run(
            f"tippecanoe -z{max_zoom} -Z{min_zoom} -f -o {pmtiles_filepath} {border_features_filepath} {label_features_filepath}",
            shell=True,
        )
