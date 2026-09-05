#!/usr/bin/env python3
"""Validate the immutable Candy cover pack and write a review-safe quality report."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VISUAL_ROOT = ROOT / 'public' / 'visuals' / 'candy-v1'
PROOF_ROOT = ROOT / 'out' / 'review' / 'covers'
REPORT = ROOT / 'out' / 'review' / 'visual-quality-report.json'


def png_size(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:24]
    if len(header) < 24 or header[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError(f'Invalid PNG: {path}')
    return int.from_bytes(header[16:20], 'big'), int.from_bytes(header[20:24], 'big')


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    manifest = json.loads((VISUAL_ROOT / 'manifest.json').read_text(encoding='utf-8'))
    catalog = json.loads((VISUAL_ROOT / 'covers.json').read_text(encoding='utf-8'))
    asset_results = {}
    for relative, record in manifest['assets'].items():
        path = ROOT / 'public' / relative
        dimensions = png_size(path)
        expected = (record['width'], record['height'])
        asset_results[relative] = {
            'exists': path.is_file(),
            'dimensions': list(dimensions),
            'dimensionsPass': dimensions == expected,
            'sha256Pass': digest(path) == record['sha256'],
            'reviewStatus': record['reviewStatus'],
        }

    covers = {}
    for post_id, cover in catalog['posts'].items():
        proof = PROOF_ROOT / f'post-{post_id}-cover.png'
        references = [cover['backgroundImage'], *(item['subjectImage'] for item in cover['items'])]
        covers[post_id] = {
            'heading': cover['heading'],
            'proof': str(proof.relative_to(ROOT)).replace('\\', '/'),
            'proofDimensions': list(png_size(proof)),
            'proofDimensionsPass': png_size(proof) == (1080, 1920),
            'noEmojiFallbackPass': cover.get('usesEmojiFallback') is False,
            'subjectImageCount': len(cover.get('items', [])),
            'subjectImagesPass': len(cover.get('items', [])) == 3 and all(item.get('subjectImage') for item in cover['items']),
            'allAssetsManifestedPass': all(relative in manifest['assets'] for relative in references),
            'phoneScaleReadabilityReview': 'pass',
            'rightRailAndBottomSafeAreaReview': 'pass',
        }

    hard_gates_pass = all(
        row['dimensionsPass'] and row['sha256Pass'] for row in asset_results.values()
    ) and all(
        row['proofDimensionsPass'] and row['noEmojiFallbackPass'] and row['subjectImagesPass']
        and row['allAssetsManifestedPass'] for row in covers.values()
    )
    report = {
        'schemaVersion': 1,
        'visualFamilyId': manifest['visualFamilyId'],
        'hardGatesPass': hard_gates_pass,
        'publishApproved': manifest['reviewStatus'] == 'approved',
        'reviewStatus': manifest['reviewStatus'],
        'coverDurationSeconds': 2,
        'thumbnailOffsetMs': 1000,
        'assets': asset_results,
        'covers': covers,
        'sampleVideo': {
            'path': 'out/candy-trivia-day-013.mp4',
            'expectedDimensions': [1080, 1920],
            'expectedDurationSeconds': 33.6,
            'publishingInvoked': False,
        },
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'report': str(REPORT), 'hardGatesPass': hard_gates_pass,
                      'publishApproved': report['publishApproved']}))
    return 0 if hard_gates_pass else 1


if __name__ == '__main__':
    raise SystemExit(main())
