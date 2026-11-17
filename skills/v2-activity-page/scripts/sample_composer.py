"""Compose a 1x candidate from frozen full-width rows and explicit foregrounds.

This is a mechanical guard, not an automatic art/seam judgement. No AI calls,
KV overlays, background resizing, alpha extraction or nonuniform scaling.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
from PIL import Image

ROLES = {'module.title', 'package.card', 'package.card-selected',
         'package.button', 'package.qr-background', 'blind.art',
         'blind.prize-card', 'blind.button', 'task.card', 'task.button',
         'rule.button', 'record.button', 'text', 'decoration',
         'gift.card', 'gift.button', 'marquee.item', 'marquee.center',
         'flip.card', 'points.card', 'points.button', 'marquee.highlight'}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checked_image(root, item):
    name = item.get('file')
    if not isinstance(name, str) or not name:
        raise ValueError('Missing source file')
    path = (root / name).resolve()
    if not path.is_relative_to(root):
        raise ValueError('Source must stay in the activity directory')
    if item.get('sha256') != digest(path):
        raise ValueError('Frozen source changed: ' + name)
    with Image.open(path) as im:
        return im.convert('RGBA').copy()


def review_pass(review, key):
    value = review.get(key, {})
    if value.get('status') != 'pass' or not value.get('observation', '').strip():
        raise ValueError('Visual review required: ' + key)


def transition_template(manifest):
    """Source-bound pending reviews; never make an aesthetic pass automatically."""
    rows = manifest.get('rows', [])
    return [{'upper_row': i-1, 'lower_row': i,
             'upper_sha256': rows[i-1]['sha256'], 'lower_sha256': rows[i]['sha256'],
             'review': {key: {'status': 'pending', 'observation': ''}
                        for key in ('left', 'center', 'right', 'overall_tone')}}
            for i in range(1, len(rows))]


def validate_vertical_transitions(manifest):
    expected = transition_template(manifest)
    actual = manifest.get('vertical_transitions', [])
    if not isinstance(actual, list) or len(actual) != len(expected):
        raise ValueError('Vertical transition reviews required for every adjacent row pair')
    for want, entry in zip(expected, actual):
        if not isinstance(entry, dict) or any(entry.get(k) != want[k] for k in
                ('upper_row', 'lower_row', 'upper_sha256', 'lower_sha256')):
            raise ValueError('Vertical transition review does not match current row sources')
        for key in ('left', 'center', 'right', 'overall_tone'):
            review_pass(entry.get('review', {}), key)


def compose_background(root, manifest, require_reviews=True):
    root = Path(root).resolve()
    height = manifest.get('height')
    if manifest.get('width') != 1920 or type(height) is not int or height <= 0:
        raise ValueError('Candidate requires width 1920 and a positive integer height')
    rows = manifest.get('rows', [])
    if not rows:
        raise ValueError('Full-width frozen background rows required')
    canvas = Image.new('RGBA', (1920, height))
    y = 0
    background_hashes = set()
    for row in rows:
        image = checked_image(root, row)
        if row.get('y') != y or image.width != 1920 or image.height <= 0 or y + image.height > height:
            raise ValueError('Rows must fill the page consecutively at native 1920 width')
        if image.getextrema()[3] != (255, 255):
            raise ValueError('Background rows must be opaque')
        if require_reviews:
            review_pass(row.get('review', {}), 'seams')
            if row.get('contains_kv'):
                review_pass(row.get('review', {}), 'kv_preserved')
        canvas.alpha_composite(image, (0, y))
        y += image.height
        background_hashes.add(row['sha256'])
    if y != height:
        raise ValueError('Rows do not fill the confirmed page height')
    if require_reviews:
        validate_vertical_transitions(manifest)
    return canvas



def validate_blind_placement(item, image, rows, page_height):
    """Bind the reviewed contact to the exact cutout, rect and row coordinates."""
    placement = item.get('environment_placement', {})
    row_index = placement.get('row_index')
    if type(row_index) is not int or not 0 <= row_index < len(rows):
        raise ValueError('Blind environment requires a registered row_index')
    row = rows[row_index]
    if (row['sha256'] != item.get('environment_row_sha256')
            or placement.get('row_sha256') != row['sha256']
            or placement.get('art_sha256') != item['sha256']
            or placement.get('rect') != item['rect']):
        raise ValueError('Blind placement changed; recheck body and environment together')
    source = placement.get('source_contact')
    target = placement.get('row_contact')
    for point in (source, target):
        if (not isinstance(point, list) or len(point) != 2
                or any(type(v) not in (int, float) or not math.isfinite(v) for v in point)):
            raise ValueError('Blind contact requires two finite coordinates')
    row_end = rows[row_index + 1]['y'] if row_index + 1 < len(rows) else page_height
    x, y, w, h = item['rect']
    if not row['y'] <= y or y + h > row_end:
        raise ValueError('Blind rectangle must belong to its environment row')
    if not (0 <= source[0] <= image.width and 0 <= source[1] <= image.height
            and 0 <= target[0] <= 1920 and 0 <= target[1] <= row_end - row['y']):
        raise ValueError('Blind contact is outside source or environment row')
    mapped = [x + source[0] * w / image.width,
              y - row['y'] + source[1] * h / image.height]
    if any(abs(a - b) > 1 for a, b in zip(mapped, target)):
        raise ValueError('Blind contact does not align with the registered environment')


def validate_task_geometry(manifest, prepared):
    """Use measured design dimensions, not just the source PNG aspect ratio."""
    groups = {}
    for item, image in prepared:
        if item['role'] in {'task.card', 'task.button'}:
            if not item.get('module_id'):
                raise ValueError('Task requires module_id')
            groups.setdefault(item['module_id'], []).append((item, image))
    configs = manifest.get('task_modules', {})
    if set(configs) != set(groups):
        raise ValueError('Task modules must match visible task cards and buttons')
    for module, group in groups.items():
        config = configs[module]
        profile = config.get('profile')
        if profile == 'example_v2_dual':
            sizes = {'task.card': [600, 120], 'task.button': [160, 60]}
        elif profile == 'measured':
            if not isinstance(config.get('size_source'), str) or not config['size_source'].strip():
                raise ValueError('Measured task profile requires actual size_source')
            sizes = {'task.card': config.get('card_size'), 'task.button': config.get('button_size')}
        else:
            raise ValueError('Task requires example_v2_dual or measured geometry profile')
        for size in sizes.values():
            if not isinstance(size, list) or len(size) != 2 or any(type(v) is not int or v <= 0 for v in size):
                raise ValueError('Task design sizes must be positive integer pairs')
        cards = {}
        buttons = []
        for item, image in group:
            if item['rect'][2:] != sizes[item['role']]:
                raise ValueError('Task display size differs from measured geometry; do not flatten')
            # Detect a thin strip hidden inside a correctly sized transparent canvas.
            bounds = image.getchannel('A').point(lambda a: 255 if a >= 128 else 0).getbbox()
            if not bounds or (bounds[2]-bounds[0] < image.width * .85
                              or bounds[3]-bounds[1] < image.height * .85):
                raise ValueError('Task visible body does not fill its design canvas')
            if item['role'] == 'task.card':
                ident = item.get('id')
                if not ident or ident in cards:
                    raise ValueError('Task cards require unique ids')
                cards[ident] = item
            else:
                buttons.append(item)
        if config.get('count') != len(cards) or len(buttons) != len(cards):
            raise ValueError('Task count must match cards and individual buttons')
        parents = [button.get('task_card_id') for button in buttons]
        if len(set(parents)) != len(cards) or set(parents) != set(cards):
            raise ValueError('Each task button must reference its own task_card_id')
        for button in buttons:
            cx, cy, cw, ch = cards[button['task_card_id']]['rect']
            bx, by, bw, bh = button['rect']
            if not (cx <= bx and cy <= by and bx+bw <= cx+cw and by+bh <= cy+ch):
                raise ValueError('Task button must fit inside its card')
            if profile == 'example_v2_dual' and (cx+cw-bx-bw != 40 or 2*(by-cy)+bh != ch):
                raise ValueError('Task button must be centered vertically with right inset 40')
        review_pass(config, 'proportion_and_content')



def validate_package_button_spacing(prepared):
    cards = {(item.get('module_id'), item.get('id')): item
             for item, _ in prepared if item['role'] in {'package.card', 'package.card-selected'}}
    used = set()
    for button, _ in prepared:
        if button['role'] != 'package.button':
            continue
        key = (button.get('module_id'), button.get('card_id'))
        if key not in cards or key in used:
            raise ValueError('Package button requires its own card_id and module_id')
        used.add(key)
        card = cards[key]
        safe = card.get('button_safe_rect')
        if (not isinstance(safe, list) or len(safe) != 4
                or any(type(v) is not int for v in safe) or min(safe) <= 0):
            raise ValueError('Package card requires an inset button_safe_rect')
        sx, sy, sw, sh = safe
        cx, cy, cw, ch = card['rect']
        if sx+sw >= cw or sy+sh >= ch:
            raise ValueError('Package button safe region must stay clear of card edges')
        bx, by, bw, bh = button['rect']
        if not (cx+sx <= bx and cy+sy <= by and bx+bw <= cx+sx+sw and by+bh <= cy+sy+sh):
            raise ValueError('Package button exceeds its interior safe region')
        review_pass(button.get('review', {}), 'edge_clearance')


def compose(root, manifest):
    root = Path(root).resolve()
    canvas = compose_background(root, manifest)
    height = canvas.height
    background = canvas.copy()
    background_hashes = {row['sha256'] for row in manifest['rows']}
    items = manifest.get('foregrounds', [])
    package_groups = {}
    title_groups = {}
    forbidden = background_hashes | set(manifest.get('protected_kv_sha256', []))
    prepared = []
    for item in items:
        role = item.get('role')
        if role not in ROLES or item.get('sha256') in forbidden:
            raise ValueError('KV/background cannot be overlaid as a foreground')
        rect = item.get('rect', [])
        if (len(rect) != 4 or any(type(v) is not int for v in rect)
                or min(rect[:2]) < 0 or min(rect[2:]) <= 0
                or rect[0]+rect[2] > 1920 or rect[1]+rect[3] > height):
            raise ValueError('Foreground must use its confirmed integer rectangle')
        image = checked_image(root, item)
        if role == 'blind.art':
            alpha_min, alpha_max = image.getextrema()[3]
            if alpha_min != 0 or alpha_max == 0:
                raise ValueError('Blind foreground requires transparent exterior and visible body')
            # Alpha alone cannot detect a residual scene patch with transparent corners.
            review_pass(item.get('review', {}), 'clean_cutout')
            review_pass(item.get('review', {}), 'environment_match')
            if item.get('environment_row_sha256') not in background_hashes:
                raise ValueError('Blind environment must belong to a frozen background row')
            validate_blind_placement(item, image, manifest['rows'], height)
        # Allow only integer-raster rounding, never flatten a title/card into a new ratio.
        if abs(image.width*rect[3]-image.height*rect[2]) > max(image.size):
            raise ValueError('Foreground aspect ratio differs; repair source, do not stretch')
        if role == 'module.title':
            group = item.get('title_group')
            typography = item.get('typography', {})
            size = typography.get('source_font_size_px')
            style = typography.get('style_id')
            if not isinstance(group, str) or not group or not style or type(size) is not int or size <= 0:
                raise ValueError('Title requires group, typography style and source font size')
            title_groups.setdefault(group, []).append((style, size * rect[3] / image.height))
        if role in {'package.card', 'package.card-selected'}:
            module = item.get('module_id')
            ident = item.get('id')
            if not module or not ident:
                raise ValueError('Package requires module_id and stable id')
            package_groups.setdefault(module, []).append((item, image))
        prepared.append((item, image))
    validate_task_geometry(manifest, prepared)
    validate_package_button_spacing(prepared)
    marquee_groups = {}
    for item, source in prepared:
        if item['role'].startswith('marquee.'):
            if not item.get('module_id'):
                raise ValueError('Marquee assets require module_id')
            marquee_groups.setdefault(item['module_id'], []).append((item, source))
    for group in marquee_groups.values():
        cards = [(item, source) for item, source in group
                 if item['role'] in {'marquee.item', 'marquee.card'}]
        highlights = [(item, source) for item, source in group if item['role'] == 'marquee.highlight']
        if not cards or len(highlights) != 1:
            raise ValueError('Marquee candidate requires exactly one visible marquee.highlight on a prize cell')
        highlight, high_source = highlights[0]
        matches = [(item, source) for item, source in cards if item['rect'] == highlight['rect']]
        if len(matches) != 1 or highlight.get('normal_source_sha256') != matches[0][0]['sha256']:
            raise ValueError('Marquee highlight must align to one cell and reference its normal source')
        if high_source.getchannel('A').getextrema()[1] == 0:
            raise ValueError('Marquee highlight must be visible')
        if high_source.size == matches[0][1].size and high_source.tobytes() == matches[0][1].tobytes():
            raise ValueError('Marquee highlight cannot be identical to normal source')
        if items.index(highlight) < items.index(matches[0][0]):
            raise ValueError('Marquee highlight must render above the normal prize cell')
        review_pass(highlight.get('review', {}), 'highlight_visibility')
    title_configs = manifest.get('title_groups', {})
    if set(title_configs) != set(title_groups):
        raise ValueError('Title group configuration must match visible titles')
    for group, titles in title_groups.items():
        config = title_configs[group]
        if config.get('count') != len(titles):
            raise ValueError('Title group count does not match')
        style, rendered_size = titles[0]
        if any(other_style != style or abs(other_size - rendered_size) > 0.01
               for other_style, other_size in titles):
            raise ValueError('Grouped titles must share style and rendered font size')
        review_pass(config, 'title_consistency')
    configs = manifest.get('package_modules', {})
    if set(configs) != set(package_groups):
        raise ValueError('Package modules and visible cards must match')
    for module, group in package_groups.items():
        config = configs[module]
        ids = [item['id'] for item, _ in group]
        if len(ids) != len(set(ids)) or config.get('count') != len(group):
            raise ValueError('Package count/ids do not match visible cards')
        selected = [item['id'] for item, _ in group if item['role'] == 'package.card-selected']
        if len(group) == 1:
            if selected or config.get('initial_selected_id') is not None:
                raise ValueError('Single package must use ordinary state without selection')
            continue  # QR panels do not count; no state contrast review applies.
        target = config.get('initial_selected_id', ids[0])
        if selected != [target]:
            raise ValueError('Exactly one initial package must be selected; default is the first')
        review_pass(config, 'state_contrast')
        if len(group) > 1:
            chosen = next(im for item, im in group if item['id'] == target)
            for item, image in group:
                if item['id'] != target and image.size == chosen.size and image.tobytes() == chosen.tobytes():
                    raise ValueError('Selected and unselected card pixels are identical')
    for item, image in prepared:
        x, y, w, h = item['rect']
        if image.size != (w, h):
            image = image.resize((w, h), Image.Resampling.LANCZOS)
        canvas.alpha_composite(image, (x, y))
    return canvas, background


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('manifest', type=Path)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--background-review-only', action='store_true',
                    help='Output only native background assembly and pending transition reviews')
    args = ap.parse_args()
    config = json.loads(args.manifest.read_text(encoding='utf-8'))
    if args.background_review_only:
        background = compose_background(args.manifest.resolve().parent, config, require_reviews=False)
        out = args.output.resolve()
        report = out.with_suffix('.transitions.pending.json')
        sources = {(args.manifest.resolve().parent / item['file']).resolve()
                   for item in config['rows'] + config.get('foregrounds', [])}
        if any(path in sources or path == args.manifest.resolve() for path in (out, report)):
            raise ValueError('Output cannot overwrite source/manifest')
        out.parent.mkdir(parents=True, exist_ok=True)
        background.save(out)
        report.write_text(json.dumps({'manifest_sha256': digest(args.manifest),
            'background_check_sha256': digest(out), 'final_visual_review': 'pending',
            'vertical_transitions': transition_template(config)}, ensure_ascii=False, indent=2), encoding='utf-8')
        print(str(out))
        return
    preview, background = compose(args.manifest.resolve().parent, config)
    out = args.output.resolve()
    # Complete all checks before writing; never overwrite a source.
    source_paths = [(args.manifest.resolve().parent / item['file']).resolve()
                    for item in config['rows'] + config.get('foregrounds', [])]
    outputs = [out, out.with_name(out.stem+'-background-check.png'), out.with_suffix('.composition.json')]
    if any(p in source_paths or p == args.manifest.resolve() for p in outputs):
        raise ValueError('Output cannot overwrite source/manifest')
    out.parent.mkdir(parents=True, exist_ok=True)
    preview.save(outputs[0])
    background.save(outputs[1])
    outputs[2].write_text(json.dumps({
        'manifest_sha256': digest(args.manifest), 'output_sha256': digest(out),
        'background_check_sha256': digest(outputs[1]),
        'mechanical_check': 'pass', 'final_visual_review': 'pending',
        'note': 'Inspect actual preview before presenting; mechanical pass is not art approval.'
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print(str(out))


if __name__ == '__main__':
    main()
