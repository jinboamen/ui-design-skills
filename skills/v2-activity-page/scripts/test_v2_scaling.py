import unittest
import layout_contract as lc

class ScalingTests(unittest.TestCase):
    def test_auto_height_pixel_rounding(self):
        height = 230 * 80 / 308
        item = dict(display_width=230,display_height=height,width=460,height=119,rounding_rule='nearest_pixel')
        self.assertEqual(lc.scaled_size(item),(460,119))
        self.assertLessEqual(abs(119/2-height),0.25)
        item.pop('rounding_rule')
        with self.assertRaises(ValueError): lc.scaled_size(item)

    def test_bad_or_arbitrary_sizes_rejected(self):
        for value in (True,float('inf'),float('nan'),0,-1):
            with self.assertRaises(ValueError):
                lc.scaled_size(dict(display_width=value,display_height=60,width=460,height=120))
        with self.assertRaises(ValueError):
            lc.scaled_size(dict(display_width=230,display_height=230*80/308,width=460,height=120,rounding_rule='nearest_pixel'))

    def test_four_tasks_are_a_valid_catalog_variant(self):
        from test_v2_contract import fixture
        data=fixture()
        member=data['layout']['rows'][2]['modules'][0]
        member['type']='task'
        mid=member['id']
        data['module_configs'][mid]['task_count']=4
        data['assets']=[a for a in data['assets'] if a['module_id']!=mid]
        roles=['task.background','task.title','task.row','task.button-available','task.button-claimed']
        data['assets'].extend(dict(module_id=mid,role=role) for role in roles)
        errors=[]
        lc.validate_counts(data,errors)
        self.assertEqual(errors,[])

    def test_verified_pc_scale_limits(self):
        self.assertEqual(lc.responsive_scale(960,'example_backend_v2'),1200/1920)
        self.assertEqual(lc.responsive_scale(1280,'example_backend_v2'),1280/1920)
        self.assertEqual(lc.responsive_scale(4096,'example_backend_v2'),2)

if __name__ == '__main__': unittest.main()
