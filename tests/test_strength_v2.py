import unittest,json,math,hashlib
from pathlib import Path
import numpy as np
from hoklab.strength_v2 import score_pool,MIN_POOL,LANE_E_WEIGHTS
from hoklab.coverage_audit import daily_bp_contract,official_bp_contract
ROOT=Path(__file__).resolve().parents[1]
class V2NumericalTests(unittest.TestCase):
    def pool(self,n=8):return [{'hero_id':i,'wRaw':.4+i*.02,'bpRate':.01+i*.05} for i in range(n)]
    def test_exact_formula_population_sigma_raw_average_ranks_and_winsor_z(self):
        rows=self.pool();result=score_pool(rows)
        w=np.array([r['wRaw'] for r in rows]);bp=np.array([r['bpRate'] for r in rows]);lo,hi=np.quantile(bp,[.05,.95]);adj=np.clip(bp,lo,hi)
        for i,row in enumerate(rows):
            r=result[row['hero_id']];self.assertAlmostEqual(r['wZ'],(w[i]-w.mean())/w.std(ddof=0));self.assertAlmostEqual(r['bpZ'],(adj[i]-adj.mean())/adj.std(ddof=0))
            self.assertAlmostEqual(r['wPercentile'],(i+1)/len(rows));self.assertAlmostEqual(r['bpPercentile'],(i+1)/len(rows))
            self.assertAlmostEqual(r['E'],100*(r['wPercentile']+r['wNormalized'])/2);self.assertAlmostEqual(r['B'],100*(r['bpPercentile']+r['bpNormalized'])/2)
            self.assertAlmostEqual(r['score'],.65*r['E']+.35*r['B']);self.assertAlmostEqual(r['score'],r['eContribution']+r['bContribution'])
    def test_ties_zero_variance_are_neutral_not_nan_or_one_hundred(self):
        rows=[{'hero_id':i,'wRaw':.5,'bpRate':.1} for i in range(8)];result=score_pool(rows)
        for r in result.values():
            self.assertEqual(r['wZ'],0);self.assertEqual(r['bpZ'],0);self.assertEqual(r['wNormalized'],.5);self.assertEqual(r['bpNormalized'],.5)
            self.assertAlmostEqual(r['wPercentile'],4.5/8);self.assertLess(r['score'],60);self.assertTrue(math.isfinite(r['score']))
    def test_ties_use_average_raw_rank_and_permutation_does_not_change_heroes(self):
        rows=self.pool();rows[1]['bpRate']=rows[0]['bpRate'];a=score_pool(rows);b=score_pool(rows[::-1]);self.assertEqual(a,b)
        self.assertAlmostEqual(a[0]['bpPercentile'],1.5/8);self.assertEqual(a[0]['bpPercentile'],a[1]['bpPercentile'])
    def test_invalid_small_and_duplicate_pools_fail_without_fake_zero(self):
        self.assertEqual(score_pool(self.pool(MIN_POOL-1)),{})
        with self.assertRaises(ValueError):score_pool(self.pool()+[self.pool()[0]])
        rows=self.pool();rows[0]['wRaw']=float('nan')
        with self.assertRaises(ValueError):score_pool(rows)
        with self.assertRaises(ValueError):score_pool(self.pool(),1.2)
    def test_no_hero_specific_adjustment(self):
        rows=self.pool();a=score_pool(rows);relabel=[{**r,'hero_id':1000+r['hero_id']} for r in rows];b=score_pool(relabel)
        for hid,r in a.items():self.assertEqual(r,b[1000+hid])
    def test_bp_contract_uses_reported_same_basis_and_rejects_not_clips(self):
        good={'hero_id':1,'pickRate':.2,'banRate':.4,'bpRate':.6};bad={**good,'hero_id':2,'bpRate':.5};too_large={**good,'hero_id':3,'pickRate':.8}
        result=daily_bp_contract([good,bad,too_large]);self.assertTrue(result[1]['bp_valid']);self.assertFalse(result[2]['bp_valid']);self.assertIsNone(result[3]['bpRate'])
        rows=[{'hero_id':i,'picks':10+i,'pickRate':(10+i)/100,'bans':20+i,'banRate':(20+i)/100} for i in range(5)];rows[-1]['banRate']=.6
        result=official_bp_contract(rows);self.assertTrue(result[0]['bp_valid']);self.assertFalse(result[4]['bp_valid'])

