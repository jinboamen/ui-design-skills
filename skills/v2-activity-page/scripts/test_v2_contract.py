"""Focused regression checks for V2 mixed rows, module scope and 2x exports.

Uses only tiny synthetic, temporary images; does not generate activity assets or
access Figma, production pages, user images, or a backend.
"""
from __future__ import annotations
import copy
import json
import hashlib
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from PIL import Image
import layout_contract as lc
import validate_output as validator
from export_background_slices import export_slices


def fixture():
    rows = [
        {'id': 'r-hero', 'modules': [{'id':'kv', 'type':'hero', 'design_rect':dict(x=0,y=0,width=1920,height=10)}]},
        {'id': 'r-banner-1', 'modules': [{'id':'banner-1', 'type':'banner','design_rect':dict(x=0,y=10,width=1920,height=8)}]},
        {'id': 'r-pair', 'modules': [
            {'id':'banner-2','type':'banner','design_rect':dict(x=0,y=18,width=960,height=12)},
            {'id':'banner-3','type':'banner','design_rect':dict(x=960,y=18,width=960,height=12)}]},
    ]
    data={'export_scale':2, 'export_ppi':72, 'background_mode':'segmented',
          'layout':dict(source='backend',design_width=1920,design_height=30,rows=rows),
          'module_configs':{},'assets':[], 'rule_floating_enabled':False,
          'background_master':{'file':'design/master.png','slices':[]}}
    for row in rows:
        for member in row['modules']:
            mid=member['id']; r=member['design_rect']
            data['module_configs'][mid]={'layout_profile':'v1_single' if len(row['modules'])==1 else 'v2_half'}
            filename='assets/'+mid+'.png'
            data['assets'].append(dict(module_id=mid,role=member['type'],file=filename,
                                       width=r['width']*2,height=r['height']*2,
                                       display_width=r['width'],display_height=r['height']))
            data['background_master']['slices'].append(dict(module_id=mid,file=filename,**r))
    return data


