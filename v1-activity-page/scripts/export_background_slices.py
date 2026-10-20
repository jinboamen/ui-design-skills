#!/usr/bin/env python3
"""Export background slices from the reviewed final master without resampling.

Usage: python export_background_slices.py OUTPUT_DIR
Supports continuous and segmented designs; this performs no image generation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image
from validate_output import expected_size, local_file, export_ppi

MODES = {"continuous", "整体衔接", "segmented", "按模块区分"}


def export_slices(root: Path) -> int:
    root = root.resolve()
    data = json.loads((root / "assets.json").read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("background_mode") not in MODES:
        raise ValueError("background_mode须为continuous或segmented（或对应中文模式）")
    ppi = export_ppi(data)
    master = data.get("background_master")
    if not isinstance(master, dict):
        raise ValueError("两种背景模式都须先完成跨界组合母图，再导出")
    source_path = local_file(root, master["file"])
    parts = master.get("slices")
    if not isinstance(parts, list) or not parts:
        raise ValueError("母图切片清单不能为空")
    assets = {a["file"]: a for a in data.get("assets", [])
              if isinstance(a, dict) and isinstance(a.get("file"), str)}
    required = {}
    for filename, asset in assets.items():
        role = asset.get("role", "")
        if role in {"hero", "banner"} or role.endswith(".background"):
            size = expected_size(role, asset, data)
            if size and size[0] == 1920:
                required[filename] = size
    names = [part.get("file") for part in parts if isinstance(part, dict)]
    if (len(names) != len(parts) or len(set(names)) != len(names)
            or set(names) != set(required)):
        raise ValueError("须恰好列出全部1920px头图／背景切片，不能漏项或重复")
    if assets[names[0]].get("role") != "hero" or parts[0].get("top") != 0:
        raise ValueError("母图第一片须为从y=0开始的头图")
    with Image.open(source_path) as original:
        if original.width != 1920:
            raise ValueError("最终母图须先校正为1920px宽，导出器不会缩放")
        if "A" in original.getbands() and original.getchannel("A").getextrema()[0] != 255:
            raise ValueError("背景母图须不透明")
        image = original.convert("RGB")
    prepared = []
    cursor = 0
    for part in parts:
        top, height = part.get("top"), part.get("height")
        if (any(not isinstance(v, int) or isinstance(v, bool) for v in (top, height))
                or top < 0 or height <= 0):
            raise ValueError("切片top须为非负整数，height须为正整数")
        if top < cursor or (not data.get("gift_count") and top != cursor):
            raise ValueError("切片范围有重叠或空缺，不能重复导出生成时的上下文")
        if (1920, height) != required[part["file"]] or top + height > image.height:
            raise ValueError("切片尺寸与V1规格不符或超出母图")
        output = local_file(root, part["file"])
        if output == source_path or output.suffix.lower() != ".png":
            raise ValueError("切片须为独立PNG路径，不能覆盖母图")
        prepared.append((output, image.crop((0, top, 1920, top + height))))
        cursor = top + height
    if not data.get("gift_count") and cursor != image.height:
        raise ValueError("母图总高与模块累计高度不一致")
    # All ranges and targets are checked before any output is written.
    for output, picture in prepared:
        output.parent.mkdir(parents=True, exist_ok=True)
        picture.save(output, format="PNG", dpi=(ppi, ppi))
    return len(prepared)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    try:
        count = export_slices(args.output_dir)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(1, f"背景导出失败：{exc}\n")
    print(f"已从同一最终母图原像素导出{count}张背景；仍须实际浏览器逐缝验收。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
