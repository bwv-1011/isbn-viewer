## Requirements

* [uv](https://docs.astral.sh/uv/) for Python package and environment management. It will also handle python installation.
* [tippecanoe](https://github.com/felt/tippecanoe)

## Installation

Dependencies are managed with uv which can be installed following [these](https://docs.astral.sh/uv/#getting-started) instructions.

Change into this directory and run:

```console
$ uv sync
```

We also need tippecanoe to create pmtiles from geojson files, it can be installed following [these](https://github.com/felt/tippecanoe?tab=readme-ov-file#installation) instructions. 

## Build raster tiles

Get the latest from the `codes_benc` directory in `aa_derived_mirror_metadata` and place in data folder.

```console
$ uv run create_raster_tiles.py
```

## Build country vector tiles

```console
$ uv run create_country_polygons.py
```

## Build holding extrusion vector tiles

```console
$ uv run create_holding_polygons.py
```

Finally copy all pmtiles files from output/pmtiles into public folder. 
