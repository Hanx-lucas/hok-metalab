import unittest
from copy import deepcopy
from hoklab.strength import daily_scores, combined_score, ranked

class StrengthTests(unittest.TestCase):
    def test_composite_daily_fallback_and_missing_daily(self):
        self.assertEqual(combined_score(80,60),70)
        self.assertIsNone(combined_score(80,None));self.assertEqual(combined_score(None,60),60)
        self.assertEqual(combined_score(0,0),0);self.assertEqual(combined_score(None,0),0);self.assertIsNone(combined_score(None,None))
    def test_missing_not_zero_and_variants_not_double_counted(self):
        rows=[dict(hero_id=1,winRate=.6,pickRate=.1,banRate=.1),dict(hero_id=2,winRate=.4,pickRate=.2,banRate=.1),dict(hero_id=3,winRate=None,pickRate=.9,banRate=.9)]
        expected=daily_scores(rows,{1,2,3})
        duplicate=dict(hero_id=50701,winRate=.99,pickRate=.99,banRate=.99)
        self.assertEqual(expected,daily_scores(rows+[duplicate],{1,2,3}));self.assertNotIn(3,expected)
        self.assertAlmostEqual(expected[1]['score'],83.75);self.assertAlmostEqual(expected[2]['score'],66.25)
    def test_reject_duplicate_hero_identity(self):
        r=dict(hero_id=1,winRate=.5,pickRate=.1,banRate=.1)
        with self.assertRaises(ValueError):daily_scores([r,deepcopy(r)],{1})
    def test_rank_uses_full_precision_and_keeps_unrated(self):
        rows=[dict(hero_id=3,score=None,rank=None),dict(hero_id=2,score=80.01,rank=None),dict(hero_id=1,score=80.02,rank=None)]
        r=ranked(rows);self.assertEqual([x['hero_id'] for x in r],[1,2,3]);self.assertIsNone(r[-1]['rank'])

if __name__=='__main__':unittest.main()
