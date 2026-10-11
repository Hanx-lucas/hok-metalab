import json
import unittest
from pathlib import Path
from hoklab.seasonal import seasonal_evidence
from scripts.configure_camp import validate_headers
ROOT=Path(__file__).resolve().parents[1]
class SeasonalChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        read=lambda n:json.loads((ROOT/f'data/processed/{n}.json').read_text(encoding='utf-8'))
        cls.rows=read('hero_metrics');cls.coverage=read('coverage')
        cls.seasons,cls.leaders,cls.history=seasonal_evidence(cls.rows,cls.coverage,'20260003')
    def test_season_winners_match_real_rows_and_minimum_sample(self):
        for e in self.seasons:
            group=[r for r in self.rows if r['league_id']==e['league_id'] and r['battles']>=30 and r['posteriorRate'] is not None]
            if e['basis']=='综合指数':
                best=max((r for r in group if r['score'] is not None),key=lambda r:r['score'])
                self.assertEqual(e['leader_id'],best['hero_id'])
                self.assertEqual(e['score'],best['score'])
            if e['leader_id'] is not None:self.assertGreaterEqual(e['battles'],30)
            else:self.assertEqual(e['basis'],'证据不足')
    def test_missing_bp_has_distinct_basis_and_no_fake_index(self):
        for e in self.seasons:
            if e['event'].startswith('2019'):
                self.assertIn(e['basis'],('仅胜率证据','证据不足'))
                self.assertIsNone(e['score'])
        for r in self.history:
            if r['event'].startswith('2019'):self.assertIsNone(r['score'])
    def test_history_has_unique_hero_season_identity_and_no_low_sample_score(self):
        self.assertEqual(len({(r['hero_id'],r['league_id']) for r in self.history}),len(self.history))
        for r in self.history:
            if r['score'] is not None:self.assertGreaterEqual(r['battles'],30)
    def test_auth_headers_reject_injection_and_drop_transport_headers(self):
        self.assertEqual(validate_headers({'token':'local-example',':authority':'kohcamp.qq.com','host':'example','content-length':'20'}),{'token':'local-example'})
        for headers in ({'token':'a\r\nb'},{'token':'YOUR_VALUE'},{'openId':'x'}):
            with self.assertRaises(ValueError):validate_headers(headers)
