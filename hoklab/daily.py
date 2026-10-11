"""Offline normalization of a limited, attributable third-party source pilot.

Public ranking uses did; hero history uses bid (0 returns all column groups).
Keep this source separate from official KPL and authorized Camp observations.
"""
from __future__ import annotations
import csv
import hashlib
import json
import math
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw/alternative'
OUT = ROOT / 'data/processed'
SEGMENTS = {0: '巅峰千强', 3: '顶端排位', 4: '巅峰赛1350+', 5: '全分段'}
HEROES = {107: '赵云', 140: '关羽', 525: '鲁班大师', 527: '蒙恬'}
HISTORY_PREFIXES = {'巅峰千强': '巅峰千强', '顶端排位': '顶端排位', '巅峰赛1350+': '1350+', '全分段': '全分段'}


def rate(value, *, unit='percentage_points'):
    """Missing stays missing; units are endpoint contracts, never magnitude guesses."""
    if value in (None, '', '--', '-', '　'):
        return None
    try:
        number = float(str(value).rstrip('%'))
    except (ValueError, TypeError):
        raise ValueError(f'Invalid rate value: {value!r}')
    number = number / 100 if unit == 'percentage_points' else number
    if not math.isfinite(number) or not 0 <= number <= 1:
        raise ValueError(f'Rate outside [0, 1]: {value!r} ({unit})')
    return number


def displayed_ban(value):
    # The first member counts double bans and can exceed 100%; the public UI
    # displays the second. Do not clip the first and mistake it for a fraction.
    if isinstance(value, list):
        if len(value) != 2:
            raise ValueError('Unexpected dual-ban schema')
        return rate(value[1])
    return rate(value)


def checked(key):
    path = RAW / f'{key}.json'
    meta = json.loads(path.with_suffix('.meta.json').read_text(encoding='utf-8'))
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != meta['sha256']:
        raise ValueError(f'Third-party raw snapshot hash mismatch: {key}')
    obj = json.loads(body)
    if obj.get('status', {}).get('code') != 200:
        raise ValueError(f'Non-success source response: {key}')
    return obj, meta


def normalize_current(obj, segment, observation_date):
    date.fromisoformat(observation_date)
    rows = []
    for r in obj['data']['result']['rows']:
        rows.append({'hero_id': int(r['id']), 'hero': r['name'], 'segment': segment,
                     'date': observation_date, 'winRate': rate(r.get('allWinRate')),
                     'pickRate': rate(r.get('allPickRate')), 'banRate': displayed_ban(r.get('allBanRate')),
                     'bpRate': rate(r.get('allBPRate')), 'sample_size': None,
                     'source_class': 'third_party_public_aggregate'})
    if len({r['hero_id'] for r in rows}) != len(rows):
        raise ValueError(f'Duplicate current hero IDs in {segment}')
    return rows


def normalize_history(obj, hero_id):
    result = obj['data']['result']
    # Require the all-segment response, rather than silently attaching did to
    # an unlabeled single-segment response where the parameter is ignored.
    if '全分段:胜率' not in result['columns']:
        raise ValueError('History requires bid=0 and labeled segment columns')
    rows = []
    seen = {}
    for r in result['rows']:
        observed = r['日期'][:10]
        date.fromisoformat(observed)
        if observed in seen:
            if seen[observed] == r:
                continue  # Exact duplicate retained in raw evidence, counted below.
            raise ValueError(f'Conflicting history date for {hero_id}: {observed}')
        seen[observed] = r
        for segment, prefix in HISTORY_PREFIXES.items():
            rows.append({'hero_id': hero_id, 'hero': HEROES[hero_id], 'segment': segment,
                         'date': observed, 'winRate': rate(r.get(prefix + ':胜率'), unit='fraction'),
                         'pickRate': rate(r.get(prefix + ':出场'), unit='fraction'),
                         'banRate': rate(r.get(prefix + ':禁用'), unit='fraction'),
                         'sample_size': None, 'source_class': 'third_party_public_aggregate'})
    return rows


