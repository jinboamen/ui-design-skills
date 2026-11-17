"""Validate 1x design proposals followed by one genuinely separate 2x work set.

Only the final set is checked for delivery. Candidate manifests, cut-up backgrounds
and pixel equality between proposals and final art are deliberately not required.
"""
from collections import Counter
import hashlib
import json
from PIL import Image
import layout_contract as layout

MODE = 'draft-preview-selected-hd-v2'


def validate(root, data, evidence, picture, lineage, by_file):
    if data.get('production_workflow') != MODE or evidence.get('production_workflow') != MODE:
        raise ValueError('assets与设计证据须使用同一快速样张流程')
    selection = evidence['design_selection']
    selected_proposal = next(p for p in selection['proposals']
                             if p['id'] == selection['selected_id'])
    # A user selection or a canvas-size check must not erase a known visual failure.
    if selected_proposal.get('status') in {'revise', 'needs_repair', 'awaiting_revision', 'failed', 'rejected'}:
        raise ValueError('所选样张已标记需要修复，不能凭整页尺寸或用户选择直接进入正式交付')
    size = (1920, data['layout']['design_height'])
    chosen = next(picture(p['file']) for p in selection['proposals']
                  if p['id'] == selection['selected_id'])
    proposals = {picture(p['file']) for p in selection['proposals']}
    unselected = proposals - {chosen}
    for preview in proposals:
        with Image.open(preview) as image:
            if image.size != size:
                raise ValueError('快速样张须为1920px宽、按已确认行高累计的完整1倍设计预览')
        rec = by_file.get(preview)
        if rec is None or rec[0] not in {'generated', 'derived'}:
            raise ValueError('样张须保留实际生成或组合来源，不能仅登记为用户提供')

    final = evidence.get('selected_working_set')
    if not isinstance(final, dict) or final.get('selected_id') != selection['selected_id']:
        raise ValueError('只为选中方案制作一套正式高清工作集')
    manifest = layout_path(root, final.get('file'))
    if final.get('manifest_sha256', '').lower() != digest(manifest):
        raise ValueError('最终工作清单缺少冻结哈希或已变化')
    work = json.loads(manifest.read_text(encoding='utf-8'))
    if (work.get('layout') != data['layout'] or work.get('export_scale') != 2
            or (work.get('page_width'), work.get('page_height')) != size):
        raise ValueError('正式工作集须保持已确认布局，并按2倍规格制作')

    def frozen(item):
        if not isinstance(item, dict):
            raise ValueError('工作源记录须为对象')
        path = picture(item.get('file'))
        if item.get('sha256', '').lower() != digest(path):
            raise ValueError('最终工作源缺少冻结哈希或已变化')
        return path

    master = frozen(work.get('background_master'))
    with Image.open(master) as image:
        if image.size != (size[0] * 2, size[1] * 2):
            raise ValueError('正式背景母图须为3840px宽及2倍设计高度')
    reached = lineage(master, set())
    if chosen not in reached or reached & unselected:
        raise ValueError('正式背景须依据选中样张高清制作，不能混入未选方案')

    background_roles = {'hero', 'banner'} | {r for r in
        (a.get('role') for a in data['assets']) if isinstance(r, str) and r.endswith('.background')}
    members = {}
    for field, label in (('assets', 'role'), ('decorations', 'name')):
        items = work.get(field)
        if not isinstance(items, list) or (field == 'assets' and not items):
            raise ValueError('正式工作清单须列全assets和decorations')
        for item in items:
            path = frozen(item)
            if (path in members or not isinstance(item.get(label), str)
                    or not item[label].strip() or type(item.get('used_in_preview', True)) is not bool):
                raise ValueError('工作源重复、角色缺失或used_in_preview不是布尔值')
            reached = lineage(path, set())
            if reached & unselected or chosen not in reached:
                raise ValueError('正式素材须依据选中方案，不能只凭KV重新设计或混入未选方案')
            if field == 'assets' and item['role'] in background_roles and master not in reached:
                raise ValueError('正式背景切片须来自最终2倍共同母图')
            members[path] = (field, item)
    expected_backgrounds = Counter(
        (mid, layout.background_role(member, data['module_configs'][mid]))
        for mid, member in layout.modules(data).items())
    actual_backgrounds = Counter((item.get('module_id'), item['role'])
        for field, item in members.values() if field == 'assets' and item['role'] in background_roles)
    if actual_backgrounds != expected_backgrounds:
        raise ValueError('最终工作集须包含每个实际后台模块的背景一次')

    preview = picture(final.get('preview'))
    if preview in proposals:
        raise ValueError('正式验收截图不能复用候选样张')
    with Image.open(preview) as image:
        if image.size != size:
            raise ValueError('正式完整预览须保持1920px基准及实际页面高度')
    rec = by_file.get(preview)
    renderer = next((r.get('renderer') for r in evidence['records']
                     if r.get('file') == final.get('preview')), None)
    needed = {path for path, (_, item) in members.items() if item.get('used_in_preview', True)}
    if not rec or rec[0] != 'derived' or renderer != 'browser' or not needed.issubset(set(rec[1])):
        raise ValueError('正式预览须在浏览器实际恢复正式工作素材并记录直接输入')

    inherited = evidence.get('design_inheritance')
    if (not isinstance(inherited, dict) or inherited.get('status') != 'pass'
            or picture(inherited.get('source')) != chosen or picture(inherited.get('result')) != preview
            or not isinstance(inherited.get('observation'), str) or not inherited['observation'].strip()
            or not isinstance(inherited.get('adjustments'), list)
            or any(not isinstance(x, str) or not x.strip() for x in inherited['adjustments'])):
        raise ValueError('须记录选中样张与高清成品的实际设计继承对照及细节调整')
    picture(inherited.get('comparison'))
    foregrounds = {path: item['role'] for path, (field, item) in members.items()
                   if field == 'assets' and item['role'] not in background_roles}
    validate_foreground_refinement(inherited, foregrounds, picture, chosen, preview)

    seen = set()
    def match(item, field, label, path):
        source = picture(item.get('working_source'))
        expected = members.get(source)
        if (not expected or expected[0] != field or expected[1].get(label) != item.get(label)
                or (field == 'assets' and expected[1].get('module_id') != item.get('module_id'))):
            raise ValueError('交付working_source不属于所选正式工作集或角色不符')
        if digest(path) != expected[1]['sha256'].lower() or source not in lineage(path, set()):
            raise ValueError('交付文件须直接复制已验收的正式工作源，并保留来源链')
        seen.add(source)
    for item in data['assets']:
        match(item, 'assets', 'role', picture(item.get('file')))
    final_master = data.get('background_master', {})
    if (picture(final_master.get('working_source')) != master
            or picture(final_master.get('file')).read_bytes() != master.read_bytes()):
        raise ValueError('交付母图须直接复制正式2倍工作母图')
    if data.get('decorations_enabled', True):
        decor_manifest = layout_path(root, data['decoration_manifest'])
        decor = json.loads(decor_manifest.read_text(encoding='utf-8'))
        for item in decor['assets']:
            path = layout_path(decor_manifest.parent, item['file'])
            if not path.is_relative_to(root.resolve()):
                raise ValueError('装饰路径超出页面目录')
            match(item, 'decorations', 'name', path)
    if seen != set(members):
        raise ValueError('正式工作素材尚未完整交付')
    return set(members) | {master}



