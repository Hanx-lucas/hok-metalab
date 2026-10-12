"""Coverage and BP-contract audits, without manufacturing observations."""
from __future__ import annotations
import math
from statistics import median
from hoklab.daily import checked

BP_ROUNDING_TOLERANCE=0.0002
CATEGORIES=['完整有效','完全无记录','胜率缺失','其他指标缺失','赛事场次不足','统计口径异常','玩法条目']

def finite_rate(value):
    return isinstance(value,(int,float)) and math.isfinite(value) and 0<=value<=1

def official_bp_contract(rows):
    """A median denominator is diagnostic only; never treated as observed game N."""
    ratios=[]
    for row in rows:
        for count,rate in [('picks','pickRate'),('bans','banRate')]:
            c,x=row.get(count),row.get(rate)
            if finite_rate(x) and x>0 and isinstance(c,(int,float)) and math.isfinite(c) and c>0:ratios.append(c/x)
    denominator=median(ratios) if len(ratios)>=4 else None
    result={}
    for row in rows:
        p,b=row.get('pickRate'),row.get('banRate')
        reason=None
        if not finite_rate(p) or not finite_rate(b):reason='BP指标缺失或越界'
        elif p+b>1.00011:reason='BP和大于1；不截断，等待分母/双禁核验'
        elif denominator is None:reason='没有足够计数/比例用于核查共同BP分母'
        else:
            for count,rate in [('picks','pickRate'),('bans','banRate')]:
                c,x=row.get(count),row[rate]
                if not isinstance(c,(int,float)) or not math.isfinite(c) or c<0 or abs(x-c/denominator)>BP_ROUNDING_TOLERANCE:
                    reason='BP计数/比例与同届共同分母不一致';break
        result[row['hero_id']]={'bp_valid':reason is None,'bp_reason':reason or '同届BP块计数/比例一致；仅诊断共同分母',
            'bpRate':p+b if reason is None else None,'bp_reported':None,'bp_denominator_diagnostic':denominator}
    return result

def daily_bp_contract(rows):
    result={}
    for row in rows:
        p,b,reported=row.get('pickRate'),row.get('banRate'),row.get('bpRate')
        reason=None
        if not all(finite_rate(x) for x in [p,b,reported]):reason='出场、展示禁用或公布BP缺失/越界'
        elif p+b>1.00011:reason='BP和大于1；不截断、不使用双禁数组第一项'
        elif abs(p+b-reported)>0.00015:reason='公布BP不等于出场+展示禁用，口径待核验'
        result[row['hero_id']]={'bp_valid':reason is None,'bp_reason':reason or '公布BP=出场+展示禁用（原数组第二项），舍入容差0.00015',
            'bpRate':p+b if reason is None else None,'bp_reported':reported,'bp_denominator_diagnostic':None}
    return result

def build_coverage(snapshot,catalog):
    q=snapshot['queries'];ids={h['ename'] for h in catalog};hero={h['ename']:h['cname'] for h in catalog}
    audits=[];contracts=[];contexts=q['strength_contexts']['rows']
    for context in contexts:
        dim=context['dimension']
        if dim=='overall':continue
        if dim=='arena':raw=[r for r in q['hero_metrics']['rows'] if str(r['league_id'])==context['league_id']];bp=official_bp_contract(raw)
        else:raw=[r for r in q['daily_current']['rows'] if r['segment']==context['segment']];bp=daily_bp_contract(raw)
        lookup={r['hero_id']:r for r in raw};canonical=[r for r in raw if r['hero_id'] in ids]
        raw_ban_arrays=0;raw_dual_gt100=0
        if dim=='daily':
            from hoklab.daily import SEGMENTS
            did=next(k for k,v in SEGMENTS.items() if v==context['segment']);obj,_=checked(f'susu_rank_{did}')
            items=obj['data']['result']['rows'];raw_ban_arrays=sum(isinstance(r.get('allBanRate'),list) for r in items)
            raw_dual_gt100=sum(isinstance(r.get('allBanRate'),list) and r['allBanRate'][0]>100 for r in items)
        contracts.append({'context_id':context['context_id'],'dimension':dim,'event':context['event'],'segment':context['segment'],
            'records':len(canonical),'bp_passed':sum(bp[r['hero_id']]['bp_valid'] for r in canonical),'bp_rejected':sum(not bp[r['hero_id']]['bp_valid'] for r in canonical),
            'dual_ban_arrays':raw_ban_arrays,'dual_ban_gt100':raw_dual_gt100,
            'denominator_status':'计数/率一致性诊断；非已公开精确总局数' if dim=='arena' else '独立对局分母未提供；只核验同一公布指标字段的相加关系',
            'bp_definition':'pickRate+banRate，同届BP块；共同分母容差0.0002' if dim=='arena' else 'allPickRate+allBanRate[1]；与allBPRate核对，容差0.00015',
            'source_link':next(link['url'] for link in q['hero_metrics']['source']['links'] if 'league' in link['url']) if dim=='arena' else 'https://pvp.91m.top/ranking'})
        for hid in sorted(ids):
            row=lookup.get(hid);check=bp.get(hid,{'bp_valid':False,'bp_reason':'无统计记录','bpRate':None,'bp_reported':None,'bp_denominator_diagnostic':None})
            missing=[]
            if row is None:category='完全无记录';reason='该场景来源响应没有此英雄ID；不能据此认定爬取失败或英雄较弱'
            else:
                missing=[k for k in ['winRate','pickRate','banRate'] if row.get(k) is None]
                if dim=='arena' and not row.get('sample_coherent'):category='统计口径异常';reason='胜负计数/胜率不一致，保留原始数据，不计算后验'
                elif any(row.get(k) is not None and not finite_rate(row[k]) for k in ['winRate','pickRate','banRate']):category='统计口径异常';reason='原始比例越界或非有限数，不截断'
                elif row.get('winRate') is None:category='胜率缺失';reason='来源记录存在，但胜率为缺失标记，不由出场/禁用推算'
                elif missing:category='其他指标缺失';reason='来源缺少'+','.join(missing)
                elif not check['bp_valid']:category='统计口径异常';reason=check['bp_reason']
                elif dim=='arena' and row['battles']<30:category='赛事场次不足';reason=f"仅{row['battles']}场，正式排名要求至少30场"
                else:category='完整有效';reason='满足本场景V2数据资格要求'
            audits.append({'context_id':context['context_id'],'dimension':dim,'league_id':context['league_id'],'event':context['event'],'segment':context['segment'],
                'date':context['observation_date'] if dim=='daily' else context['event_end'],'hero_id':hid,'hero':hero[hid],
                'record_present':row is not None,'category':category,'missing_fields':','.join(missing),'reason':reason,
                'winRate':row.get('winRate') if row else None,'pickRate':row.get('pickRate') if row else None,'banRate':row.get('banRate') if row else None,
                'battles':row.get('battles') if dim=='arena' and row else None,
                'source_class':'official_public_aggregate' if dim=='arena' else 'third_party_public_aggregate',**check})
    counts=[]
    for c in contexts:
        if c['dimension']=='overall':continue
        rows=[r for r in audits if r['context_id']==c['context_id']]
        counts.append({'context_id':c['context_id'],'dimension':c['dimension'],'event':c['event'],'segment':c['segment'],'catalogue':len(ids),
                       **{k:sum(r['category']==k for r in rows) for k in CATEGORIES},'recorded':sum(r['record_present'] for r in rows)})
    return audits,counts,contracts
