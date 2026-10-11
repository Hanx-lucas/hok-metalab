import json
import unittest
from pathlib import Path
from hoklab.strength import LANES
ROOT=Path(__file__).resolve().parents[1]

class RankingDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        q=json.loads((ROOT/'data/reviewed_snapshot.json').read_text(encoding='utf-8'))['queries']
        cls.rows=q['strength_rankings']['rows'];cls.contexts=q['strength_contexts']['rows'];cls.lanes=q['strength_lane_rankings']['rows'];cls.q=q
    def test_every_context_preserves_catalog_and_unique_ids(self):
        ids={h['ename'] for h in json.loads((ROOT/'data/raw/heroes.json').read_text(encoding='utf-8'))}
        for c in self.contexts:
            rows=[r for r in self.rows if r['context_id']==c['context_id']]
            self.assertEqual(len(rows),len({r['hero_id'] for r in rows}))
            self.assertTrue(ids.issubset({r['hero_id'] for r in rows}))
            self.assertEqual(sum(r['rank'] is not None for r in rows),c['scored'])
            ranked=[r for r in rows if r['rank'] is not None]
            self.assertEqual([r['rank'] for r in ranked],list(range(1,len(ranked)+1)))
            self.assertEqual([r['score'] for r in ranked],sorted((r['score'] for r in ranked),reverse=True))
    def test_composite_matches_two_contexts_and_explicit_daily_fallback(self):
        for c in self.contexts:
            if c['dimension']!='overall':continue
            arenas={r['hero_id']:r for r in self.rows if r['context_id']=='arena:'+c['league_id']}
            daily={r['hero_id']:r for r in self.rows if r['context_id']=='daily:'+c['segment']}
            for r in [r for r in self.rows if r['context_id']==c['context_id']]:
                a=arenas.get(r['hero_id'],{}).get('score');d=daily[r['hero_id']]['score']
                self.assertEqual(r['arenaScore'],a);self.assertEqual(r['dailyScore'],d)
                if d is None:self.assertIsNone(r['score']);self.assertIsNone(r['rank'])
                elif a is None:self.assertEqual(r['score'],d);self.assertEqual(r['overallBasis'],'daily_only');self.assertIsNotNone(r['rank'])
                else:self.assertAlmostEqual(r['score'],(a+d)/2);self.assertEqual(r['overallBasis'],'balanced')
    def test_lane_top5_uses_global_scores_without_reranking_population(self):
        for c in self.contexts:
            for lane in LANES:
                full=[r for r in self.rows if r['context_id']==c['context_id'] and r['rank'] is not None and lane in r['roles'].split('/')][:5]
                shown=[r for r in self.lanes if r['context_id']==c['context_id'] and r['lane']==lane]
                self.assertEqual([(r['hero_id'],r['score']) for r in shown],[(r['hero_id'],r['score']) for r in full])
    def test_unrated_and_variant_rows_never_inherit_rank_or_fake_sample_size(self):
        for r in self.rows:
            if r['score'] is None:self.assertIsNone(r['rank'])
            if r['dimension']=='arena' and r['rank'] is not None:self.assertGreaterEqual(r['battles'],30)
            if r['hero_id'] in [50701,50702]:self.assertIsNone(r['score']);self.assertIsNone(r['rank'])
            if r['dimension']=='daily':self.assertIsNone(r['battles']);self.assertIsNone(r['lowerRate'])

if __name__=='__main__':unittest.main()
