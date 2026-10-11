"""Three transparent ranking dimensions; missing evidence stays unranked."""
from __future__ import annotations
import hashlib
import json
import sqlite3
from copy import deepcopy
from pathlib import Path
import pandas as pd
from hoklab.daily import write_table
ROOT = Path(__file__).resolve().parents[1]
LANES = ['对抗路', '打野', '中路', '发育路', '游走']
OFFICIAL_LANES = dict(zip('12345', LANES))
VARIANTS = {50701: '光信_统御', 50702: '暗信_狂暴'}
MIN_BATTLES = 30


def ranked(rows):
    valid = sorted((r for r in rows if r['score'] is not None), key=lambda r: (-r['score'], r['hero_id']))
    for i, r in enumerate(valid, 1):r['rank'] = i
    return sorted(rows, key=lambda r: (r['rank'] is None, r['rank'] or 0, r['hero_id']))


def daily_scores(rows, canonical_ids):
    pool = [r for r in rows if r['hero_id'] in canonical_ids and all(r.get(k) is not None for k in ['winRate', 'pickRate', 'banRate'])]
    if len({r['hero_id'] for r in rows}) != len(rows):raise ValueError('Duplicate hero ID within daily segment')
    if not pool:return {}
    frame = pd.DataFrame(pool).set_index('hero_id')
    percentiles = frame[['winRate', 'pickRate', 'banRate']].rank(method='average', pct=True)
    result = {}
    for hid, r in percentiles.iterrows():
        result[int(hid)] = {'score': 100 * (.6*r.winRate + .25*r.pickRate + .15*r.banRate),
                            'winPercentile': r.winRate, 'pickPercentile': r.pickRate, 'banPercentile': r.banRate}
    return result


def combined_score(arena_score, daily_score):
    if daily_score is None:return None
    if arena_score is None:return daily_score
    return .5*arena_score + .5*daily_score


