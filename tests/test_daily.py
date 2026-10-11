import unittest
from copy import deepcopy
from hoklab.daily import rate, displayed_ban, normalize_history

class DailySourceTests(unittest.TestCase):
    def test_endpoint_units_and_missing(self):
        self.assertAlmostEqual(rate(54.97),.5497)
        self.assertAlmostEqual(rate(.5497,unit='fraction'),.5497)
        self.assertIsNone(rate('--'))
        with self.assertRaises(ValueError):rate(1.21,unit='fraction')
    def test_dual_ban_is_not_clipped(self):
        self.assertAlmostEqual(displayed_ban([121.28,86.47]),.8647)
        with self.assertRaises(ValueError):displayed_ban([86.47])
    def fixture(self):
        return {'data':{'result':{'columns':['日期','全分段:胜率'],'rows':[{'日期':'2026-10-10 周六','全分段:胜率':.5,'全分段:出场':.02,'全分段:禁用':None}]}}}
    def test_labeled_segments_and_null_preservation(self):
        rows=normalize_history(self.fixture(),107)
        self.assertEqual(len(rows),4)
        self.assertTrue(all(r['sample_size'] is None for r in rows))
        self.assertIsNone(next(r for r in rows if r['segment']=='巅峰千强')['winRate'])
    def test_reject_unlabeled_history(self):
        obj=self.fixture();obj['data']['result']['columns']=['日期','胜率']
        with self.assertRaises(ValueError):normalize_history(obj,107)
    def test_exact_duplicate_only(self):
        obj=self.fixture();r=obj['data']['result']['rows'][0];obj['data']['result']['rows'].append(deepcopy(r))
        self.assertEqual(len(normalize_history(obj,107)),4)
        obj['data']['result']['rows'][1]['全分段:胜率']=.7
        with self.assertRaises(ValueError):normalize_history(obj,107)

if __name__=='__main__':unittest.main()