class V2DatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.q=json.loads((ROOT/'data/reviewed_snapshot.json').read_text(encoding='utf-8'))['queries'];cls.rows=cls.q['model_rankings']['rows'];cls.contexts=cls.q['model_contexts']['rows']
        cls.lookup={(r['model'],r['context_id'],r['scope'],r['hero_id']):r for r in cls.rows}
    def test_v1_original_scores_remain_byte_equal_to_baseline(self):
        baseline=ROOT/'output/v1-baseline/strength_rankings.json'
        if baseline.exists():self.assertEqual(json.loads(baseline.read_text(encoding='utf-8')),self.q['strength_rankings']['rows'])
        old={(r['context_id'],r['hero_id']):r for r in self.q['strength_rankings']['rows']}
        for r in self.rows:
            if r['model']=='V1' and r['scope']=='全部英雄' and r['dimension']!='overall':self.assertEqual(r['score'],old[r['context_id'],r['hero_id']]['score'])
    def test_v1_all_original_tables_match_frozen_canonical_hashes(self):
        fixture=json.loads((ROOT/'tests/fixtures/v1-regression.json').read_text(encoding='utf-8'))
        for name,expected in fixture.items():
            actual=hashlib.sha256(json.dumps(self.q[name]['rows'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            self.assertEqual(actual,expected,name)
    def test_model_rankings_unique_keys_and_every_scored_v2_entry_is_canonical(self):
        self.assertEqual(len(self.lookup),len(self.rows))
        canonical={r['hero_id'] for r in self.q['coverage_audit']['rows']}
        for row in self.rows:
            if row['model']=='V2' and row['score'] is not None:self.assertIn(row['hero_id'],canonical)
    def test_all_ranks_and_contributions_reconcile(self):
        for c in self.contexts:
            rows=[r for r in self.rows if (r['model'],r['context_id'],r['scope'])==(c['model'],c['context_id'],c['scope'])];self.assertEqual(len(rows),len({r['hero_id'] for r in rows}))
            scored=[r for r in rows if r['score'] is not None];self.assertEqual([r['rank'] for r in scored],list(range(1,len(scored)+1)))
            self.assertEqual([r['score'] for r in scored],sorted((r['score'] for r in scored),reverse=True));self.assertEqual(len(scored),c['scored'])
            for row in rows:
                if row['score'] is None:self.assertIsNone(row['rank'])
                else:self.assertAlmostEqual(row['score'],row['eContribution']+row['bContribution']);self.assertGreaterEqual(row['score'],0);self.assertLessEqual(row['score'],100)
    def test_v2_z_pool_excludes_low_n_and_matches_actual_eligible_heroes(self):
        for c in self.contexts:
            if c['model']!='V2' or c['dimension']=='overall':continue
            rows=[r for r in self.rows if r['model']=='V2' and r['context_id']==c['context_id'] and r['scope']==c['scope'] and r['score'] is not None]
            if not rows:continue
            self.assertGreaterEqual(len(rows),MIN_POOL)
            for r in rows:
                self.assertEqual(r['comparisonN'],len(rows));self.assertAlmostEqual(r['wMean'],sum(r['wRaw'] for r in rows)/len(rows));self.assertNotIn(r['hero_id'],[50701,50702])
                if c['dimension']=='arena':self.assertGreaterEqual(r['battles'],30)
                else:self.assertIsNone(r['battles']);self.assertIsNone(r['lowerRate']);self.assertEqual(r['wRaw'],r['dailyWinRate'])
    def test_lane_statistics_are_recomputed_and_uniform_weights_match_same_components(self):
        found_difference=False
        for r in self.rows:
            if r['model']!='V2' or r['scope']=='全部英雄' or r['dimension']=='overall' or r['score'] is None:continue
            global_row=self.lookup['V2',r['context_id'],'全部英雄',r['hero_id']]
            self.assertAlmostEqual(r['weightE'],LANE_E_WEIGHTS[r['scope']]);self.assertAlmostEqual(r['uniformScore'],.65*r['E']+.35*r['B'])
            found_difference |= r['wMean']!=global_row['wMean'] or r['comparisonN']!=global_row['comparisonN']
        self.assertTrue(found_difference)
    def test_composite_30_70_and_daily_fallback_mixed_rank_with_explicit_basis(self):
        for r in self.rows:
            if r['dimension']!='overall':continue
            if r['score'] is None:
                self.assertIsNone(r['rank']);continue
            a=self.lookup[r['model'],'arena:'+r['league_id'],r['scope'],r['hero_id']]
            d=self.lookup[r['model'],'daily:'+r['segment'],r['scope'],r['hero_id']]
            if r['arenaScore'] is not None:
                self.assertIsNotNone(r['dailyScore']);self.assertAlmostEqual(r['score'],.3*r['arenaScore']+.7*r['dailyScore']);self.assertEqual(r['route'],'paired')
                self.assertEqual((r['tWeight'],r['dWeight']),(.3,.7));self.assertAlmostEqual(r['E'],.3*a['E']+.7*d['E'])
            else:
                self.assertEqual(r['score'],r['dailyScore']);self.assertEqual(r['route'],'daily_fallback')
                self.assertEqual((r['tWeight'],r['dWeight']),(0.,1.));self.assertEqual(r['scoreBasis'],'仅日常参考');self.assertTrue(r['arenaMissingReason']);self.assertEqual(r['E'],d['E'])
            self.assertAlmostEqual(r['bContribution'],r['tWeight']*(a['bContribution'] or 0)+r['dWeight']*d['bContribution'])
        for r in self.q['daily_observations']['rows']:self.assertEqual(r['score'],r['dailyScore'])
    def test_coverage_numbers_are_reconciled_not_assumed(self):
        coverage={r['context_id']:r for r in self.q['coverage_summary']['rows']};expected={'全分段':120,'巅峰赛1350+':128,'顶端排位':123,'巅峰千强':108}
        for segment,n in expected.items():
            c=coverage['daily:'+segment];self.assertEqual(c['完整有效'],n);self.assertEqual(c['recorded'],133);self.assertEqual(c['胜率缺失'],133-n)
        c=coverage['arena:20260003'];self.assertEqual((c['完整有效'],c['赛事场次不足'],c['完全无记录']),(56,43,34))
        for c in coverage.values():self.assertEqual(sum(c[k] for k in ['完整有效','完全无记录','胜率缺失','其他指标缺失','赛事场次不足','统计口径异常','玩法条目']),133)
    def test_temporal_pairs_and_validation_never_use_overlapping_windows(self):
        pairs=self.q['model_temporal_pairs']['rows'];self.assertTrue(pairs)
        for p in pairs:
            self.assertLess(p['previous_end'],p['target_start']);self.assertGreaterEqual(p['nextBattles'],30)
            r=self.lookup['V2','arena:'+p['previous_league_id'],p['scope'],p['hero_id']];self.assertEqual(r['score'],p['v2Score'])
        for r in self.q['model_temporal_validation']['rows']:self.assertGreaterEqual(r['paired_heroes'],8);self.assertLess(r['previous_end'],r['target_start'])
        self.assertTrue(any('重叠' in r['reason'] for r in self.q['model_temporal_exclusions']['rows']))
    def test_three_bp_anomalies_are_excluded_only_in_v2(self):
        anomalies=[r for r in self.q['coverage_audit']['rows'] if r['dimension']=='arena' and r['category']=='统计口径异常' and 'BP计数' in r['reason']]
        self.assertTrue(anomalies)
        for r in anomalies:self.assertIsNone(self.lookup['V2',r['context_id'],'全部英雄',r['hero_id']]['score'])
if __name__=='__main__':unittest.main()
