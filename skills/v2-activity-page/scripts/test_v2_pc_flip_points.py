"""PC-only static asset branches; no real drawing or redemption requests."""
from pathlib import Path
import tempfile
import unittest
import layout_contract as lc
import validate_output as validator
from test_v2_contract import fixture


FLIP_ROLES = ('flip.title', 'flip.card-front', 'flip.card-front-highlight',
              'flip.card-back', 'flip.card-back-highlight', 'flip.button', 'flip.popup-background')
POINTS_ROLES = ('points.title', 'points.card-background', 'points.stock-badge',
                'points.button-available', 'points.button-sold-out', 'points.button-exchanged')


def add_module(data, mid, kind, count):
    member = lc.modules(data)[mid]
    member['type'] = kind
    config = data['module_configs'][mid]
    if kind == 'lottery':
        config.update(lottery_style='flip_card', flip_card_count=count)
        roles = FLIP_ROLES
        bg = 'flip.background'
    else:
        config.update(points_prize_count=count)
        roles = POINTS_ROLES
        bg = 'points.background'
    original = next(a for a in data['assets'] if a['module_id'] == mid)
    data['assets'] = [a for a in data['assets'] if a['module_id'] != mid]
    data['assets'].append(dict(original, role=bg))
    for role in roles:
        size = (160, 220) if role.startswith('flip.card-') else (128, 30)
        item = dict(module_id=mid, role=role, file=f'assets/{mid}-{role}.png',
                    width=size[0]*2, height=size[1]*2, display_width=size[0], display_height=size[1])
        if role.endswith('.title'):
            item.update(file=f'assets/titles/{mid}.png', text='测试标题', title_style='synthetic-pc')
        data['assets'].append(item)
    return data


def new_fixture(kind='lottery', count=6):
    return add_module(fixture(), 'banner-2', kind, count)


class PcFlipPointsTests(unittest.TestCase):
    def test_all_five_pc_card_counts_need_only_shared_state_templates(self):
        for n in (2, 3, 4, 6, 8):
            data = new_fixture(count=n)
            errors = []
            lc.validate_counts(data, errors)
            self.assertEqual(errors, [], n)
            self.assertEqual(len([a for a in data['assets'] if a['role'] == 'flip.card-back']), 1)
            self.assertEqual(len(lc.slice_plan(data)), 4)

    def test_unsupported_card_count_or_missing_state_is_rejected(self):
        data = new_fixture(count=7)
        errors = []
        lc.validate_counts(data, errors)
        self.assertTrue(any('2/3/4/6/8' in e for e in errors))
        data = new_fixture()
        data['assets'] = [a for a in data['assets'] if a['role'] != 'flip.card-back-highlight']
        errors = []
        lc.validate_counts(data, errors)
        self.assertTrue(any('flip.card-back-highlight' in e for e in errors))

    def test_card_face_canvas_cannot_jump_between_states(self):
        data = new_fixture()
        next(a for a in data['assets'] if a['role'] == 'flip.card-front-highlight')['width'] = 322
        errors = []
        lc.validate_counts(data, errors)
        self.assertTrue(any('相同画布' in e for e in errors))

    def test_points_has_no_invented_fifteen_item_backend_cap(self):
        for n in (1, 6, 15, 16):
            data = new_fixture('points', n)
            errors = []
            lc.validate_counts(data, errors)
            self.assertEqual(errors, [], n)
        data = new_fixture('points', 0)
        errors = []
        lc.validate_counts(data, errors)
        self.assertTrue(errors)

    def test_points_all_three_states_are_required_and_same_size(self):
        data = new_fixture('points')
        next(a for a in data['assets'] if a['role'] == 'points.button-exchanged')['height'] = 62
        errors = []
        lc.validate_counts(data, errors)
        self.assertTrue(any('相同画布' in e for e in errors))
        data = new_fixture('points')
        data['assets'] = [a for a in data['assets'] if a['role'] != 'points.button-sold-out']
        errors = []
        lc.validate_counts(data, errors)
        self.assertTrue(any('points.button-sold-out' in e for e in errors))

    def test_points_and_lottery_coexist_without_sharing_counters(self):
        data = new_fixture('lottery', 4)
        add_module(data, 'banner-3', 'points', 11)
        errors = []
        lc.validate_counts(data, errors)
        self.assertEqual(errors, [])
        self.assertEqual(lc.scoped(data, 'banner-2')['points_prize_count'], 0)
        self.assertEqual(lc.scoped(data, 'banner-3')['lottery_style'], None)
        self.assertEqual(len(lc.slice_plan(data)), 4)

    def test_figma_planning_sizes_are_not_claimed_as_live_measurements(self):
        data = new_fixture()
        item = next(a for a in data['assets'] if a['role'] == 'flip.card-front')
        spec = dict(display_width=160, display_height=220, source='Synthetic Figma reference',
                    measured_viewport_width=1920, applies_to_profile='v2_half', source_kind='figma_pc_reference')
        data['module_configs']['banner-2']['asset_sizes'] = {'flip.card-front': spec}
        with self.assertRaisesRegex(ValueError, '纯Figma'):
            validator.expected_size(item['role'], item, data)
        spec.update(source_kind='user_confirmed', source='Synthetic explicit size approval for regression only')
        self.assertEqual(validator.expected_size(item['role'], item, data), (320, 440))
        item['width'] = 160
        with self.assertRaises(ValueError):
            validator.expected_size(item['role'], item, data)

    def test_new_titles_render_in_the_correct_module(self):
        for kind, role, module in [('lottery', 'flip.title', 'lottery'), ('points', 'points.title', 'points')]:
            data = new_fixture(kind)
            scoped = lc.scoped(data, 'banner-2')
            title = next(a for a in data['assets'] if a['role'] == role)
            html = (f'<section data-module="{module}" data-module-id="banner-2">'
                    f'<img data-role="module-title" data-title-role="{role}" src="{title["file"]}" '
                    f'alt="{title["text"]}" width="128" height="30"></section>')
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / 'index.html').write_text(html, encoding='utf-8')
                errors = []
                validator.validate_module_titles(root, scoped, errors)
                self.assertEqual(errors, [], kind)


if __name__ == '__main__':
    unittest.main()
