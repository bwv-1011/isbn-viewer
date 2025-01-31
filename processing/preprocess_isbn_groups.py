
import geojson
import json
from tqdm import tqdm
from collections import defaultdict
from pathlib import Path
from utils import (
    project_x_y_to_coordinate,
    string_to_number
)
from polygon_utils import isbn_position_range_to_polygon

geojson.geometry.DEFAULT_PRECISION = 18


if __name__ == "__main__":
    
    input_file = "data/annas_archive_meta__aacid__isbngrp_records__20240920T194930Z--20240920T194930Z.jsonl.seekable"

    output_folder = Path('output') / 'groups'
    output_folder.mkdir(parents=True, exist_ok=True)


    isbn_prefixes = defaultdict(lambda: [])

    with open(input_file) as f:
        for line in tqdm(f, total=2744530):
            data = json.loads(line)

            for x in data["metadata"]["record"]["isbns"]:
                if x["isbn_type"] == "prefix":
                    if data["metadata"]["record"]["registrant_name"]:
                        isbn_prefixes[x["isbn"].replace('-','')].append(data["metadata"]["record"]["registrant_name"])

    with open(output_folder / "groups.geojson", "w") as f_out:
        f_out.write('{"type": "FeatureCollection", "features": [')
        first = True

        for prefix, names in tqdm(isbn_prefixes.items()):
            
            if len(prefix) < 11:

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
                    properties={"name": main_name, "additional_names": ';'.join(names)}
                )

                if not first:
                    f_out.write(",")
                else:
                    first = False

                geojson.dump(feature, f_out)

        f_out.write("]}")