def write_table(name, rows):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/f'{name}.json').write_text(json.dumps(rows, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    if rows:
        with (OUT/f'{name}.csv').open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def build_daily_queries(snapshot):
    if not RAW.exists():
        return
    current, history, manifest = [], [], []
    app, app_meta = checked('susu_app_info')
    # The full year is available in the published announcement; daily is MM-DD.
    year = app['data']['appInfo']['updateInfo']['title'][:4]
    observed = year + '-' + app['data']['appInfo']['updateInfo']['daily']
    manifest.append(app_meta)
    for did, segment in SEGMENTS.items():
        obj, meta = checked(f'susu_rank_{did}'); manifest.append(meta)
        current.extend(normalize_current(obj, segment, observed))
    for hero_id in HEROES:
        obj, meta = checked(f'susu_history_{hero_id}'); manifest.append(meta)
        history.extend(normalize_history(obj, hero_id))
    history.sort(key=lambda r: (r['date'], r['hero_id'], r['segment']))
    profile = []
    for hero_id, hero in HEROES.items():
        for segment in SEGMENTS.values():
            pool = [r for r in history if r['hero_id'] == hero_id and r['segment'] == segment]
            valid = [r for r in pool if all(r[k] is not None for k in ['winRate','pickRate','banRate'])]
            dates = sorted(date.fromisoformat(r['date']) for r in pool)
            absent_dates = sum(max(0, (b-a).days-1) for a,b in zip(dates,dates[1:]))
            profile.append({'hero':hero,'segment':segment,'dated_rows':len(pool),'complete_metrics':len(valid),
                            'missing_metrics':len(pool)-len(valid),'first_complete':valid[0]['date'] if valid else None,
                            'last_complete':valid[-1]['date'] if valid else None,'absent_dates':absent_dates})
    valid_current = sum(all(r[k] is not None for k in ['winRate','pickRate','banRate']) for r in current)
    historical_latest={(r['hero_id'],r['segment']):r for r in history if r['date']==observed}
    reconciliation=[]
    for c in current:
        h=historical_latest.get((c['hero_id'],c['segment']))
        if not h:continue
        deltas={k:100*(c[k]-h[k]) if c[k] is not None and h[k] is not None else None for k in ['winRate','pickRate','banRate']}
        reconciliation.append({'hero':c['hero'],'segment':c['segment'],'date':observed,
                               'win_delta_pp':deltas['winRate'],'pick_delta_pp':deltas['pickRate'],'ban_delta_pp':deltas['banRate'],
                               'current_winRate':c['winRate'],'history_winRate':h['winRate'],
                               'different':any(v is not None and abs(v)>.011 for v in deltas.values()) or any((c[k] is None)!=(h[k] is None) for k in deltas)})
    summary = {'current_rows':len(current),'current_complete':valid_current,'current_heroes':len({r['hero_id'] for r in current}),
               'segments':list(SEGMENTS.values()),'observation_date':observed,'history_heroes':len(HEROES),
               'history_rows':len(history),'history_complete':sum(p['complete_metrics'] for p in profile),
               'history_first':min(r['date'] for r in history),'history_last':max(r['date'] for r in history),
               'exact_duplicate_days_removed':sum(len(checked(f'susu_history_{hid}')[0]['data']['result']['rows'])-len({r['date'] for r in history if r['hero_id']==hid}) for hid in HEROES),
               'reconciliation_rows':len(reconciliation),'endpoints_disagree':sum(r['different'] for r in reconciliation),
               'officially_reconciled':False,'sample_sizes_available':False,'season_mapping_available':False}
    caveats = ['第三方整理的公开数据，尚未与王者营地独立对账，不代表官方。',
               '没有每英雄样本场次、胜负计数及完整采样规则；不计算贝叶斯可信区间或统计显著性。',
               '昨日榜单和每日历史记录不等于单日原始逐局样本；统计窗口以来源页面为准。',
               '历史仅验证4位英雄；早期分段缺失与日期断档保留，不能声称全英雄多赛季完整覆盖。',
               '未提供游戏S赛季映射，保持真实日期；未核验来源长期分段定义是否发生变化。']
    caveats.extend(['当前榜单与历史末日存在差异，可能是更新/统计窗口差异；原因未核验，不混合、平均或用历史值填补当前缺失。',
                    '来源英雄ID包含李信玩法、元流之子形态条目，未强行合并为官方英雄口径。'])
    source = {'title':'苏苏助手数据站：日常分段公开数据（有限验证）','provider':'苏苏助手数据站 / 非官方',
              'classification':'third_party_public_aggregate','executedAt':max(m['retrieved_at'] for m in manifest),
              'links':[{'label':'公开英雄排行','url':'https://pvp.91m.top/ranking'},
                       {'label':'提供者使用声明','url':'https://docs.91m.top/%E5%A3%B0%E6%98%8E.html'},
                       {'label':'排行接口文档','url':'https://xug887phix.apifox.cn/api-429517673'},
                       {'label':'历史接口文档','url':'https://xug887phix.apifox.cn/api-184881160'}],
              'files':[f"data/raw/alternative/{m['key']}.json" for m in manifest],
              'metricDefinitions':[{'label':'百分比单位','definition':'当前榜单百分点除以100；历史端已是0–1比例，禁止二次除以100。'},
                                   {'label':'禁用率','definition':'当前allBanRate数组取页面显示的第二项；第一项为双禁口径，可能超过100%。'},
                                   {'label':'观察日期','definition':'当前榜单取提供者公告的daily日期；历史取响应日期。采集时间另行记录。'},
                                   {'label':'分段参数','definition':'榜单did=0/3/4/5；历史bid=0返回带前缀的各分段列，did不作为历史分段。'}],
              'caveats':caveats,'evidenceFlow':[{'title':'匿名公开来源验证','detail':'在新浏览器会话切换四档榜单，对照页面数值与真实请求；不用用户cookie或token。'},
                                             {'title':'原始证据与清洗','detail':'保留响应、URL、采集时间、SHA-256；分开存储当前榜单与4英雄历史，缺失不补零。'}]}
    for name, rows in [('daily_current',current),('daily_history',history),('daily_coverage',profile),('daily_reconciliation',reconciliation),('daily_summary',[summary])]:
        write_table(name, rows)
        snapshot['queries'][name] = {'rows':rows,'source':source}
    (OUT/'daily_source_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    return summary
