from pathlib import Path
import geojson
import json
import numpy as np
from PIL import Image
from tqdm import tqdm
import subprocess 

from utils import hilbert_rectangle_projection, project_x_y_to_coordinate

Image.MAX_IMAGE_PIXELS = None
geojson.geometry.DEFAULT_PRECISION = 24


if __name__ == "__main__":

    holding_info_filepath = Path("data") / 'oclc_holdings_per_position.jsonl'
    geojson_output_filepath = Path('output') / 'geojson'
    geojson_output_filepath.mkdir(parents=True, exist_ok=True)

    datasets = [
        "all_isbns",
        "md5",
        "cadal_ssno",
        "cerlalc",
        "duxiu_ssid",
        "edsebk",
        "gbooks",
        "goodreads",
        "ia",
        "isbndb",
        "isbngrp",
        "libby",
        "nexusstc",
        "oclc",
        "ol",
        "rgb",
        "trantor"
    ]

    print("reading holding counts")
    holdings = {}
    with open(holding_info_filepath, "r") as f:
        for x in f:
            isbn_position, holding = json.loads(x)
            holdings[isbn_position] = holding

    isbn_positions = np.array(list(holdings.keys()))
    holding_counts = np.array(list(holdings.values()))

    holding_counts_scaled = np.exp(-0.8 * holding_counts) * 3000
    holding_counts_scaled[holding_counts_scaled < 10] = 0

    locs = hilbert_rectangle_projection(isbn_positions)

    n = len(locs)

    for dataset in datasets:
        print(f"processing {dataset}")
        image_filepath = Path('output') / 'images' / f'{dataset}.png'
        
        # use image to quickly look up whether it is in the dataset and with what color
        with Image.open(image_filepath) as img:
            geojson_filepath = geojson_output_filepath / f"extrusions_{dataset}.geojson"
            with open(geojson_output_filepath / f"extrusions_{dataset}.geojson", "w") as f:
                f.write('{"type": "FeatureCollection", "features": [')
                first = True

                for position, holding_info, isbn_position in tqdm(
                    zip(locs, holding_counts_scaled, isbn_positions), total=n
                ):
                    if int(holding_info) == 0:
                        continue

                    x = int(position[0])
                    y = int(position[1])

                    rgb_color = img.getpixel((x, y))[:3]

                    if rgb_color == (0, 0, 0):
                        continue

                    lat_start, lng_start = project_x_y_to_coordinate(x, y)
                    lat_end, lng_end = project_x_y_to_coordinate(x + 1, y + 1)

                    coordinates = [
                        [lat_start, lng_start],
                        [lat_start, lng_end],
                        [lat_end, lng_end],
                        [lat_end, lng_start],
                        [lat_start, lng_start],
                    ]

                    feature = geojson.Feature(
                        id=int(isbn_position),
                        geometry=geojson.Polygon([coordinates]),
                        properties={
                            "height": int(holding_info),
                            "color": "#{:02x}{:02x}{:02x}".format(*rgb_color),
                        },
                    )

                    if not first:
                        f.write(",")
                    else:
                        first = False

                    geojson.dump(feature, f)

                f.write("]}")


        subprocess.run(
            f"tippecanoe -l holdings -z8 -Z8 -f -o output/pmtiles/{dataset}_holdings.pmtiles {geojson_filepath}",
            shell=True
        )
        geojson_filepath.unlink()
