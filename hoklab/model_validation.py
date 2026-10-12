"""Fixed-grid sensitivity and strictly chronological descriptive associations."""
from __future__ import annotations
from collections import defaultdict
from statistics import mean
import math
import numpy as np
from scipy.stats import spearmanr

E_WEIGHTS=[.55,.60,.65,.70,.75]
SCENE_WEIGHTS=[.25,.30,.40,.50,.60,.75]

def rho(x,y):
    if len(x)<8 or len(set(x))<2 or len(set(y))<2:return None
    value=float(spearmanr(x,y).statistic)
    return value if math.isfinite(value) else None

def sorted_rows(rows,key='score'):
    return sorted([r for r in rows if r.get(key) is not None],key=lambda r:(-r[key],r['hero_id']))

def overlap(a,b,n=10):
    n=min(n,len(a),len(b))
    return len(set(r['hero_id'] for r in a[:n])&set(r['hero_id'] for r in b[:n]))/n if n else None

def build_validation(rows,contexts,snapshot):
    q=snapshot['queries'];groups=defaultdict(list)
    for row in rows:groups[row['model'],row['context_id'],row['scope']].append(row)
    comparisons=[];sensitivity=[];representatives=[];lane_coverage=[]
    for c in contexts:
        key=c['model'],c['context_id'],c['scope'];pool=sorted_rows(groups[key])
        if c['model']=='V2':
            for weight in E_WEIGHTS:
                alternate=sorted([{**r,'score':weight*r['E']+(1-weight)*r['B']} for r in pool],key=lambda r:(-r['score'],r['hero_id']))
                match={r['hero_id']:r['score'] for r in alternate}
                sensitivity.append({'context_id':c['context_id'],'dimension':c['dimension'],'scope':c['scope'],'event':c['event'],'segment':c['segment'],
                    'experiment':'E/B权重','e_weight':weight,'t_weight':None,'heroes':len(pool),'rank_spearman':rho([r['score'] for r in pool],[match[r['hero_id']] for r in pool]),
                    'top10_retained':overlap(pool,alternate),'top3':'、'.join(r['hero'] for r in alternate[:3])})
            if c['dimension']=='overall':
                for tweight in SCENE_WEIGHTS:
                    alternate=sorted([{**r,'score':tweight*r['arenaScore']+(1-tweight)*r['dailyScore'] if r['arenaScore'] is not None else r['dailyScore']} for r in pool],key=lambda r:(-r['score'],r['hero_id']))
                    match={r['hero_id']:r['score'] for r in alternate}
                    sensitivity.append({'context_id':c['context_id'],'dimension':c['dimension'],'scope':c['scope'],'event':c['event'],'segment':c['segment'],
                        'experiment':'T/D场景权重','e_weight':None,'t_weight':tweight,'heroes':len(pool),'rank_spearman':rho([r['score'] for r in pool],[match[r['hero_id']] for r in pool]),
                        'top10_retained':overlap(pool,alternate),'top3':'、'.join(r['hero'] for r in alternate[:3])})
            previous={r['hero_id']:r for r in sorted_rows(groups['V1',c['context_id'],c['scope']])};joined=[r for r in pool if r['hero_id'] in previous]
            v1=sorted([previous[r['hero_id']] for r in joined],key=lambda r:(-r['score'],r['hero_id']));v2=sorted_rows(joined)
            comparisons.append({'context_id':c['context_id'],'dimension':c['dimension'],'scope':c['scope'],'event':c['event'],'segment':c['segment'],
                'paired_heroes':len(joined),'v1_scored':len(previous),'v2_scored':len(pool),'same_pool_rank_spearman':rho([r['score'] for r in joined],[previous[r['hero_id']]['score'] for r in joined]),
                'same_pool_top10_retained':overlap(v1,v2),'uniform_vs_lane_rank_spearman':rho([r['score'] for r in pool],[r['uniformScore'] for r in pool]) if c['scope']!='全部英雄' else None,
                'uniform_vs_lane_top10_retained':overlap(pool,sorted_rows(pool,'uniformScore')) if c['scope']!='全部英雄' else None})
            if c['scope']!='全部英雄' and (c['dimension']=='daily' or c['league_id']==str(q['summary']['rows'][0]['latest_completed_league'])):
                lane_coverage.append({'context_id':c['context_id'],'dimension':c['dimension'],'segment':c['segment'],'event':c['event'],'lane':c['scope'],
                    'eligible':len(pool),'catalogue_in_lane':c['canonical_heroes'],'e_weight':c['weightE'],'trust':c['trust']})
            if c['scope']=='全部英雄' and (c['dimension']!='arena' or c['league_id']==str(q['summary']['rows'][0]['latest_completed_league'])):
                by_id={r['hero_id']:r for r in groups[key]}
                for hid in [519,107,199]:
                    r=by_id[hid];old=previous.get(hid)
                    representatives.append({'context_id':c['context_id'],'dimension':c['dimension'],'segment':c['segment'],'event':c['event'],'hero_id':hid,'hero':r['hero'],
                        'v1Score':old['score'] if old else None,'v1Rank':old['rank'] if old else None,'legacy_v1_rank':r['v1Rank'],'v2Score':r['score'],'v2Rank':r['rank'],
                        'winRate':r['winRate'] if c['dimension']=='arena' else r['dailyWinRate'],'pickRate':r['pickRate'] if c['dimension']=='arena' else r['dailyPickRate'],
                        'banRate':r['banRate'] if c['dimension']=='arena' else r['dailyBanRate'],'bpRate':r['bpRate'],
                        'E':r['E'],'B':r['B'],'wPercentile':r['wPercentile'],'wZ':r['wZ'],'wNormalized':r['wNormalized'],
                        'bpPercentile':r['bpPercentile'],'bpZ':r['bpZ'],'bpNormalized':r['bpNormalized'],'comparisonN':r['comparisonN'],'reason':r['scoreReason'],'scoreBasis':r['scoreBasis'],'tWeight':r['tWeight'],'dWeight':r['dWeight']})
    events=sorted([c for c in contexts if c['model']=='V2' and c['dimension']=='arena' and c['scope']=='全部英雄' and c['event_status']=='已结束'
        and '季前' not in c['event'] and any(name in c['event'] for name in ['KPL春季赛','KPL夏季赛','KPL秋季赛'])],key=lambda c:c['event_start'])
    metrics=[];exclusions=[];pairs=[]
    inputs=defaultdict(dict)
    for row in q['hero_metrics']['rows']:inputs[str(row['league_id'])][row['hero_id']]=row
    for prev,target in zip(events,events[1:]):
        if not prev['event_end'] or prev['event_end']>=target['event_start']:
            exclusions.append({'previous_league_id':prev['league_id'],'target_league_id':target['league_id'],'previous_end':prev['event_end'],
                'target_start':target['event_start'],'reason':'前届目录窗口尚未闭合；保守排除重叠过渡'});continue
        target_lookup={hid:r for hid,r in inputs[target['league_id']].items() if r['sample_coherent'] and r['battles']>=30}
        for scope in ['全部英雄','对抗路','打野','中路','发育路','游走']:
            v1={r['hero_id']:r for r in groups['V1',prev['context_id'],scope] if r['score'] is not None}
            v2={r['hero_id']:r for r in groups['V2',prev['context_id'],scope] if r['score'] is not None}
            shared=sorted(set(v1)&set(v2)&set(target_lookup))
            if len(shared)<8:
                exclusions.append({'previous_league_id':prev['league_id'],'target_league_id':target['league_id'],'previous_end':prev['event_end'],
                    'target_start':target['event_start'],'reason':scope+'可配对且下一届≥30场英雄不足8名，不报告相关系数'});continue
            target_w=[target_lookup[hid]['winRate'] for hid in shared]
            labels=[('V1原分位',None),('V2初始参数',None),('V2分路统一65/35',.65)]
            if scope=='全部英雄':labels+=[(f'V2 E{int(w*100)}/B{100-int(w*100)}',w) for w in [.55,.60,.70,.75]]
            for label,weight in labels:
                scores=[v1[hid]['score'] if label.startswith('V1') else v2[hid]['score'] if weight is None else weight*v2[hid]['E']+(1-weight)*v2[hid]['B'] for hid in shared]
                metrics.append({'previous_league_id':prev['league_id'],'previous_event':prev['event'],'previous_end':prev['event_end'],
                    'target_league_id':target['league_id'],'target_event':target['event'],'target_start':target['event_start'],'scope':scope,'scheme':label,
                    'paired_heroes':len(shared),'score_to_next_win_spearman':rho(scores,target_w),
                    'assessment':'预设权重的跨届描述关联；非预测胜率，不作MAE或最优权重声明'})
            for hid in shared:pairs.append({'previous_league_id':prev['league_id'],'target_league_id':target['league_id'],'scope':scope,'hero_id':hid,'hero':v2[hid]['hero'],
                'previous_end':prev['event_end'],'target_start':target['event_start'],'v1Score':v1[hid]['score'],'v2Score':v2[hid]['score'],
                'v2E':v2[hid]['E'],'v2B':v2[hid]['B'],'nextWinRate':target_lookup[hid]['winRate'],'nextBattles':target_lookup[hid]['battles']})
    summary=[]
    for scope,scheme in sorted({(r['scope'],r['scheme']) for r in metrics}):
        values=[r for r in metrics if r['scope']==scope and r['scheme']==scheme and r['score_to_next_win_spearman'] is not None]
        summary.append({'scope':scope,'scheme':scheme,'transitions':len(values),'mean_next_win_spearman':mean(r['score_to_next_win_spearman'] for r in values) if values else None,
            'paired_observations':sum(r['paired_heroes'] for r in values),'positive_transitions':sum(r['score_to_next_win_spearman']>0 for r in values),
            'limitation':'原始响应为回顾性聚合快照，无历史时点不可变记录；只研究排名延续性，不能证明线上预测性能或因果关系'})
    return [('model_comparison',comparisons),('model_sensitivity',sensitivity),('model_representatives',representatives),('lane_coverage',lane_coverage),
            ('model_temporal_validation',metrics),('model_temporal_pairs',pairs),('model_temporal_exclusions',exclusions),('model_validation_summary',summary)]
