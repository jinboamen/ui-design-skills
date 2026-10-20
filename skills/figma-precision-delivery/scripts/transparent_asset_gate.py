#!/usr/bin/env python3
"""Fail-closed admission gate for transparent PNG-origin WebP assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

try:
    from PIL import Image, ImageChops
except ImportError as exc:
    raise SystemExit("Pillow is required; transparent asset admission is blocked.") from exc


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("project-root", "intermediate-png", "candidate-webp", "reference", "destination", "report"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    parser.add_argument("--expected-width", required=True, type=int)
    parser.add_argument("--expected-height", required=True, type=int)
    parser.add_argument("--node-id", required=True)
    parser.add_argument("--render-node-id", required=True)
    parser.add_argument("--reference-kind", required=True, choices=("official-canvas-render", "figma-manual-export"))
    parser.add_argument("--max-changed-ratio", type=float, default=0.0025)
    parser.add_argument("--max-mae", type=float, default=1.0)
    parser.add_argument("--max-alpha-mae", type=float, default=1.0)
    parser.add_argument("--max-boundary-error", type=int, default=1)
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def load(path: Path, expected_format: str, errors: list[str]) -> Image.Image | None:
    try:
        image = Image.open(path)
        image.load()
    except Exception as exc:
        errors.append(f"{path.name}: cannot decode: {exc}")
        return None
    if image.format != expected_format:
        errors.append(f"{path.name}: expected {expected_format}, got {image.format}")
    return image


def summary(image: Image.Image) -> dict[str, object]:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    histogram = alpha.histogram()
    present = [value for value, count in enumerate(histogram) if count]
    width, height = rgba.size
    corners = [list(rgba.getpixel(point)) for point in ((0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1))]
    bounds = alpha.point(lambda value: 255 if value > 0 else 0).getbbox()
    return {
        "mode": image.mode,
        "minAlpha": min(present),
        "maxAlpha": max(present),
        "transparentPixels": histogram[0],
        "semitransparentPixels": sum(histogram[1:255]),
        "opaquePixels": histogram[255],
        "corners": corners,
        "contentBounds": list(bounds) if bounds else None,
    }


def check_transparency(name: str, data: dict[str, object], errors: list[str]) -> None:
    if data["minAlpha"] == 255:
        errors.append(f"{name}: every pixel is opaque")
    if data["transparentPixels"] == 0 and data["semitransparentPixels"] == 0:
        errors.append(f"{name}: no transparent pixels")
    corners = data["corners"]
    if all(corner[3] == 255 for corner in corners) and all(corner[:3] == corners[0][:3] for corner in corners[1:]):
        errors.append(f"{name}: same opaque RGB background in all corners {corners[0][:3]}")


def compare(left: Image.Image, right: Image.Image) -> dict[str, object]:
    left, right = left.convert("RGBA"), right.convert("RGBA")
    if left.size != right.size:
        return {"sameSize": False, "leftSize": list(left.size), "rightSize": list(right.size)}
    diff = ImageChops.difference(left, right)
    raw = diff.tobytes()
    pixels = left.width * left.height
    changed = total = alpha_total = 0
    histogram = [0] * 256
    for offset in range(0, len(raw), 4):
        values = raw[offset:offset + 4]
        changed += max(values) > 16
        alpha_total += values[3]
        for value in values:
            total += value
            histogram[value] += 1
    target, cumulative, p95 = int(len(raw) * 0.95 + 0.999999), 0, 255
    for value, count in enumerate(histogram):
        cumulative += count
        if cumulative >= target:
            p95 = value
            break
    return {
        "sameSize": True,
        "changedPixelRatioAt16": changed / pixels,
        "meanAbsoluteError": total / len(raw),
        "alphaMeanAbsoluteError": alpha_total / pixels,
        "p95AbsoluteError": p95,
        "exactDecodedPixels": left.tobytes() == right.tobytes(),
    }


def boundary_delta(left: dict[str, object], right: dict[str, object]) -> int | None:
    if left["contentBounds"] is None or right["contentBounds"] is None:
        return None
    return max(abs(a - b) for a, b in zip(left["contentBounds"], right["contentBounds"]))


def save_report(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    pending.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
    os.replace(pending, path)


def add_comparison_errors(
    name: str,
    result: dict[str, object],
    errors: list[str],
    max_changed_ratio: float,
    max_mae: float,
    max_alpha_mae: float,
) -> None:
    if not result.get("sameSize"):
        errors.append(f"{name}: dimensions differ")
        return
    if result["changedPixelRatioAt16"] > max_changed_ratio:
        errors.append(f"{name}: changed pixel ratio exceeds threshold")
    if result["meanAbsoluteError"] > max_mae:
        errors.append(f"{name}: RGBA MAE exceeds threshold")
    if result["alphaMeanAbsoluteError"] > max_alpha_mae:
        errors.append(f"{name}: Alpha MAE exceeds threshold")


def main() -> int:
    args = arguments()
    project = resolve(args.project_root)
    png_path = resolve(args.intermediate_png)
    webp_path = resolve(args.candidate_webp)
    reference_path = resolve(args.reference)
    destination = resolve(args.destination)
    report_path = resolve(args.report)
    errors: list[str] = []

    if args.expected_width <= 0 or args.expected_height <= 0:
        errors.append("expected dimensions must be positive")
    for staged in (png_path, webp_path, reference_path, report_path):
        if inside(staged, project):
            errors.append(f"staged evidence must stay outside project root: {staged}")
    if not inside(destination, project):
        errors.append("destination must resolve inside project root")
    if png_path == reference_path or webp_path == reference_path:
        errors.append("independent reference must not reuse a candidate path")
    for path in (png_path, webp_path, reference_path):
        if not path.is_file():
            errors.append(f"required input does not exist: {path}")

    png = load(png_path, "PNG", errors) if png_path.is_file() else None
    webp = load(webp_path, "WEBP", errors) if webp_path.is_file() else None
    reference = load(reference_path, "PNG", errors) if reference_path.is_file() else None
    expected_size = (args.expected_width, args.expected_height)
    summaries: dict[str, dict[str, object]] = {}
    for name, image in (("intermediatePng", png), ("candidateWebp", webp), ("independentReference", reference)):
        if image is None:
            continue
        if image.size != expected_size:
            errors.append(f"{name}: expected size {expected_size}, got {image.size}")
        summaries[name] = summary(image)
        check_transparency(name, summaries[name], errors)

    comparisons: dict[str, dict[str, object]] = {}
    if png is not None and reference is not None:
        result = compare(png, reference)
        comparisons["pngToIndependentReference"] = result
        add_comparison_errors(
            "pngToIndependentReference", result, errors,
            args.max_changed_ratio, args.max_mae, args.max_alpha_mae,
        )
        delta = boundary_delta(summaries["intermediatePng"], summaries["independentReference"])
        result["contentBoundaryMaxError"] = delta
        if delta is None or delta > args.max_boundary_error:
            errors.append("pngToIndependentReference: content boundary exceeds threshold")

    if webp is not None and png is not None:
        result = compare(webp, png)
        comparisons["webpToIntermediatePng"] = result
        delta = boundary_delta(summaries["candidateWebp"], summaries["intermediatePng"])
        result["contentBoundaryMaxError"] = delta
        if not result.get("sameSize") or not result.get("exactDecodedPixels"):
            errors.append("webpToIntermediatePng: decoded pixels are not lossless-identical")
        if delta != 0:
            errors.append("webpToIntermediatePng: Alpha content bounds changed")

    report: dict[str, object] = {
        "status": "failed" if errors else "passed",
        "nodeId": args.node_id,
        "renderNodeId": args.render_node_id,
        "referenceKind": args.reference_kind,
        "expectedSize": list(expected_size),
        "summaries": summaries,
        "comparisons": comparisons,
        "errors": errors,
        "promoted": False,
    }
    if errors:
        if not inside(report_path, project):
            save_report(report_path, report)
        print(json.dumps(report, ensure_ascii=True, indent=2))
        return 1

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent, delete=False) as handle:
        pending = Path(handle.name)
    try:
        shutil.copyfile(webp_path, pending)
        os.replace(pending, destination)
    finally:
        pending.unlink(missing_ok=True)
    report["promoted"] = True
    report["destinationSha256"] = digest(destination)
    save_report(report_path, report)
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
