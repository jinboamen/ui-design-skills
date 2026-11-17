import copy
import json
import tempfile
import unittest
from pathlib import Path
from sample_composer import digest
from review_candidate import check_review, COLOR_CHECKS


class CandidateColorReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.source=self.root/'source.png';self.source.write_bytes(b'fixture-source')
        self.manifest=self.root/'manifest.json'
        self.manifest.write_text(json.dumps({'rows':[{'file':'source.png','sha256':digest(self.source)}]}))
        self.preview=self.root/'preview.png';self.preview.write_bytes(b'fixture-render')
        self.record={'mechanical_check':'pass','manifest_sha256':digest(self.manifest),'output_sha256':digest(self.preview)}
        self.preview.with_suffix('.composition.json').write_text(json.dumps(self.record))
        self.review={'manifest_sha256':digest(self.manifest),'preview_sha256':digest(self.preview),
                     **{k:{'status':'pass','observation':'Synthetic review fixture'} for k in COLOR_CHECKS}}

    def test_geometry_pass_does_not_replace_color_review(self):
        with self.assertRaisesRegex(ValueError,'missing or stale'):check_review(self.manifest,self.preview,{})

    def test_missing_or_failed_color_check_rejects_candidate(self):
        for key in COLOR_CHECKS:
            for status in ('pending','revise'):
                data=copy.deepcopy(self.review);data[key]['status']=status
                with self.assertRaisesRegex(ValueError,key):check_review(self.manifest,self.preview,data)

    def test_preview_or_manifest_replacement_invalidates_review(self):
        for key in ('manifest_sha256','preview_sha256'):
            data=copy.deepcopy(self.review);data[key]='stale'
            with self.assertRaisesRegex(ValueError,'stale'):check_review(self.manifest,self.preview,data)

    def test_source_changed_after_review_is_detected(self):
        self.source.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'source changed'):check_review(self.manifest,self.preview,self.review)

    def test_tonal_design_needs_no_special_permission_but_all_reviews(self):
        self.assertEqual(check_review(self.manifest,self.preview,self.review)['candidate_status'],'reviewed')
        self.review['visual_variety']['status']='revise'
        with self.assertRaisesRegex(ValueError,'visual_variety'):check_review(self.manifest,self.preview,self.review)

    def test_more_hues_cannot_override_failed_coherence(self):
        self.review['palette_mode']='multi_hue'
        self.review['palette_coherence']['status']='revise'
        with self.assertRaisesRegex(ValueError,'palette_coherence'):check_review(self.manifest,self.preview,self.review)

    def test_old_hue_pass_is_not_new_balanced_review(self):
        self.review.pop('palette_coherence');self.review.pop('visual_variety')
        self.review['hue_separation']={'status':'pass','observation':'Old different-hue approval'}
        with self.assertRaisesRegex(ValueError,'palette_coherence'):check_review(self.manifest,self.preview,self.review)

    def test_complete_review_binds_exact_output(self):
        result=check_review(self.manifest,self.preview,self.review)
        self.assertEqual(result['preview_sha256'],digest(self.preview))

if __name__=='__main__':unittest.main()
