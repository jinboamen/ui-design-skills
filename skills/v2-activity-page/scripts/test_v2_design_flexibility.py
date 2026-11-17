"""Behavioral regressions for optional panels and independent title hierarchy."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import layout_contract as lc
import validate_output as validator
from test_v2_contract import fixture


def blind_fixture():
    data = fixture()
    mid = 'banner-1'
    data['layout']['rows'][1]['modules'][0]['type'] = 'lottery'
    data['module_configs'][mid].update(
        lottery_style='blind_box', blind_prize_count=0, blind_prizes=[])
    for asset in data['assets']:
        if asset['module_id'] == mid:
            asset['role'] = 'blind.background'
    for role in ('blind.title', 'blind.art', 'blind.button'):
        data['assets'].append({'module_id': mid, 'role': role})
    return data


class DesignFlexibilityTests(unittest.TestCase):
    def test_open_layout_without_panel_needs_no_user_cancellation(self):
        for explicit in (False, None):
            data = blind_fixture()
            if explicit is not None:
                data['module_configs']['banner-1']['blind_backdrop_enabled'] = explicit
            errors = []
            lc.validate_counts(data, errors)
            self.assertEqual(errors, [])
            with tempfile.TemporaryDirectory() as tmp:
                # A missing layout report is legitimate when no panel is used.
                module_data = dict(data['module_configs']['banner-1'])
                validator.validate_blind_layout(Path(tmp), module_data, errors)
            self.assertEqual(errors, [])

    def test_enabled_panel_still_requires_layout_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            errors = []
            validator.validate_blind_layout(Path(tmp), {
                'lottery_style': 'blind_box', 'blind_backdrop_enabled': True}, errors)
            self.assertTrue(any('layout-check' in e for e in errors))

    def test_panel_switch_rejects_string_false(self):
        data = blind_fixture()
        data['module_configs']['banner-1']['blind_backdrop_enabled'] = 'false'
        errors = []
        lc.validate_counts(data, errors)
        self.assertTrue(any('blind_backdrop_enabled' in e for e in errors))

    def test_titles_can_use_distinct_hierarchies_and_canvases(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = {'package_count': 1, 'task_count': 1, 'assets': [
                {'role': 'package.title', 'file': 'assets/titles/package.png',
                 'width': 960, 'height': 160, 'display_width': 480, 'display_height': 80,
                 'text': '套餐购买', 'title_style': 'activity-primary'},
                {'role': 'task.title', 'file': 'assets/titles/task.png',
                 'width': 720, 'height': 120, 'display_width': 360, 'display_height': 60,
                 'text': '获取抽奖机会', 'title_style': 'activity-secondary'}]}
            html = ''.join(
                f'<section data-module="{a["role"].split(".")[0]}">'
                f'<img data-role="module-title" data-title-role="{a["role"]}" '
                f'src="{a["file"]}" alt="{a["text"]}" '
                f'width="{a["display_width"]}" height="{a["display_height"]}"></section>'
                for a in data['assets'])
            (root / 'index.html').write_text(html, encoding='utf-8')
            # Pixel-size provenance has separate tests; isolate title usage here.
            with patch.object(validator, 'expected_size',
                              side_effect=lambda role, item, data: (item['width'], item['height'])):
                errors = []
                validator.validate_module_titles(root, data, errors)
                self.assertEqual(errors, [])
                data['assets'][1]['height'] = 100
                validator.validate_module_titles(root, data, errors)
                self.assertTrue(any('不能拉伸字形' in e for e in errors))


if __name__ == '__main__':
    unittest.main()
