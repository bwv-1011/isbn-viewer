import bencodepy
import struct
import zstandard
import numpy as np
import PIL.Image
import shutil

from PIL import Image
from pathlib import Path
import math
from tqdm import tqdm
import random
import pyvips
from multiprocessing import Pool
from pmtiles.tile import zxy_to_tileid, tileid_to_zxy, TileType, Compression
from pmtiles.writer import Writer


from utils import hilbert_rectangle_projection


class RasterTilesMaker:
    def __init__(
        self,
        packed_isbns_ints_filepath: Path,
        output_folder_path: Path = Path("output"),
        published_color: tuple = (37, 150, 190),
        archived_color: tuple = (191, 191, 191),
        single_dataset_color: tuple = (31, 173, 109),
        dataset: str = "all_isbns",
    ) -> None:
        self.packed_isbns_ints_filepath = packed_isbns_ints_filepath
        self.dataset = dataset
        self.published_color = published_color
        self.archived_color = archived_color
        self.single_dataset_color = single_dataset_color
        self.output_folder_path = output_folder_path
        self.tiles_folder = self.output_folder_path / "tiles"
        self.image_width = 2**16
        self.image_height = 2**15
        self.tile_size = 1000
        if self.dataset == "all_isbns":
            self.yes_color = self.archived_color
        else:
            self.yes_color = self.single_dataset_color

    def run(self):
        self.make_isbn_image()
        self.tile_image()
        self.resample_all_tiles()
        self.create_pmtiles()

    def make_isbn_image(self):
        print(f"creating image ({f'{self.dataset}.png'})")
        isbn_data = bencodepy.bread(
            zstandard.ZstdDecompressor().stream_reader(
                open(self.packed_isbns_ints_filepath, "rb")
            )
        )
        image = np.zeros((self.image_height, self.image_width, 4), dtype=np.uint8)

        if self.dataset == "all_isbns":
            for prefix, packed_isbns_binary in isbn_data.items():
                if prefix == b"md5":
                    continue
                print(
                    f"adding {prefix.decode('utf-8')} to image in color {self.published_color}"
                )
                image = self.color_image(
                    image,
                    packed_isbns_binary,
                    color=(*self.published_color, 255),
                )

            print(f"adding md5 to image in color {self.archived_color}")
            image = self.color_image(
                image, isbn_data[b"md5"], color=(*self.archived_color, 255)
            )
        else:
            print(f"adding {self.dataset} to image in color {self.single_dataset_color}")
            dataset_key = b"" + self.dataset.encode()
            image = self.color_image(
                image, isbn_data[dataset_key], color=(*self.single_dataset_color, 255)
            )

        image_folder = self.output_folder_path / "images"
        image_folder.mkdir(parents=True, exist_ok=True)

        self.img = PIL.Image.fromarray(image)
        self.img.save(image_folder / f"{self.dataset}.png")

    def tile_image(self):
        if self.tiles_folder.exists():
            shutil.rmtree(self.tiles_folder)
        self.tiles_folder.mkdir(parents=True, exist_ok=True)
        zoom_dir = self.tiles_folder / "7"
        zoom_dir.mkdir(parents=True, exist_ok=True)

        width, height = self.img.size

        x_tiles = math.ceil(self.image_width / self.tile_size)
        y_tiles = math.ceil(self.image_height / self.tile_size)

        x_offset = 32
        y_offset = 48

        with tqdm(total=x_tiles * y_tiles, desc="Creating tiles") as pbar:
            for x in range(x_tiles):
                row_dir = zoom_dir / f"{x + x_offset}"
                row_dir.mkdir(exist_ok=True)
                for y in range(y_tiles):
                    left = x * self.tile_size
                    right = min(left + self.tile_size, self.image_width)
                    upper = y * self.tile_size
                    lower = min(upper + self.tile_size, self.image_height)
                    box = (left, upper, right, lower)

                    cropped_img = self.img.crop(box)
                    tile = Image.new(
                        "RGBA", (self.tile_size, self.tile_size), (0, 0, 0, 0)
                    )
                    tile.paste(cropped_img, (0, 0), mask=cropped_img)

                    tile_filename = row_dir / f"{y + y_offset}.webp"
                    tile.save(tile_filename, format="WEBP", lossless=True, quality=100)
                    pbar.update(1)
        del self.img

    @staticmethod
    def color_image(image, packed_isbns_binary, color):
        packed_isbns_ints = struct.unpack(
            f"{len(packed_isbns_binary) // 4}I", packed_isbns_binary
        )
        isbn_streak = True  # Alternate between reading `isbn_streak` and `gap_size`.
        position = 0  # ISBN (without check digit) is `978000000000 + position`.
        positions = []
        for value in packed_isbns_ints:
            if isbn_streak:
                for _ in range(0, value):
                    positions.append(position)
                    position += 1
            else:  # Reading `gap_size`.
                position += value
            isbn_streak = not isbn_streak

        locs = hilbert_rectangle_projection(positions)
        image[locs[:, 1], locs[:, 0]] = color
        return image

    def resample_all_tiles(self):
        # Source tiles
        max_x = 128
        max_y = 128
        source_z = 7

        for z in range(source_z - 1, -1, -1):
            max_x = math.ceil(max_x / 2)
            max_y = math.ceil(max_y / 2)
            print(f"Downsampling for zoom level {z}")

            tasks = [
                (z, x, y, self.tile_size, self.yes_color, self.published_color, self.tiles_folder)
                for x in range(max_x) for y in range(max_y)]

            with Pool() as pool:
                list(
                    tqdm(
                        pool.imap_unordered(self.resample_tile, tasks),
                        total=len(tasks),
                        desc="Resampling tiles",
                    )
                )

    @staticmethod
    def resample_tile(args):
        def combine_pixels(pixels, yes_color, no_color):
            n_no = 0
            n_yes = 0
            total_alpha = 0

            n_yes = sum(1 for x in pixels if x[:3] == yes_color)
            n_no = sum(1 for x in pixels if x[:3] == no_color)
            total_alpha = sum(x[3] for x in pixels)
            n_transparent = 4 - n_no - n_yes

            if n_transparent > 3:
                return (0, 0, 0, 0)

            if n_yes > 0:
                if n_yes == n_no:
                    # flip a coin!
                    if random.randint(0, 1) == 0:
                        return (*no_color, total_alpha // 10)
                    else:
                        return (*yes_color, total_alpha // 10)
                elif n_yes > n_no:
                    brightness = (total_alpha * n_yes) // 8
                    return (*yes_color, brightness)

            if n_no > 0 and n_no > n_yes:
                brightness = (total_alpha * n_no) // 8
                return (*no_color, brightness)


        z, x, y, tile_size, yes_color, no_color, tiles_folder = args
        tile = Image.new("RGBA", (tile_size, tile_size), (0, 0, 0, 0))

        x_offset = 0
        y_offset = 0

        n_transparent_tiles = 0

        for tile_x in range(0, 2):
            for tile_y in range(0, 2):
                x_offset = tile_x * tile_size // 2
                y_offset = tile_y * tile_size // 2

                filepath = (
                    tiles_folder
                    / str(z + 1)
                    / str(x * 2 + tile_x)
                    / f"{y * 2 + tile_y}.webp"
                )
                if not filepath.exists():
                    n_transparent_tiles += 1
                    continue

                image = pyvips.Image.new_from_file(str(filepath), access="sequential")
                img_np = image.numpy()
                alpha_channel_sum = np.sum(img_np[:, :, 3])
                if alpha_channel_sum == 0:
                    n_transparent_tiles += 1
                    continue
                pil_image = Image.fromarray(img_np)

                for i in range(0, img_np.shape[0], 2):
                    for j in range(0, img_np.shape[1], 2):
                        pixels = [
                            pil_image.getpixel((j, i)),
                            pil_image.getpixel((j + 1, i)),
                            pil_image.getpixel((j, i + 1)),
                            pil_image.getpixel((j + 1, i + 1)),
                        ]

                        new_pixel = combine_pixels(pixels, yes_color, no_color)
                        tile.putpixel((j // 2 + x_offset, i // 2 + y_offset), new_pixel)

        if n_transparent_tiles != 4:
            tile_image = pyvips.Image.new_from_array(tile)
            out_dir = tiles_folder / str(z) / str(x)
            out_dir.mkdir(parents=True, exist_ok=True)
            tile_image.write_to_file(str(out_dir / f"{y}.webp"), Q=100, lossless=True)
        return 1

    def create_pmtiles(self):
        pmtiles_folder = self.output_folder_path / 'pmtiles'
        pmtiles_folder.mkdir(parents=True, exist_ok=True)
        acc = 0
        with open(pmtiles_folder / f"{self.dataset}.pmtiles", "wb") as f:
            writer = Writer(f)

            for tileid in range(0, zxy_to_tileid(8, 0, 0)):
                acc += 1
                z, x, y = tileid_to_zxy(tileid)
                file_path = self.tiles_folder / str(z) / str(x) / f"{y}.webp"
                if file_path.exists():
                    with open(file_path, "rb") as f:
                        writer.write_tile(tileid, f.read())

            writer.finalize(
                {
                    "tile_type": TileType.WEBP,
                    "tile_compression": Compression.NONE,
                    "min_zoom": 0,
                    "max_zoom": 7,
                    "min_lon_e7": int(-180.0 * 10000000),
                    "min_lat_e7": int(-85.0 * 10000000),
                    "max_lon_e7": int(180.0 * 10000000),
                    "max_lat_e7": int(85.0 * 10000000),
                    "center_zoom": 0,
                    "center_lon_e7": 0,
                    "center_lat_e7": 0,
                },
                {},
            )


if __name__ == "__main__":
    # Get the latest from the `codes_benc` directory in `aa_derived_mirror_metadata`:
    # https://annas-archive.org/torrents#aa_derived_mirror_metadata

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
        "trantor",
    ]

    for dataset in datasets:
        x = RasterTilesMaker(
            packed_isbns_ints_filepath=Path("data")
            / "aa_isbn13_codes_20250111T024210Z.benc.zst",
            output_folder_path=Path("output"),
            published_color=(140, 31, 0),
            archived_color=(191, 191, 191),
            single_dataset_color=(31, 173, 109),
            dataset=dataset,
        )
        x.run()
