import unittest
import tempfile
from pathlib import Path
from PIL import Image
import layout_contract as lc
import validate_output as validator
from test_v2_contract import fixture

def package_fixture():
    data=fixture();mid='banner-2'
    data['layout']['rows'][2]['modules'][0]['type']='package'
    data['module_configs'][mid]['package_count']=2
    data['module_configs'][mid]['qr_background_enabled']=False  # Fixture explicitly excludes the cashier panel.
    data['assets']=[a for a in data['assets'] if a['module_id']!=mid]
    for role in ('package.background','package.title','package.card','package.card-selected','package.button'):
        data['assets'].append(dict(module_id=mid,role=role,file=role+'.png',width=400,height=560,display_width=200,display_height=280))
    return data

class PackageStateTests(unittest.TestCase):
    def test_single_package_only_ordinary_with_qr(self):
        data=package_fixture()
        config=data['module_configs']['banner-2']
        config.update(package_count=1, qr_background_enabled=True)
        data['assets']=[a for a in data['assets'] if a['role']!='package.card-selected']
        qr=dict(next(a for a in data['assets'] if a['role']=='package.card'))
        qr.update(role='package.qr-background', file='qr.png')
        data['assets'].append(qr)
        errors=[];lc.validate_counts(data,errors);self.assertEqual(errors,[])
        config['initial_selected_id']='p1'
        errors=[];lc.validate_counts(data,errors);self.assertTrue(any('initial_selected_id' in e for e in errors))

    def test_single_package_selected_asset_rejected(self):
        data=package_fixture();data['module_configs']['banner-2']['package_count']=1
        errors=[];lc.validate_counts(data,errors)
        self.assertTrue(any('package.card-selected' in e for e in errors))

    def test_three_packages_still_require_both_states(self):
        data=package_fixture();data['module_configs']['banner-2']['package_count']=3
        errors=[];lc.validate_counts(data,errors);self.assertEqual(errors,[])
        data['assets']=[a for a in data['assets'] if a['role']!='package.card-selected']
        errors=[];lc.validate_counts(data,errors);self.assertTrue(errors)

    def test_both_states_required_and_same_dimensions(self):
        data=package_fixture();errors=[];lc.validate_counts(data,errors);self.assertEqual(errors,[])
        selected=next(a for a in data['assets'] if a['role']=='package.card-selected')
        selected['width']=402
        errors=[];lc.validate_counts(data,errors);self.assertTrue(errors)
        data['assets'].remove(selected)
        errors=[];lc.validate_counts(data,errors);self.assertTrue(any('package.card-selected' in e for e in errors))

    def test_identical_pixels_even_with_different_metadata_are_rejected(self):
        data=package_fixture()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for role in ('package.card','package.card-selected'):
                Image.new('RGBA',(4,4),(10,20,30,255)).save(root/(role+'.png'))
            errors=[];lc.validate_package_card_states(root,data,errors,validator);self.assertTrue(errors)
            Image.new('RGBA',(4,4),(200,90,10,255)).save(root/'package.card-selected.png')
            errors=[];lc.validate_package_card_states(root,data,errors,validator);self.assertEqual(errors,[])

if __name__=='__main__': unittest.main()
