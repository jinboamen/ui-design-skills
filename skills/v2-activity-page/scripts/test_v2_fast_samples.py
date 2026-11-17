"""End-to-end checks for 1x proposals and one selected 2x formal work set."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from PIL import Image

import draft_workflow
import validate_output as validator
from test_v2_contract import complete_fixture


def fast_fixture(root):
    # Reuse the existing layout and final QA evidence, not its candidate work sets.
    data = complete_fixture(root)
    evidence_path = root / data['design_evidence']
    evidence = json.loads(evidence_path.read_text(encoding='utf-8'))
    data['production_workflow'] = evidence['production_workflow'] = draft_workflow.MODE
    kv = evidence['kv_images'][0]
    ref = evidence['references'][0]['file']
    records = [dict(file=name, kind='provided', source_file=name) for name in (kv, ref)]
    proposals = evidence['design_selection']['proposals']
    for proposal in proposals:
        proposal.pop('background_set')
        records.append(dict(file=proposal['file'], kind='generated', input_images=[kv, ref],
                            source='synthetic-unit-test'))
        # Prove the workflow needs no candidate backgrounds, concepts or manifest.
        for path in (root / proposal['file']).parent.iterdir():
            if path.name != 'preview.png':
                path.unlink()
    evidence['design_selection']['approval'].pop('background_set_sha256')
    chosen = proposals[0]['file']
    directory = root / 'design/hd'
    directory.mkdir()
    master = 'design/hd/master.png'
    shutil.copyfile(root / data['background_master']['file'], root / master)
    records.append(dict(file=master, kind='generated', input_images=[chosen, kv, ref],
                        source='synthetic-high-resolution-test'))
    digest = lambda name: hashlib.sha256((root / name).read_bytes()).hexdigest()
    members = []
    for asset in data['assets']:
        source = 'design/hd/' + asset['module_id'] + '.png'
        shutil.copyfile(root / asset['file'], root / source)
        records.append(dict(file=source, kind='derived', input_images=[master]))
        asset['working_source'] = source
        records.append(dict(file=asset['file'], kind='derived', input_images=[source]))
        members.append(dict(role=asset['role'], module_id=asset['module_id'],
                            file=source, sha256=digest(source)))
    data['background_master']['working_source'] = master
    records.append(dict(file=data['background_master']['file'], kind='derived', input_images=[master]))
    preview = 'design/hd-final-preview.png'
    shutil.copyfile(root / 'design/final-preview.png', root / preview)
    records.append(dict(file=preview, kind='derived', renderer='browser',
                        input_images=[item['file'] for item in members]))
    work = dict(layout=data['layout'], export_scale=2, page_width=1920, page_height=30,
                background_master=dict(file=master, sha256=digest(master)), assets=members, decorations=[])
    work_file = 'design/hd-work.json'
    (root / work_file).write_text(json.dumps(work), encoding='utf-8')
    evidence['records'] = records
    evidence['selected_working_set'] = dict(selected_id='A', file=work_file,
        manifest_sha256=digest(work_file), preview=preview)
    evidence.pop('background_inheritance')
    evidence['design_inheritance'] = dict(status='pass', source=chosen, result=preview,
        comparison=preview, observation='Synthetic structural example only',
        adjustments=['Synthetic high-resolution production from the selected design'])
    review = evidence['review']
    review.update(composition=preview, comparison=preview)
    review['visual_review'].update(page=preview, component_comparison=preview, background_comparison=preview)
    for check in review['visual_review']['checks'].values():
        check['evidence'] = preview
    save(root, data, evidence)
    return data, evidence


def save(root, data, evidence):
    (root / 'assets.json').write_text(json.dumps(data), encoding='utf-8')
    (root / data['design_evidence']).write_text(json.dumps(evidence), encoding='utf-8')


def inspect(root, data):
    errors = []
    validator.validate_design_evidence(root, data, errors)
    return errors


class FastSampleTests(unittest.TestCase):
    def test_complete_cli_accepts_one_x_samples_without_candidate_background_sets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'delivery'
            root.mkdir()
            data, evidence = fast_fixture(root)
            self.assertEqual(inspect(root, data), [])
            for proposal in evidence['design_selection']['proposals']:
                self.assertNotIn('background_set', proposal)
                self.assertEqual([p.name for p in (root / proposal['file']).parent.iterdir()], ['preview.png'])
            result = subprocess.run([sys.executable, validator.__file__, str(root)],
                                    capture_output=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_candidate_is_1920_not_a_required_two_x_background(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data, evidence = fast_fixture(root)
            target = root / evidence['design_selection']['proposals'][1]['file']
            Image.new('RGB', (3840, 60)).save(target)
            self.assertTrue(any('1920px' in e for e in inspect(root, data)))

    def test_known_visual_regression_cannot_pass_with_valid_dimensions(self):
        for status in ('revise', 'needs_repair', 'awaiting_revision', 'failed', 'rejected'):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                data, evidence = fast_fixture(root)
                evidence['design_selection']['proposals'][0]['status'] = status
                save(root, data, evidence)
                self.assertTrue(any('所选样张已标记需要修复' in e for e in inspect(root, data)))

    def test_unselected_revision_does_not_block_selected_design(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data, evidence = fast_fixture(root)
            evidence['design_selection']['proposals'][1]['status'] = 'revise'
            save(root, data, evidence)
            self.assertEqual(inspect(root, data), [])

    def test_final_master_must_still_be_two_x(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data, evidence = fast_fixture(root)
            work_path = root / evidence['selected_working_set']['file']
            work = json.loads(work_path.read_text(encoding='utf-8'))
            target = root / work['background_master']['file']
            Image.new('RGB', (1920, 30)).save(target)
            work['background_master']['sha256'] = hashlib.sha256(target.read_bytes()).hexdigest()
            work_path.write_text(json.dumps(work), encoding='utf-8')
            evidence['selected_working_set']['manifest_sha256'] = hashlib.sha256(work_path.read_bytes()).hexdigest()
            save(root, data, evidence)
            self.assertTrue(any('3840px' in e for e in inspect(root, data)))

    def test_unselected_proposal_cannot_enter_final_production(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data, evidence = fast_fixture(root)
            next(r for r in evidence['records'] if r['file'] == 'design/hd/master.png')['input_images'].append(
                evidence['design_selection']['proposals'][1]['file'])
            save(root, data, evidence)
            self.assertTrue(any('未选方案' in e for e in inspect(root, data)))

    def test_changed_selected_sample_requires_new_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data, evidence = fast_fixture(root)
            target = root / evidence['design_selection']['proposals'][0]['file']
            Image.new('RGB', (1920, 30), 'red').save(target)
            self.assertTrue(any('所选样张版本已变化' in e for e in inspect(root, data)))

    def test_formal_review_cannot_reuse_the_candidate_screenshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data, evidence = fast_fixture(root)
            evidence['selected_working_set']['preview'] = evidence['design_selection']['proposals'][0]['file']
            save(root, data, evidence)
            self.assertTrue(any('不能复用候选样张' in e for e in inspect(root, data)))



class RefinementEvidenceTests(unittest.TestCase):
    def check(self, entries):
        draft_workflow.validate_foreground_refinement(
            {'foreground_refinement':entries}, {'card.png':'package.card'},
            lambda path: path, 'sample.png', 'final.png')

    def entry(self):
        return dict(status='pass', targets=['card.png'], before='sample.png',
            after='final.png', comparison='side-by-side.png', decision='refined',
            changes=['Reworked edge structure'], visible_result='Edge depth visible at normal size')

    def test_requires_refinement_evidence(self):
        with self.assertRaisesRegex(ValueError,'缺少精修'):self.check([])

    def test_rejects_empty_improvement(self):
        item=self.entry();item['changes']=[]
        with self.assertRaisesRegex(ValueError,'具体改进'):self.check([item])

    def test_rejects_final_preview_as_comparison(self):
        item=self.entry();item['comparison']='final.png'
        with self.assertRaisesRegex(ValueError,'同尺度前后'):self.check([item])

    def test_all_retained_cannot_claim_refinement(self):
        item=self.entry();item.update(decision='retained',reason='Simple style')
        with self.assertRaisesRegex(ValueError,'全部前景'):self.check([item])

    def test_rejects_unreviewed_or_wrong_target(self):
        for field,value in [('status','revise'),('targets',['unrelated.png'])]:
            item=self.entry();item[field]=value
            with self.assertRaises(ValueError):self.check([item])

    def test_recorded_refinement_passes_structure_only(self):
        self.check([self.entry()])

if __name__ == '__main__':
    unittest.main()
