#!/usr/bin/env python3
"""Build deterministic large and phone-size review sheets from cover proofs."""
from pathlib import Path
from math import ceil

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
PROOFS = ROOT / 'out' / 'review' / 'covers'
OUTPUT = ROOT / 'out' / 'review'


def build(name: str, tile: tuple[int, int]) -> None:
    files = sorted(PROOFS.glob('post-*-cover.png'))
    if not files:
        raise RuntimeError('Expected at least 1 cover proof, found 0')
    width, height = tile
    columns = 4
    rows = ceil(len(files) / columns)
    sheet = Image.new('RGB', (width * columns, height * rows), 'black')
    for index, file in enumerate(files):
        with Image.open(file) as source:
            image = source.convert('RGB').resize(tile, Image.Resampling.LANCZOS)
        sheet.paste(image, ((index % columns) * width, (index // columns) * height))
    sheet.save(OUTPUT / name, format='PNG', optimize=True)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    build('covers-contact-sheet-phone.png', (270, 480))
    build('covers-contact-sheet-large.png', (540, 960))


if __name__ == '__main__':
    main()
