"""Reviewed chart inputs: exact score decomposition and honest event history."""
from copy import deepcopy
import math
import sqlite3
from pathlib import Path
import pandas as pd
from hoklab.daily import write_table
ROOT=Path(__file__).resolve().parents[1]

def analysis_points(rows):
    output=[]
    for r in rows:
        if r['score'] is None:continue
        dimension=r['dimension']
        if dimension=='arena':parts=[r[k] for k in ['winContribution','pickContribution','banContribution']]
        elif dimension=='daily' or r['overallBasis']=='daily_only':parts=[r[k] for k in ['dailyWinContribution','dailyPickContribution','dailyBanContribution']]
        else:parts=[.5*r[a]+.5*r[d] for a,d in zip(['winContribution','pickContribution','banContribution'],['dailyWinContribution','dailyPickContribution','dailyBanContribution'])]
        if not math.isclose(sum(parts),r['score'],abs_tol=1e-8):raise ValueError('Score contributions do not reconcile')
        win=r['posteriorRate'] if dimension=='arena' else r['dailyWinRate']
        pick=r['pickRate'] if dimension=='arena' else r['dailyPickRate']
        ban=r['banRate'] if dimension=='arena' else r['dailyBanRate']
        output.append({'context_id':r['context_id'],'dimension':dimension,'hero_id':r['hero_id'],'hero':r['hero'],'name':r['hero'],
            'rank':r['rank'],'roles':r['roles'],'primaryLane':r['roles'].split('/')[0],
            'score':r['score'],'winPoints':parts[0],'pickPoints':parts[1],'banPoints':parts[2],
            'winRate':win,'pickRate':pick,'banRate':ban,'battles':r['battles'] if dimension=='arena' else None,
            'arenaScore':r['arenaScore'],'dailyScore':r['dailyScore'],'basis':r['scoreReason'],
            'sceneGap':r['dailyScore']-r['arenaScore'] if dimension=='overall' and r['arenaScore'] is not None else None,
            'banPressure':'低于5%' if ban<.05 else '5%至20%' if ban<.20 else '20%及以上'})
    return output

def analysis_history(rankings,contexts,seasons):
    eligible={str(s['league_id']) for s in seasons if s['regular'] and s['event_status']=='已结束'}
    info={c['context_id']:c for c in contexts if c['dimension']=='arena' and c['league_id'] in eligible}
    rows=[]
    for r in rankings:
        c=info.get(r['context_id'])
        if c is None:continue
        rows.append({'hero_id':r['hero_id'],'hero':r['hero'],'name':r['hero'],'event':c['event'],'eventStart':c['event_start'],
            'league_id':c['league_id'],'score':r['score'],'rank':r['rank'],'battles':r['battles'],
            'posteriorRate':r['posteriorRate'],'basis':r['scoreReason']})
    return sorted(rows,key=lambda r:(r['eventStart'],r['hero_id']))

def build_strength_visual_queries(snapshot):
    q=snapshot['queries']
    points=analysis_points(q['strength_rankings']['rows'])
    drivers=[{'context_id':p['context_id'],'hero_id':p['hero_id'],'hero':p['hero'],'name':p['hero'],'driver':label,'contribution':p[field],'score':p['score'],'basis':p['basis']}
             for p in points for field,label in [('winPoints','胜率贡献'),('pickPoints','出场贡献'),('banPoints','ban贡献')]]
    history=analysis_history(q['strength_rankings']['rows'],q['strength_contexts']['rows'],q['season_summary']['rows'])
    source=deepcopy(q['strength_rankings']['source'])
    source.update(title='英雄强度解读：评分贡献、场景差异与赛事变化',files=source['files']+['data/processed/strength_rankings.json','data/processed/strength_contexts.json'])
    source['metricDefinitions'] += [
        {'label':'评分贡献','definition':'赛事与日常的胜率/出场/ban分位贡献分别为60P/25P/15P。综合双场景将对应贡献各取50%再相加；日常替代沿用日常贡献。三个分数组成总分，未舍入值精确核对。'},
        {'label':'禁用压力色组','definition':'依据当前场景ban率，划分为低于5%、5%至20%（不含20%）、20%及以上；这是项目描述性阈值，不是官方强度等级。'},
        {'label':'场景差值','definition':'sceneGap=日常强度D−赛事强度T，仅双场景有效者有值。两个分数在各自有效池内计算，观察时间及玩家环境不同，差值是相对位置对照，不表示因果或胜率变化。'},
        {'label':'赛事历史曲线','definition':'只取已结束常规KPL春夏秋季赛，按官方event_start真实时间排序；每届沿用原强度评分。缺BP、异常或少于30场的score保持null，折线不跨缺失点连接。不是游戏S赛季或同版本实验。'}]
    source['caveats'] += ['日常点图使用原始胜率，赛事使用Beta平滑胜率；各图标题明确场景。日常没有样本量，点大小一致，不制造置信区间。',
                          '评分贡献是公式分解，不证明因果机制。分段热力图使用各分段相对分数，不能当成同一人群的胜率提升。']
    source['evidenceFlow'].append({'title':'图表输入与完整性','detail':'hoklab.strength_visuals核对每个评分三项贡献之和；历史保留空值。图表筛选只过滤已审阅行，不重算排名或分位数。'})
    for name,rows in [('strength_analysis_points',points),('strength_analysis_history',history),('strength_analysis_drivers',drivers)]:
        write_table(name,rows);q[name]={'rows':rows,'source':deepcopy(source)}
        with sqlite3.connect(ROOT/'data/processed/hoklab.sqlite') as conn:pd.DataFrame(rows).to_sql(name,conn,index=False,if_exists='replace')
    return {'points':len(points),'history':len(history)}
