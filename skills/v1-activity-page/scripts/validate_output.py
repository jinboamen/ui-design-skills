#!/usr/bin/env python3
"""Validate a generated V1 activity page delivery folder without creating an archive.

Usage: python validate_output.py OUTPUT_DIR
Requires Pillow for PNG pixel and alpha inspection.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import re
import sys

try:
    from PIL import Image, ImageFilter, ImageChops
except ImportError:
    print("需要 Pillow 才能检查 PNG 透明度；请使用带 Pillow 的 Python 环境。", file=sys.stderr)
    raise SystemExit(2)


FIXED_SIZES = {
    "package.background": (1920, 520),
    "package.card": (201, 280),
    "package.button": (160, 60),
    "blind.background": (1920, 806),
    "blind.art": (317, 300),
    "blind.button": (232, 80),
    "marquee.prize": (200, 200),
    "marquee.highlight": (200, 200),
    "lottery.record": (160, 60),
    "lottery.probability": (640, 402),
    "task.row": (700, 120),
    "task.button-available": (160, 60),
    "task.button-claimed": (160, 60),
    "gift.background": (1044, 400),
    "gift.unclaimed": (201, 137),
    "gift.claimed": (201, 137),
    "gift.empty": (201, 137),
    "rule.button": (209, 64),
}
TITLE_MODULES = {
    "package.title": "package", "blind.title": "lottery",
    "marquee.title": "lottery", "task.title": "task",
    "gift.title": "gift", "banner.title": "banner", "rule.title": "rule",
}
FOREGROUND_ROLES = set(TITLE_MODULES) | {
    "package.card", "package.button", "blind.art", "blind.backdrop", "blind.prize-card", "blind.button", "marquee.prize",
    "marquee.center", "marquee.highlight", "lottery.record", "task.row",
    "task.button-available", "task.button-claimed",
    "gift.unclaimed", "gift.claimed", "gift.empty", "rule.button",
}
ALL_ROLES = set(FIXED_SIZES) | set(TITLE_MODULES) | {"hero", "banner", "marquee.center", "marquee.background", "task.background", "rule.background", "blind.backdrop", "blind.prize-card"}
MARQUEE_CENTERS = {8: (180, 180), 10: (410, 180), 12: (300, 300)}


class LocalReferences(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.references: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for key, value in attrs:
            if key in {"src", "href"} and value:
                self.references.append(value)


class PageStructure(HTMLParser):
    """Track module ownership and visible text without a browser dependency."""
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[dict] = []
        self.roles: list[dict] = []
        self.nodes: list[dict] = []
        self.module_text: dict[str, str] = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        module = attrs.get("data-module") or (self.stack[-1]["module"] if self.stack else None)
        node = {"tag": tag, "module": module, "role": attrs.get("data-role"), "attrs": attrs,
                "parents": [n["role"] for n in self.stack], "text": "",
                "parent_card": next((n for n in reversed(self.stack) if n["role"] in {"blind-prize-card", "marquee-prize"}), None)}
        self.nodes.append(node)
        if node["role"]:
            self.roles.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]["tag"] == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        if not self.stack or self.stack[-1]["tag"] in {"script", "style"}:
            return
        module = self.stack[-1]["module"]
        if module:
            self.module_text[module] = self.module_text.get(module, "") + data
        for node in self.stack:
            if node["role"]:
                node["text"] += data


def validate_structure(root: Path, data: dict, errors: list[str]) -> None:
    path = root / "index.html"
    if not path.is_file():
        return
    page = PageStructure()
    page.feed(path.read_text(encoding="utf-8"))
    requirements = []
    if data.get("lottery_style") in {"blind_box", "marquee"}:
        requirements.append(("prize-probability", "lottery", "奖品概率"))
    tasks = data.get("task_count", 0)
    if isinstance(tasks, int) and tasks > 0:
        requirements.extend((role, "task", label) for role, label in (
            ("task-account", ""), ("username", "用户名"),
            ("draw-count", "抽奖次数"), ("lottery-record", "中奖记录")))
    for role, module, label in requirements:
        nodes = [n for n in page.roles if n["role"] == role]
        if len(nodes) != 1 or nodes[0]["module"] != module:
            errors.append(f"结构错误：{role} 必须恰好出现一次并位于 data-module={module} 内")
            continue
        node = nodes[0]
        if label not in re.sub(r"\s+", "", node["text"]):
            errors.append(f"结构错误：{role} 缺少可见的“{label}”文字")
        if role in {"username", "draw-count", "lottery-record"} and "task-account" not in node["parents"]:
            errors.append(f"结构错误：{role} 必须位于任务模块的 task-account 用户信息行")
    for module, forbidden in (("task", "领取记录"), ("lottery", "中奖记录")):
        if forbidden in re.sub(r"\s+", "", page.module_text.get(module, "")):
            errors.append(f"结构错误：{module} 模块不应显示“{forbidden}”")
    count = data.get("blind_prize_count")
    if data.get("lottery_style") == "blind_box" and isinstance(count, int) and not isinstance(count, bool) and count >= 0:
        cards = [n for n in page.roles if n["role"] == "blind-prize-card"]
        if len(cards) != count:
            errors.append(f"结构错误：blind-prize-card 展示项应为 {count} 个，实际 {len(cards)} 个")
        for card in cards:
            sides = {"blind-prizes-left", "blind-prizes-right"}.intersection(card["parents"])
            if card["module"] != "lottery" or len(sides) != 1:
                errors.append("结构错误：单奖品展示必须在抽奖模块的左侧或右侧奖品容器内")
            for role in ("blind-prize-image", "blind-prize-name"):
                parts = [n for n in page.roles if n["role"] == role and n["parent_card"] is card]
                if len(parts) != 1:
                    errors.append(f"结构错误：每个奖品卡必须各有一个 {role} 上方图片区或下方名称区")
        if count > 0:
            for role in ("blind-prizes-left", "blind-prizes-right"):
                nodes = [n for n in page.roles if n["role"] == role]
                if len(nodes) != 1 or nodes[0]["module"] != "lottery":
                    errors.append(f"结构错误：{role} 必须恰好出现一次并位于抽奖模块内")
        names = data.get("blind_prizes")
        if isinstance(names, list) and all(isinstance(name, str) for name in names):
            normalize = lambda value: re.sub(r"\s+", "", value)
            name_parts = [n for n in page.roles if n["role"] == "blind-prize-name" and n["parent_card"] in cards]
            if Counter(normalize(n["text"]) for n in name_parts) != Counter(normalize(name) for name in names):
                errors.append("结构错误：盲盒展示的完整奖品名称与 blind_prizes 不一致")


def validate_rule_module(root: Path, data: dict, errors: list[str]) -> None:
    path = root / "index.html"
    if not path.is_file():
        return
    page = PageStructure()
    page.feed(path.read_text(encoding="utf-8"))
    modules = [n for n in page.nodes if n["attrs"].get("data-module") == "rule"]
    content = [n for n in page.roles if n["role"] == "rule-content"]
    enabled = data.get("rule_inline_enabled", False) is True
    if not enabled:
        if modules or content:
            errors.append("平铺活动规则默认关闭，未启用时不得出现rule模块或正文")
        return
    if len(modules) != 1 or len(content) != 1 or content[0]["module"] != "rule":
        errors.append("平铺规则需要一个data-module=rule及其内部唯一rule-content文本容器")
        return
    text = data.get("rule_text")
    if not isinstance(text, str) or not text.strip():
        errors.append("平铺规则须记录rule_text实际正文或明确待后台配置占位")
    else:
        normalize = lambda value: re.sub(r"\s+", "", value)
        if normalize(content[0]["text"]) != normalize(text):
            errors.append("规则正文与rule_text不一致，不能省略或截断后台待配置内容")
    if content[0]["tag"] not in {"div", "article", "section", "p", "ol", "ul"}:
        errors.append("rule-content须使用可编辑文本容器，不能用图片替代正文")
    if any(n["tag"] in {"img", "canvas", "svg", "iframe", "object", "embed"}
           and "rule-content" in n["parents"] for n in page.nodes):
        errors.append("规则正文应为文本，不得以图片、画布或嵌入页代替")


def local_file(root: Path, name: str) -> Path:
    relative = Path(name)
    if relative.is_absolute() or name.startswith(("/", "\\")) or ".." in relative.parts:
        raise ValueError(f"非法的相对路径：{name}")
    target = (root / relative).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError(f"路径超出页面目录：{name}")
    return target


def validate_references(root: Path, errors: list[str]) -> None:
    html_file = root / "index.html"
    css_file = root / "styles.css"
    for path in (html_file, css_file):
        if not path.is_file():
            errors.append(f"缺少 {path.name}")
    if not html_file.is_file() or not css_file.is_file():
        return
    html = html_file.read_text(encoding="utf-8")
    parser = LocalReferences()
    parser.feed(html)
    css = css_file.read_text(encoding="utf-8")
    embedded_urls = re.findall(r"url\(\s*['\"]?([^)'\"]+)", html + css)
    imports = re.findall(r"@import\s+['\"]([^'\"]+)", css)
    for name in parser.references + embedded_urls + imports:
        name = name.strip()
        if name.startswith("#") or name == "":
            continue
        if re.match(r"^(?:https?:|//|data:|javascript:)", name, re.I):
            errors.append(f"页面包含非本地引用：{name[:100]}")
            continue
        try:
            target = local_file(root, name.split("#", 1)[0].split("?", 1)[0])
            if not target.is_file():
                errors.append(f"页面引用缺失：{name}")
        except ValueError as exc:
            errors.append(str(exc))


def marquee_background_height(slots: int) -> int:
    if type(slots) is not int or slots not in MARQUEE_CENTERS:
        raise ValueError("跑马灯需要 lottery_slots=8、10 或 12")
    board_height = 890 if slots == 12 else 660
    return 150 + board_height + 10 + 38 + 90


def expected_size(role: str, item: dict, data: dict) -> tuple[int, int] | None:
    if role == "marquee.background":
        return (1920, marquee_background_height(data.get("lottery_slots")))
    if role in {"blind.backdrop", "blind.prize-card"} or role in TITLE_MODULES:
        size = (item.get("width"), item.get("height"))
        if any(not isinstance(v, int) or isinstance(v, bool) or v <= 0 for v in size):
            raise ValueError(f"{role} 必须记录正整数 width 和 height")
        return size
    if role in {"hero", "banner", "rule.background"}:
        height = item.get("height")
        if not isinstance(height, int) or isinstance(height, bool) or height <= 0:
            raise ValueError(f"{role} 必须记录正整数 height")
        return (1920, height)
    if role == "marquee.center":
        slots = data.get("lottery_slots")
        if slots not in MARQUEE_CENTERS:
            raise ValueError("跑马灯中心图需要 lottery_slots=8、10 或 12")
        return MARQUEE_CENTERS[slots]
    if role == "task.background":
        count = data.get("task_count")
        if not isinstance(count, int) or isinstance(count, bool) or count not in (1, 2, 3):
            raise ValueError("任务背景需要 task_count=1、2 或 3")
        return (1920, 299 + 166 * count)
    return FIXED_SIZES[role]


def validate_counts(data: dict, counts: Counter, errors: list[str]) -> None:
    for name in ("task_count", "gift_count", "package_count"):
        value = data.get(name)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            errors.append(f"{name} 必须为非负整数")
    tasks = data.get("task_count", 0)
    gifts = data.get("gift_count", 0)
    packages = data.get("package_count", 0)
    inline = data.get("rule_inline_enabled", False)
    floating = data.get("rule_floating_enabled", True)
    for name in ("rule_inline_enabled", "rule_floating_enabled"):
        if name in data and not isinstance(data[name], bool):
            errors.append(f"{name} 必须为布尔值")
    if counts["rule.background"] != int(inline is True):
        errors.append("规则背景仅在 rule_inline_enabled=true 时需要恰好1张，默认不生成")
    if "rule_floating_enabled" in data or inline is True:
        if counts["rule.button"] != int(floating is True):
            errors.append("rule.button 数量与 rule_floating_enabled 不一致")
    if counts["hero"] != 1:
        errors.append("头图必须恰好 1 张")
    if isinstance(packages, int) and not isinstance(packages, bool) and packages >= 0:
        expected_package_assets = int(packages > 0)
        for role in ("package.card", "package.button", "package.background"):
            if counts[role] != expected_package_assets:
                errors.append(
                    f"{role} 数量应为 {expected_package_assets}；package_count 表示页面套餐实例数，"
                    "启用套餐时卡片和购买按钮各只保留 1 张共用素材"
                )
    if isinstance(tasks, int) and tasks >= 0:
        if tasks > 3:
            errors.append("抽奖任务最多 3 项")
        if counts["task.background"] != int(tasks > 0):
            errors.append("任务背景与 task_count 不一致")
        expected_task_asset_counts = (0,) if tasks == 0 else (1, tasks)
        for role in ("task.row", "task.button-available", "task.button-claimed"):
            if counts[role] not in expected_task_asset_counts:
                errors.append(f"{role} 数量应为 1 张共用素材或 {tasks} 张独立素材")
        if counts["lottery.record"] != int(tasks > 0):
            errors.append("任务模块需要一张 lottery.record 中奖记录按钮；未启用任务模块时不生成该按钮")
    if isinstance(gifts, int) and gifts >= 0:
        if counts["gift.background"] != int(gifts > 0):
            errors.append("礼包背景与 gift_count 不一致")
        for role in ("gift.unclaimed", "gift.claimed", "gift.empty"):
            if counts[role] != gifts:
                errors.append(f"{role} 数量应为 {gifts}")
    style = data.get("lottery_style")
    if style == "blind_box":
        backdrop_enabled = data.get("blind_backdrop_enabled", True)
        if not isinstance(backdrop_enabled, bool):
            errors.append("blind_backdrop_enabled 必须为布尔值；底框默认保留并绘入blind.background")
        if data.get("blind_backdrop_layer", "background") != "background":
            errors.append("盲盒底框须归background，不能恢复为独立blind.backdrop")
        if counts["blind.backdrop"]:
            errors.append("盲盒底框已并入blind.background，不再导出或引用blind.backdrop独立素材")
        if backdrop_enabled is False:
            reason = data.get("blind_backdrop_omit_reason")
            if not isinstance(reason, str) or not reason.strip():
                errors.append("取消底框本身须记录用户明确要求及非空blind_backdrop_omit_reason；并入背景不等于取消底框")
    elif counts["blind.backdrop"]:
        errors.append("blind.backdrop 仅限盲盒模式，非盲盒模式不得生成底框")
    prize_fields = "blind_prize_count" in data or "blind_prizes" in data or counts["blind.prize-card"] > 0
    if prize_fields:
        prize_count, prize_names = data.get("blind_prize_count"), data.get("blind_prizes")
        valid_count = isinstance(prize_count, int) and not isinstance(prize_count, bool) and prize_count >= 0
        if not valid_count:
            errors.append("盲盒奖品展示必须记录用户确认的非负整数 blind_prize_count")
        if (not isinstance(prize_names, list) or not all(isinstance(name, str) and name.strip() for name in prize_names)
                or (valid_count and len(prize_names) != prize_count)):
            errors.append("blind_prizes 必须是与 blind_prize_count 一致的非空奖品名称数组；数量为0时用空数组")
        if style != "blind_box" and (counts["blind.prize-card"] or prize_count != 0 or prize_names != []):
            errors.append("blind.prize-card 与盲盒奖品展示字段仅限盲盒模式")
        if style == "blind_box" and valid_count and counts["blind.prize-card"] != int(prize_count > 0):
            errors.append("启用盲盒奖品展示时需要恰好1张共用 blind.prize-card；数量为0时不生成")
    if style not in (None, "blind_box", "marquee"):
        errors.append("lottery_style 只能为 null、blind_box 或 marquee")
    if style == "blind_box":
        for role in ("blind.background", "blind.art", "blind.button"):
            if counts[role] != 1:
                errors.append(f"盲盒模式需要 1 张 {role}")
        if any(counts[r] for r in ("marquee.background", "marquee.prize", "marquee.center", "marquee.highlight")):
            errors.append("盲盒模式不能混入跑马灯素材")
    elif style == "marquee":
        slots = data.get("lottery_slots")
        if slots not in MARQUEE_CENTERS:
            errors.append("跑马灯必须确认 lottery_slots=8、10 或 12")
        if counts["marquee.background"] != 1 or counts["marquee.center"] != 1:
            errors.append("跑马灯需要 1 张背景和 1 张中心图")
        if counts["marquee.highlight"] != 1:
            errors.append("跑马灯需要恰好1张共用 marquee.highlight 透明高亮素材")
        if counts["marquee.prize"] != slots:
            errors.append(f"跑马灯奖品图数量应为 {slots}")
        if any(counts[r] for r in ("blind.background", "blind.art", "blind.button")):
            errors.append("跑马灯模式不能混入盲盒素材")
    elif any(counts[r] for r in (
        "blind.background", "blind.art", "blind.button", "marquee.background",
        "marquee.prize", "marquee.center", "marquee.highlight", "lottery.record", "lottery.probability"
    )):
        errors.append("没有抽奖模块时不应列出抽奖素材")


def same_png_except_resolution(first: bytes, second: bytes) -> bool:
    """Permit only a pHYs change; keep IDAT, color profiles and all other chunks exact."""
    if first == second:
        return True
    from normalize_png_ppi import normalize_png
    try:
        return normalize_png(first, 72) == normalize_png(second, 72)
    except (OSError, ValueError):
        return False


def export_ppi(data: dict) -> float:
    value = data.get("export_ppi", 72)
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value <= 0):
        raise ValueError("export_ppi 必须为正数，默认 72 PPI")
    return float(value)


def validate_png_ppi(image, data: dict) -> None:
    expected = export_ppi(data)
    dpi = image.info.get("dpi")
    if (not isinstance(dpi, (tuple, list)) or len(dpi) != 2
            or any(not isinstance(v, (int, float)) or not math.isfinite(v)
                   or abs(v - expected) > 0.02 for v in dpi)):
        raise ValueError(f"PNG分辨率信息应为 {expected:g} PPI（双轴），实际 {dpi}；像素尺寸正确不能代替PPI校验")
    exif = image.getexif()
    if any(tag in exif for tag in (282, 283, 296)):
        unit = exif.get(296)
        factor = 1 if unit == 2 else 2.54 if unit == 3 else None
        if factor is None or any(tag not in exif for tag in (282, 283)):
            raise ValueError("PNG的EXIF分辨率字段不完整或单位未知")
        values = [float(exif[tag]) * factor for tag in (282, 283)]
        if any(not math.isfinite(v) or abs(v - expected) > 0.02 for v in values):
            raise ValueError("PNG的EXIF分辨率与目标PPI冲突")


def validate_assets(root: Path, data: dict, errors: list[str]) -> None:
    assets = data.get("assets")
    if not isinstance(assets, list):
        errors.append("assets 必须是数组")
        return
    counts: Counter = Counter()
    seen_files: set[str] = set()
    for index, item in enumerate(assets, 1):
        if not isinstance(item, dict):
            errors.append(f"素材 #{index} 不是对象")
            continue
        role, filename = item.get("role"), item.get("file")
        if role == "task.record":
            errors.append("已停用 task.record：任务模块没有领取记录；中奖记录使用 lottery.record 并放在任务用户信息行")
            continue
        if role not in ALL_ROLES:
            errors.append(f"素材 #{index} 的 role 未知：{role}")
            continue
        if not isinstance(filename, str) or not filename.lower().endswith(".png"):
            errors.append(f"素材 #{index} 需要 PNG 相对路径")
            continue
        counts[role] += 1
        if filename in seen_files:
            errors.append(f"重复列出的素材路径：{filename}")
        seen_files.add(filename)
        try:
            path = local_file(root, filename)
            size = expected_size(role, item, data)
            if not path.is_file():
                errors.append(f"素材缺失：{filename}")
                continue
            with Image.open(path) as image:
                validate_png_ppi(image, data)
                if image.format != "PNG":
                    errors.append(f"不是 PNG 文件：{filename}")
                if image.size != size:
                    errors.append(f"尺寸错误：{filename} 应为 {size[0]}×{size[1]}，实际 {image.width}×{image.height}")
                alpha = image.convert("RGBA").getchannel("A")
                minimum, maximum = alpha.getextrema()
                if role in FOREGROUND_ROLES and not (minimum == 0 and maximum > 0):
                    errors.append(f"前景图缺少真实透明背景：{filename}")
                if role not in FOREGROUND_ROLES and minimum != 255:
                    errors.append(f"背景图应为不透明：{filename}")
        except (ValueError, OSError) as exc:
            errors.append(f"{filename}：{exc}")
    validate_counts(data, counts, errors)


def validate_module_titles(root: Path, data: dict, errors: list[str]) -> None:
    """Require separate, shared-style title assets and their actual module use.

    Pixel typography and stylistic consistency still need visual review.
    """
    assets = data.get("assets")
    if not isinstance(assets, list):
        return
    required = set()
    for module in ("package", "task", "gift"):
        count = data.get(module + "_count", 0)
        if isinstance(count, int) and not isinstance(count, bool) and count > 0:
            required.add(module + ".title")
    style = data.get("lottery_style")
    if style in {"blind_box", "marquee"}:
        required.add("blind.title" if style == "blind_box" else "marquee.title")
    if data.get("rule_inline_enabled", False) is True:
        required.add("rule.title")
    titles = [a for a in assets if isinstance(a, dict) and a.get("role") in TITLE_MODULES]
    counts = Counter(a["role"] for a in titles)
    for role in TITLE_MODULES:
        expected = int(role in required)
        if role == "banner.title":
            if counts[role] > 1 or (counts[role] and not any(
                    isinstance(a, dict) and a.get("role") == "banner" for a in assets)):
                errors.append("banner.title 仅用于已启用且需要标题的Banner，最多1张")
        elif counts[role] != expected:
            errors.append(f"模块标题 {role} 应为 {expected} 张独立PNG，实际 {counts[role]} 张")
    page = PageStructure()
    html = root / "index.html"
    if html.is_file():
        page.feed(html.read_text(encoding="utf-8"))
    nodes = [n for n in page.roles if n["role"] == "module-title"]
    for node in nodes:
        if node["attrs"].get("data-title-role") not in counts:
            errors.append("页面模块标题缺少对应素材：data-title-role 必须引用清单中的标题角色")
    sizes, styles, display_sizes = set(), set(), set()
    for item in titles:
        role = item["role"]
        try:
            size = expected_size(role, item, data)
            sizes.add(size)
            display = (item.get("display_width"), item.get("display_height"))
            if any(not isinstance(n, int) or isinstance(n, bool) or n <= 0 for n in display):
                raise ValueError("须记录正整数display_width/display_height，区分高清导出与页面显示")
            display_sizes.add(display)
            if size[0] * display[1] != size[1] * display[0]:
                raise ValueError("标题导出与页面显示尺寸须等比，不能拉伸字形")
            text, title_style = item.get("text"), item.get("title_style")
            if not isinstance(text, str) or not text.strip():
                raise ValueError("须记录实际标题文案 text")
            if not isinstance(title_style, str) or not title_style.strip():
                raise ValueError("须记录统一标题母版标识 title_style")
            styles.add(title_style)
            filename = item.get("file")
            if not isinstance(filename, str):
                raise ValueError("须记录标题PNG的相对路径")
            target = local_file(root, filename)
            if not target.is_relative_to((root / "assets/titles").resolve()):
                raise ValueError("独立标题须放在 assets/titles/ 文件夹")
            matched = [n for n in nodes if n["attrs"].get("data-title-role") == role]
            if len(matched) != 1:
                raise ValueError("页面须恰好引用一次该标题图片并标记 data-role=module-title")
            node = matched[0]
            attrs = node["attrs"]
            if node["tag"] != "img" or node["module"] != TITLE_MODULES[role]:
                raise ValueError("标题须以img放入对应data-module模块，不能只交付图片或用普通文字代替")
            if attrs.get("width") != str(display[0]) or attrs.get("height") != str(display[1]):
                raise ValueError("HTML标题宽高须使用display_width/display_height，不用高清导出尺寸撑大")
            if local_file(root, attrs.get("src", "")) != target or attrs.get("alt") != text:
                raise ValueError("页面标题图片src或alt与素材路径、完整文案不一致")
        except (ValueError, TypeError) as exc:
            errors.append(f"{role}：{exc}")
    if len(sizes) > 1 or len(styles) > 1 or len(display_sizes) > 1:
        errors.append("所有模块标题须共用一套title_style、画布及显示宽高，只替换文案；实际字形、显示尺度和效果另作视觉验收")


def validate_marquee_structure(root: Path, data: dict, errors: list[str]) -> None:
    if data.get("lottery_style") != "marquee" or not (root / "index.html").is_file():
        return
    slots = data.get("lottery_slots")
    if type(slots) is not int or slots not in MARQUEE_CENTERS:
        return
    page = PageStructure()
    page.feed((root / "index.html").read_text(encoding="utf-8"))
    for role in ("marquee-board", "marquee-toggle"):
        nodes = [n for n in page.roles if n["role"] == role]
        if len(nodes) != 1 or nodes[0]["module"] != "lottery":
            errors.append(f"跑马灯需要一个位于lottery内的 {role}")
        elif role == "marquee-toggle" and (nodes[0]["tag"] != "button"
                or nodes[0]["attrs"].get("type") != "button"
                or "marquee-board" not in nodes[0]["parents"]):
            errors.append("跑马灯中心须为棋盘内的普通button，用于暂停／继续演示")
    cards = [n for n in page.roles if n["role"] == "marquee-prize"]
    if (len(cards) != slots or {n["attrs"].get("data-marquee-index") for n in cards}
            != {str(i) for i in range(slots)}):
        errors.append("跑马灯外围奖品数量与顺序编号须覆盖0至lottery_slots-1且不重复")
    highlights = [a for a in data.get("assets", []) if a.get("role") == "marquee.highlight"]
    overlays = [n for n in page.roles if n["role"] == "marquee-highlight"]
    if len(overlays) != slots:
        errors.append("每个跑马灯奖品格均须引用共用高亮图片")
    for card in cards:
        if card["module"] != "lottery" or "marquee-board" not in card["parents"]:
            errors.append("跑马灯奖品格必须位于lottery的棋盘内")
        parts = [n for n in overlays if n["parent_card"] is card]
        if len(parts) != 1 or parts[0]["tag"] != "img":
            errors.append("每个跑马灯奖品格须包含一个img高亮叠层")
            continue
        if len(highlights) == 1:
            try:
                if local_file(root, parts[0]["attrs"].get("src", "")) != local_file(root, highlights[0]["file"]):
                    errors.append("跑马灯各格高亮须复用清单中的同一张PNG")
            except (ValueError, KeyError) as exc:
                errors.append(f"跑马灯高亮引用错误：{exc}")
    if sum(n["attrs"].get("data-active") == "true" for n in cards) != 1:
        errors.append("跑马灯初始HTML须恰好一格高亮，以便静态截图与脚本未启动时预览")


def validate_preview(root: Path, data: dict, errors: list[str]) -> None:
    path = root.with_name(root.name + "-preview.png")
    if not path.is_file():
        errors.append(f"缺少独立的最终整页预览 {path.name}；请在 1920px 浏览器画布重新截图")
        return
    try:
        with Image.open(path) as image:
            if image.format != "PNG" or image.width != 1920:
                errors.append(f"{path.name} 必须是 1920px 宽的 PNG，实际为 {image.width}×{image.height}")
            heights = [item.get("height", 0) for item in data.get("assets", [])
                       if isinstance(item, dict) and item.get("role") in {"hero", "banner"}]
            minimum = sum(h for h in heights if isinstance(h, int) and not isinstance(h, bool))
            minimum += 520 * int(data.get("package_count", 0) > 0)
            minimum += (marquee_background_height(data.get("lottery_slots"))
                        if data.get("lottery_style") == "marquee"
                        else 806 if data.get("lottery_style") == "blind_box" else 0)
            tasks = data.get("task_count", 0)
            if isinstance(tasks, int) and tasks > 0:
                minimum += 299 + 166 * tasks
            minimum += 400 * int(data.get("gift_count", 0) > 0)
            if image.height < minimum:
                errors.append(f"{path.name} 高度不足：至少 {minimum}px，实际 {image.height}px；请截取到页尾")
    except (OSError, TypeError, ValueError) as exc:
        errors.append(f"{path.name} 无法检查：{exc}")


def validate_blind_background_lineage(root: Path, data: dict, lineage, errors: list[str]) -> None:
    """Require the final background workflow to reference the actual final box."""
    if data.get("lottery_style") != "blind_box":
        return
    try:
        assets = data.get("assets", [])
        paths = {}
        for role in ("blind.art", "blind.background"):
            matches = [a for a in assets if isinstance(a, dict) and a.get("role") == role]
            if len(matches) != 1:
                raise ValueError(f"盲盒融合绑定需要恰好1个{role}")
            source = matches[0].get("working_source") if data.get("production_workflow") in {"shared-assets-preview-v1", "background-final-foreground-concept-v1"} else None
            paths[role] = local_file(root, source or matches[0]["file"])
        if paths["blind.art"] not in lineage(paths["blind.background"], set()):
            errors.append("blind.background来源链未包含本次最终blind.art：须先冻结实际盒体，再以该PNG或包含它的组合基准修复接触阴影及衬托；仅共同引用样张或旧背景不算成组制作")
    except (ValueError, TypeError, KeyError) as exc:
        errors.append(f"盲盒背景与最终盒体的来源绑定无效：{exc}")


def validate_blind_layout(root: Path, data: dict, errors: list[str]) -> None:
    """Check the background-contained backdrop against the independently rendered box."""
    if data.get("lottery_style") != "blind_box" or data.get("blind_backdrop_enabled", True) is False:
        return
    assets = data.get("assets", [])
    report = root / "design/blind-layout-check.json"
    if not report.is_file():
        errors.append("缺少design/blind-layout-check.json：底框并入背景仍须按承托类型检查几何、构图或接触及完整盲盒组合，不能因没有独立PNG而跳过")
        return
    try:
        layout = json.loads(report.read_text(encoding="utf-8"))
        if not isinstance(layout, dict):
            raise ValueError("布局报告须为对象")
        def number(value):
            return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        if layout.get("viewport_width") != 1920:
            raise ValueError("底框测量必须来自1920px浏览器视口")
        support_type = layout.get("support_type", "enclosing_frame")
        allowed_types = {"enclosing_frame", "graphic_backing", "physical_support"}
        if not isinstance(support_type, str) or support_type not in allowed_types:
            raise ValueError("support_type须为enclosing_frame、graphic_backing或physical_support")
        additional = layout.get("additional_support_type")
        if additional is not None and (support_type != "enclosing_frame" or additional != "physical_support"):
            raise ValueError("additional_support_type仅用于包裹框同时具有实体承托时，值须为physical_support")
        padding, inset = layout.get("minimum_padding", 0), layout.get("backdrop_inset")
        if not all(number(value) and value >= 0 for value in (padding, inset)):
            raise ValueError("minimum_padding默认0且须为非负数，backdrop_inset须为非负数")
        bounds = {}
        for key, role in (("art", "blind.art"), ("backdrop", "blind.background")):
            node = layout.get(key, {})
            if not isinstance(node, dict) or not any(
                a.get("role") == role and a.get("file") == node.get("file")
                for a in assets if isinstance(a, dict)
            ):
                raise ValueError(f"{key}文件与素材清单不一致；底框须指向blind.background")
            if (not all(number(node.get(k)) for k in ("left", "top", "width", "height"))
                    or node["width"] <= 0 or node["height"] <= 0):
                raise ValueError(f"{key}缺少有效浏览器位置或尺寸")
            with Image.open(local_file(root, node["file"])) as image:
                if key == "art":
                    mask = image.convert("RGBA").getchannel("A").point(lambda p: 255 if p >= 128 else 0)
                    mask = mask.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3))
                    box = mask.getbbox()
                    if box is None:
                        raise ValueError("art没有可见主体")
                else:
                    # The background is opaque: alpha of the whole module is not the backdrop.
                    box = node.get("visible_bounds")
                    if (not isinstance(box, list) or len(box) != 4
                            or not all(number(v) for v in box)
                            or not (0 <= box[0] < box[2] <= image.width
                                    and 0 <= box[1] < box[3] <= image.height)):
                        raise ValueError("背景底框须记录从最终PNG实测的visible_bounds=[左,上,右,下]，不能用整张背景范围代替")
                    if box == [0, 0, image.width, image.height]:
                        raise ValueError("底板须为盲盒对应的局部承托区域，不能以整张背景冒充底板")
                sx, sy = node["width"] / image.width, node["height"] / image.height
                expected = (317 / 296) if key == "art" else (image.width / image.height)
                if abs(node["width"] / node["height"] / expected - 1) > 0.01:
                    errors.append(f"{key}显示比例失真，须保持既有盲盒与背景显示规格")
                bounds[key] = [node["left"] + box[0] * sx, node["top"] + box[1] * sy,
                               node["left"] + box[2] * sx, node["top"] + box[3] * sy]
        art, plate = bounds["art"], bounds["backdrop"]
        if support_type == "enclosing_frame":
            margins = [art[0] - plate[0] - inset, art[1] - plate[1] - inset,
                       plate[2] - art[2] - inset, plate[3] - art[3] - inset]
            for side, value in zip(("左", "上", "右", "下"), margins):
                if value + 1 < padding:
                    errors.append(f"背景内盲盒底框{side}侧未覆盖完整主体：边界差{value:.1f}px，须覆盖蝴蝶结、盒盖及突出部分")
            dx, dy = [(plate[i] + plate[i + 2] - art[i] - art[i + 2]) / 2 for i in (0, 1)]
            if abs(dx) > 3 or abs(dy) > 3:
                errors.append(f"背景内盲盒底框与完整主体未居中：水平偏差{dx:.1f}px，垂直偏差{dy:.1f}px；不能只对齐盒身")
        required_checks = {
            "enclosing_frame": (),
            "graphic_backing": ("composition", "visual_center", "occlusion"),
            "physical_support": ("perspective", "depth", "contact"),
        }[support_type]
        if additional == "physical_support":
            required_checks += ("perspective", "depth", "contact")
        checks = layout.get("type_checks", {})
        if required_checks and not isinstance(checks, dict):
            raise ValueError("type_checks须记录本次所选承托类型的实际视觉检查")
        for key in required_checks:
            item = checks.get(key)
            if (not isinstance(item, dict) or not isinstance(item.get("observation"), str)
                    or not item["observation"].strip()):
                raise ValueError(f"承托类型{support_type}缺少实际观察：{key}")
            if item.get("status") != "pass":
                errors.append(f"承托类型检查{key}未通过，须修复后重新查看完整组合")
        review = layout.get("fusion_review")
        if (not isinstance(review, dict) or not isinstance(review.get("observation"), str)
                or not review["observation"].strip()):
            raise ValueError("缺少fusion_review：须记录恢复盲盒、奖品和按钮后与确认样张的实际融合对照")
        art_hash = review.get("art_sha256")
        current_hash = hashlib.sha256(local_file(root, layout["art"]["file"]).read_bytes()).hexdigest()
        if not isinstance(art_hash, str) or art_hash.lower() != current_hash:
            raise ValueError("fusion_review须绑定本次最终blind.art的art_sha256；盒体变化后须重新修复背景侧交互并验收")
        with Image.open(local_file(root, review["comparison"])) as comparison:
            comparison.verify()
        interaction = review.get("interaction_checks")
        if not isinstance(interaction, dict):
            raise ValueError("缺少interaction_checks：接触／图形连接、原始衬托和背景侧光影须分别检查")
        for key in ("contact", "support", "lighting"):
            item = interaction.get(key)
            if (not isinstance(item, dict) or not isinstance(item.get("observation"), str)
                    or not item["observation"].strip()):
                raise ValueError(f"盲盒交互缺少实际观察：{key}")
            if item.get("status") != "pass":
                errors.append(f"盲盒交互{key}未恢复：不能只通过几何或类型检查后交付")
        if review.get("status") != "pass":
            errors.append("盲盒与背景内底框的融合未通过，须返修背景并重新回填检查")
        with Image.open(local_file(root, review["file"])) as screenshot:
            if screenshot.size != (1920, 806):
                raise ValueError("fusion_review须为真实1920×806盲盒模块浏览器截图，含完整盒体、奖品和操作")
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        errors.append(f"盲盒底框测量或融合报告无效：{exc}")


def validate_continuous_background(root: Path, data: dict, errors: list[str]) -> None:
    # Segmented colors may change, but cross-boundary art must share one reviewed composition.
    if data.get("background_mode") not in {"continuous", "整体衔接", "segmented", "按模块区分"}:
        errors.append("background_mode须为continuous或segmented（或对应中文模式），不能跳过接缝校验")
        return
    master = data.get("background_master")
    if not isinstance(master, dict):
        errors.append("背景缺少background_master：两种模式都须先完成包含头图与内容区的最终跨界组合母图，再按坐标导出；按模块区分仍保留底色差异")
        return
    try:
        path = local_file(root, master["file"])
        slices = master.get("slices")
        if not isinstance(slices, list) or not slices:
            raise ValueError("母图切片清单不能为空")
        assets = {a["file"]: a for a in data.get("assets", []) if isinstance(a, dict) and isinstance(a.get("file"), str)}
        hero = next(a["file"] for a in assets.values() if a.get("role") == "hero")
        if slices[0].get("file") != hero or slices[0].get("top") != 0:
            raise ValueError("背景组合母图第一片必须是从y=0开始的头图")
        required = {filename for filename, a in assets.items()
                    if (a.get("role") in {"hero", "banner"} or a.get("role", "").endswith(".background"))
                    and expected_size(a["role"], a, data)[0] == 1920}
        if {s.get("file") for s in slices} != required or len(slices) != len(required):
            raise ValueError("母图必须记录头图和全部1920px背景切片，各一次；局部底板不列入")
        with Image.open(path) as original:
            validate_png_ppi(original, data)
            if original.width != 1920:
                raise ValueError("最终背景组合母图宽度必须为1920px")
            image = original.convert("RGB")
            cursor = 0
            for part in slices:
                top, height = part.get("top"), part.get("height")
                if any(not isinstance(v, int) or isinstance(v, bool) for v in (top, height)) or top < 0 or height <= 0:
                    raise ValueError("母图切片top须为非负整数、height须为正整数")
                # Non-full-width local sections may occupy intervals in the full page master.
                if top < cursor or (not data.get("gift_count") and top != cursor):
                    errors.append(f"背景母图切片坐标不连续或重叠：{part['file']} top={top}，前片终点={cursor}")
                with Image.open(local_file(root, part["file"])) as exported:
                    if exported.size != (1920, height) or top + height > image.height:
                        errors.append(f"母图切片范围或尺寸错误：{part['file']}")
                        continue
                    if ImageChops.difference(exported.convert("RGB"), image.crop((0, top, 1920, top + height))).getbbox():
                        errors.append(f"{part['file']}与母图裁切像素不一致：禁止切片后独立缩放、裁剪、调色或生图")
                cursor = top + height
            if not data.get("gift_count") and cursor != image.height:
                errors.append("背景组合母图高度与头图及内容区累计高度不一致")
        review = local_file(root, master["seam_review"])
        with Image.open(review) as screenshot:
            if screenshot.width != 1920 or screenshot.height < 200:
                raise ValueError("接缝验收截图须为1920px宽、至少200px高的原比例视图")
        # Matching source pixels does not prove that the master or browser seams are visually sound.
        expected_boundaries = {edge for part in slices
                               for edge in (part["top"], part["top"] + part["height"])
                               if 0 < edge < image.height}
        reviews = master.get("seam_reviews")
        if not isinstance(reviews, list):
            raise ValueError("缺少seam_reviews：须逐条记录全部内部边界的真实浏览器截图与验收结果")
        seen = set()
        for item in reviews:
            if not isinstance(item, dict):
                raise ValueError("逐缝验收项必须为对象")
            boundary, capture_top = item.get("top"), item.get("capture_top")
            if (not isinstance(boundary, int) or isinstance(boundary, bool)
                    or boundary not in expected_boundaries or boundary in seen):
                raise ValueError("逐缝验收top须对应真实内部边界且每条恰好一次")
            seen.add(boundary)
            if not isinstance(capture_top, int) or isinstance(capture_top, bool) or capture_top < 0:
                raise ValueError("逐缝截图capture_top须为页面中的非负整数坐标")
            observation = item.get("observation")
            if not isinstance(observation, str) or not observation.strip():
                raise ValueError("逐缝验收须记录实际观察结果observation")
            if item.get("status") != "pass":
                errors.append(f"接缝y={boundary}未通过视觉验收，须修复后重新截图")
            with Image.open(local_file(root, item["file"])) as screenshot:
                if (screenshot.width != 1920 or screenshot.height < 200
                        or boundary - capture_top < min(80, boundary)
                        or capture_top + screenshot.height - boundary < min(80, image.height - boundary)
                        or capture_top + screenshot.height > image.height):
                    raise ValueError("逐缝浏览器截图须1920px宽、至少200px高，覆盖交界上下各至少80px且不超出页面")
                expected_view = image.crop((0, capture_top, 1920, capture_top + screenshot.height))
                if ImageChops.difference(screenshot.convert("RGB"), expected_view).getbbox():
                    errors.append(f"接缝y={boundary}的纯背景浏览器证据与母图同坐标像素不一致：检查缩放、cover裁剪、背景重复和容器裁边后重新截图")
        if seen != expected_boundaries:
            raise ValueError(f"逐缝验收未覆盖全部内部边界：缺少{sorted(expected_boundaries - seen)}")
    except (OSError, ValueError, TypeError, KeyError, AttributeError, StopIteration) as exc:
        errors.append(f"背景组合母图记录无效：{exc}")


def validate_decorations(root: Path, data: dict, errors: list[str]) -> int:
    enabled = data.get("decorations_enabled", True)
    if not isinstance(enabled, bool):
        errors.append("decorations_enabled 必须为布尔值；默认同步生成独立装饰")
        return 0
    if not enabled:
        reason = data.get("decorations_omit_reason")
        if not isinstance(reason, str) or not reason.strip():
            errors.append("跳过默认装饰须记录用户明确要求及 decorations_omit_reason")
        return 0
    count = 0
    try:
        filename = data.get("decoration_manifest")
        if not isinstance(filename, str) or not filename:
            raise ValueError("缺少 decoration_manifest；完整生成默认交付 decorations/ 独立装饰素材")
        folder = (root / "decorations").resolve()
        manifest = local_file(root, filename)
        if not manifest.is_relative_to(folder):
            raise ValueError("装饰清单必须单独放在 decorations/ 文件夹")
        content = json.loads(manifest.read_text(encoding="utf-8"))
        assets = content.get("assets") if isinstance(content, dict) else None
        if not isinstance(assets, list) or not assets:
            raise ValueError("装饰素材清单 assets 须为非空数组，数量按本次页面决定")
        for required in ("prompts.md", "index.html"):
            if not (folder / required).is_file():
                errors.append(f"独立装饰缺少 decorations/{required}")
        seen = set()
        for index, item in enumerate(assets, 1):
            try:
                if not isinstance(item, dict):
                    raise ValueError("素材须为对象")
                for key in ("name", "file", "suggested_display_width", "suggested_use"):
                    if not isinstance(item.get(key), str) or not item[key].strip():
                        raise ValueError(f"缺少非空字段 {key}")
                if not item["file"].lower().endswith(".png"):
                    raise ValueError("文件须为 PNG")
                path = local_file(manifest.parent, item["file"])
                if not path.is_relative_to(folder):
                    raise ValueError("PNG须单独存放在 decorations/ 文件夹")
                if path in seen:
                    raise ValueError("重复列出的PNG路径")
                seen.add(path)
                size = (item.get("width"), item.get("height"))
                if any(not isinstance(v, int) or isinstance(v, bool) or v <= 0 for v in size):
                    raise ValueError("width、height须记录实际导出尺寸的正整数")
                with Image.open(path) as image:
                    validate_png_ppi(image, data)
                    if image.format != "PNG" or image.size != size:
                        raise ValueError(f"格式或尺寸不符，实际为 {image.format} {image.width}×{image.height}")
                    minimum, maximum = image.convert("RGBA").getchannel("A").getextrema()
                    if minimum != 0 or maximum == 0:
                        raise ValueError("缺少真实透明背景或可见主体")
                count += 1
            except (OSError, ValueError, TypeError) as exc:
                errors.append(f"独立装饰 #{index}：{exc}")
    except (OSError, ValueError, TypeError) as exc:
        errors.append(f"独立装饰交付无效：{exc}")
    return count



VISUAL_REVIEW_CRITERIA = (
    "kv_identity", "reference_translation", "background_design", "component_craft",
    "color_hierarchy", "content_composition", "export_fidelity",
)


def validate_visual_review(review: dict, picture) -> None:
    """Require declared final visual checks; do not infer aesthetic quality."""
    visual = review.get("visual_review")
    if not isinstance(visual, dict) or visual.get("stage") != "final-render":
        raise ValueError("缺少最终浏览器回填视觉检查，不能用组合样张验收代替")
    picture(visual.get("page"))
    picture(visual.get("component_comparison"))
    picture(visual.get("background_comparison"))
    checks = visual.get("checks")
    if not isinstance(checks, dict):
        raise ValueError("视觉检查须包含七项具体观察")
    for key in VISUAL_REVIEW_CRITERIA:
        item = checks.get(key)
        if not isinstance(item, dict):
            raise ValueError(f"视觉检查缺少分项：{key}")
        if item.get("status") != "pass":
            raise ValueError(f"视觉分项尚未通过：{key}；须修正后重新查看")
        observation = item.get("observation")
        if not isinstance(observation, str) or not observation.strip():
            raise ValueError(f"视觉分项缺少实际观察：{key}")
        picture(item.get("evidence"))
    issues = visual.get("remaining_issues")
    if not isinstance(issues, list) or any(not isinstance(x, str) or not x.strip() for x in issues):
        raise ValueError("remaining_issues须为具体问题字符串数组")
    if issues or visual.get("status") != "pass":
        raise ValueError("仍有待返工设计或最终视觉检查未通过，不能作为完成版文件夹交付")



def validate_design_selection(evidence: dict, picture):
    """Check declared user selection and snapshot, not approval authenticity."""
    selection = evidence.get("design_selection")
    if not isinstance(selection, dict) or selection.get("status") != "approved":
        raise ValueError("真实样张尚未获得用户手动确认，不能整理交付完成版文件夹；工作素材允许在样张阶段制作")
    round_number = selection.get("round")
    if not isinstance(round_number, int) or isinstance(round_number, bool) or round_number <= 0:
        raise ValueError("样张round须为正整数")
    proposals = selection.get("proposals")
    if not isinstance(proposals, list) or len(proposals) != 3:
        raise ValueError("当前轮须记录3套完整方案样张")
    by_id, paths = {}, set()
    for proposal in proposals:
        if not isinstance(proposal, dict):
            raise ValueError("样张方案记录须为对象")
        ident, summary = proposal.get("id"), proposal.get("design_summary")
        if not isinstance(ident, str) or not ident.strip() or ident in by_id:
            raise ValueError("样张方案id须非空且唯一")
        if not isinstance(summary, str) or not summary.strip():
            raise ValueError("须记录各套方案的实际设计差异")
        path = picture(proposal.get("file"))
        if path in paths:
            raise ValueError("3套样张不能引用同一图片文件")
        by_id[ident] = path
        paths.add(path)
    selected = selection.get("selected_id")
    if not isinstance(selected, str) or selected not in by_id:
        raise ValueError("用户确认必须明确指向当前轮的一套样张")
    approval = selection.get("approval")
    if (not isinstance(approval, dict) or not isinstance(approval.get("user_reply"), str)
            or not approval["user_reply"].strip()):
        raise ValueError("缺少用户实际确认反馈，不能以内部验收代替")
    chosen = by_id[selected]
    if approval.get("sample_sha256") != hashlib.sha256(chosen.read_bytes()).hexdigest():
        raise ValueError("所选样张版本已变化或缺少确认时哈希，须重新展示并确认")
    return chosen, paths



def validate_hybrid_working_set(root: Path, data: dict, evidence: dict, picture, lineage, by_file) -> set[Path]:
    """Check final backgrounds + lightweight concepts, then one selected production set."""
    mode = "background-final-foreground-concept-v1"
    if data.get("production_workflow") != mode or evidence.get("production_workflow") != mode:
        raise ValueError("assets与设计证据须使用同一制作流程")
    selection = evidence["design_selection"]
    selected = None
    page_size = None
    candidate_sources = {}
    background_roles = {"hero", "banner"} | {r for r in ALL_ROLES if r.endswith(".background")}

    def frozen(item):
        if not isinstance(item, dict):
            raise ValueError("素材记录须为对象")
        path = picture(item.get("file"))
        digest = item.get("sha256")
        if (not isinstance(digest, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", digest)
                or hashlib.sha256(path.read_bytes()).hexdigest() != digest.lower()):
            raise ValueError("背景／示意／工作源已变化或缺少实际SHA256")
        return path

    def work_size(work):
        size = (work.get("page_width"), work.get("page_height"))
        if size[0] != 1920 or not isinstance(size[1], int) or isinstance(size[1], bool) or size[1] <= 0:
            raise ValueError("样张与工作素材须按1920px宽及实际累计高度制作")
        return size

    def image_size(path, size):
        with Image.open(path) as im:
            if im.size != size:
                raise ValueError("背景母图／整页截图尺寸与最终页面规格不一致")

    def browser_preview(name, size, needed):
        path = picture(name)
        image_size(path, size)
        rec = by_file.get(path)
        renderer = next((r.get("renderer") for r in evidence["records"] if r.get("file") == name), None)
        if not rec or rec[0] != "derived" or renderer != "browser" or not needed.issubset(set(rec[1])):
            raise ValueError("样张须在浏览器实际拼入对应背景和前景图，记录直接输入；不能用AI整页图替换背景")
        return path

    for proposal in selection["proposals"]:
        manifest = local_file(root, proposal["background_set"])
        work = json.loads(manifest.read_text(encoding="utf-8"))
        size = work_size(work)
        if page_size is not None and size != page_size:
            raise ValueError("三套样张须使用同一最终页面规格")
        page_size = size
        master = frozen(work.get("background_master"))
        image_size(master, size)
        items, concepts = work.get("assets"), work.get("concept_images")
        if not isinstance(items, list) or not items or not isinstance(concepts, list) or not concepts:
            raise ValueError("候选须有最终背景清单和轻量前景示意图，不需要三套完整前景")
        backgrounds = {}
        for item in items:
            path = frozen(item)
            if item.get("role") not in background_roles or path in backgrounds:
                raise ValueError("候选背景清单仅允许背景角色，不能要求预先制作完整卡片／按钮／状态")
            if master not in lineage(path, set()):
                raise ValueError("候选背景切片须来自本套实际母背景")
            backgrounds[path] = item
        concept_paths = {frozen(item) for item in concepts}
        if len(concept_paths) != len(concepts) or concept_paths & (set(backgrounds) | {master}):
            raise ValueError("前景示意须为独立且不重复的实际图片")
        candidate_sources[proposal["id"]] = set(backgrounds) | concept_paths | {master}
        browser_preview(proposal["file"], size, set(backgrounds) | concept_paths)
        if proposal["id"] == selection["selected_id"]:
            if selection["approval"].get("background_set_sha256", "").lower() != hashlib.sha256(manifest.read_bytes()).hexdigest():
                raise ValueError("选定背景与示意清单已变化或缺少确认时background_set_sha256")
            selected = (master, backgrounds, concept_paths, size)
    if selected is None:
        raise ValueError("缺少选定背景方案")
    selected_master, backgrounds, concepts, size = selected
    unselected = set().union(*(sources for ident, sources in candidate_sources.items() if ident != selection["selected_id"])) - candidate_sources[selection["selected_id"]]
    final = evidence.get("selected_working_set")
    if not isinstance(final, dict) or final.get("selected_id") != selection["selected_id"]:
        raise ValueError("只允许制作用户选中的这一套完整工作素材")
    manifest = local_file(root, final["file"])
    if final.get("manifest_sha256", "").lower() != hashlib.sha256(manifest.read_bytes()).hexdigest():
        raise ValueError("最终工作清单缺少冻结哈希或已变化")
    work = json.loads(manifest.read_text(encoding="utf-8"))
    if work_size(work) != size:
        raise ValueError("最终制作不能改变已选样张的页面规格")
    master = frozen(work.get("background_master"))
    image_size(master, size)
    if lineage(master, set()) & unselected:
        raise ValueError("最终背景混入未选方案的背景或示意")
    if selected_master not in lineage(master, set()):
        raise ValueError("最终背景须复用选定母图，允许基于它局部融合修补，不能整页另起生成")
    inherited = evidence.get("background_inheritance")
    if (not isinstance(inherited, dict) or inherited.get("status") != "pass"
            or not isinstance(inherited.get("observation"), str) or not inherited["observation"].strip()
            or picture(inherited.get("source")) != selected_master or picture(inherited.get("result")) != master):
        raise ValueError("缺少实际选定背景与最终背景的继承对照")
    picture(inherited.get("comparison"))
    changes = inherited.get("local_changes")
    if not isinstance(changes, list) or any(not isinstance(c, str) or not c.strip() for c in changes):
        raise ValueError("local_changes须为具体局部修补说明数组；未修改填写空数组")
    if not changes and not same_png_except_resolution(master.read_bytes(), selected_master.read_bytes()):
        raise ValueError("背景存在超出PPI元数据的变化，须记录局部修补并实际对照")
    members = {}
    for field, label in (("assets", "role"), ("decorations", "name")):
        items = work.get(field)
        if not isinstance(items, list) or (field == "assets" and not items):
            raise ValueError("最终工作清单缺少完整素材列表")
        for item in items:
            path = frozen(item)
            if path in members or not isinstance(item.get(label), str) or not item[label].strip():
                raise ValueError("最终工作源重复或缺少角色／名称")
            if not isinstance(item.get("used_in_preview", True), bool):
                raise ValueError("used_in_preview须为布尔值")
            reached = lineage(path, set())
            if reached & unselected:
                raise ValueError("最终工作素材混入未选方案的背景或示意")
            if field == "assets" and item["role"] in background_roles:
                if master not in reached:
                    raise ValueError("最终背景切片须来自最终组合母图")
            elif not reached & (concepts | {picture(next(p["file"] for p in selection["proposals"] if p["id"] == selection["selected_id"]))}):
                raise ValueError("正式前景／装饰须依据选中样张或其实际示意图制作，不能只凭KV重新设计")
            members[path] = (field, item)
    if {i["role"] for i in backgrounds.values()} != {i["role"] for f, i in members.values() if f == "assets" and i["role"] in background_roles}:
        raise ValueError("最终交付遗漏或增加了未选定的背景模块")
    needed = {path for path, (_, item) in members.items() if item.get("used_in_preview", True)}
    preview = browser_preview(final["preview"], size, needed)
    seen = set()
    def match_final(item, field, label, path):
        source = picture(item.get("working_source"))
        expected = members.get(source)
        if not expected or expected[0] != field or expected[1].get(label) != item.get(label):
            raise ValueError("working_source不属于选定方案的最终工作集或角色不符")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected[1]["sha256"].lower():
            raise ValueError("正式文件未直接复用已验收工作文件")
        if source not in lineage(path, set()):
            raise ValueError("正式素材来源链缺少working_source")
        seen.add(source)
    for item in data["assets"]:
        match_final(item, "assets", "role", picture(item.get("file")))
    final_master = data.get("background_master", {})
    if picture(final_master.get("working_source")) != master or picture(final_master.get("file")).read_bytes() != master.read_bytes():
        raise ValueError("交付母背景未直接复用最终工作母图")
    if data.get("decorations_enabled", True):
        decor_manifest = local_file(root, data["decoration_manifest"])
        decor = json.loads(decor_manifest.read_text(encoding="utf-8"))
        for item in decor["assets"]:
            path = (decor_manifest.parent / item["file"]).resolve()
            if not path.is_relative_to(root.resolve()):
                raise ValueError("装饰路径超出页面目录")
            match_final(item, "decorations", "name", path)
    if seen != set(members):
        raise ValueError("最终工作素材尚未完整交付")
    return set(members) | {master}


def validate_working_set_reuse(root: Path, data: dict, evidence: dict, picture, lineage, by_file) -> set[Path]:
    """Validate rendered previews and byte-identical reuse of their frozen working files."""
    if data.get("production_workflow") == "background-final-foreground-concept-v1":
        return validate_hybrid_working_set(root, data, evidence, picture, lineage, by_file)
    mode = "shared-assets-preview-v1"
    if data.get("production_workflow") != mode or evidence.get("production_workflow") != mode:
        raise ValueError("制作流程须为shared-assets-preview-v1：样张由真实工作素材拼合，交付复用所选素材")
    selection = evidence["design_selection"]
    selected = None
    page_size = None

    def checked_member(item):
        if not isinstance(item, dict):
            raise ValueError("工作文件记录须为对象")
        path = picture(item.get("file"))
        digest = item.get("sha256")
        if (not isinstance(digest, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", digest)
                or hashlib.sha256(path.read_bytes()).hexdigest() != digest.lower()):
            raise ValueError(f"{path.name}工作文件已变化或缺少实际SHA256，须重新预览并冻结")
        if not isinstance(item.get("used_in_preview", True), bool):
            raise ValueError("used_in_preview须为布尔值")
        return path

    for proposal in selection["proposals"]:
        manifest = local_file(root, proposal["working_set"])
        work = json.loads(manifest.read_text(encoding="utf-8"))
        if not isinstance(work, dict):
            raise ValueError("工作素材清单须为对象")
        size = (work.get("page_width"), work.get("page_height"))
        if (size[0] != 1920 or not isinstance(size[1], int)
                or isinstance(size[1], bool) or size[1] <= 0):
            raise ValueError("工作样张须按1920px宽与实际累计高度制作")
        if page_size is not None and size != page_size:
            raise ValueError("三套样张须使用同一最终页面规格")
        page_size = size
        master = checked_member(work.get("background_master"))
        with Image.open(master) as image:
            if image.size != size:
                raise ValueError("工作背景母图尺寸与实际页面规格不一致")
        members = {}
        for field, label in (("assets", "role"), ("decorations", "name")):
            items = work.get(field)
            if not isinstance(items, list) or (field == "assets" and not items):
                raise ValueError(f"工作清单缺少{field}")
            for item in items:
                path = checked_member(item)
                if path in members or not isinstance(item.get(label), str) or not item[label].strip():
                    raise ValueError("工作文件重复或缺少角色／名称")
                members[path] = (field, item)
        preview = picture(proposal["file"])
        with Image.open(preview) as image:
            if image.size != size:
                raise ValueError("完整样张必须是最终1920px规格的页面截图，不能用概念图代替")
        rec = by_file.get(preview)
        renderer = next((r.get("renderer") for r in evidence["records"] if r.get("file") == proposal["file"]), None)
        reached = lineage(preview, set())
        needed = {p for p, (_, item) in members.items() if item.get("used_in_preview", True)}
        needed.add(master)
        if not rec or rec[0] != "derived" or renderer != "browser" or not needed.issubset(reached):
            raise ValueError("三套样张均须由对应工作素材在真实浏览器拼合，不能直接生整页图或漏记实际输入")
        if proposal["id"] == selection["selected_id"]:
            digest = selection["approval"].get("working_set_sha256")
            if (not isinstance(digest, str)
                    or digest.lower() != hashlib.sha256(manifest.read_bytes()).hexdigest()):
                raise ValueError("所选工作清单已变化或缺少确认时working_set_sha256")
            selected = (master, members)
    if selected is None:
        raise ValueError("缺少选定工作素材清单")
    master, members = selected
    seen = set()

    def match_final(item, field, label, final_path):
        source = picture(item.get("working_source"))
        expected = members.get(source)
        if not expected or expected[0] != field or expected[1].get(label) != item.get(label):
            raise ValueError("正式文件working_source不属于选定工作集或角色／名称不一致")
        if hashlib.sha256(final_path.read_bytes()).hexdigest() != expected[1]["sha256"].lower():
            raise ValueError(f"{final_path.name}未直接复用选定工作文件：不能确认后重生、缩放或改画")
        seen.add(source)

    for asset in data["assets"]:
        path = picture(asset.get("file"))
        match_final(asset, "assets", "role", path)
        if local_file(root, asset["working_source"]) not in lineage(path, set()):
            raise ValueError("正式素材来源链须实际引用working_source，不从样张PNG反向重建")
    final_master = data.get("background_master", {})
    if picture(final_master.get("working_source")) != master:
        raise ValueError("最终母背景未绑定选定工作母图")
    if hashlib.sha256(picture(final_master.get("file")).read_bytes()).digest() != hashlib.sha256(master.read_bytes()).digest():
        raise ValueError("正式母背景与用户看到的工作母图不同，禁止整页重新生成")
    if data.get("decorations_enabled", True):
        manifest = local_file(root, data["decoration_manifest"])
        decor = json.loads(manifest.read_text(encoding="utf-8"))
        for item in decor["assets"]:
            path = (manifest.parent / item["file"]).resolve()
            if not path.is_relative_to(root.resolve()):
                raise ValueError("装饰路径超出页面目录")
            match_final(item, "decorations", "name", path)
    if seen != set(members):
        raise ValueError("选定工作集的素材或装饰未完整复用交付")
    return set(members) | {master}


def validate_design_evidence(root: Path, data: dict, errors: list[str]) -> None:
    """Check declared image-input lineage, not visual quality or log authenticity."""
    try:
        filename = data.get("design_evidence")
        if not isinstance(filename, str) or not filename.strip():
            raise ValueError("缺少 design_evidence：须记录实际KV、参考图片输入与组合样张")
        evidence = json.loads(local_file(root, filename).read_text(encoding="utf-8"))
        if not isinstance(evidence, dict):
            raise ValueError("证据文件须为对象")

        def picture(name):
            if not isinstance(name, str) or not name.strip():
                raise ValueError("图片路径须为非空字符串")
            path = local_file(root, name)
            with Image.open(path) as im:
                im.verify()
            return path

        kv_names = evidence.get("kv_images")
        references = evidence.get("references")
        records = evidence.get("records")
        if not isinstance(kv_names, list) or not kv_names:
            raise ValueError("缺少实际KV图片")
        kv = {picture(name) for name in kv_names}
        if not isinstance(references, list) or not references:
            raise ValueError("缺少实际参考截图及来源")
        refs = set()
        for ref in references:
            if (not isinstance(ref, dict)
                    or not isinstance(ref.get("url"), str)
                    or not re.match(r"^https?://[^/\s]+", ref["url"])
                    or not isinstance(ref.get("use"), str) or not ref["use"].strip()):
                raise ValueError("参考须有实际网址与非空借鉴用途")
            refs.add(picture(ref.get("file")))
        if kv & refs:
            raise ValueError("KV图片不能同时充当第三方参考")
        if not isinstance(records, list) or not records:
            raise ValueError("缺少素材生成记录")
        by_file = {}
        for rec in records:
            if not isinstance(rec, dict):
                raise ValueError("生成记录须为对象")
            path = picture(rec.get("file"))
            if path in by_file:
                raise ValueError("素材记录重复；编辑前后请保留不同文件")
            kind = rec.get("kind")
            if kind == "provided":
                picture(rec.get("source_file"))
                inputs = []
            elif kind in {"generated", "derived"}:
                names = rec.get("input_images")
                if not isinstance(names, list) or not names:
                    raise ValueError(f"{rec['file']} 未记录实际图片输入")
                inputs = [picture(name) for name in names]
                if kind == "generated" and (not isinstance(rec.get("source"), str)
                                              or not rec["source"].strip()):
                    raise ValueError(f"{rec['file']} 缺少实际工具结果标识")
            else:
                raise ValueError("kind须为generated、derived或provided")
            by_file[path] = (kind, inputs)

        memo = {}
        def lineage(path, active):
            if path in active:
                raise ValueError("生成图片输入形成循环，不能自己引用自己")
            if path in memo:
                return memo[path]
            reached = {path}
            rec = by_file.get(path)
            if rec:
                for image in rec[1]:
                    reached |= lineage(image, active | {path})
            memo[path] = reached
            return reached

        for path in by_file:
            reached = lineage(path, set())
            kind, inputs = by_file[path]
            if kind == "derived" and not any(i in by_file for i in inputs):
                raise ValueError(f"{path.name} 的处理记录缺少原始素材记录")
        chosen, proposals = validate_design_selection(evidence, picture)
        working_sources = validate_working_set_reuse(root, data, evidence, picture, lineage, by_file)
        for proposal in proposals:
            rec = by_file.get(proposal)
            reached = lineage(proposal, set())
            if not rec or rec[0] != "derived" or not reached & kv or not reached & refs:
                raise ValueError("3套真实样张均须从工作素材追溯到实际KV与参考输入")
        assets = data.get("assets")
        if not isinstance(assets, list):
            raise ValueError("assets须为数组")
        for asset in assets:
            if not isinstance(asset, dict):
                raise ValueError("业务素材须为对象")
            path = picture(asset.get("file"))
            rec = by_file.get(path)
            if rec is None:
                raise ValueError(f"{asset.get('file')} 缺少素材来源记录")
            reached = lineage(path, set())
            if not reached & working_sources:
                raise ValueError(f"{asset.get('file')} 未复用所选工作素材")
            if data.get("production_workflow") == "background-final-foreground-concept-v1":
                if reached & (proposals - {chosen}):
                    raise ValueError("正式素材混入未选方案；只依据选中背景与前景示意制作")
            elif reached & proposals:
                raise ValueError("正式素材不能从预览截图重新生成；应直接引用所选工作源，避免循环")
            if rec[0] != "provided" and (not reached & kv or not reached & refs):
                raise ValueError(f"{asset.get('file')} 的工作素材来源链缺少KV或参考")
        validate_blind_background_lineage(root, data, lineage, errors)
        review = evidence.get("review")
        if not isinstance(review, dict) or not isinstance(review.get("notes"), str) or not review["notes"].strip():
            raise ValueError("缺少实际组合对照及观察记录")
        composition = picture(review.get("composition"))
        expected = (picture(evidence["selected_working_set"]["preview"])
                    if data.get("production_workflow") == "background-final-foreground-concept-v1" else chosen)
        if composition != expected:
            raise ValueError("review.composition须使用选中方案的真实最终组合预览；示意不能冒充最终验收")
        picture(review.get("comparison"))
        if composition not in by_file or by_file[composition][0] == "provided":
            raise ValueError("组合设计样张须有实际生成或处理记录")
        reached = lineage(composition, set())
        if not reached & kv or not reached & refs:
            raise ValueError("组合设计样张缺少KV与真实参考图片输入")
        validate_visual_review(review, picture)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        errors.append(f"设计参考证据无效：{exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    root = args.output_dir.resolve()
    manifest = root / "assets.json"
    if not root.is_dir() or not manifest.is_file():
        print("页面目录或 assets.json 不存在。", file=sys.stderr)
        return 1
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"无法读取 assets.json：{exc}", file=sys.stderr)
        return 1
    if not isinstance(data, dict):
        print("assets.json 顶层必须是对象。", file=sys.stderr)
        return 1
    errors: list[str] = []
    validate_assets(root, data, errors)
    validate_design_evidence(root, data, errors)
    validate_references(root, errors)
    validate_structure(root, data, errors)
    validate_rule_module(root, data, errors)
    validate_marquee_structure(root, data, errors)
    validate_module_titles(root, data, errors)
    validate_preview(root, data, errors)
    validate_blind_layout(root, data, errors)
    validate_continuous_background(root, data, errors)
    decoration_count = validate_decorations(root, data, errors)
    if errors:
        for error in errors:
            print(f"错误：{error}", file=sys.stderr)
        return 1
    print(f"校验通过：{len(data['assets'])} 张业务 PNG、{decoration_count} 张独立装饰 PNG，页面引用、参考输入及最终视觉分项记录完整，抽奖与任务信息归属正确。此校验不判断审美或观察真实性。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
