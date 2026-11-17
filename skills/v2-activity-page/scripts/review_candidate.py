"""Check source-bound color review of a rendered candidate, not aesthetic quality.

Run after sample_composer and actual visual inspection. Never infer pass from
geometry, color counts or text prompts. A draft can exist while review fails.
"""
import argparse
import json
from pathlib import Path
from sample_composer import digest

COLOR_CHECKS = ('palette_coherence', 'visual_variety', 'functional_distribution', 'kv_relationship')


def check_review(manifest_path, preview_path, review):
    manifest_path, preview_path = Path(manifest_path), Path(preview_path)
    composition_path = preview_path.with_suffix('.composition.json')
    record = json.loads(composition_path.read_text(encoding='utf-8'))
    manifest_hash, preview_hash = digest(manifest_path), digest(preview_path)
    if (record.get('mechanical_check') != 'pass'
            or record.get('manifest_sha256') != manifest_hash
            or record.get('output_sha256') != preview_hash):
        raise ValueError('Candidate does not match its composition record')
    if (review.get('manifest_sha256') != manifest_hash
            or review.get('preview_sha256') != preview_hash):
        raise ValueError('Color review is missing or stale for this actual candidate')
    # Detect source replacement after composition, even if manifest is unchanged.
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    for item in manifest.get('rows', []) + manifest.get('foregrounds', []):
        if digest(manifest_path.parent / item['file']) != item['sha256']:
            raise ValueError('Candidate source changed; recompose and inspect again')
    for key in COLOR_CHECKS:
        entry = review.get(key, {})
        if (entry.get('status') != 'pass' or not isinstance(entry.get('observation'), str)
                or not entry['observation'].strip()):
            raise ValueError('Actual candidate color review required: ' + key)
    return {'candidate_status': 'reviewed', 'preview_sha256': preview_hash,
            'note': 'Recorded visual review checked; this is not an automatic aesthetic score.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('preview', type=Path)
    parser.add_argument('review', type=Path)
    args = parser.parse_args()
    try:
        result = check_review(args.manifest, args.preview,
                              json.loads(args.review.read_text(encoding='utf-8')))
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1, str(exc) + '\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
