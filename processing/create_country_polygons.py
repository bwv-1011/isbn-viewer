import geojson
import json
import subprocess
from tqdm import tqdm
from pathlib import Path

from utils import project_x_y_to_coordinate, string_to_number, n_prefix_to_zoom_level

from polygon_utils import (
    isbn_position_range_to_polygon,
    calculate_polygon_label_position,
    merge_geojson_polygons,
)

geojson.geometry.DEFAULT_PRECISION = 18


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
                properties={
                    "name": feature.properties["name"],
                },
                tippecanoe={
                    "minzoom": n_prefix_to_zoom_level(n_prefix),
                    "maxzoom": 9,
                },
            )
        )
    return geojson.FeatureCollection(label_features)


if __name__ == "__main__":
    with open("data/isbn_prefix_countries.json", "r") as f:
        data = json.load(f)

    geojson_folder = Path("output") / "geojson"
    geojson_folder.mkdir(parents=True, exist_ok=True)

    for n_prefix, countries in data.items():
        border_features = []
        label_features = []
        for prefix, country in tqdm(countries.items()):
            min_isbn = prefix.replace("-", "").ljust(12, "0")
            max_isbn = prefix.replace("-", "").ljust(12, "9")

            min_position = int(min_isbn) - 978000000000
            max_position = int(max_isbn) - 978000000000

            polygon_points = isbn_position_range_to_polygon(
                min_position, max_position
            )

            coordinates = [
                project_x_y_to_coordinate(int(x), int(y))
                for (x, y) in polygon_points
            ]

            border_features.append(
                geojson.Feature(
                    id=string_to_number(country),
                    geometry=geojson.Polygon([coordinates]),
                    properties={"name": country},
                )
            )

        feature_collection = geojson.FeatureCollection(border_features)
        feature_collection = merge_geojson_polygons(feature_collection)

        border_features_filepath = geojson_folder / f"country_{n_prefix}.geojson"
        with open(border_features_filepath, "w") as f:
            geojson.dump(feature_collection, f)

        label_feature_collection = create_polygon_labels(
            feature_collection, n_prefix
        )
        label_features_filepath = (
            geojson_folder / f"country_{n_prefix}_labels.geojson"
        )
        with open(label_features_filepath, "w") as f:
            geojson.dump(label_feature_collection, f)

        subprocess.run(
            f"tippecanoe -z11 -Z0 -f -o output/pmtiles/country_{n_prefix}.pmtiles {border_features_filepath} {label_features_filepath}",
            shell=True,
        )
