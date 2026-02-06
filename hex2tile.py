#!/usr/bin/env python3
import json
import math
import os
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any, Optional

import click
from PIL import Image


@dataclass(frozen=True)
class Bounds:
    south: float
    west: float
    north: float
    east: float

    @property
    def width_world(self) -> float:
        return self.east - self.west

    @property
    def height_world(self) -> float:
        return self.south - self.north


def compute_bounds_from_hexes(entries, hex_size):
    half_width = hex_size / 2
    half_height = (math.sqrt(3) / 2.0) * half_width

    west = float("inf")
    east = float("-inf")
    south = float("-inf")
    north = float("inf")

    for e in entries:
        q = float(e["q"])
        p = float(e["p"])

        x, y = compute_hex_center(
            q=q,
            p=p,
            hex_size=hex_size
        )

        west = min(west, x - half_width)
        east = max(east, x + half_width)
        south = max(south, y + half_height)
        north = min(north, y - half_height)

    return Bounds(
        south=south,
        west=west,
        north=north,
        east=east,
    )


def pad_bounds_to_tile(bounds: Bounds, tile_size: int) -> Bounds:
    base_w = int(math.ceil(bounds.width_world))
    base_h = int(math.ceil(bounds.height_world))
    padded_w = ((base_w + tile_size - 1) // tile_size) * tile_size
    padded_h = ((base_h + tile_size - 1) // tile_size) * tile_size
    pad_w = padded_w - base_w
    pad_h = padded_h - base_h
    if pad_w == 0 and pad_h == 0:
        return bounds
    pad_w_left = pad_w // 2
    pad_w_right = pad_w - pad_w_left
    pad_h_top = pad_h // 2
    pad_h_bottom = pad_h - pad_h_top
    return Bounds(
        south=bounds.south + pad_h_bottom,
        west=bounds.west - pad_w_left,
        north=bounds.north - pad_h_top,
        east=bounds.east + pad_w_right,
    )

def compute_hex_center(q: float, p: float, hex_size: float) -> Tuple[float, float]:
    """
    Returns center of the hex in pixel coordinates
    """
    hex_height = math.sqrt(3) * (hex_size/2)

    py_component = p * (hex_height/2)
    qy_component = q * hex_height
    
    x = p * math.sqrt(3)/2 * hex_height
    y = qy_component + py_component

    return [x, y]


def load_config(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError("Config JSON must be an object keyed by hex id.")

    entries: List[Dict[str, Any]] = []

    for hex_id, e in data.items():
        if not isinstance(e, dict):
            raise ValueError(f"Entry '{hex_id}' is not an object.")

        for k in ("file", "q", "p"):
            if k not in e:
                raise ValueError(f"Entry '{hex_id}' missing required key: {k}")

        entry = {
            "id": hex_id,
            "name": e.get("name", hex_id),
            "file": e["file"],
            "q": e["q"],
            "p": e["p"],
        }

        entries.append(entry)

    return entries


def ensure_rgba(im: Image.Image) -> Image.Image:
    return im.convert("RGBA") if im.mode != "RGBA" else im


def composite_centered(canvas: Image.Image, sprite: Image.Image, center_x: float, center_y: float) -> None:
    """
    Alpha-composite sprite onto canvas so that sprite is centered at (center_x, center_y).
    """
    sw, sh = sprite.size
    tlx = int(round(center_x - sw/2))
    tly = int(round(center_y - sh/2))
    canvas.alpha_composite(sprite, (tlx, tly))


def make_master(
        entries: List[Dict[str, Any]],
        hex_size: int,
        background: Tuple[int, int, int, int] = (0, 0, 0, 0),
        verbose: bool = True,
        tile_size: int = 256
    ) -> Image.Image:

    bounds = compute_bounds_from_hexes(entries, hex_size)
    bounds = pad_bounds_to_tile(bounds, tile_size)
    print(f"Map bounds: {bounds}")
    master_w = int(math.ceil(bounds.width_world))
    master_h = int(math.ceil(bounds.height_world))
    print(f"Map size: {master_w}x{master_h}")

    if master_w <= 0 or master_h <= 0:
        raise ValueError(f"Computed master size is invalid. Check bounds/max_zoom.")

    canvas = Image.new("RGBA", (master_w, master_h), background)

    for e in entries:
        path = e["file"]
        q = float(e["q"])
        p = float(e["p"])

        sprite = ensure_rgba(Image.open(path))
        cx, cy = compute_hex_center(q, p, hex_size)
        cx = cx - bounds.west
        cy = cy - bounds.north

        if verbose and e.get("name"):
            click.echo(f"Placing {e['name']} px({cx:.1f},{cy:.1f})")

        composite_centered(canvas, sprite, cx, cy)

    return canvas


def save_tiles_from_master(master: Image.Image,
                           out_dir: str,
                           max_zoom: int,
                           min_zoom: int,
                           tile_size: int = 256) -> None:
    """
    Build a simple XYZ pyramid where z=max_zoom is the master resolution.
    Lower zooms are downsampled by powers of two.
    """
    master = ensure_rgba(master)
    W, H = master.size

    for z in range(max_zoom, min_zoom-1, -1):
        scale = 2 ** (max_zoom - z)  # z=max_zoom -> 1
        zw = int(math.ceil(W / scale))
        zh = int(math.ceil(H / scale))

        if scale == 1:
            zimg = master
        else:
            zimg = master.resize((zw, zh), resample=Image.Resampling.LANCZOS)

        x_tiles = int(math.ceil(zw / tile_size))
        y_tiles = int(math.ceil(zh / tile_size))

        for x in range(x_tiles):
            for y in range(y_tiles):
                left = x * tile_size
                upper = y * tile_size
                right = min(left + tile_size, zw)
                lower = min(upper + tile_size, zh)

                tile = Image.new("RGBA", (tile_size, tile_size), (0, 0, 0, 0))
                crop = zimg.crop((left, upper, right, lower))
                tile.alpha_composite(crop, (0, 0))

                tile_path = os.path.join(out_dir, str(z), str(x), f"{y}.png")
                os.makedirs(os.path.dirname(tile_path), exist_ok=True)
                tile.save(tile_path, "PNG")


@click.command()
@click.option("--hexes", "config_path", required=True, type=click.Path(exists=True, dir_okay=False),
              help=(
                  "Path to config JSON with format: "
                  "{<hex_id>: { 'name': <hex_name>, 'file': <hex_png>, 'q': <q>, 'p': <p> } } "
                  "q and p are axial hexagon coordinates")
              )
@click.option("--out", "out_dir", required=True, type=click.Path(file_okay=False),
              help="Output directory for tiles (creates z/x/y.png).")
@click.option("--max-zoom", default=5, show_default=True, type=int,
              help="Max zoom level (master resolution uses ppu = 2^maxZoom).")
@click.option("--min-zoom", default=0, show_default=True, type=int,
              help="Min zoom level")
@click.option("--tile-size", default=256, show_default=True, type=int,
              help="Tile size in pixels (typically 256).")
@click.option("--hex-size", default=1024, show_default=True, type=int,
              help="Size of the hex map (width/diagonal) in pixels.")
@click.option("--write-master", default=None, type=click.Path(dir_okay=False),
              help="Optional path to write the assembled master PNG for debugging.")
@click.option("--quiet", is_flag=True, help="Reduce logging.")
def main(
    config_path: str, 
    out_dir: str, 
    max_zoom: int, 
    min_zoom: int,
    tile_size: int,
    hex_size: int, 
    write_master: Optional[str], 
    quiet: bool
) -> None:

    entries = load_config(config_path)

    master = make_master(
        entries=entries,
        hex_size=hex_size,
        verbose=not quiet,
    )

    if write_master:
        os.makedirs(os.path.dirname(write_master) or ".", exist_ok=True)
        master.save(write_master, "PNG")
        if not quiet:
            click.echo(f"Wrote master: {write_master} ({master.size[0]}x{master.size[1]})")

    save_tiles_from_master(
        master, out_dir=out_dir, max_zoom=max_zoom, min_zoom=min_zoom, tile_size=tile_size
    )
    if not quiet:
        click.echo(f"Tiles written to: {out_dir}")


if __name__ == "__main__":
    main()
