#!/usr/bin/env python3
"""Set PNG pHYs resolution without resampling or re-encoding image data.

Usage: python normalize_png_ppi.py PATH [--recursive] [--ppi 72]
       Add --apply --backup-dir PATH to write; otherwise inspect only.
"""
from __future__ import annotations
import argparse
from io import BytesIO
import math
from pathlib import Path
import struct
import tempfile
import zlib
from PIL import Image

SIGNATURE = b'\x89PNG\r\n\x1a\n'

def normalize_png(raw: bytes, ppi: float = 72) -> bytes:
    if isinstance(ppi, bool) or not isinstance(ppi, (int, float)) or not math.isfinite(ppi) or ppi <= 0:
        raise ValueError('PPI must be a positive finite number')
    ppm = round(ppi / 0.0254)
    if not 1 <= ppm <= 0xffffffff:
        raise ValueError('PPI is outside PNG pHYs range')
    if not raw.startswith(SIGNATURE):
        raise ValueError('Not a PNG')
    chunks = []
    offset = len(SIGNATURE)
    ended = False
    while offset < len(raw):
        if offset + 12 > len(raw):
            raise ValueError('Truncated PNG chunk')
        length = struct.unpack('>I', raw[offset:offset + 4])[0]
        end = offset + length + 12
        if end > len(raw):
            raise ValueError('Truncated PNG data')
        kind = raw[offset + 4:offset + 8]
        body = raw[offset + 8:end - 4]
        crc = struct.unpack('>I', raw[end - 4:end])[0]
        if zlib.crc32(kind + body) & 0xffffffff != crc:
            raise ValueError('Invalid PNG CRC')
        chunks.append((kind, raw[offset:end]))
        offset = end
        if kind == b'IEND':
            ended = True
            break
    if not ended or offset != len(raw) or chunks[0][0] != b'IHDR':
        raise ValueError('Invalid PNG structure or trailing data')
    with Image.open(BytesIO(raw)) as before:
        if getattr(before, 'n_frames', 1) != 1:
            raise ValueError('Animated PNG is not supported')
        exif = before.getexif()
        if any(tag in exif for tag in (282, 283, 296)):
            raise ValueError('EXIF resolution also present; reconcile it explicitly before changing pHYs')
        size = before.size
        pixels = before.convert('RGBA').tobytes()
    payload = b'pHYs' + struct.pack('>IIB', ppm, ppm, 1)
    replacement = struct.pack('>I', 9) + payload + struct.pack('>I', zlib.crc32(payload) & 0xffffffff)
    result = SIGNATURE + chunks[0][1] + replacement + b''.join(chunk for kind, chunk in chunks[1:] if kind != b'pHYs')
    with Image.open(BytesIO(result)) as after:
        if after.size != size or after.convert('RGBA').tobytes() != pixels:
            raise ValueError('Pixel or alpha data changed')
    return result

def write_atomic(path: Path, content: bytes) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.ppi-', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        temporary.replace(path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', type=Path)
    parser.add_argument('--ppi', type=float, default=72)
    parser.add_argument('--recursive', action='store_true')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--backup-dir', type=Path)
    args = parser.parse_args()
    try:
        target = args.path.resolve(strict=True)
        base = target if target.is_dir() else target.parent
        files = sorted(target.rglob('*.png') if args.recursive else target.glob('*.png')) if target.is_dir() else [target]
        if not files:
            raise ValueError('No PNG files found')
        if args.apply and not args.backup_dir:
            raise ValueError('--apply requires --backup-dir for original files')
        backup = args.backup_dir.resolve() if args.backup_dir else None
        if backup and (backup == base or backup.is_relative_to(base)):
            raise ValueError('Backup directory must be outside the input directory')
        prepared = []
        for path in files:
            if path.is_symlink() or not path.resolve().is_relative_to(base):
                raise ValueError('Refusing a file outside the requested directory')
            raw = path.read_bytes()
            result = normalize_png(raw, args.ppi)
            with Image.open(BytesIO(raw)) as im:
                print(f'{path.name}: {im.size}, {im.info.get("dpi")} -> {args.ppi:g} PPI; pixels and alpha unchanged')
            if result != raw:
                saved = backup / path.relative_to(base) if backup else None
                if saved and saved.exists():
                    raise ValueError(f'Backup already exists: {saved}')
                prepared.append((path, raw, result, saved))
        if args.apply:
            for path, raw, result, saved in prepared:
                saved.parent.mkdir(parents=True, exist_ok=True)
                saved.write_bytes(raw)
            for path, raw, result, saved in prepared:
                if path.read_bytes() != raw:
                    raise ValueError(f'File changed since inspection: {path}')
                write_atomic(path, result)
        print(f'{"Updated" if args.apply else "Would update"}: {len(prepared)} PNG files; no resampling')
    except (OSError, ValueError) as exc:
        parser.exit(1, f'PNG PPI normalization failed: {exc}\n')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
