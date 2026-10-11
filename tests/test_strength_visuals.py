import json,math,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class VisualEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.q=json.loads((ROOT/'data/reviewed_snapshot.json').read_text(encoding='utf-8'))['queries']
    def test_contributions_cover_only_rated_heroes_and_reconcile_all_dimensions(self):
        original={(r['context_id'],r['hero_id']):r for r in self.q['strength_rankings']['rows'] if r['score'] is not None}
        points=self.q['strength_analysis_points']['rows']
        self.assertEqual(len(points),len(original))
        for p in points:
            r=original[p['context_id'],p['hero_id']]
            self.assertTrue(math.isclose(p['winPoints']+p['pickPoints']+p['banPoints'],r['score'],abs_tol=1e-8))
            self.assertNotIn(p['hero_id'],[50701,50702])
            if r['overallBasis']=='daily_only':
                self.assertEqual(p['winPoints'],r['dailyWinContribution']);self.assertIsNone(p['sceneGap'])
            if p['dimension']=='daily':self.assertIsNone(p['battles'])
            if r['overallBasis']=='balanced':self.assertAlmostEqual(p['sceneGap'],r['dailyScore']-r['arenaScore'])
    def test_waterfall_drivers_are_unique_and_match_reviewed_totals(self):
        from collections import defaultdict
        groups=defaultdict(list)
        for row in self.q['strength_analysis_drivers']['rows']:groups[row['context_id'],row['hero_id']].append(row)
        points=self.q['strength_analysis_points']['rows']
        self.assertEqual(len(groups),len(points))
        for point in points:
            rows=groups[point['context_id'],point['hero_id']]
            self.assertEqual([r['driver'] for r in rows],['胜率贡献','出场贡献','ban贡献'])
            self.assertAlmostEqual(sum(r['contribution'] for r in rows),point['score'])
            self.assertTrue(all(r['score']==point['score'] and r['basis']==point['basis'] for r in rows))
    def test_history_uses_completed_real_dates_without_filling_unrated(self):
        seasons={str(s['league_id']):s for s in self.q['season_summary']['rows'] if s['regular'] and s['event_status']=='已结束'}
        original={(r['league_id'],r['hero_id']):r for r in self.q['strength_rankings']['rows'] if r['dimension']=='arena'}
        history=self.q['strength_analysis_history']['rows']
        self.assertEqual(len(history),len(seasons)*133)
        self.assertEqual(len(history),len({(p['league_id'],p['hero_id']) for p in history}))
        self.assertEqual([p['eventStart'] for p in history],sorted(p['eventStart'] for p in history))
        for p in history:
            self.assertIn(p['league_id'],seasons);self.assertEqual(p['score'],original[p['league_id'],p['hero_id']]['score'])
            if p['score'] is not None:self.assertGreaterEqual(p['battles'],30)
        self.assertTrue(any(p['score'] is None for p in history))
if __name__=='__main__':unittest.main()
