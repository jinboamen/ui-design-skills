import copy
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from sample_composer import compose, digest, compose_background, transition_template


class SampleComposerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.row = self.asset('row.png', (1920, 200), (30, 70, 90, 255))
        self.one = self.asset('one.png', (20, 40), (20, 200, 70, 255))
        self.two = self.asset('two.png', (20, 40), (30, 70, 90, 255))
        self.data = {'width':1920, 'height':200,
            'rows':[{**self.row, 'y':0, 'contains_kv':True, 'review':{
                'seams':{'status':'pass','observation':'Synthetic continuous field'},
                'kv_preserved':{'status':'pass','observation':'Synthetic fixture'}}}],
            'foregrounds':[
                {**self.one,'id':'p1','module_id':'pkg','role':'package.card-selected','rect':[1200,10,20,40]},
                {**self.two,'id':'p2','module_id':'pkg','role':'package.card','rect':[1240,10,20,40]}],
            'package_modules':{'pkg':{'count':2,'state_contrast':{'status':'pass','observation':'Different synthetic colors'}}}}

    def asset(self, name, size, color):
        p = self.root / name
        Image.new('RGBA',size,color).save(p)
        return {'file':name,'sha256':digest(p)}

    def single_package(self):
        d=copy.deepcopy(self.data)
        d['foregrounds']=d['foregrounds'][:1]
        d['foregrounds'][0]['role']='package.card'
        d['package_modules']['pkg']={'count':1}
        return d

    def test_single_ordinary_without_state_review_and_qr(self):
        d=self.single_package()
        d['foregrounds'].append({**self.two,'role':'package.qr-background','module_id':'pkg','rect':[1240,10,20,40]})
        compose(self.root,d)

    def test_single_selected_card_rejected(self):
        d=self.single_package();d['foregrounds'][0]['role']='package.card-selected'
        with self.assertRaisesRegex(ValueError,'Single package'):compose(self.root,d)

    def test_single_initial_selection_rejected(self):
        d=self.single_package();d['package_modules']['pkg']['initial_selected_id']='p1'
        with self.assertRaisesRegex(ValueError,'Single package'):compose(self.root,d)

    def test_frozen_row_survives_composition(self):
        preview, bg = compose(self.root,self.data)
        with Image.open(self.root/'row.png') as source:
            self.assertEqual(source.tobytes(),bg.tobytes())
        self.assertEqual(preview.getpixel((960,100)),bg.getpixel((960,100)))
        self.assertEqual(preview.getpixel((1205,15)),(20,200,70,255))

    def test_stale_background_rejected(self):
        Image.new('RGBA',(1920,200),'red').save(self.root/'row.png')
        with self.assertRaisesRegex(ValueError,'Frozen source'):compose(self.root,self.data)

    def test_half_row_rejected(self):
        self.data['rows'][0].update(self.asset('half.png',(960,200),'green'))
        with self.assertRaisesRegex(ValueError,'native 1920'):compose(self.root,self.data)

    def test_second_kv_overlay_rejected(self):
        self.data['foregrounds'].append({**self.row,'role':'hero','rect':[0,0,1920,200]})
        with self.assertRaisesRegex(ValueError,'cannot be overlaid'):compose(self.root,self.data)

    def test_protected_kv_cannot_masquerade_as_decoration(self):
        self.data['protected_kv_sha256']=[self.one['sha256']]
        with self.assertRaisesRegex(ValueError,'cannot be overlaid'):compose(self.root,self.data)

    def test_zero_or_two_selected_rejected(self):
        for roles in [('package.card','package.card'),('package.card-selected','package.card-selected')]:
            d=copy.deepcopy(self.data)
            for item,role in zip(d['foregrounds'],roles):item['role']=role
            with self.assertRaisesRegex(ValueError,'Exactly one'):compose(self.root,d)

    def test_explicit_second_selection(self):
        self.data['foregrounds'][0]['role']='package.card'
        self.data['foregrounds'][1]['role']='package.card-selected'
        self.data['package_modules']['pkg']['initial_selected_id']='p2'
        compose(self.root,self.data)

    def test_identical_state_images_rejected(self):
        self.data['foregrounds'][1].update(self.one)
        with self.assertRaisesRegex(ValueError,'pixels are identical'):compose(self.root,self.data)

    def test_visual_failure_cannot_be_geometry_pass(self):
        self.data['rows'][0]['review']['seams']['status']='revise'
        with self.assertRaisesRegex(ValueError,'Visual review required'):compose(self.root,self.data)

    def test_no_nonuniform_title_scaling(self):
        self.data['foregrounds'].append({**self.one,'role':'module.title','rect':[0,0,200,40]})
        with self.assertRaisesRegex(ValueError,'aspect ratio'):compose(self.root,self.data)


    def two_rows(self):
        self.data['height'] = 400
        lower = self.asset('lower.png', (1920, 200), (20, 40, 60, 255))
        self.data['rows'].append({**lower, 'y': 200, 'review': {
            'seams': {'status': 'pass', 'observation': 'Synthetic row'}}})

    def reviewed_pairs(self):
        self.data['vertical_transitions'] = transition_template(self.data)
        for pair in self.data['vertical_transitions']:
            for check in pair['review'].values():
                check.update(status='pass', observation='Synthetic test-only observation')

    def test_unreviewed_pair_can_make_background_check_but_not_candidate(self):
        self.two_rows()
        background = compose_background(self.root, self.data, require_reviews=False)
        self.assertEqual(background.getpixel((10, 199)), (30, 70, 90, 255))
        self.assertEqual(background.getpixel((10, 200)), (20, 40, 60, 255))
        pending = transition_template(self.data)
        self.assertTrue(all(c['status'] == 'pending' for c in pending[0]['review'].values()))
        with self.assertRaisesRegex(ValueError, 'Vertical transition reviews required'):
            compose(self.root, self.data)

    def test_reviewed_adjacent_rows_compose(self):
        self.two_rows(); self.reviewed_pairs()
        preview, background = compose(self.root, self.data)
        self.assertEqual(background.size, (1920, 400))

    def test_each_transition_region_and_overall_tone_must_pass(self):
        self.two_rows(); self.reviewed_pairs()
        for key in ('left', 'center', 'right', 'overall_tone'):
            d = copy.deepcopy(self.data)
            d['vertical_transitions'][0]['review'][key]['status'] = 'revise'
            with self.assertRaisesRegex(ValueError, 'Visual review required'):
                compose(self.root, d)

    def test_changed_background_invalidates_transition_review(self):
        self.two_rows(); self.reviewed_pairs()
        self.data['rows'][1].update(self.asset('replacement.png', (1920, 200), 'white'))
        with self.assertRaisesRegex(ValueError, 'does not match current row sources'):
            compose(self.root, self.data)

    def test_each_adjacent_pair_needs_its_own_review(self):
        self.two_rows(); self.reviewed_pairs()
        self.data['height'] = 600
        row = self.asset('third.png', (1920, 200), 'black')
        self.data['rows'].append({**row, 'y': 400, 'review': {
            'seams': {'status': 'pass', 'observation': 'Synthetic third row'}}})
        with self.assertRaisesRegex(ValueError, 'Vertical transition reviews required'):
            compose(self.root, self.data)

    def marquee_pair(self):
        normal = self.asset('marquee-normal.png', (40, 40), (30, 40, 50, 255))
        high = self.asset('marquee-high.png', (40, 40), (240, 200, 80, 180))
        self.data['foregrounds'].extend([
            {**normal, 'module_id': 'lottery', 'role': 'marquee.item', 'rect': [400,80,40,40]},
            {**high, 'module_id': 'lottery', 'role': 'marquee.highlight', 'rect': [400,80,40,40],
             'normal_source_sha256': normal['sha256'], 'review': {'highlight_visibility': {
                 'status': 'pass', 'observation': 'Synthetic bright cell; content not included in fixture'}}}])

    def test_marquee_candidate_requires_actual_highlight(self):
        self.marquee_pair(); self.data['foregrounds'].pop()
        with self.assertRaisesRegex(ValueError, 'exactly one visible'):
            compose(self.root, self.data)

    def test_marquee_highlight_is_composited_on_cell(self):
        self.marquee_pair()
        preview, _ = compose(self.root, self.data)
        self.assertNotEqual(preview.getpixel((410,90)), (30,40,50,255))

    def test_marquee_highlight_requires_alignment_and_source_binding(self):
        self.marquee_pair()
        for key, value in [('rect', [450,80,40,40]), ('normal_source_sha256', 'stale')]:
            d=copy.deepcopy(self.data); d['foregrounds'][-1][key]=value
            with self.assertRaisesRegex(ValueError, 'align to one cell'):
                compose(self.root, d)

    def test_marquee_highlight_visibility_failure_blocks_candidate(self):
        self.marquee_pair()
        self.data['foregrounds'][-1]['review']['highlight_visibility']['status']='revise'
        with self.assertRaisesRegex(ValueError, 'highlight_visibility'):
            compose(self.root, self.data)

    def blind_item(self):
        im=Image.new('RGBA',(40,40),(0,0,0,0))
        im.paste((80,160,60,255),(8,6,32,36))
        im.save(self.root/'blind.png')
        return {'file':'blind.png','sha256':digest(self.root/'blind.png'),
            'role':'blind.art','rect':[400,80,40,40],
            'environment_row_sha256':self.row['sha256'],
            'environment_placement':{'row_index':0,'row_sha256':self.row['sha256'],'art_sha256':digest(self.root/'blind.png'),
                'rect':[400,80,40,40],'source_contact':[20,36],'row_contact':[420,116]},
            'review':{k:{'status':'pass','observation':'Synthetic transparent body and registered ground'}
                for k in ['clean_cutout','environment_match']}}

    def test_opaque_blind_scene_patch_rejected(self):
        item=self.blind_item()
        item.update(self.asset('opaque-blind.png',(40,40),'green'))
        self.data['foregrounds'].append(item)
        with self.assertRaisesRegex(ValueError,'transparent exterior'):compose(self.root,self.data)

    def test_blind_cutout_needs_review_and_matching_environment(self):
        for change in ['review','source']:
            d=copy.deepcopy(self.data);item=self.blind_item()
            if change=='review':item['review']['clean_cutout']['status']='revise'
            else:item['environment_row_sha256']='unrelated'
            d['foregrounds'].append(item)
            with self.assertRaises(ValueError):compose(self.root,d)

    def test_clean_blind_composes_without_rectangular_patch(self):
        self.data['foregrounds'].append(self.blind_item())
        preview,bg=compose(self.root,self.data)
        self.assertEqual(preview.getpixel((400,80)),bg.getpixel((400,80)))
        self.assertEqual(preview.getpixel((412,92)),(80,160,60,255))

    def title_pair(self):
        for name,width,x in [('short',80,0),('long',200,200)]:
            asset=self.asset(name+'.png',(width,40),'white')
            self.data['foregrounds'].append({**asset,'role':'module.title',
                'title_group':'lower','rect':[x,100,width,40],
                'typography':{'style_id':'lower-master','source_font_size_px':32}})
        self.data['title_groups']={'lower':{'count':2,'title_consistency':{
            'status':'pass','observation':'Synthetic same-size typography with different widths'}}}

    def test_grouped_titles_allow_different_widths(self):
        self.title_pair();compose(self.root,self.data)

    def test_grouped_titles_reject_long_title_scaled_down(self):
        self.title_pair();self.data['foregrounds'][-1]['rect']=[200,100,100,20]
        with self.assertRaisesRegex(ValueError,'rendered font size'):compose(self.root,self.data)

    def test_grouped_titles_reject_different_source_font_sizes(self):
        self.title_pair();self.data['foregrounds'][-1]['typography']['source_font_size_px']=24
        with self.assertRaisesRegex(ValueError,'rendered font size'):compose(self.root,self.data)

    def test_titles_require_typography_metadata(self):
        self.title_pair();del self.data['foregrounds'][-1]['typography']
        with self.assertRaisesRegex(ValueError,'Title requires'):compose(self.root,self.data)


    def task_fixture(self):
        self.data['foregrounds'] = [
            {**self.asset('task.png',(600,120),'white'), 'role':'task.card',
             'id':'t1','module_id':'tasks','rect':[100,20,600,120]},
            {**self.asset('task-button.png',(160,60),'orange'), 'role':'task.button',
             'task_card_id':'t1','module_id':'tasks','rect':[500,50,160,60]}]
        self.data['package_modules'] = {}
        self.data['task_modules'] = {'tasks':{'profile':'example_v2_dual','count':1,
            'proportion_and_content':{'status':'pass','observation':'Synthetic geometry fixture'}}}

    def test_task_uses_real_card_and_button_sizes(self):
        self.task_fixture()
        preview,_=compose(self.root,self.data)
        self.assertEqual(preview.getpixel((101,139)),(255,255,255,255))
        self.assertEqual(preview.getpixel((501,51)),(255,165,0,255))

    def test_thin_task_source_cannot_pass_by_matching_its_own_ratio(self):
        self.task_fixture()
        self.data['foregrounds'][0].update(self.asset('thin.png',(600,60),'white'),rect=[100,20,600,60])
        with self.assertRaisesRegex(ValueError,'Task display size'):compose(self.root,self.data)

    def test_thin_body_inside_correct_canvas_is_rejected(self):
        self.task_fixture()
        im=Image.new('RGBA',(600,120));im.paste('white',(0,40,600,80));im.save(self.root/'task.png')
        self.data['foregrounds'][0]['sha256']=digest(self.root/'task.png')
        with self.assertRaisesRegex(ValueError,'visible body'):compose(self.root,self.data)

    def test_task_button_wrong_size_and_position_rejected(self):
        self.task_fixture()
        for rect in ([500,50,80,30],[500,21,160,60]):
            d=copy.deepcopy(self.data);d['foregrounds'][1]['rect']=rect
            with self.assertRaisesRegex(ValueError,'Task'):compose(self.root,d)

    def test_task_missing_profile_or_review_rejected(self):
        self.task_fixture()
        for key in ('profile','proportion_and_content'):
            d=copy.deepcopy(self.data);del d['task_modules']['tasks'][key]
            with self.assertRaises(ValueError):compose(self.root,d)

    def test_other_measured_task_size_allowed_with_source(self):
        self.task_fixture()
        config=self.data['task_modules']['tasks']
        config.update(profile='measured',card_size=[700,140],button_size=[160,60],size_source='Synthetic renderer measurement')
        self.data['foregrounds'][0].update(self.asset('custom.png',(700,140),'white'),rect=[100,20,700,140])
        compose(self.root,self.data)
        del config['size_source']
        with self.assertRaisesRegex(ValueError,'size_source'):compose(self.root,self.data)

    def test_blind_moving_or_scaling_invalidates_environment_binding(self):
        for rect in ([410,80,40,40],[400,80,20,20]):
            d=copy.deepcopy(self.data);item=self.blind_item();item['rect']=rect
            d['foregrounds'].append(item)
            with self.assertRaisesRegex(ValueError,'placement changed'):compose(self.root,d)

    def test_blind_retrim_or_replacement_invalidates_environment_binding(self):
        item=self.blind_item()
        with Image.open(self.root/'blind.png') as im:
            im.crop((4,4,36,36)).save(self.root/'trimmed.png')
        item.update(file='trimmed.png',sha256=digest(self.root/'trimmed.png'))
        self.data['foregrounds'].append(item)
        with self.assertRaisesRegex(ValueError,'placement changed'):compose(self.root,self.data)

    def test_blind_wrong_contact_rejected_even_if_file_and_rect_match(self):
        item=self.blind_item();item['environment_placement']['row_contact']=[420,125]
        self.data['foregrounds'].append(item)
        with self.assertRaisesRegex(ValueError,'does not align'):compose(self.root,self.data)

    def test_blind_lower_row_uses_row_local_contact_not_page_y(self):
        self.two_rows();self.reviewed_pairs()
        item=self.blind_item();item['rect']=[400,280,40,40]
        item['environment_row_sha256']=self.data['rows'][1]['sha256']
        item['environment_placement'].update(row_index=1,row_sha256=item['environment_row_sha256'],rect=item['rect'][:])
        self.data['foregrounds'].append(item)
        preview,_=compose(self.root,self.data)
        self.assertEqual(preview.getpixel((412,292)),(80,160,60,255))
        item['environment_placement']['row_contact']=[420,316]
        with self.assertRaises(ValueError):compose(self.root,self.data)


    def test_blind_replaced_background_requires_new_contact_review(self):
        item=self.blind_item()
        new_row=self.asset('new-ground.png',(1920,200),'black')
        self.data['rows'][0].update(new_row)
        item['environment_row_sha256']=new_row['sha256']
        self.data['foregrounds'].append(item)
        with self.assertRaisesRegex(ValueError,'placement changed'):compose(self.root,self.data)

    def test_blind_2x_source_maps_contact_to_same_1x_location(self):
        item=self.blind_item()
        with Image.open(self.root/'blind.png') as im:
            im.resize((80,80),Image.Resampling.NEAREST).save(self.root/'double.png')
        item.update(file='double.png',sha256=digest(self.root/'double.png'))
        item['environment_placement'].update(art_sha256=item['sha256'],source_contact=[40,72])
        self.data['foregrounds'].append(item)
        preview,_=compose(self.root,self.data)
        self.assertEqual(preview.getpixel((420,100)),(80,160,60,255))

    def test_blind_missing_registration_cannot_use_old_pass_review(self):
        item=self.blind_item();del item['environment_placement']
        self.data['foregrounds'].append(item)
        with self.assertRaisesRegex(ValueError,'registered row_index'):compose(self.root,self.data)


    def package_button_fixture(self):
        self.data=self.single_package()
        card=self.data['foregrounds'][0]
        card.update(self.asset('large-card.png',(200,280),'purple'),rect=[100,10,200,280],button_safe_rect=[20,200,160,60])
        self.data['height']=300
        self.data['rows'][0].update(self.asset('tall-row.png',(1920,300),'black'))
        button={**self.asset('purchase.png',(150,50),'orange'), 'role':'package.button',
            'module_id':'pkg','card_id':'p1','rect':[125,215,150,50],
            'review':{'edge_clearance':{'status':'pass','observation':'Synthetic inset fixture'}}}
        self.data['foregrounds'].append(button)
        return card,button

    def test_purchase_button_inside_reserved_region(self):
        self.package_button_fixture()
        preview,_=compose(self.root,self.data)
        self.assertEqual(preview.getpixel((130,220)),(255,165,0,255))

    def test_purchase_button_inside_card_but_touching_bottom_rejected(self):
        _,button=self.package_button_fixture();button['rect'][1]=240
        with self.assertRaisesRegex(ValueError,'interior safe region'):compose(self.root,self.data)

    def test_purchase_button_touching_side_rejected(self):
        _,button=self.package_button_fixture();button['rect'][0]=100
        with self.assertRaisesRegex(ValueError,'interior safe region'):compose(self.root,self.data)

    def test_purchase_button_cannot_use_whole_card_as_safe_region(self):
        card,_=self.package_button_fixture();card['button_safe_rect']=[1,1,199,279]
        with self.assertRaisesRegex(ValueError,'clear of card edges'):compose(self.root,self.data)

    def test_purchase_button_needs_parent_and_visual_review(self):
        _,button=self.package_button_fixture()
        for key in ('card_id','review'):
            d=copy.deepcopy(self.data);del d['foregrounds'][-1][key]
            with self.assertRaises(ValueError):compose(self.root,d)

if __name__=='__main__':unittest.main()

