import json
from collections import defaultdict
from pathlib import Path

import geojson
from polygon_utils import isbn_position_range_to_polygon
from tqdm import tqdm
from utils import project_x_y_to_coordinate, string_to_number

geojson.geometry.DEFAULT_PRECISION = 18


if __name__ == "__main__":
    input_file = "data/annas_archive_meta__aacid__isbngrp_records__20240920T194930Z--20240920T194930Z.jsonl.seekable"

    output_folder = Path("output") / "groups"
    output_folder.mkdir(parents=True, exist_ok=True)

    groups_prefixes = defaultdict(lambda: defaultdict(lambda: []))

    with open(input_file) as f:
        for line in tqdm(f, total=2744530, desc="Sorting by prefix"):
            data = json.loads(line)

            for x in data["metadata"]["record"]["isbns"]:
                if x["isbn_type"] == "prefix":
                    if data["metadata"]["record"]["registrant_name"]:
                        isbn_prefix = x["isbn"].replace("-", "")
                        if len(isbn_prefix) > 11:
                            continue
                        groups_prefixes[len(isbn_prefix)][isbn_prefix].append(
                            data["metadata"]["record"]["registrant_name"]
                        )

    with open(output_folder / "groups.geojsonl", "w") as f:
        for prefix_length, prefixes in groups_prefixes.items():
            for prefix, names in tqdm(
                prefixes.items(),
                desc=f"Creating polygons for prefix length {prefix_length}",
            ):
                min_isbn = str(prefix).ljust(12, "0")
                max_isbn = str(prefix).ljust(12, "9")

                min_position = int(min_isbn) - 978000000000
                max_position = int(max_isbn) - 978000000000

                polygon_points = isbn_position_range_to_polygon(
                    min_position, max_position
                )

                coordinates = [
                    project_x_y_to_coordinate(int(x), int(y))
                    for (x, y) in polygon_points
                ]

                main_name = min(names, key=len)
                names.remove(main_name)

                feature = geojson.Feature(
                    id=string_to_number(main_name),
                    geometry=geojson.Polygon([coordinates]),
                    properties={"name": main_name, "additional_names": ";".join(names)},
                )

                geojson.dump(feature, f)
                f.write("\n")
