"""Descriptive season leaders and comparable relative-strength histories."""
from collections import Counter
import re

MIN_BATTLES = 30

def is_regular(event):
    return bool(re.search(r'KPL.*[春夏秋]季赛', event)) and '季前' not in event

def seasonal_evidence(records, coverage, latest_id):
    summaries, leaders = [], []
    events = sorted(coverage, key=lambda e: e['event_start'])
    for event in events:
        group = [r for r in records if str(r['league_id']) == str(event['league_id'])]
        eligible = [r for r in group if r.get('posteriorRate') is not None and r['battles'] >= MIN_BATTLES]
        scored = sorted([r for r in eligible if r.get('score') is not None], key=lambda r: (-r['score'], r['hero_id']))
        fallback = sorted(eligible, key=lambda r: (-r['posteriorRate'], r['hero_id']))
        ranking = scored or fallback
        leader = ranking[0] if ranking else None
        basis = '综合指数' if scored else '仅胜率证据' if ranking else '证据不足'
        base = {k:event[k] for k in ('league_id','event','event_start','event_status')}
        base.update(regular=is_regular(event['event']), min_battles=MIN_BATTLES, eligible_heroes=len(eligible), scored_heroes=len(scored), basis=basis)
        summaries.append({**base, 'leader':leader['hero'] if leader else None,
            'leader_id':leader['hero_id'] if leader else None, 'runner_up':ranking[1]['hero'] if len(ranking)>1 else None,
            'third':ranking[2]['hero'] if len(ranking)>2 else None,
            **{key:leader.get(key) if leader else None for key in ('score','posteriorRate','lowerRate','upperRate','pickRate','banRate','battles','top10WeightShare')}})
        for rank, row in enumerate(ranking[:5], 1):
            leaders.append({**row, 'seasonRank':rank, 'basis':basis, 'min_battles':MIN_BATTLES, 'regular':is_regular(event['event'])})
    regular = [e for e in events if is_regular(e['event']) and e['event_status']=='已结束']
    regular_ids = {str(e['league_id']) for e in regular}
    recurring = Counter(r['hero_id'] for r in leaders if str(r['league_id']) in regular_ids and r['basis']=='综合指数')
    recent = [r['hero_id'] for r in leaders if str(r['league_id'])==str(latest_id)][:3]
    chosen = list(dict.fromkeys(recent+[hid for hid, count in sorted(recurring.items(), key=lambda item:(-item[1],item[0]))]))[:12]
    lookup = {(str(r['league_id']),r['hero_id']):r for r in records}
    labels = {r['hero_id']:r.get('current_name') or r['hero'] for r in records}
    history=[]
    for hero_id in chosen:
        for event in regular:
            row = lookup.get((str(event['league_id']),hero_id))
            allowed = bool(row and row.get('score') is not None and row['battles']>=MIN_BATTLES)
            history.append({'league_id':str(event['league_id']), 'event':event['event'], 'event_start':event['event_start'],
                'seasonLabel':event['event'].replace('年','').replace('KPL','').replace('季赛',''),
                'hero_id':hero_id, 'hero':labels[hero_id], 'score':row['score'] if allowed else None,
                'battles':row['battles'] if row else None, 'rank':row.get('rank') if allowed else None,
                'posteriorRate':row.get('posteriorRate') if row else None,
                'observation': '可比较' if allowed else '少于30场' if row and row['battles']<MIN_BATTLES else '缺少有效BP/观察',
                'min_battles':MIN_BATTLES})
    return summaries,leaders,history