def validate_foreground_refinement(inherited, targets, picture, chosen, preview):
    """Check evidence coverage, not visual quality; humans must inspect the comparison."""
    if not targets:
        return
    entries = inherited.get('foreground_refinement')
    if not isinstance(entries, list) or not entries:
        raise ValueError('正式前景缺少精修对照记录，不能只凭高清导出交付')
    seen = set()
    refined = False
    for entry in entries:
        if not isinstance(entry, dict) or entry.get('status') != 'pass':
            raise ValueError('前景精修尚未通过实际对照')
        files = entry.get('targets')
        if not isinstance(files, list) or not files:
            raise ValueError('精修记录须绑定正式前景工作源')
        for name in files:
            path = picture(name)
            if path not in targets or path in seen:
                raise ValueError('精修对象不属于前景工作集或重复登记')
            seen.add(path)
        if picture(entry.get('before')) != chosen or picture(entry.get('after')) != preview:
            raise ValueError('精修前后须绑定本次所选样张及实际正式预览')
        comparison = picture(entry.get('comparison'))
        if comparison in {chosen, preview}:
            raise ValueError('精修对照须展示同尺度前后，不得直接拿单张预览冒充')
        decision = entry.get('decision')
        if decision == 'refined':
            changes = entry.get('changes')
            if (not isinstance(changes, list) or not changes
                    or any(not isinstance(x, str) or not x.strip() for x in changes)
                    or not isinstance(entry.get('visible_result'), str)
                    or not entry['visible_result'].strip()):
                raise ValueError('精修须说明具体改进及正常显示尺寸下的可见结果')
            refined = True
        elif decision == 'retained':
            if not isinstance(entry.get('reason'), str) or not entry['reason'].strip():
                raise ValueError('保留简洁组件须说明实际完成度与保留理由')
        else:
            raise ValueError('精修记录须明确refined或retained')
    if seen != set(targets):
        raise ValueError('正式前景精修记录未覆盖实际工作源')
    if not refined and any(role != 'package.qr-background' for role in targets.values()):
        raise ValueError('不能将全部前景标记为无需精修后宣称已完成精细优化')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def layout_path(root, name):
    if not isinstance(name, str) or not name.strip():
        raise ValueError('清单路径须为非空相对路径')
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('清单路径超出页面目录')
    return path
