#!/usr/bin/env python3
"""Build deterministic large and phone-size review sheets from cover proofs."""
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
PROOFS = ROOT / 'out' / 'review' / 'covers'
OUTPUT = ROOT / 'out' / 'review'


def build(name: str, tile: tuple[int, int]) -> None:
    files = sorted(PROOFS.glob('post-*-cover.png'))
    if len(files) != 14:
        raise RuntimeError(f'Expected 14 cover proofs, found {len(files)}')
    width, height = tile
    sheet = Image.new('RGB', (width * 4, height * 4), 'black')
    for index, file in enumerate(files):
        with Image.open(file) as source:
            image = source.convert('RGB').resize(tile, Image.Resampling.LANCZOS)
        sheet.paste(image, ((index % 4) * width, (index // 4) * height))
    sheet.save(OUTPUT / name, format='PNG', optimize=True)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    build('covers-contact-sheet-phone.png', (270, 480))
    build('covers-contact-sheet-large.png', (540, 960))


if __name__ == '__main__':
    main()
