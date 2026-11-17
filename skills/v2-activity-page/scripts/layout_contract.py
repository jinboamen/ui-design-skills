"""V2 backend row layout, 1920 design coordinates and genuine 2x raster exports.

The validator checks declared geometry and evidence structure. It cannot establish
that screenshots came from a browser or that a 2x image contains genuine detail.
"""
from __future__ import annotations
from collections import Counter
import json
import math
import math
from pathlib import Path

TYPES = {'hero', 'banner', 'package', 'lottery', 'task', 'gift', 'rule', 'points'}
BG = {'hero', 'banner', 'package.background', 'blind.background', 'marquee.background',
      'task.background', 'gift.background', 'rule.background', 'flip.background', 'points.background'}


def integer(value, minimum=1):
    return type(value) is int and value >= minimum


def rect(value):
    if not isinstance(value, dict) or not all(integer(value.get(k), 0 if k in {'x', 'y'} else 1)
                                              for k in ('x', 'y', 'width', 'height')):
        raise ValueError('design_rect须有非负整数x/y及正整数width/height')
    return tuple(value[k] for k in ('x', 'y', 'width', 'height'))


def modules(data):
    layout = data.get('layout')
    if not isinstance(layout, dict) or layout.get('source') != 'backend':
        raise ValueError('V2须记录layout.source=backend及本次后台行列配置')
    if layout.get('design_width') != 1920 or not integer(layout.get('design_height')):
        raise ValueError('layout须使用design_width=1920和正整数design_height；不是设备视口尺寸')
    if data.get('export_scale') != 2 or type(data.get('export_scale')) is not int:
        raise ValueError('V2全部素材须export_scale=2，不能用PPI代替像素翻倍')
    rows = layout.get('rows')
    configs = data.get('module_configs')
    if not isinstance(rows, list) or not rows or not isinstance(configs, dict):
        raise ValueError('layout.rows须非空，module_configs须按稳定模块id保存配置')
    result, row_ids, cursor = {}, set(), 0
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('每行须为对象')
        rid, members = row.get('id'), row.get('modules')
        if not isinstance(rid, str) or not rid or rid in row_ids:
            raise ValueError('每行须有不重复的非空id')
        row_ids.add(rid)
        if not isinstance(members, list) or len(members) not in (1, 2):
            raise ValueError('每行只支持1个1920宽模块或2个各960宽模块')
        height = None
        for col, member in enumerate(members):
            if not isinstance(member, dict):
                raise ValueError('模块须为对象')
            mid, kind = member.get('id'), member.get('type')
            if not isinstance(mid, str) or not mid or mid == 'global' or mid in result or kind not in TYPES:
                raise ValueError('模块id须非空且全页唯一，type须为已有业务模块')
            x, y, width, h = rect(member.get('design_rect'))
            column_width = 1920 // len(members)
            if (x, y, width) != (col * column_width, cursor, column_width):
                raise ValueError(f'{mid}须按后台顺序填满本行：x={col*column_width},y={cursor},width={column_width}')
            if height is not None and h != height:
                raise ValueError('同一双列行的两个背景槽须共用y和height，短内容在槽内留白')
            height = h
            config = configs.get(mid)
            if not isinstance(config, dict) or config.get('layout_profile') != ('v1_single' if len(members) == 1 else 'v2_half'):
                raise ValueError(f'{mid}缺少匹配本行的layout_profile=v1_single或v2_half')
            result[mid] = member
        cursor += height
    if cursor != layout['design_height']:
        raise ValueError('design_height须等于逐行高度之和，不能把双列两模块高度相加')
    if set(configs) != set(result):
        raise ValueError('module_configs须与实际模块id一一对应')
    heroes = [m for m in result.values() if m['type'] == 'hero']
    if len(heroes) > 1:
        raise ValueError('最多一个独立hero；主KV可由Banner承载，位置与单/双列由后台配置决定')
    profile = data.get('backend_profile')
    if profile not in (None, 'example_backend_v2'):
        raise ValueError('不支持的backend_profile，不能自行猜测其他后台的模块约束')
    if profile == 'example_backend_v2':
        line = data.get('business_line')
        if not isinstance(line, str) or not line.strip():
            raise ValueError('example_backend_v2须记录实际business_line；此字段是离线清单映射')
        counts = Counter(member['type'] for member in result.values())
        duplicates = [kind for kind, count in counts.items()
                      if count > 1 and kind != 'banner' and not (kind == 'package' and line == 'repeat_packages')]
        if duplicates:
            raise ValueError('此后台Banner可重复，套餐仅repeat_packages示例分支可重复，其余组件只能一个：' + ', '.join(sorted(duplicates)))
    return result