def materialize(root,data):
    (root/'design').mkdir()
    image=Image.new('RGB',(3840,data['layout']['design_height']*2))
    for y in range(image.height):
        for x in range(image.width):
            image.putpixel((x,y),((x//12)%256,y%256,180 if x<1920 else 60))
    image.save(root/'design/master.png',dpi=(72,72))
    (root/'assets.json').write_text(json.dumps(data),encoding='utf-8')
    return image


def complete_fixture(root, data=None):
    """Synthetic metadata fixture only; never an asserted real design or user approval."""
    data=fixture() if data is None else data
    materialize(root,data);export_slices(root)
    mode='background-final-foreground-concept-v1'
    data.update(production_workflow=mode,decorations_enabled=False,
                decorations_omit_reason='Synthetic test has no production decorations',design_evidence='design/evidence.json')
    records=[]
    def img(name,size=(32,32),color='white'):
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True)
        Image.new('RGB',size,color).save(path,dpi=(72,72));return name
    def digest(name):return hashlib.sha256((root/name).read_bytes()).hexdigest()
    def record(name,kind,inputs,**extra):
        records.append(dict(file=name,kind=kind,input_images=inputs,**extra))
    def write(name,value):
        (root/name).write_text(json.dumps(value),encoding='utf-8')
    kv=img('design/test-kv.png');reference=img('design/test-reference.png',color='gray')
    proposals=[];works={}
    for letter in 'ABC':
        prefix='design/'+letter+'/'
        master=prefix+'master.png';(root/master).parent.mkdir(parents=True)
        (root/master).write_bytes((root/'design/master.png').read_bytes())
        record(master,'generated',[kv,reference],source='synthetic-unit-test')
        backgrounds=[]
        for asset in data['assets']:
            filename=prefix+asset['module_id']+'.png'
            (root/filename).write_bytes((root/asset['file']).read_bytes())
            record(filename,'derived',[master])
            backgrounds.append(dict(role=asset['role'],module_id=asset['module_id'],file=filename,sha256=digest(filename)))
        concept=img(prefix+'concept.png');record(concept,'generated',[kv,reference],source='synthetic-unit-test')
        preview=img(prefix+'preview.png',(1920,30));record(preview,'derived',[a['file'] for a in backgrounds]+[concept],renderer='browser')
        work=dict(layout=data['layout'],export_scale=2,page_width=1920,page_height=30,
                  background_master=dict(file=master,sha256=digest(master)),assets=backgrounds,
                  concept_images=[dict(file=concept,sha256=digest(concept))])
        manifest=prefix+'working.json';write(manifest,work);works[letter]=work
        proposals.append(dict(id=letter,file=preview,background_set=manifest,design_summary='Synthetic case '+letter))
    final_work=copy.deepcopy(works['A']);final_work['decorations']=[]
    write('design/selected.json',final_work)
    final_preview=img('design/final-preview.png',(1920,30))
    record(final_preview,'derived',[a['file'] for a in final_work['assets']],renderer='browser')
    for asset,working in zip(data['assets'],final_work['assets']):
        asset['working_source']=working['file'];record(asset['file'],'derived',[working['file']])
    data['background_master']['working_source']=final_work['background_master']['file']
    record('design/master.png','derived',[final_work['background_master']['file']])
    checks={key:dict(status='pass',observation='Synthetic structural test only',evidence=final_preview) for key in validator.VISUAL_REVIEW_CRITERIA}
    evidence=dict(production_workflow=mode,kv_images=[kv],references=[dict(url='https://example.invalid/test',file=reference,use='Synthetic fixture only')],records=records,
                  design_selection=dict(status='approved',round=1,selected_id='A',proposals=proposals,
                    approval=dict(user_reply='Synthetic fixture, not real approval',sample_sha256=digest(proposals[0]['file']),background_set_sha256=digest(proposals[0]['background_set']))),
                  selected_working_set=dict(selected_id='A',file='design/selected.json',manifest_sha256=digest('design/selected.json'),preview=final_preview),
                  background_inheritance=dict(status='pass',source=final_work['background_master']['file'],result=final_work['background_master']['file'],comparison=final_preview,observation='Synthetic equality check',local_changes=[]),
                  review=dict(notes='Synthetic metadata only',composition=final_preview,comparison=final_preview,
                    visual_review=dict(stage='final-render',page=final_preview,component_comparison=final_preview,background_comparison=final_preview,checks=checks,remaining_issues=[],status='pass')))
    write('design/evidence.json',evidence)
    data['background_master']['seam_reviews']=[]
    for key,(axis,boundary,start,end) in lc.seam_keys(data).items():
        capture=dict(x=0,y=0,width=1920,height=30) if axis=='horizontal' else dict(x=880,y=start,width=160,height=end-start)
        screenshot=img('design/'+key.replace(':','-')+'.png',(capture['width'],capture['height']))
        data['background_master']['seam_reviews'].append(dict(id=key,axis=axis,capture_rect=capture,file=screenshot,status='pass',observation='Synthetic bounds check'))
    responsive=img('design/responsive.png',(1440,23))
    large_responsive=img('design/responsive-large.png',(2560,40))
    data['layout_review']=dict(status='pass',design_width=1920,file=final_preview,modules=[dict(id=m['id'],design_rect=m['design_rect']) for m in lc.modules(data).values()],
        responsive_reviews=[dict(viewport_width=1440,scale=0.75,file=responsive,columns_preserved=True,status='pass',scaling_method='Synthetic equal-scale preview assumption',observation='Synthetic bounds check',backend_behavior_verified=False),dict(viewport_width=2560,scale=2560/1920,file=large_responsive,columns_preserved=True,status='pass',scaling_method='Synthetic equal-scale preview assumption',observation='Synthetic bounds check',backend_behavior_verified=False)])
    (root/'index.html').write_text(''.join('<section data-module="'+m['type']+'" data-module-id="'+m['id']+'"></section>' for m in lc.modules(data).values()),encoding='utf-8')
    (root/'styles.css').write_text('/* synthetic fixture */',encoding='utf-8')
    Image.new('RGB',(1920,30)).save(root.with_name(root.name+'-preview.png'))
    write('assets.json',data)
    return data


class ContractTests(unittest.TestCase):
    def test_mixed_rows_count_height_once_and_keep_banner_ids(self):
        data=fixture()
        self.assertEqual(list(lc.modules(data)),['kv','banner-1','banner-2','banner-3'])
        self.assertEqual(len(lc.slice_plan(data)),4)
        errors=[]; lc.validate_counts(data,errors)
        self.assertEqual(errors,[])
        self.assertEqual(set(lc.seam_keys(data)),{'before:r-banner-1','before:r-pair','between:r-pair'})

    def test_reject_missing_layout_or_one_x(self):
        for mutate in (lambda d:d.pop('layout'), lambda d:d.update(export_scale=1)):
            data=fixture();mutate(data)
            with self.assertRaises(ValueError):lc.modules(data)

    def test_reject_duplicate_ids_bad_row_height_and_arbitrary_column_width(self):
        variants=[]
        d=fixture();d['layout']['rows'][2]['modules'][1]['id']='banner-2';variants.append(d)
        d=fixture();d['layout']['design_height']=42;variants.append(d)
        d=fixture();d['layout']['rows'][2]['modules'][0]['design_rect']['width']=900;variants.append(d)
        d=fixture();d['layout']['rows'][2]['modules'][1]['design_rect']['height']=11;variants.append(d)
        for data in variants:
            with self.assertRaises(ValueError):lc.modules(data)

    def test_two_x_pixels_are_not_dpi(self):
        data=fixture(); item=data['assets'][0]
        self.assertEqual(validator.expected_size('hero',item,data),(3840,20))
        item['width']=1920
        with self.assertRaises(ValueError):validator.expected_size('hero',item,data)
        item['width']=3840;item['height']=20
        image=Image.new('RGB',(3840,20));image.info['dpi']=(144,144)
        with self.assertRaises(ValueError):validator.validate_png_ppi(image,data)

    def test_half_sizes_and_unknown_role_requires_actual_source(self):
        data=fixture(); data['layout']['rows'][2]['modules'][0]['type']='task'
        data['module_configs']['banner-2'].update(task_count=2)
        item=dict(module_id='banner-2',role='task.row',file='assets/row.png',display_width=600,display_height=120,width=1200,height=240)
        with self.assertRaises(ValueError):validator.expected_size('task.row',item,data)
        data['module_configs']['banner-2']['asset_sizes']={'task.row':dict(display_width=600,display_height=120,source='Measured live reference',measured_viewport_width=1920,applies_to_profile='v2_half')}
        self.assertEqual(validator.expected_size('task.row',item,data),(1200,240))
        item.update(role='lottery.record',display_width=160,display_height=60,width=320,height=120)
        with self.assertRaises(ValueError):validator.expected_size('lottery.record',item,data)
        data['module_configs']['banner-2']['asset_sizes']={'lottery.record':dict(display_width=160,display_height=60,source='Confirmed measured design',measured_viewport_width=1920,applies_to_profile='v2_half')}
        self.assertEqual(validator.expected_size('lottery.record',item,data),(320,120))

    def test_single_requires_its_own_measured_size_then_two_x(self):
        data=fixture(); data['layout']['rows'][1]['modules'][0]['type']='package'
        data['module_configs']['banner-1'].update(package_count=2)
        item=dict(module_id='banner-1',role='package.card',file='assets/card.png',display_width=200,display_height=280,width=400,height=560)
        with self.assertRaises(ValueError):validator.expected_size('package.card',item,data)
        data['module_configs']['banner-1']['asset_sizes']={'package.card':dict(display_width=200,display_height=280,source='Measured single-column live reference',measured_viewport_width=1920,applies_to_profile='v1_single')}
        self.assertEqual(validator.expected_size('package.card',item,data),(400,560))
        data['module_configs']['banner-1']['asset_sizes']['package.card']['applies_to_profile']='v2_half'
        with self.assertRaises(ValueError):validator.expected_size('package.card',item,data)

    def test_scope_parser_keeps_repeated_types_separate(self):
        html='<section data-module="banner" data-module-id="a"><img data-role="module-title"><p>AAA</p></section><section data-module="banner" data-module-id="b"><img data-role="module-title"><p>BBB</p></section>'
        page=validator.PageStructure('b');page.feed(html)
        self.assertEqual(len(page.roles),1)
        self.assertEqual(page.module_text,{'banner':'BBB'})
        self.assertEqual(page.roles[0]['module_id'],'b')

    def test_half_task_does_not_require_old_account_row(self):
        with tempfile.TemporaryDirectory(prefix='v2-contract-') as tmp:
            root=Path(tmp);(root/'index.html').write_text('<section data-module="task" data-module-id="task-a"></section>',encoding='utf-8')
            errors=[]
            validator.validate_structure(root,dict(_module_id='task-a',layout_profile='v2_half',task_count=2,lottery_style=None),errors)
            self.assertEqual(errors,[])
            validator.validate_structure(root,dict(_module_id='task-a',layout_profile='v1_single',task_count=2,lottery_style=None),errors)
            self.assertTrue(errors)

    def test_real_two_dimensional_crops_preserve_pixels_and_ppi(self):
        with tempfile.TemporaryDirectory(prefix='v2-contract-') as tmp:
            root=Path(tmp);data=fixture();master=materialize(root,data)
            self.assertEqual(export_slices(root),4)
            for part,(x,y,w,h) in lc.slice_plan(data):
                with Image.open(root/part['file']) as image:
                    self.assertEqual(image.size,(w*2,h*2))
                    self.assertEqual(image.tobytes(),master.crop((x*2,y*2,(x+w)*2,(y+h)*2)).tobytes())
                    validator.validate_png_ppi(image,data)

    def test_invalid_last_slice_writes_nothing(self):
        with tempfile.TemporaryDirectory(prefix='v2-contract-') as tmp:
            root=Path(tmp);data=fixture();data['background_master']['slices'][-1]['x']=0
            materialize(root,data)
            with self.assertRaises(ValueError):export_slices(root)
            self.assertFalse((root/'assets').exists())

    def test_path_escape_rejected_before_any_output(self):
        with tempfile.TemporaryDirectory(prefix='v2-contract-') as tmp:
            root=Path(tmp);data=fixture()
            data['assets'][-1]['file']='../escape.png';data['background_master']['slices'][-1]['file']='../escape.png'
            materialize(root,data)
            with self.assertRaises(ValueError):export_slices(root)
            self.assertFalse((root/'assets').exists())

    def test_doubled_screenshot_height_is_not_valid(self):
        with tempfile.TemporaryDirectory(prefix='v2-contract-') as tmp:
            root=Path(tmp)/'delivery';root.mkdir();data=fixture()
            output=root.with_name('delivery-preview.png')
            Image.new('RGB',(1920,30)).save(output)
            errors=[];lc.validate_preview(root,data,errors);self.assertEqual(errors,[])
            Image.new('RGB',(1920,60)).save(output)
            lc.validate_preview(root,data,errors);self.assertTrue(errors)

    def test_complete_cli_contract_and_frozen_module_identity(self):
        with tempfile.TemporaryDirectory(prefix='v2-contract-') as tmp:
            root=Path(tmp)/'delivery';root.mkdir();data=complete_fixture(root)
            command=[sys.executable,str(Path(validator.__file__)),str(root)]
            result=subprocess.run(command,capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            data['assets'][1]['module_id']='banner-2'
            (root/'assets.json').write_text(json.dumps(data),encoding='utf-8')
            result=subprocess.run(command,capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(result.returncode,1,result.stdout+result.stderr)
            self.assertNotIn('Traceback',result.stderr)

    def test_backend_profile_repeat_rules(self):
        data=fixture();data.update(backend_profile='example_backend_v2',business_line='repeat_packages')
        self.assertEqual(len(lc.modules(data)),4)  # Repeated banners remain supported.
        for member in data['layout']['rows'][2]['modules']:
            member['type']='task'
            data['module_configs'][member['id']].update(task_count=2)
        with self.assertRaises(ValueError):lc.modules(data)
        for member in data['layout']['rows'][2]['modules']:
            member['type']='package'
            data['module_configs'][member['id']].update(package_count=2)
        self.assertEqual(len(lc.modules(data)),4)
        data['business_line']='OTHER'
        with self.assertRaises(ValueError):lc.modules(data)

    def test_responsive_checks_require_both_sides_and_actual_scale(self):
        with tempfile.TemporaryDirectory(prefix='v2-contract-') as tmp:
            root=Path(tmp)/'delivery';root.mkdir();data=complete_fixture(root)
            errors=[];lc.validate_geometry_evidence(root,data,errors,validator);self.assertEqual(errors,[])
            data['layout_review']['responsive_reviews'][1]['scale']=1
            errors=[];lc.validate_geometry_evidence(root,data,errors,validator);self.assertTrue(errors)
            data['layout_review']['responsive_reviews'].pop()
            errors=[];lc.validate_geometry_evidence(root,data,errors,validator);self.assertTrue(errors)

    def test_hero_can_share_row_move_right_or_move_down(self):
        for hero_id in ('banner-2','banner-3','banner-1'):
            data=fixture()
            data['layout']['rows'][0]['modules'][0]['type']='banner'
            data['assets'][0]['role']='banner'
            for row in data['layout']['rows']:
                for member in row['modules']:
                    if member['id']==hero_id:
                        member['type']='hero'
                    elif row['id']=='r-pair':
                        member['type']='package'
                        data['module_configs'][member['id']]['package_count']=2
            for asset in data['assets']:
                if asset['module_id']==hero_id:asset['role']='hero'
                elif asset['module_id'] in ('banner-2','banner-3'):asset['role']='package.background'
            self.assertEqual(lc.modules(data)[hero_id]['type'],'hero')
            self.assertEqual(len(lc.slice_plan(data)),4)

    def test_complete_cli_accepts_half_hero_in_either_column_and_banner_kv(self):
        for hero_id in ('banner-2','banner-3',None):
            with tempfile.TemporaryDirectory(prefix='v2-contract-') as tmp:
                data=fixture();data['layout']['rows'][0]['modules'][0]['type']='banner';data['assets'][0]['role']='banner'
                if hero_id is not None:
                    for row in data['layout']['rows']:
                        for member in row['modules']:
                            if member['id']==hero_id:member['type']='hero'
                    for asset in data['assets']:
                        if asset['module_id']==hero_id:asset['role']='hero'
                root=Path(tmp)/'delivery';root.mkdir();complete_fixture(root,data)
                result=subprocess.run([sys.executable,str(Path(validator.__file__)),str(root)],capture_output=True,text=True,encoding='utf-8')
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_decoration_two_x_contract(self):
        self.assertEqual(lc.scaled_size(dict(display_width=100,display_height=80,width=200,height=160)),(200,160))
        with self.assertRaises(ValueError):lc.scaled_size(dict(width=200,height=160))


if __name__=='__main__':
    unittest.main(verbosity=2)
