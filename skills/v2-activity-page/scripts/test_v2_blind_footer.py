from pathlib import Path
import tempfile
import unittest
import draft_workflow
import validate_output as validator


COUNT = '<span data-role="draw-count">抽奖次数：0次</span>'
PROB = '<a data-role="prize-probability">*奖品概率</a>'


def check(body, profile='v2_half'):
    data = dict(lottery_style='blind_box', production_workflow=draft_workflow.MODE,
                layout_profile=profile, blind_prize_count=0, blind_prizes=[], task_count=0)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / 'index.html').write_text('<section data-module="lottery">'+body+'</section>',encoding='utf-8')
        errors = []
        validator.validate_structure(root, data, errors)
        return errors


class BlindFooterTests(unittest.TestCase):
    def test_same_group_is_accepted_for_half_and_full_width(self):
        html='<div data-role="blind-footer">'+COUNT+PROB+'</div>'
        for profile in ('v2_half','v1_single'):
            self.assertEqual(check(html,profile),[],profile)

    def test_reversed_order_or_separate_group_is_rejected(self):
        cases=[
            '<div data-role="blind-footer">'+PROB+COUNT+'</div>',
            '<div data-role="blind-footer">'+COUNT+'</div>'+PROB,
        ]
        for html in cases:
            self.assertTrue(any('同一blind-footer' in e for e in check(html)))

    def test_extra_separator_is_not_a_new_design_option(self):
        errors=check('<div data-role="blind-footer">'+COUNT+' | '+PROB+'</div>')
        self.assertTrue(any('分隔符' in e for e in errors))

    def test_probability_keeps_its_asterisk_and_group_is_required(self):
        errors=check('<div data-role="blind-footer">'+COUNT+PROB.replace('*','')+'</div>')
        self.assertTrue(any('前导*' in e for e in errors))
        self.assertTrue(any('blind-footer' in e for e in check(COUNT+PROB)))

    def test_actual_count_can_change_without_new_layout(self):
        for text in ('抽奖次数：1次','抽奖次数：123次','抽奖次数：待配置'):
            html='<div data-role="blind-footer" style="color:#182c21">'+COUNT.replace('抽奖次数：0次',text)+PROB+'</div>'
            self.assertEqual(check(html),[])


if __name__=='__main__':
    unittest.main()