def build_strength_queries(snapshot):
    raw = ROOT/'data/raw/heroes.json'
    meta = json.loads(raw.with_name('heroes.meta.json').read_text(encoding='utf-8'))
    if hashlib.sha256(raw.read_bytes()).hexdigest() != meta['sha256']:raise ValueError('Hero catalog hash mismatch')
    catalog = json.loads(raw.read_text(encoding='utf-8'))
    heroes = {int(h['ename']): {'hero_id':int(h['ename']), 'hero':h['cname'],
              'roles':'/'.join(OFFICIAL_LANES[k] for k in str(h.get('roles','')).split('|') if k in OFFICIAL_LANES) or '未知'} for h in catalog}
    canonical_ids = set(heroes)
    for hid, name in VARIANTS.items():heroes[hid] = {'hero_id':hid, 'hero':name, 'roles':'对抗路'}
    q = snapshot['queries'];arena_raw = q['hero_metrics']['rows']
    latest_id = str(q['summary']['rows'][0]['latest_completed_league'])
    daily_raw = q['daily_current']['rows'];segments = q['daily_summary']['rows'][0]['segments']
    observation = q['daily_summary']['rows'][0]['observation_date']
    events = sorted(q['coverage']['rows'], key=lambda r:r['event_start'], reverse=True)
    rankings, contexts, lane_rankings = [], [], [];arena_by_event = {}
    def finish(rows, context):
        rows = ranked(rows);rankings.extend(rows)
        scored = [r for r in rows if r['rank'] is not None]
        context.update({'entries':len(rows), 'canonical_heroes':sum(r['hero_id'] in canonical_ids for r in rows),
                        'scored':len(scored), 'unscored':len(rows)-len(scored),
                        'combined_count':sum(r.get('overallBasis')=='balanced' for r in scored),
                        'daily_only_count':sum(r.get('overallBasis')=='daily_only' for r in scored),
                        'leader':scored[0]['hero'] if scored else None,
                        'leader_id':scored[0]['hero_id'] if scored else None,
                        'leader_score':scored[0]['score'] if scored else None,
                        'top3':'、'.join(r['hero'] for r in scored[:3])})
        contexts.append(context)
        for lane in LANES:
            pool = [r for r in scored if lane in r['roles'].split('/')]
            for i, row in enumerate(pool[:5],1):lane_rankings.append({**row, 'lane':lane, 'lane_rank':i})
        return {r['hero_id']:r for r in rows}
    def base(hid, dimension, context_id, league_id=None, segment=None):
        return {**heroes[hid], 'dimension':dimension, 'context_id':context_id, 'league_id':league_id,
                'segment':segment, 'overallBasis':None, 'rank':None, 'score':None, 'arenaScore':None, 'dailyScore':None,
                'winRate':None, 'posteriorRate':None, 'pickRate':None, 'banRate':None, 'battles':None,
                'dailyWinRate':None, 'dailyPickRate':None, 'dailyBanRate':None,
                'winContribution':None, 'pickContribution':None, 'banContribution':None,
                'dailyWinContribution':None, 'dailyPickContribution':None, 'dailyBanContribution':None,
                'lowerRate':None, 'upperRate':None, 'status':'待补数据', 'scoreReason':'没有相应数据'}
    for event in events:
        eid = str(event['league_id']);context_id = 'arena:'+eid
        source = {r['hero_id']:r for r in arena_raw if str(r['league_id'])==eid};rows=[]
        for hid in sorted(canonical_ids):
            row=base(hid,'arena',context_id,eid);r=source.get(hid)
            if r:
                for key in ['winRate','posteriorRate','pickRate','banRate','battles','lowerRate','upperRate']:row[key]=r.get(key)
                if r['score'] is not None and r['battles'] >= MIN_BATTLES:
                    row.update(score=r['score'],arenaScore=r['score'],status='已评分',scoreReason='三项指标有效且战斗场次≥30')
                    row.update(winContribution=60*r['winPercentile'],pickContribution=25*r['pickPercentile'],banContribution=15*r['banPercentile'])
                else:row['scoreReason']='战斗场次不足30' if r['battles']<MIN_BATTLES else '缺少BP指标或胜负计数异常'
            rows.append(row)
        dated = next((r for r in arena_raw if str(r['league_id'])==eid), {})
        arena_by_event[eid]=finish(rows, {'dimension':'arena','context_id':context_id,'league_id':eid,'segment':None,
            'event':event['event'],'event_status':event['event_status'],'event_start':event['event_start'],
            'event_end':dated.get('event_end'),'observation_date':None})
    latest_context = next(c for c in contexts if c['league_id']==latest_id)
    for segment in segments:
        raw_segment = [r for r in daily_raw if r['segment']==segment]
        if any(r['date'] != observation for r in raw_segment):raise ValueError('Mixed observation dates in daily ranking')
        if any(r['hero_id'] not in heroes for r in raw_segment):raise ValueError('Unknown daily hero ID; review catalog before ranking')
        scores=daily_scores(raw_segment,canonical_ids)
        source = {r['hero_id']:r for r in raw_segment}
        context_id='daily:'+segment;rows=[]
        for hid in sorted(heroes):
            row=base(hid,'daily',context_id,segment=segment);r=source.get(hid)
            if r:
                row.update(dailyWinRate=r['winRate'],dailyPickRate=r['pickRate'],dailyBanRate=r['banRate'])
                if hid in scores:
                    d=scores[hid];row.update(score=d['score'],dailyScore=d['score'],status='已评分',scoreReason='当前分段三项指标完整')
                    row.update(dailyWinContribution=60*d['winPercentile'],dailyPickContribution=25*d['pickPercentile'],dailyBanContribution=15*d['banPercentile'])
                else:row['scoreReason']='李信玩法条目，仅展示原始指标，不重复参与英雄排名' if hid in VARIANTS else '当前分段有指标缺失'
            rows.append(row)
        day=finish(rows,{'dimension':'daily','context_id':context_id,'league_id':None,'segment':segment,
            'event':None,'event_status':None,'event_start':None,'event_end':None,'observation_date':observation})
        overall=[];context_id='overall:'+segment
        for hid in sorted(heroes):
            row=deepcopy(day[hid]);row.update(dimension='overall',context_id=context_id,league_id=latest_id,rank=None)
            arena=arena_by_event[latest_id].get(hid)
            if arena:
                for key in ['arenaScore','winRate','posteriorRate','pickRate','banRate','battles','lowerRate','upperRate','winContribution','pickContribution','banContribution']:row[key]=arena[key]
            row['score']=combined_score(row['arenaScore'],row['dailyScore']);row['status']='已评分' if row['score'] is not None else '待补数据'
            row['overallBasis']='daily_only' if row['score'] is not None and row['arenaScore'] is None else 'balanced' if row['score'] is not None else 'unavailable'
            row['scoreReason']='日常替代（100%日常强度）' if row['overallBasis']=='daily_only' else '赛事与日常各占50%' if row['overallBasis']=='balanced' else '玩法条目，不参与综合排名' if hid in VARIANTS else '缺少有效日常数据'
            overall.append(row)
        finish(overall,{**{k:v for k,v in latest_context.items() if k not in ['entries','scored','unscored','leader','leader_id','leader_score','top3']},
            'dimension':'overall','context_id':context_id,'segment':segment,'observation_date':observation})
    source={'title':'三维英雄强度榜：可复算派生指标','provider':'HoK MetaLab / 腾讯公开赛事 + 苏苏助手公开日常整理',
        'classification':'reviewed_derived','executedAt':snapshot.get('generatedAt'),
        'links':q['hero_metrics']['source']['links']+q['daily_current']['source']['links']+[{'label':'腾讯英雄目录','url':meta['url']}],
        'files':['data/processed/hero_metrics.json','data/processed/daily_current.json','data/raw/heroes.json']+q['daily_current']['source']['files'],
        'metricDefinitions':[
            {'label':'赛事强度 T','definition':'T=100×(0.60×P(平滑胜率)+0.25×P(出场率)+0.15×P(ban率))；平滑胜率=(胜场+10)/(场次+20)。P取原分析当届有效BP且计数一致的完整英雄池平均秩/N；排名门槛≥30场，过滤门槛后不重算分位。'},
            {'label':'日常强度 D','definition':'D=100×(0.60×P(原始胜率)+0.25×P(出场率)+0.15×P(ban率))。P在同日期、同分段、三项指标完整的官方目录英雄子集中计算平均秩/N；无样本数，不伪造平滑胜率或区间。'},
            {'label':'综合强度 C','definition':'C=0.50×T+0.50×D；双场景有效时各占50%；赛事无有效评分且日常有效时C=D（100%日常），并标记日常替代；日常无有效评分时不评分。T使用最新已结束赛事，D使用当前选定分段。'},
            {'label':'名次与分路','definition':'使用未舍入分数降序，同分按英雄ID升序稳定排序；分路Top5沿用全局分数，按当前腾讯推荐标签过滤，多分路英雄允许重复出现。'},
            {'label':'英雄匹配','definition':'仅按相同官方英雄ID连接。元流之子各形态分别保留；光信/暗信玩法保留原始日常数据但不重复参与英雄分位数或榜单。'}],
        'caveats':['权重是项目设定，不是官方评级；分数表示当前范围内的相对表现，不证明因果强度。',
            f'综合将{latest_context["event"]}（{latest_context["event_start"]}至{latest_context["event_end"]}）与{observation}公告日常榜单组合；统计时间不一致，只作跨场景参考，不能当成同版本结论。',
            '日常来源为非官方苏苏助手，未与营地对账，无样本数或精确统计窗口；仅作描述排名，早期手工数据不参与。',
            '综合榜混合双场景评分与日常替代评分；评分依据明确标记，日常替代不代表赛事实力。日常缺失者仍留空；玩法条目不重复排名。',
            '赛事2019早期BP缺失时不能提供三维排名；进行中赛事标记状态，不与已结束赛事混淆。'],
        'evidenceFlow':[{'title':'独立场景评分','detail':'从已核验hero_metrics和daily_current派生；日常目录ID重复或目录SHA不一致立即报错。'},
                        {'title':'统一榜单标准','detail':'综合双场景50/50、赛事缺失100%日常；Top10、分路Top5与完整总榜使用同一上下文、同一替代规则及未舍入分数。'}]}
    for name, rows in [('strength_rankings',rankings),('strength_contexts',contexts),('strength_lane_rankings',lane_rankings)]:
        write_table(name,rows);q[name]={'rows':rows,'source':source}
        with sqlite3.connect(ROOT/'data/processed/hoklab.sqlite') as conn:
            pd.DataFrame(rows).to_sql(name,conn,index=False,if_exists='replace')
    from hoklab.strength_visuals import build_strength_visual_queries
    build_strength_visual_queries(snapshot)
    return {'contexts':len(contexts),'ranking_rows':len(rankings),'lane_rows':len(lane_rankings),'latest_event':latest_context['event']}