def positive_number(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def responsive_scale(width, profile):
    effective = min(3840, max(1200, width)) if profile == 'example_backend_v2' else width
    return effective / 1920


def scaled_size(item):
    display = (item.get('display_width'), item.get('display_height'))
    if not all(positive_number(v) for v in display):
        raise ValueError('display_width/display_height须为有限正数设计尺寸')
    if any(v != int(v) for v in display) and item.get('rounding_rule') != 'nearest_pixel':
        raise ValueError('亚像素设计尺寸须明确rounding_rule=nearest_pixel')
    pixels = tuple(math.floor(v * 2 + 0.5) for v in display)
    if not all(integer(item.get(k)) for k in ('width','height')) or (item.get('width'), item.get('height')) != pixels:
        raise ValueError('PNG宽高须为2倍设计尺寸按最近像素取整，不能任意改比例')
    return pixels


def measured_size(spec, profile):
    if (not isinstance(spec, dict) or not isinstance(spec.get('source'), str)
            or not spec['source'].strip() or spec.get('measured_viewport_width') != 1920
            or spec.get('applies_to_profile') != profile):
        raise ValueError('非动态素材须有实际线上source、measured_viewport_width=1920及匹配的applies_to_profile；单列标识不授权继承V1旧尺寸')
    size = (spec.get('display_width'), spec.get('display_height'))
    if not all(positive_number(v) for v in size):
        raise ValueError('线上实测尺寸须使用有限正数display_width/display_height设计坐标')
    return size


def expected_size(role, item, data, title_roles):
    by_id = modules(data)
    mid = item.get('module_id')
    pixels = scaled_size(item)
    display = (item['display_width'], item['display_height'])
    if mid == 'global':
        if role not in {'rule.button', 'lottery.record'}:
            raise ValueError('global仅用于已配置的规则或公共奖品入口')
        required = measured_size(data.get('global_asset_sizes', {}).get(role), 'global')
    else:
        member = by_id.get(mid)
        if member is None:
            raise ValueError('业务PNG须有对应真实模块的module_id')
        config = data['module_configs'][mid]
        if role in BG:
            required = rect(member['design_rect'])[2:]
        elif role in title_roles or role == 'blind.prize-card':
            required = display  # Content-dependent canvases retain the actual recorded design size.
        else:
            overrides = config.get('asset_sizes', {})
            if not isinstance(overrides, dict):
                raise ValueError('asset_sizes须为按role记录的线上实测规格')
            spec = overrides.get(role, overrides.get('package.card') if role == 'package.card-selected' else None)
            required = measured_size(spec, config['layout_profile'])
            if role.startswith(('flip.', 'points.')) and spec.get('source_kind') not in {'live', 'live_css', 'user_confirmed'}:
                raise ValueError('新PC玩法正式尺寸须有线上来源或用户明确确认；纯Figma参考不能冒充上线实测')
    if display != required:
        raise ValueError(f'{mid}/{role}设计显示尺寸应为{required}，实际{display}')
    return pixels


def scoped(data, mid):
    member = modules(data)[mid]
    result = dict(data)
    for key in ('package_count', 'task_count', 'gift_count'):
        result[key] = 0
    result.update({'lottery_style': None, 'points_prize_count': 0, 'rule_inline_enabled': False, 'rule_floating_enabled': False})
    result.update(data['module_configs'][mid])
    result['_module_id'] = mid
    result['assets'] = [a for a in data.get('assets', []) if isinstance(a, dict) and a.get('module_id') == mid]
    result['rule_inline_enabled'] = member['type'] == 'rule'
    return result


def background_role(member, config):
    if member['type'] == 'lottery':
        return {'blind_box': 'blind.background', 'marquee': 'marquee.background', 'flip_card': 'flip.background'}.get(config.get('lottery_style'))
    return member['type'] if member['type'] in {'hero', 'banner'} else member['type'] + '.background'


def validate_counts(data, errors):
    by_id = modules(data)
    assets = data.get('assets', [])
    global_count = sum(a.get('module_id') == 'global' and a.get('role') == 'rule.button' for a in assets if isinstance(a, dict))
    floating = data.get('rule_floating_enabled', not any(m['type'] == 'rule' for m in by_id.values()))
    if type(floating) is not bool or global_count != int(floating):
        errors.append('浮动rule.button数量须与rule_floating_enabled一致，且module_id=global')
    records = sum(a.get('module_id') == 'global' and a.get('role') == 'lottery.record' for a in assets if isinstance(a, dict))
    record_enabled = data.get('prize_record_enabled', False)
    if type(record_enabled) is not bool or records != int(record_enabled):
        errors.append('公共奖品入口仅在prize_record_enabled=true时交付一张module_id=global的lottery.record')
    for mid, member in by_id.items():
        config = data['module_configs'][mid]
        counts = Counter(a.get('role') for a in assets if isinstance(a, dict) and a.get('module_id') == mid)
        kind = member['type']
        required = {background_role(member, config): 1}
        optional = set()
        def count(key, minimum=1, maximum=None):
            value = config.get(key)
            if not integer(value, minimum) or (maximum is not None and value > maximum):
                raise ValueError(f'{mid}.{key}须为{minimum}至{maximum or "实际配置数量"}的整数')
            return value
        try:
            if kind == 'package':
                package_count = count('package_count')
                required.update({'package.title': 1, 'package.card': 1, 'package.card-selected': int(package_count > 1), 'package.button': 1})
                if package_count == 1 and config.get('initial_selected_id') is not None:
                    errors.append(f'{mid}单套餐不得配置initial_selected_id或选中态')
                qr_requested = config.get('qr_background_enabled', True)
                if type(qr_requested) is not bool:
                    errors.append(f'{mid}.qr_background_enabled须为布尔值')
                qr_enabled = config.get('cashier_style') == 'qr_code' or qr_requested is True
                required['package.qr-background'] = int(qr_enabled)
                states = [[a for a in assets if isinstance(a, dict) and a.get('module_id') == mid and a.get('role') == role]
                          for role in ('package.card', 'package.card-selected')]
                if all(len(items) == 1 for items in states):
                    keys = ('width', 'height', 'display_width', 'display_height')
                    if tuple(states[0][0].get(k) for k in keys) != tuple(states[1][0].get(k) for k in keys):
                        errors.append(f'{mid}套餐默认态与选中态的设计及导出尺寸须完全一致')
            elif kind == 'task':
                n = count('task_count')
                required['task.title'] = 1
                if config['layout_profile'] == 'v1_single':
                    required['lottery.record'] = 1
                for role in ('task.row', 'task.button-available', 'task.button-claimed'):
                    if counts[role] not in (1, n):
                        errors.append(f'{mid}/{role}须共用1张或按{n}项任务各1张')
                    optional.add(role)
            elif kind == 'gift':
                n = count('gift_count')
                required.update({'gift.title': 1, 'gift.unclaimed': n, 'gift.claimed': n, 'gift.empty': n})
            elif kind == 'points':
                count('points_prize_count')
                required.update({'points.title': 1, 'points.card-background': 1, 'points.stock-badge': 1,
                                 'points.button-available': 1, 'points.button-sold-out': 1, 'points.button-exchanged': 1})
            elif kind == 'rule':
                required['rule.title'] = 1
            elif kind == 'banner':
                if counts['banner.title'] > 1:
                    errors.append(f'{mid}最多一个独立标题')
                optional.add('banner.title')
            elif kind == 'lottery':
                style = config.get('lottery_style')
                optional.add('lottery.probability')
                if counts['lottery.probability'] > 1:
                    errors.append(f'{mid}最多一张概率弹窗背景')
                if style == 'blind_box':
                    required.update({'blind.title': 1, 'blind.art': 1, 'blind.button': 1})
                    n = count('blind_prize_count', minimum=0)
                    names = config.get('blind_prizes')
                    if not isinstance(names, list) or len(names) != n or any(not isinstance(s, str) or not s.strip() for s in names):
                        errors.append(f'{mid}.blind_prizes须与奖品数量一致并保留完整名称')
                    required['blind.prize-card'] = int(n > 0)
                    if config.get('blind_backdrop_layer', 'background') != 'background' or counts['blind.backdrop']:
                        errors.append(f'{mid}底框须归背景，不单独导出blind.backdrop')
                    if type(config.get('blind_backdrop_enabled', False)) is not bool:
                        errors.append(f'{mid}.blind_backdrop_enabled须为布尔值')
                elif style == 'marquee':
                    n = count('lottery_slots')
                    if n not in (8, 10, 12):
                        errors.append(f'{mid}跑马灯仅支持8/10/12格')
                    required.update({'marquee.title': 1, 'marquee.prize': n, 'marquee.center': 1, 'marquee.highlight': 1})
                elif style == 'flip_card':
                    n = count('flip_card_count')
                    if n not in (2, 3, 4, 6, 8):
                        errors.append(f'{mid}当前翻牌已核对2/3/4/6/8张，不静默改牌数')
                    required.update({'flip.title': 1, 'flip.card-front': 1, 'flip.card-front-highlight': 1,
                                     'flip.card-back': 1, 'flip.card-back-highlight': 1,
                                     'flip.button': 1, 'flip.popup-background': 1})
                else:
                    errors.append(f'{mid}须选blind_box、marquee或flip_card')
            state_roles = (('flip.card-front', 'flip.card-front-highlight', 'flip.card-back', 'flip.card-back-highlight')
                           if kind == 'lottery' and config.get('lottery_style') == 'flip_card'
                           else ('points.button-available', 'points.button-sold-out', 'points.button-exchanged')
                           if kind == 'points' else ())
            state_items = [a for a in assets if isinstance(a, dict) and a.get('module_id') == mid and a.get('role') in state_roles]
            if len({tuple(a.get(k) for k in ('width', 'height', 'display_width', 'display_height')) for a in state_items}) > 1:
                errors.append(f'{mid}同组牌面或积分按钮状态须保持相同画布及显示尺寸')
            for role, n in required.items():
                if counts[role] != n:
                    errors.append(f'{mid}/{role}应为{n}张，实际{counts[role]}张')
            if set(counts) - set(required) - optional:
                errors.append(f'{mid}包含不属于本模块的素材角色：{sorted(set(counts)-set(required)-optional)}')
        except ValueError as exc:
            errors.append(str(exc))


def slice_plan(data):
    by_id = modules(data)
    master = data.get('background_master')
    if not isinstance(master, dict) or not isinstance(master.get('slices'), list):
        raise ValueError('须有background_master及二维slices清单')
    backgrounds = {a['file']: a for a in data.get('assets', []) if isinstance(a, dict) and a.get('role') in BG}
    result, seen, module_ids = [], set(), set()
    for part in master['slices']:
        if not isinstance(part, dict) or part.get('file') not in backgrounds or part.get('file') in seen:
            raise ValueError('每张模块背景须恰好有一项切片，不得漏项或重复')
        asset = backgrounds[part['file']]
        mid = part.get('module_id')
        if mid != asset.get('module_id') or mid not in by_id or mid in module_ids:
            raise ValueError('切片必须绑定唯一模块id，重复Banner按不同id区分')
        bounds = rect(part)
        if bounds != rect(by_id[mid]['design_rect']):
            raise ValueError('切片x/y/width/height须与模块design_rect一致，均为1x坐标')
        if scaled_size(asset) != (bounds[2] * 2, bounds[3] * 2):
            raise ValueError('背景PNG须为模块设计矩形的2倍尺寸')
        seen.add(part['file']); module_ids.add(mid)
        result.append((part, bounds))
    if seen != set(backgrounds) or module_ids != set(by_id):
        raise ValueError('二维切片须覆盖全部模块背景，不能仅导出1920宽模块或漏掉重复Banner')
    return result


def seam_keys(data):
    rows = data['layout']['rows']
    keys = {}
    for row in rows:
        members = row['modules']
        r = members[0]['design_rect']
        if r['y'] > 0:
            keys['before:' + row['id']] = ('horizontal', r['y'], 0, 1920)
        if len(members) == 2:
            keys['between:' + row['id']] = ('vertical', 960, r['y'], r['y'] + r['height'])
    return keys


def validate_background(root, data, errors, api):
    from PIL import Image, ImageChops
    try:
        plan = slice_plan(data)
        if data.get('background_mode') not in {'continuous', '整体衔接', 'segmented', '按模块区分'}:
            raise ValueError('background_mode须保留已确认的整体或分块模式')
        master = data['background_master']
        with Image.open(api.local_file(root, master['file'])) as source:
            api.validate_png_ppi(source, data)
            if source.size != (3840, data['layout']['design_height'] * 2):
                raise ValueError('母图须为3840×(design_height*2)，不能把双列模块高度累加')
            if source.convert('RGBA').getchannel('A').getextrema()[0] != 255:
                raise ValueError('背景母图须不透明')
            source = source.convert('RGB')
        for part, (x, y, width, height) in plan:
            with Image.open(api.local_file(root, part['file'])) as target:
                cropped = source.crop((x*2, y*2, (x+width)*2, (y+height)*2))
                if target.size != cropped.size or ImageChops.difference(target.convert('RGB'), cropped).getbbox():
                    errors.append(f'{part["file"]}未按母图二维坐标原像素导出')
        required = seam_keys(data)
        reviews = master.get('seam_reviews')
        if not isinstance(reviews, list):
            raise ValueError('须有seam_reviews覆盖行间横缝与双列中缝')
        seen = set()
        for item in reviews:
            if not isinstance(item, dict) or item.get('id') not in required or item.get('id') in seen:
                raise ValueError('每条接缝须以before:<row-id>或between:<row-id>唯一登记')
            seen.add(item['id'])
            axis, boundary, start, end = required[item['id']]
            if item.get('axis') != axis or item.get('status') != 'pass' or not isinstance(item.get('observation'), str) or not item['observation'].strip():
                raise ValueError('逐缝须记录对应axis、pass和实际观察，不能只验像素一致')
            x, y, width, height = rect(item.get('capture_rect'))
            if x+width > 1920 or y+height > data['layout']['design_height']:
                raise ValueError('接缝截图坐标超出设计页面')
            if axis == 'horizontal':
                ok = x == 0 and width == 1920 and y <= max(0, boundary-80) and y+height >= min(data['layout']['design_height'], boundary+80)
            else:
                ok = x <= boundary-80 and x+width >= boundary+80 and y <= start and y+height >= end
            if not ok:
                raise ValueError('接缝截图须覆盖整条边界和两侧至少80px上下文')
            with Image.open(api.local_file(root, item['file'])) as im:
                if im.size != (width, height):
                    raise ValueError('接缝浏览器截图须与1x capture_rect一致，不使用2x素材裁片冒充')
        if seen != set(required):
            raise ValueError('接缝证据未覆盖全部行间横缝或双列中缝')
    except (ValueError, OSError, TypeError, KeyError, AttributeError) as exc:
        errors.append(f'V2背景与接缝：{exc}')


def validate_geometry_evidence(root, data, errors, api):
    from PIL import Image
    try:
        by_id = modules(data)
        page = api.PageStructure()
        page.feed((root/'index.html').read_text(encoding='utf-8'))
        nodes = [n for n in page.nodes if n['attrs'].get('data-module')]
        if Counter(n['attrs'].get('data-module-id') for n in nodes) != Counter(by_id.keys()):
            raise ValueError('HTML须按稳定id恰好呈现每个后台模块，重复Banner不能共用id')
        for node in nodes:
            if node['attrs']['data-module'] != by_id[node['attrs']['data-module-id']]['type']:
                raise ValueError('HTML模块类型与后台布局不一致')
        report = data.get('layout_review')
        if not isinstance(report, dict) or report.get('status') != 'pass' or report.get('design_width') != 1920:
            raise ValueError('须有layout_review记录1920基准的真实浏览器测量')
        measured = report.get('modules')
        if not isinstance(measured, list) or Counter(m.get('id') for m in measured if isinstance(m, dict)) != Counter(by_id.keys()):
            raise ValueError('layout_review.modules须逐模块记录id及实测design_rect')
        for item in measured:
            if rect(item.get('design_rect')) != rect(by_id[item['id']]['design_rect']):
                raise ValueError('浏览器实测模块位置与后台布局快照不一致')
        with Image.open(api.local_file(root, report['file'])) as image:
            if image.size != (1920, data['layout']['design_height']):
                raise ValueError('layout_review截图须为完整1920基准整页')
        reviews = report.get('responsive_reviews')
        if not isinstance(reviews, list) or not reviews:
            raise ValueError('须记录小于和大于1920两档响应预览')
        widths = [item.get('viewport_width') for item in reviews if isinstance(item, dict) and integer(item.get('viewport_width'))]
        if not any(w < 1920 for w in widths) or not any(w > 1920 for w in widths):
            raise ValueError('响应预览须至少有一档小于1920及一档大于1920的实际视口')
        for item in reviews:
            if (not isinstance(item, dict) or not integer(item.get('viewport_width')) or item['viewport_width'] == 1920
                    or item.get('columns_preserved') is not True or item.get('status') != 'pass'
                    or not isinstance(item.get('scaling_method'), str) or not item['scaling_method'].strip()
                    or not isinstance(item.get('observation'), str) or not item['observation'].strip()
                    or type(item.get('backend_behavior_verified')) is not bool):
                raise ValueError('响应证据须记录视口、实际缩放方式、列数保留、观察及后台行为是否验证')
            scale = item.get('scale')
            if (not isinstance(scale, (int, float)) or isinstance(scale, bool) or not math.isfinite(scale)
                    or abs(scale - responsive_scale(item['viewport_width'], data.get('backend_profile'))) > 0.001):
                raise ValueError('响应scale须符合已记录适配规则；示例预设计算范围1200至3840，其余明确等比预览使用视口宽/1920')
            with Image.open(api.local_file(root, item['file'])) as image:
                if image.width != item['viewport_width']:
                    raise ValueError('响应截图宽度与实际viewport_width不一致')
    except (ValueError, OSError, TypeError, KeyError, AttributeError) as exc:
        errors.append(f'V2布局证据：{exc}')


def validate_preview(root, data, errors):
    from PIL import Image
    try:
        with Image.open(root.with_name(root.name+'-preview.png')) as image:
            if image.format != 'PNG' or image.size != (1920, data['layout']['design_height']):
                raise ValueError('最终完整预览须为1920×design_height；2x只用于素材，不把双列高度相加')
    except (ValueError, OSError, TypeError, KeyError) as exc:
        errors.append(f'V2整页预览：{exc}')


def validate_package_card_states(root, data, errors, api):
    from PIL import Image, ImageChops
    for mid, member in modules(data).items():
        if member['type'] != 'package':
            continue
        states = [[a for a in data.get('assets', []) if isinstance(a, dict) and a.get('module_id') == mid and a.get('role') == role]
                  for role in ('package.card', 'package.card-selected')]
        if not all(len(items) == 1 for items in states):
            continue  # Missing/duplicate states are reported by validate_counts.
        try:
            with Image.open(api.local_file(root, states[0][0]['file'])) as first, Image.open(api.local_file(root, states[1][0]['file'])) as second:
                if first.size != second.size:
                    errors.append(f'{mid}套餐两态PNG画布须一致')
                elif all(bounds == (0, 0) for bounds in ImageChops.difference(first.convert('RGBA'), second.convert('RGBA')).getextrema()):
                    errors.append(f'{mid}套餐默认态和选中态像素完全相同；须有可辨认的状态设计')
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append(f'{mid}套餐双态检查失败：{exc}')
