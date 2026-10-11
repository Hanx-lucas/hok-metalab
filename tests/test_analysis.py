import json
import math
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
if (ROOT/".deps").exists():sys.path.insert(0,str(ROOT/".deps"))
from hoklab.analyze import percentage,normalize,model
import numpy as np
import pandas as pd

class AnalysisChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=json.loads((ROOT/"data/processed/hero_metrics.json").read_text(encoding="utf-8"))
        cls.df=pd.DataFrame(cls.rows)
    def test_percentage_fraction_not_divided_twice(self):
        self.assertEqual(percentage(.525),.525)
        self.assertAlmostEqual(percentage("52.5%"),.525)
        self.assertAlmostEqual(percentage("17.4%（4次）"),.174)
        self.assertEqual(percentage("0%"),0)
    def test_invalid_percentage_rejected(self):
        for value in ["wrong","-2%","101%"]:
            with self.assertRaises(ValueError):percentage(value)
    def test_compound_key_unique(self):
        self.assertFalse(self.df.duplicated(["league_id","hero_id"]).any())
    def test_raw_hashes_and_schema(self):
        raw,leagues,manifest,issues,heroes=normalize()
        self.assertEqual(len(raw),len(self.df))
        self.assertGreaterEqual(len(manifest),30)
    def test_missing_bp_is_not_zero(self):
        old=self.df[self.df.year.eq(2019)]
        self.assertEqual(len(old),385)
        self.assertTrue(old.pickRate.isna().all())
        self.assertTrue(old.banRate.isna().all())
        self.assertTrue(old.score.isna().all())
        coverage=pd.read_csv(ROOT/"data/processed/coverage.csv")
        self.assertTrue(coverage.loc[coverage.year.eq(2019),["pickRateSum","banRateSum"]].isna().all().all())
    def test_inconsistent_counts_excluded_from_posterior(self):
        bad=self.df[~self.df.sample_coherent]
        self.assertEqual(len(bad),20)
        self.assertTrue(bad.posteriorRate.isna().all())
    def test_beta_formula_and_bounds(self):
        good=self.df[self.df.posteriorRate.notna()]
        expected=(good.wins+10)/(good.battles+20)
        np.testing.assert_allclose(good.posteriorRate,expected)
        self.assertTrue(((good.lowerRate<=good.posteriorRate)&(good.posteriorRate<=good.upperRate)).all())
        self.assertTrue(good.probAbove50.between(0,1).all())
    def test_weighted_index_reconciles(self):
        good=self.df[self.df.score.notna()]
        expected=100*(.6*good.winPercentile+.25*good.pickPercentile+.15*good.banPercentile)
        np.testing.assert_allclose(good.score,expected,atol=1e-10)
        self.assertTrue(good.top10WeightShare.between(0,1).all())
    def test_score_missing_without_bp(self):
        self.assertTrue(self.df[self.df.pickRate.isna()|self.df.banRate.isna()].score.isna().all())
    def test_manual_data_kept_separate_and_no_fake_n(self):
        manual=json.loads((ROOT/"data/processed/legacy_manual.json").read_text(encoding="utf-8"))
        self.assertEqual(len(manual),127)
        self.assertEqual(set(r['source_class'] for r in manual),{'user_manual_unverified'})
        self.assertTrue(all(r['sample_size'] is None for r in manual))
    def test_temporal_backtest_has_minimum_training_and_three_baselines(self):
        m=pd.read_csv(ROOT/"data/processed/backtest.csv")
        self.assertTrue((m.train_events>=3).all())
        self.assertEqual(set(m.model),{'岭回归','50%基线','上一届平滑胜率','近三届合并平滑'})
        self.assertTrue((m.groupby('league_id').model.nunique()==4).all())
        self.assertTrue((m.train_latest_target_end < m.test_event_start).all())
    def test_weight_scenarios_stable_when_other_events_added(self):
        event=self.df[self.df.league_id.eq("20260003")]
        alone,_=model(event)
        np.testing.assert_allclose(alone.top10WeightShare,event.top10WeightShare,equal_nan=True)
    def test_overlapping_catalog_window_excluded(self):
        excluded=json.loads((ROOT/'data/processed/backtest_exclusions.json').read_text(encoding='utf-8'))
        self.assertTrue(any(r['target_league_id']=='20250002' for r in excluded))
        evaluated=pd.read_csv(ROOT/'data/processed/backtest.csv')
        self.assertNotIn(20250002,set(evaluated.league_id))
    def test_invalid_beta_prior_rejected(self):
        for prior in [0,-1,float('nan'),float('inf')]:
            with self.assertRaises(ValueError): model(self.df.iloc[:3],prior=prior)

if __name__=='__main__':unittest.main(verbosity=2)
