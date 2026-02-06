#!/usr/bin/env python3
"""
tga2png.py

Convert .tga icons from one directory to .png icons in another directory.

Usage:
  python tga2png.py --from tga-icons/ --to png-icons/
"""

from __future__ import annotations
from pathlib import Path

import click
from PIL import Image


def convert_one(src_path: Path, dst_path: Path, overwrite: bool) -> bool:
    """Convert a single TGA file to PNG. Returns True if written, False if skipped."""
    if dst_path.exists() and not overwrite:
        return False

    with Image.open(src_path) as im:
        # TGA can be paletted/LA/RGBA/etc. Convert to RGBA for consistent alpha handling.
        # If you prefer to keep RGB when no alpha exists, adjust logic below.
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGBA")
        elif im.mode == "RGB":
            # Keep as RGB (smaller) unless you want RGBA always.
            pass

        dst_path.parent.mkdir(parents=True, exist_ok=True)
        im.save(dst_path, format="PNG", optimize=True)

    return True


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--from",
    "src_dir",
    type=click.Path(path_type=Path, exists=True, file_okay=False, dir_okay=True),
    required=True,
    help="Source directory containing .tga files.",
)
@click.option(
    "--to",
    "dst_dir",
    type=click.Path(path_type=Path, exists=False, file_okay=False, dir_okay=True),
    required=True,
    help="Destination directory for .png files (created if missing).",
)
@click.option(
    "--recursive/--no-recursive",
    default=False,
    show_default=True,
    help="Search for .tga files recursively under the source directory.",
)
@click.option(
    "--overwrite/--no-overwrite",
    default=False,
    show_default=True,
    help="Overwrite existing .png files in the destination directory.",
)
def main(src_dir: Path, dst_dir: Path, recursive: bool, overwrite: bool) -> None:
    """Convert TGA icons to PNG using Pillow."""
    if recursive:
        candidates = src_dir.rglob("*")
    else:
        candidates = src_dir.iterdir()

    tga_files = sorted(
        p for p in candidates
        if p.is_file() and p.suffix.lower() == ".tga"
    )

    if not tga_files:
        click.echo(f"No .tga files found in: {src_dir}", err=True)
        raise SystemExit(1)

    converted = 0
    skipped = 0
    failed = 0

    for src_path in tga_files:
        # Preserve relative path if recursive; otherwise just use file name.
        rel = src_path.relative_to(src_dir) if recursive else src_path.name
        rel = Path(rel)

        dst_path = (dst_dir / rel).with_suffix(".png")

        try:
            written = convert_one(src_path, dst_path, overwrite=overwrite)
            if written:
                converted += 1
                click.echo(f"OK  {src_path} -> {dst_path}")
            else:
                skipped += 1
                click.echo(f"SKIP (exists) {dst_path}")
        except Exception as e:
            failed += 1
            click.echo(f"FAIL {src_path}: {e}", err=True)

    click.echo(
        f"\nDone. Converted: {converted}, Skipped: {skipped}, Failed: {failed}"
    )

    if failed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
