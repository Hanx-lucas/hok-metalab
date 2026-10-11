"""Normalize, audit, model and export; no invented rows or denominators."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from scipy.stats import beta, spearmanr
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://prod.comp.smoba.qq.com/leaguesite"
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
ROLES = {"1": "对抗路", "2": "打野", "3": "中路", "4": "发育路", "5": "游走"}
PROFESSIONS = {1: "战士", 2: "法师", 3: "坦克", 4: "刺客", 5: "射手", 6: "辅助"}

def load(name):
    return json.loads((RAW / f"{name}.json").read_text(encoding="utf-8"))

def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")

def clean(obj):
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean(v) for v in obj]
    if isinstance(obj, (np.integer, np.floating)):
        obj = obj.item()
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    return obj

def percentage(value):
    """Text percentages and Excel fraction cells; never divide a fraction twice."""
    import re
    if pd.isna(value):
        return None
    if isinstance(value, str):
        match = re.match(r"\s*(-?\d+(?:\.\d+)?)\s*(%)?", value)
        if not match:
            raise ValueError(f"Invalid percentage: {value!r}")
        number = float(match[1])
        result = number / 100 if match[2] or number > 1 else number
    else:
        number = float(value)
        result = number / 100 if number > 1 else number
    if not 0 <= result <= 1:
        raise ValueError(f"Out-of-range percentage: {value!r}")
    return result

def normalize():
    catalog = load("heroes")
    hero_lookup = {int(h["ename"]): h for h in catalog}
    leagues = load("leagues")["results"]
    observations = []
    quality = []
    sources = []
    for league in sorted(leagues, key=lambda e: e["start_time"]):
        lid = str(league["league_id"])
        path = RAW / f"league_{lid}.json"
        if not path.exists():
            continue
        records = json.loads(path.read_text(encoding="utf-8")).get("data", [])
        bp_unavailable = bool(records) and all(all(r.get("bp_statistics_info",{}).get(field,0)==0 for field in ["pick_num","pick_rate","ban_num","ban_rate"]) for r in records) and any(r.get("statistics_info",{}).get("battle_count",0)>0 for r in records)
        meta = load(f"league_{lid}.meta")
        if hashlib.sha256(path.read_bytes()).hexdigest() != meta["sha256"]:
            raise ValueError(f"Raw hash mismatch: {lid}")
        sources.append({**meta, "league_id": lid, "name": league["league_name"], "classification": "official_public_aggregate"})
        for row in records:
            hero = row["hero_info"]
            stats = row.get("statistics_info", {})
            bp = row.get("bp_statistics_info", {})
            if bp_unavailable:
                # Entire-event zero BP with positive appearances is a missing block.
                bp = {"pick_rate":None,"ban_rate":None,"pick_num":None,"ban_num":None}
            hid = int(hero["hero_id"])
            info = hero_lookup.get(hid, {})
            roles = [ROLES[r] for r in str(info.get("roles", "")).split("|") if r in ROLES]
            n = stats.get("battle_count")
            w = stats.get("victory_battle_count")
            loss = stats.get("defeated_battle_count")
            wr = stats.get("win_rate")
            flags = []
            if bp_unavailable:
                flags.append("bp_not_recorded_all_zero_block")
            for field, value in [("win_rate", wr), ("pick_rate", bp.get("pick_rate")), ("ban_rate", bp.get("ban_rate"))]:
                if bp_unavailable and field in ("pick_rate", "ban_rate"):
                    continue
                if value is None or not isinstance(value, (int, float)) or not 0 <= value <= 1:
                    flags.append(f"invalid_{field}")
            coherent = all(isinstance(v, (int, float)) and v >= 0 and int(v) == v for v in [n, w, loss]) and n > 0 and w + loss == n
            if not coherent:
                flags.append("outcome_counts_inconsistent")
            if coherent and abs(w / n - (wr if wr is not None else -1)) > 0.000061:
                flags.append("win_rate_count_mismatch")
                coherent = False
            if not bp_unavailable and bp.get("pick_num") != n:
                flags.append("bp_pick_differs_from_battle_count")
            pr, br = bp.get("pick_rate"), bp.get("ban_rate")
            if pr is not None and br is not None and pr + br > 1.00011:
                flags.append("bp_sum_over_one")
            for flag in flags:
                quality.append({"league_id": lid, "hero_id": hid, "hero": hero["hero_name"], "issue": flag})
            observations.append({"league_id": lid, "event": league["league_name"], "year": int(league["year"]), "event_start": league["start_time"][:10], "event_end": league["end_time"][:10], "event_status": "已结束" if league["status"] == 2 else "进行中", "hero_id": hid, "hero": hero["hero_name"], "current_name": info.get("cname", hero["hero_name"]), "role": roles[0] if roles else "未知", "roles": "/".join(roles), "profession": PROFESSIONS.get(info.get("hero_type"), "未知"), "winRate": wr, "pickRate": pr, "banRate": br, "battles": n, "wins": w, "losses": loss, "picks": bp.get("pick_num"), "bans": bp.get("ban_num"), "kda": stats.get("avg_kda"), "gold": stats.get("avg_gold"), "sample_coherent": bool(coherent), "quality_flags": ";".join(flags), "source_class": "official_public_aggregate", "retrieved_at": meta["retrieved_at"]})
    df = pd.DataFrame(observations)
    if df.duplicated(["league_id", "hero_id"]).any():
        raise ValueError("Duplicate league x hero IDs; manual resolution required")
    return df, leagues, sources, quality, hero_lookup

def model(df, prior=20, seed=241098181):
    if not math.isfinite(prior) or prior <= 0:
        raise ValueError("Beta prior must be positive and finite")
    df = df.copy()
    valid = df.sample_coherent & df.winRate.between(0, 1)
    df["posteriorRate"] = np.nan
    df["lowerRate"] = np.nan
    df["upperRate"] = np.nan
    df["probAbove50"] = np.nan
    a = df.loc[valid, "wins"] + prior / 2
    b = df.loc[valid, "losses"] + prior / 2
    df.loc[valid, "posteriorRate"] = a / (a+b)
    df.loc[valid, "lowerRate"] = beta.ppf(0.025, a, b)
    df.loc[valid, "upperRate"] = beta.ppf(0.975, a, b)
    df.loc[valid, "probAbove50"] = beta.sf(0.5, a, b)
    for col in ["score", "rank", "winPercentile", "pickPercentile", "banPercentile", "top10WeightShare", "rankP10", "rankP90", "pareto"]:
        df[col] = np.nan
    sensitivity = []
    for lid, group in df.groupby("league_id", sort=False):
        eligible = group[group.sample_coherent & group.posteriorRate.notna() & group.pickRate.between(0,1) & group.banRate.between(0,1) & ((group.pickRate+group.banRate)<=1.00011)].copy()
        if eligible.empty:
            continue
        ranks = np.column_stack([eligible[c].rank(pct=True, method="average").to_numpy() for c in ["posteriorRate", "pickRate", "banRate"]])
        score = 100 * ranks @ np.array([0.60, 0.25, 0.15])
        df.loc[eligible.index, ["winPercentile", "pickPercentile", "banPercentile"]] = ranks
        df.loc[eligible.index, "score"] = score
        df.loc[eligible.index, "rank"] = pd.Series(score, index=eligible.index).rank(ascending=False, method="min")
        weights = np.random.default_rng(seed + int(lid)).dirichlet([12, 5, 3], size=1000)
        scores = ranks @ weights.T
        sim_ranks = np.argsort(np.argsort(-scores, axis=0), axis=0)+1
        df.loc[eligible.index, "top10WeightShare"] = (sim_ranks <= min(10, len(eligible))).mean(axis=1)
        df.loc[eligible.index, "rankP10"] = np.quantile(sim_ranks, .1, axis=1)
        df.loc[eligible.index, "rankP90"] = np.quantile(sim_ranks, .9, axis=1)
        vals = eligible[["posteriorRate", "pickRate", "banRate"]].to_numpy()
        frontier = [not np.any(np.all(vals >= v, axis=1) & np.any(vals > v, axis=1)) for v in vals]
        df.loc[eligible.index, "pareto"] = np.array(frontier, dtype=int)
        base_rank = pd.Series(score).rank(ascending=False).to_numpy()
        for lam in [0, 10, 20, 50, 100]:
            rates = (eligible.wins.to_numpy() + lam/2)/(eligible.battles.to_numpy()+lam)
            alt = pd.Series(rates).rank(pct=True).to_numpy()*.6 + ranks[:,1]*.25+ranks[:,2]*.15
            rho = float(spearmanr(base_rank, pd.Series(alt).rank(ascending=False)).statistic) if len(eligible)>2 else None
            sensitivity.append({"league_id": lid, "event": group.event.iloc[0], "prior": lam, "spearman": rho})
    df["bpPressure"] = df.pickRate + df.banRate
    df["legacyIndex"] = df.pickRate * df.winRate
    df["sample_band"] = np.where(~df.sample_coherent, "口径异常", np.where(df.battles < 30, "小样本 <30", np.where(df.battles < 100, "中样本 30–99", "大样本 ≥100")))
    return df, sensitivity

def backtest(df, leagues):
    """One regular KPL event ahead; expanding training, never random split."""
    ids=[str(e["league_id"]) for e in sorted(leagues,key=lambda x:x["start_time"]) if any(x in e["league_name"] for x in ["KPL春季赛", "KPL秋季赛", "KPL夏季赛"]) and "季前" not in e["league_name"] and e["status"]==2]
    frames=[]
    exclusions=[]
    for i in range(1,len(ids)):
        prev=df[(df.league_id==ids[i-1]) & df.sample_coherent]
        cur=df[(df.league_id==ids[i]) & df.sample_coherent]
        if prev.empty or cur.empty:
            continue
        # A previous aggregate must have a closed catalog window at prediction time.
        if prev.event_end.max() >= cur.event_start.min():
            exclusions.append({"previous_league_id":ids[i-1],"previous_event":prev.event.iloc[0],"previous_catalog_end":prev.event_end.max(),"target_league_id":ids[i],"target_event":cur.event.iloc[0],"target_catalog_start":cur.event_start.min(),"reason":"previous_catalog_window_not_closed_by_target_start"})
            continue
        joined=prev.merge(cur,on="hero_id",suffixes=("_previous","_target"))
        if joined.empty:
            continue
        hist=df[(df.league_id.isin(ids[max(0,i-3):i])) & (df.event_end < cur.event_start.min()) & df.sample_coherent].groupby("hero_id").agg(wins=("wins","sum"), battles=("battles","sum"))
        joined["rollingRate"]=joined.hero_id.map((hist.wins+10)/(hist.battles+20))
        joined["logBattles"]=np.log1p(joined.battles_previous)
        joined["target_index"]=i
        frames.append(joined)
    if not frames:
        return [], [], exclusions
    transitions=pd.concat(frames,ignore_index=True)
    features=["posteriorRate_previous","pickRate_previous","banRate_previous","logBattles","rollingRate"]
    metrics=[]
    predictions=[]
    for i in sorted(transitions.target_index.unique()):
        test_date=transitions.loc[transitions.target_index==i,"event_start_target"].min()
        train=transitions[(transitions.target_index<i) & (transitions.event_end_target<test_date)].dropna(subset=features+["winRate_target"])
        test=transitions[transitions.target_index==i].dropna(subset=features+["winRate_target"])
        if train.target_index.nunique()<3 or len(test)<10:
            continue
        train_cutoff = train.event_end_target.max()
        test_date = test.event_start_target.min()
        if train_cutoff >= test_date:
            raise ValueError("Temporal leakage: a training target overlaps the test event")
        estimator=make_pipeline(StandardScaler(),Ridge(alpha=10))
        estimator.fit(train[features],train.winRate_target,ridge__sample_weight=np.sqrt(train.battles_target))
        preds={"50%基线": np.full(len(test),.5), "上一届平滑胜率":test.posteriorRate_previous.to_numpy(), "近三届合并平滑":test.rollingRate.to_numpy(), "岭回归":np.clip(estimator.predict(test[features]),0,1)}
        for label,p in preds.items():
            error=np.abs(p-test.winRate_target.to_numpy())
            brier=(test.wins_target.to_numpy()*(1-p)**2+test.losses_target.to_numpy()*p**2)/test.battles_target.to_numpy()
            metrics.append({"event":test.event_target.iloc[0],"league_id":str(test.league_id_target.iloc[0]),"model":label,"maePP":float(error.mean()*100),"weightedMaePP":float(np.average(error,weights=test.battles_target)*100),"brier":float(np.average(brier,weights=test.battles_target)),"hero_count":len(test),"train_rows":len(train),"train_events":int(train.target_index.nunique()),"train_latest_target_end":train_cutoff,"test_event_start":test_date,"test_battles":int(test.battles_target.sum())})
        for row,p in zip(test.to_dict("records"),preds["岭回归"]):
            predictions.append({"league_id":str(row["league_id_target"]),"event":row["event_target"],"hero":row["hero_target"],"hero_id":int(row["hero_id"]),"actualRate":row["winRate_target"],"predictedRate":float(p),"battles":int(row["battles_target"])})
    return metrics,predictions,exclusions

def legacy_data(hero_lookup):
    rows=[]
    lookup={h["cname"]:hid for hid,h in hero_lookup.items()}
    def add(season,hero,role,wr,pr,br,filename):
        rows.append({"season":season,"hero":str(hero).strip(),"hero_id":lookup.get(str(hero).strip()),"role":str(role),"winRate":percentage(wr),"pickRate":percentage(pr),"banRate":percentage(br),"source_class":"user_manual_unverified","source_file":filename,"segment":"原表未记录","sample_size":None})
    p=ROOT.parent/"hero stata s37 38.xlsx"
    if p.exists():
        for r in pd.read_excel(p).itertuples(index=False,name=None):
            if len(r)>=6 and pd.notna(r[2]):
                add(str(r[0]),r[2],r[1],*r[3:6],p.name)
    p=ROOT.parent/"hero stata s39 .xlsx"
    if p.exists():
        for r in pd.read_excel(p,header=None).itertuples(index=False,name=None):
            if len(r)>=5 and pd.notna(r[0]) and isinstance(r[2],str) and "%" in r[2]:
                add("S39",r[0],r[1],*r[2:5],p.name)
    return rows

def camp_data(hero_lookup):
    rows=[]
    for p in RAW.glob("camp_*.json"):
        if p.name.endswith(".meta.json"):
            continue
        obj=json.loads(p.read_text(encoding="utf-8"))
        meta=json.loads(p.with_suffix(".meta.json").read_text(encoding="utf-8"))
        if hashlib.sha256(p.read_bytes()).hexdigest() != meta["sha256"]:
            raise ValueError(f"Authorized camp snapshot hash mismatch: {p.name}")
        segment=meta["request_body"]["segment"]
        name={1:"全分段",3:"巅峰赛1350+",4:"顶端排位"}[segment]
        for r in obj.get("data",{}).get("list",[]):
            info=r["heroInfo"]
            rows.append({"hero_id":int(r["heroId"]),"hero":info["heroName"],"segment":name,"winRate":percentage(r.get("winRate")),"pickRate":percentage(r.get("showRate")),"banRate":percentage(r.get("banRate")),"update_time":obj["data"].get("updateTime"),"retrieved_at":meta["retrieved_at"],"source_class":"authorized_camp_aggregate","sample_size":None,"season": "未提供"})
    return rows

def build(prior=20):
    PROCESSED.mkdir(parents=True,exist_ok=True)
    df,leagues,sources,quality,hero_lookup=normalize()
    modeled,sensitivity=model(df,prior)
    metrics,predictions,exclusions=backtest(modeled,leagues)
    legacy=legacy_data(hero_lookup)
    camp=camp_data(hero_lookup)
    coverage=[]
    for lid,g in modeled.groupby("league_id",sort=False):
        sums={"league_id":lid,"event":g.event.iloc[0],"year":int(g.year.iloc[0]),"event_start":g.event_start.iloc[0],"event_status":g.event_status.iloc[0],"heroes":len(g),"eligible":int(g.score.notna().sum()),"hero_appearances":int(g.battles.sum()),"coherent_appearances":int(g.loc[g.sample_coherent,"battles"].sum()),"flagged_heroes":int(g.quality_flags.ne("").sum()),"pickRateSum":float(g.pickRate.sum(min_count=1)),"banRateSum":float(g.banRate.sum(min_count=1)),"win_total":int(g.wins.sum()),"loss_total":int(g.losses.sum())}
        estimates=g.loc[(g.pickRate>0)&(g.picks>0),"picks"]/g.loc[(g.pickRate>0)&(g.picks>0),"pickRate"]
        sums["bp_games_inferred"]=int(round(estimates.median())) if len(estimates) else None
        sums["denominator_note"]="由 picks / 公布 pickRate 中位数估计；受四位小数舍入及源口径异常影响，不作为精确比赛总数"
        coverage.append(sums)
    completed=modeled[(modeled.event_status=="已结束") & modeled.event.str.contains("KPL") & ~modeled.event.str.contains("季前|选拔")]
    latest=completed.sort_values("event_start").league_id.iloc[-1]
    top=modeled[(modeled.league_id==latest)&modeled.score.notna()].sort_values("score",ascending=False)
    summary={"official_events":len(coverage),"official_rows":len(modeled),"official_heroes":int(modeled.hero_id.nunique()),"years":sorted(modeled.year.unique().tolist()),"hero_appearances":int(modeled.battles.sum()),"quality_issue_count":len(quality),"incoherent_rows":int((~modeled.sample_coherent).sum()),"legacy_rows":len(legacy),"camp_rows":len(camp),"latest_completed_league":latest,"latest_completed_event":top.event.iloc[0],"top_heroes":top.head(10)[["hero","score","posteriorRate","winRate","pickRate","banRate","battles","lowerRate","upperRate","top10WeightShare"]].to_dict("records"),"backtest_summaries":pd.DataFrame(metrics).groupby("model")[["maePP","weightedMaePP","brier"]].mean().reset_index().to_dict("records") if metrics else [],"prior":prior,"weight_scenarios":1000,"random_seed":241098181}
    summary["backtest_event_count"]=len({r["league_id"] for r in metrics})
    summary["backtest_excluded_transitions"]=exclusions
    from .seasonal import seasonal_evidence
    season_summary,season_leaders,strength_history=seasonal_evidence(clean(modeled.to_dict('records')),coverage,latest)
    for name,items in [("hero_metrics",modeled.to_dict("records")),("coverage",coverage),("quality_issues",quality),("sensitivity",sensitivity),("backtest",metrics),("backtest_exclusions",exclusions),("predictions",predictions),("legacy_manual",legacy),("camp",camp),("season_summary",season_summary),("season_leaders",season_leaders),("strength_history",strength_history)]:
        pd.DataFrame(items).to_csv(PROCESSED/f"{name}.csv",index=False,encoding="utf-8-sig")
        dump(PROCESSED/f"{name}.json",clean(items))
    dump(PROCESSED/"summary.json",clean(summary))
    dump(PROCESSED/"source_manifest.json",sources)
    with sqlite3.connect(PROCESSED/"hoklab.sqlite") as conn:
        for name,items in [("hero_metrics",modeled), ("coverage",pd.DataFrame(coverage)), ("quality_issues",pd.DataFrame(quality)), ("backtest",pd.DataFrame(metrics)), ("legacy_manual",pd.DataFrame(legacy))]:
            if len(items):
                items.to_sql(name,conn,index=False,if_exists="replace")
        conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS hero_event_key ON hero_metrics(league_id, hero_id)')
    snapshot={"id":"hok-metalab-xhan-20261011","surface":"dashboard","title":"王者荣耀 · MetaLab","generatedAt":datetime.now(timezone.utc).isoformat(),"buildStatus":"creating","status":"reviewed","filters":[],"queries":{}}
    for name in ["hero_metrics","coverage","quality_issues","sensitivity","backtest","backtest_exclusions","legacy_manual","camp","season_summary","season_leaders","strength_history"]:
        snapshot["queries"][name]={"rows":clean(json.loads((PROCESSED/f"{name}.json").read_text(encoding="utf-8"))),"source":{"title": "腾讯公开赛事英雄汇总" if name not in ["legacy_manual","camp"] else ("原项目手工录入，未独立核验" if name=="legacy_manual" else "王者营地授权快照；未提供场次与赛季"),"provider":"Tencent / project analysis" if name not in ["legacy_manual","camp"] else "User supplied / authorized camp","executedAt":max(s["retrieved_at"] for s in sources),"tables":[name],"links":[{"label":"赛事接口", "url":BASE+"/leagues/open"},{"label":"英雄资料", "url":"https://pvp.qq.com/web201605/js/herolist.json"}],"caveats":["聚合数据无法控制选手、阵容、对手与版本混杂，结果不表示英雄的因果强度。","roles为当前目录推荐分路集合，role取其首个标签；未验证历史实战分路。","beta 95% 可信区间依赖独立同分布二项模型，未校正同局、战队及全局BP相关性。","赛事ID是赛事届次，不等同游戏S赛季。","选用场次与战斗场次可能不一致，完整保留并标记。"],"metricDefinitions":[{"label":"综合表现指数","definition":"同赛事有效英雄分位数加权：60%平滑胜率 + 25%选用率 + 15%禁用率；0–100相对指数，权重由分析者设定，非胜率预测。"},{"label":"平滑胜率","definition":f"(胜场 + {prior/2:g}) / (战斗场次 + {prior:g})；Beta({prior/2:g},{prior/2:g})先验。计数异常时不计算。"},{"label":"权重稳健度","definition":"1000组Dirichlet(12,5,3)权重下进入前10的占比，反映模型权重敏感性，不是实际胜率或采样置信度。"}],"evidenceFlow":[{"title":"公开目录与原始响应","detail":"hoklab.collect 按官方赛事目录逐届GET；SHA256、URL、请求时间及HTTP状态保存在data/raw/*.meta.json。"},{"title":"规范化、验证和建模","detail":"python -m hoklab.analyze；校验百分比、复合主键与胜负计数；异常记录保留，样本不一致者不进入贝叶斯建模；所有方法见hoklab/analyze.py。"},{"title":"时间回测","detail":"仅常规KPL春夏秋季赛；以前届数据预测下一届，扩展训练窗口，至少3届训练过渡；未做随机切分。"}]},"methods":[{"language":"python","code":"python -m hoklab.analyze --prior 20"}]}
    snapshot["queries"]["summary"]={"rows":[clean(summary)],"payloadColumns":["years","top_heroes","backtest_summaries","backtest_excluded_transitions"],"source":snapshot["queries"]["hero_metrics"]["source"]}
    for name in ('season_summary','season_leaders','strength_history'):
        source=snapshot['queries'][name]['source']
        source['title']='腾讯赛事汇总的逐届强势英雄与相对表现变化'
        source['metricDefinitions'].append({'label':'逐届榜单筛选','definition':'至少30场、计数一致。BP完整时按既有综合指数排序；BP缺失时仅按平滑胜率提供胜率证据，不混为三维排名。'})
        source['caveats'].append('强度图为每届相对表现指数，小于30场或缺少有效BP时留空；指数高低不代表跨赛季绝对战力变化。热力图选择最新届前三与历史前五出现频次最高的英雄，共至多12位，以ID关联。')
    snapshot["queries"]["backtest"]["source"]["caveats"].append("仅使用目录结束窗口早于目标开始窗口的聚合数据；重叠过渡排除。当前响应为回顾性快照，没有真实历史时点的不可变快照，不能证明线上预测效果。")
    excluded_source=snapshot["queries"]["backtest_exclusions"]["source"]
    excluded_source["title"]="腾讯官方赛事目录：回测时间窗排除审计"
    excluded_source["metricDefinitions"]=[]
    excluded_source["evidenceFlow"]=[{"title":"读取官方目录窗口","detail":"保留原始start_time与end_time，不自行改成推测的赛程日期。"},{"title":"保守判断数据可用性","detail":"前届结束窗口晚于或等于目标届次开始窗口时，排除该预测过渡。"}]
    excluded_source["caveats"]=["官方目录窗口可能不同于实际最后比赛日；没有可靠历史时点证据时保守排除，不声称数据在预测时点可用。"]
    definitions={
        "coverage":[{"label":"英雄观察","definition":"同一赛事的唯一英雄ID数；全库相加为英雄×赛事行数。赛事届次不等同游戏S赛季。"},{"label":"英雄战斗记录","definition":"统计块battle_count之和，同局多英雄重复计数，不是独立比赛局数。"},{"label":"BP分母估计","definition":"正值picks/pickRate的中位数四舍五入，仅用于诊断；不作为精确比赛总数。"}],
        "backtest":[{"label":"场次加权MAE","definition":"100 × sum(目标battles × abs(预测胜率−公布目标胜率)) / sum(目标battles)，单位为百分点；报告再对测试届次等权平均。"},{"label":"Brier","definition":"单英雄为[wins×(1−p)^2 + losses×p^2]/battles，单届按battles加权；不是对同局相关样本的显著性检验。"},{"label":"训练可用性","definition":"仅过去过渡且训练标签目录结束早于测试开始；前届与目标窗口重叠的过渡排除；StandardScaler仅拟合训练集，Ridge alpha=10。"}],
        "quality_issues":[{"label":"质量标记行","definition":"一行一个英雄×赛事×检查项；同一个英雄观察可能触发多项检查，不等于独立坏记录数。"}],
        "sensitivity":[{"label":"先验等效场次","definition":"0、10、20、50、100分别重算平滑胜率与指数；0仅用于均值敏感性，不计算Beta(0,0)区间。"},{"label":"Spearman","definition":"同赛事下替代先验指数名次与默认指数名次的Spearman相关系数，不是未来预测性能。"}],
    }
    for query_id,items in definitions.items():
        snapshot["queries"][query_id]["source"]["metricDefinitions"]=items
    legacy_source=snapshot["queries"]["legacy_manual"]["source"]
    legacy_source["classification"]="user_manual_unverified"
    legacy_source.pop("executedAt", None)
    legacy_source["links"]=[]
    legacy_source["files"]=["hero stata s37 38.xlsx","hero stata s39 .xlsx"]
    legacy_source["metricDefinitions"]=[]
    legacy_source["caveats"]=["用户说明原表为王者营地榜单手工收集；未独立核验。分段、日期、场次未记录。缺失英雄不补零，不用于贝叶斯分析。"]
    legacy_source["evidenceFlow"]=[{"title":"原项目工作簿","detail":"按实际工作簿表头逐行读取，保留S37、S38、S39标签及原表职业定位；不补造赛季和分段。"}]
    snapshot["queries"]["camp"]["source"]["classification"]="authorized_camp_aggregate" if camp else "unavailable"
    camp_source=snapshot["queries"]["camp"]["source"]
    camp_source["links"]=[{"label":"授权营地接口","url":"https://kohcamp.qq.com/hero/getdetailranklistbyid"}]
    camp_source["metricDefinitions"]=[]
    camp_source["evidenceFlow"]=[{"title":"用户授权快照","detail":"凭据从环境变量或本机private/camp_headers.json读取；原始响应和不含凭据的元数据保存。未记录样本场次与S赛季时不推断。"}]
    camp_source["caveats"]=["当前没有授权或历史快照。" if not camp else "授权榜单未提供分母、每局记录与赛季映射，只作描述比较。"]
    if camp:
        camp_source["executedAt"]=max(r["retrieved_at"] for r in camp)
    else:
        camp_source.pop("executedAt",None)
    from hoklab.daily import build_daily_queries
    build_daily_queries(snapshot)
    from hoklab.strength import build_strength_queries
    build_strength_queries(snapshot)
    dump(ROOT/"data"/"reviewed_snapshot.json",snapshot)
    print(json.dumps(clean(summary),ensure_ascii=False,indent=2))
    return summary

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prior",type=float,default=20)
    args=parser.parse_args()
    if args.prior<=0:
        parser.error("prior must be positive")
    build(args.prior)
