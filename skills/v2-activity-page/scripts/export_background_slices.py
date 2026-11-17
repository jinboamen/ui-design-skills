#!/usr/bin/env python3
"""Export V2 2x PNG backgrounds from a common 3840px master without resizing.

Usage: python export_background_slices.py OUTPUT_DIR
Rectangles are stored in the 1920px design coordinate system. One or two module
slots fill each row, and repeated banners are identified by module_id.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from PIL import Image
from validate_output import local_file, export_ppi, validate_png_ppi
from layout_contract import modules, slice_plan


def export_slices(root: Path) -> int:
    root = root.resolve()
    data = json.loads((root / 'assets.json').read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('background_mode') not in {'continuous','整体衔接','segmented','按模块区分'}:
        raise ValueError('须记录已确认的background_mode')
    modules(data)
    plan = slice_plan(data)
    master = data['background_master']
    source_path = local_file(root, master['file'])
    ppi = export_ppi(data)
    with Image.open(source_path) as source:
        if source.format != 'PNG' or source.size != (3840, data['layout']['design_height'] * 2):
            raise ValueError('母图须为3840×(design_height*2)的PNG，不允许将1x图临时放大冒充2x')
        validate_png_ppi(source, data)
        if source.convert('RGBA').getchannel('A').getextrema()[0] != 255:
            raise ValueError('母图须不透明')
        image = source.convert('RGB')
    prepared, targets = [], set()
    for part, (x, y, width, height) in plan:
        target = local_file(root, part['file'])
        if target == source_path or target.suffix.lower() != '.png' or target in targets:
            raise ValueError('背景切片须使用唯一独立PNG路径，不得覆盖母图')
        targets.add(target)
        prepared.append((target, image.crop((x*2, y*2, (x+width)*2, (y+height)*2))))
    # Validate the entire plan before writing anything; no partial output on invalid geometry.
    for target, image in prepared:
        target.parent.mkdir(parents=True, exist_ok=True)
        image.save(target, format='PNG', dpi=(ppi, ppi))
    return len(prepared)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output_dir', type=Path)
    args = parser.parse_args()
    try:
        count = export_slices(args.output_dir)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        parser.exit(1, f'V2背景导出失败：{exc}\n')
    print(f'已从共同2x母图按后台二维设计坐标导出{count}张背景；仍须实际浏览器检查横向与纵向接缝。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
