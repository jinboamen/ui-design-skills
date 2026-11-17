import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import layout_contract as lc
import validate_output as validator
from test_v2_package_states import package_fixture

ROLE = 'package.qr-background'


def add_qr(data):
    config = data['module_configs']['banner-2']
    config.setdefault('asset_sizes', {})[ROLE] = dict(
        display_width=200, display_height=280, measured_viewport_width=1920,
        applies_to_profile='v2_half', source='Synthetic CSS-derived measurement fixture')
    item = dict(module_id='banner-2', role=ROLE, file='qr-background.png',
                width=400, height=560, display_width=200, display_height=280)
    data['assets'].append(item)
    return item


class QrBackgroundTests(unittest.TestCase):
    def test_package_requires_qr_background_by_default(self):
        data = package_fixture()
        data['module_configs']['banner-2'].pop('qr_background_enabled')
        errors = []
        lc.validate_counts(data, errors)
        self.assertTrue(any(ROLE in e for e in errors))
        add_qr(data)
        errors = []
        lc.validate_counts(data, errors)
        self.assertEqual(errors, [])

    def test_explicit_no_qr_keeps_it_optional(self):
        data = package_fixture()
        data['module_configs']['banner-2']['qr_background_enabled'] = False
        errors = []
        lc.validate_counts(data, errors)
        self.assertEqual(errors, [])

    def test_inline_qr_requires_one_separate_background(self):
        data = package_fixture()
        data['module_configs']['banner-2']['cashier_style'] = 'qr_code'
        errors = []
        lc.validate_counts(data, errors)
        self.assertTrue(any(ROLE in e for e in errors))
        add_qr(data)
        errors = []
        lc.validate_counts(data, errors)
        self.assertEqual(errors, [])
        self.assertEqual(data['module_configs']['banner-2']['package_count'], 2)

    def test_explicit_user_request_also_requires_background(self):
        data = package_fixture()
        data['module_configs']['banner-2']['qr_background_enabled'] = True
        errors = []
        lc.validate_counts(data, errors)
        self.assertTrue(any(ROLE in e for e in errors))
        add_qr(data)
        errors = []
        lc.validate_counts(data, errors)
        self.assertEqual(errors, [])

    def test_without_qr_no_extra_background_and_switch_must_be_boolean(self):
        data = package_fixture()
        errors = []
        lc.validate_counts(data, errors)
        self.assertEqual(errors, [])
        add_qr(data)
        errors = []
        lc.validate_counts(data, errors)
        self.assertTrue(any(ROLE in e for e in errors))
        data['module_configs']['banner-2']['qr_background_enabled'] = 'false'
        errors = []
        lc.validate_counts(data, errors)
        self.assertTrue(any('qr_background_enabled' in e for e in errors))

    def test_qr_background_needs_own_size_source_and_two_x_pixels(self):
        data = package_fixture()
        item = add_qr(data)
        self.assertEqual(validator.expected_size(ROLE, item, data), (400, 560))
        item['width'] = 200
        with self.assertRaises(ValueError):
            validator.expected_size(ROLE, item, data)
        item['width'] = 400
        data['module_configs']['banner-2']['asset_sizes'].clear()
        with self.assertRaises(ValueError):
            validator.expected_size(ROLE, item, data)

    def test_plain_opaque_png_is_valid_without_forcing_transparent_foreground(self):
        data = package_fixture()
        item = add_qr(data)
        data['assets'] = [item]
        with tempfile.TemporaryDirectory() as tmp, patch.object(lc, 'validate_counts'):
            root = Path(tmp)
            Image.new('RGB', (400, 560), 'white').save(root / item['file'], dpi=(72, 72))
            errors = []
            validator.validate_assets(root, data, errors)
            self.assertEqual(errors, [])
            Image.new('RGBA', (400, 560), (255, 255, 255, 0)).save(root / item['file'], dpi=(72, 72))
            errors = []
            validator.validate_assets(root, data, errors)
            self.assertTrue(any('不透明' in e for e in errors))


if __name__ == '__main__':
    unittest.main()
