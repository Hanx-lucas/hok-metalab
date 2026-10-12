"""V2 descriptive E/B index and comparable V1 views; no hero-specific rules."""
from __future__ import annotations
from copy import deepcopy
from pathlib import Path
import hashlib,json,math,sqlite3
import numpy as np
import pandas as pd
from hoklab.daily import write_table
from hoklab.strength import LANES,MIN_BATTLES,VARIANTS,ranked
from hoklab.coverage_audit import build_coverage
ROOT=Path(__file__).resolve().parents[1]
MIN_POOL=5
LANE_E_WEIGHTS=dict(zip(LANES,[.65,.70,.70,.60,.60]))
GLOBAL_E_WEIGHT=.65
SCENE_T_WEIGHT=.30
SCENE_D_WEIGHT=.70
FIELDS=['context_id','dimension','league_id','segment','hero_id','hero','roles','winRate','posteriorRate','pickRate','banRate','battles',
        'dailyWinRate','dailyPickRate','dailyBanRate','lowerRate','upperRate','score','rank','arenaScore','dailyScore','status','scoreReason',
        'winContribution','pickContribution','banContribution','dailyWinContribution','dailyPickContribution','dailyBanContribution']
EXTRA=['wRaw','wPercentile','wMean','wStd','wZ','wNormalized','bpRate','bpAdjusted','bpPercentile','bpMean','bpStd','bpZ','bpNormalized',
       'bpLow','bpHigh','E','B','eContribution','bContribution','comparisonN','arenaPoolN','dailyPoolN','weightE','weightB','uniformScore','uniformRank','v1Score','v1Rank','rankPoolN','tWeight','dWeight','scoreBasis','arenaMissingReason']

def score_pool(rows,weight_e=GLOBAL_E_WEIGHT):
    """W/BP raw rank/N; BP q5/q95 winsorization affects Z only; sigma ddof=0."""
    if not 0<=weight_e<=1 or not math.isfinite(weight_e):raise ValueError('Invalid E weight')
    if len({r['hero_id'] for r in rows})!=len(rows):raise ValueError('Duplicate pool identity')
    if len(rows)<MIN_POOL:return {}
    w=np.array([r['wRaw'] for r in rows],dtype=float);bp=np.array([r['bpRate'] for r in rows],dtype=float)
    if not np.isfinite(w).all() or not np.isfinite(bp).all() or np.any((w<0)|(w>1)|(bp<0)|(bp>1.00011)):raise ValueError('Invalid pool rates')
    low,high=np.quantile(bp,[.05,.95],method='linear');adjusted=np.clip(bp,low,high)
    wp=pd.Series(w).rank(method='average',pct=True).to_numpy();bpp=pd.Series(bp).rank(method='average',pct=True).to_numpy()
    wm,ws=float(w.mean()),float(w.std(ddof=0));bm,bs=float(adjusted.mean()),float(adjusted.std(ddof=0))
    wz=(w-wm)/ws if ws>1e-12 else np.zeros(len(rows));bz=(adjusted-bm)/bs if bs>1e-12 else np.zeros(len(rows))
    wn=np.clip(.5+wz/4,0,1);bn=np.clip(.5+bz/4,0,1)
    E=100*(.5*wp+.5*wn);B=100*(.5*bpp+.5*bn);output={}
    for i,row in enumerate(rows):
        output[row['hero_id']]={'wRaw':float(w[i]),'wPercentile':float(wp[i]),'wMean':wm,'wStd':ws,'wZ':float(wz[i]),'wNormalized':float(wn[i]),
            'bpRate':float(bp[i]),'bpAdjusted':float(adjusted[i]),'bpPercentile':float(bpp[i]),'bpMean':bm,'bpStd':bs,'bpZ':float(bz[i]),'bpNormalized':float(bn[i]),
            'bpLow':float(low),'bpHigh':float(high),'E':float(E[i]),'B':float(B[i]),'eContribution':float(weight_e*E[i]),'bContribution':float((1-weight_e)*B[i]),
            'score':float(weight_e*E[i]+(1-weight_e)*B[i]),'comparisonN':len(rows),'weightE':weight_e,'weightB':1-weight_e,
            'uniformScore':float(.65*E[i]+.35*B[i])}
    return output

def fingerprint():
    # Invalidate approval after any backend/normalization/test change, not only score edits.
    files=sorted((ROOT/'hoklab').glob('*.py'))+sorted((ROOT/'tests').glob('*.py'))
    files += [ROOT/'scripts/validate_v2.py',ROOT/'requirements-lock.txt']
    files+=sorted((ROOT/'data/raw').glob('*.json'))+sorted((ROOT/'data/raw/alternative').glob('*.json'))
    digest=hashlib.sha256()
    for p in files:
        if p.exists():digest.update(p.relative_to(ROOT).as_posix().encode());digest.update(p.read_bytes())
    return digest.hexdigest()

def base_row(original,model,scope):
    row={k:original.get(k) for k in FIELDS};row.update({k:None for k in EXTRA})
    row.update(model=model,scope=scope,name=original['hero'],score=None,rank=None,arenaScore=None,dailyScore=None,
               v1Score=original['score'],v1Rank=original['rank'],comparisonN=0,trust='证据不足',route='unrated')
    return row

def annotate_context(rows,old,model,scope):
    scored=[r for r in rows if r['score'] is not None]
    return {**{k:old[k] for k in ['context_id','dimension','league_id','segment','event','event_status','event_start','event_end','observation_date']},
        'model':model,'scope':scope,'entries':len(rows),'canonical_heroes':sum(r['hero_id'] not in VARIANTS for r in rows),
        'scored':len(scored),'unscored':len(rows)-len(scored),'combined_count':sum(r['route']=='paired' for r in scored),
        'daily_only_count':sum(r['route']=='daily_fallback' for r in scored),'comparisonN':len(scored),
        'tWeight':SCENE_T_WEIGHT if old['dimension']=='overall' else None,'dWeight':SCENE_D_WEIGHT if old['dimension']=='overall' else None,
        'composite_policy':'30%T+70%D；仅日常有效时100%D同榜，并标明评分依据' if old['dimension']=='overall' else None,
        'weightE':LANE_E_WEIGHTS.get(scope,.65) if model=='V2' else .6,'weightB':1-(LANE_E_WEIGHTS.get(scope,.65) if model=='V2' else .6),
        'leader':scored[0]['hero'] if scored else None,'leader_score':scored[0]['score'] if scored else None,
        'statisticalPoolN':max((r['comparisonN'] or 0 for r in rows),default=0),'trust':'证据不足' if len(scored)<MIN_POOL else '低可信度（比较池不足10名）' if len(scored)<10 else '描述性指数；非因果强度'}

def build_v2_queries(snapshot):
    q=snapshot['queries'];catalog=json.loads((ROOT/'data/raw/heroes.json').read_text(encoding='utf-8'))
    audits,coverage,bp_contracts=build_coverage(snapshot,catalog);audit_lookup={(r['context_id'],r['hero_id']):r for r in audits}
    oldrows=q['strength_rankings']['rows'];oldcontexts=q['strength_contexts']['rows'];original={(r['context_id'],r['hero_id']):r for r in oldrows}
    by_context={c['context_id']:[r for r in oldrows if r['context_id']==c['context_id']] for c in oldcontexts}
    output=[];contexts=[];observations=[];lookup={}
    scopes=['全部英雄',*LANES]
    def finish(rows,c,model,scope):
        rows=ranked(rows)
        uniform=sorted((r for r in rows if r['uniformScore'] is not None),key=lambda r:(-r['uniformScore'],r['hero_id']))
        for i,row in enumerate(uniform,1):row['uniformRank']=i
        output.extend(rows);contexts.append(annotate_context(rows,c,model,scope))
        for row in rows:lookup[model,c['context_id'],scope,row['hero_id']]=row
    for c in oldcontexts:
        if c['dimension']=='overall':continue
        originals=by_context[c['context_id']]
        for model in ['V1','V2']:
            for scope in scopes:
                originals_scope=[r for r in originals if scope=='全部英雄' or scope in r['roles'].split('/')]
                eligible=[]
                for row in originals_scope:
                    audit=audit_lookup.get((c['context_id'],row['hero_id']))
                    if audit and audit['category']=='完整有效':
                        raw=next((r for r in q['hero_metrics']['rows'] if str(r['league_id'])==c['league_id'] and r['hero_id']==row['hero_id']),None) if c['dimension']=='arena' else None
                        w=(raw['wins']+10)/(raw['battles']+20) if raw else row['dailyWinRate']
                        eligible.append({'hero_id':row['hero_id'],'wRaw':w,'bpRate':audit['bpRate']})
                pool=score_pool(eligible,LANE_E_WEIGHTS.get(scope,.65)) if model=='V2' else {}
                scored_v1=[r for r in originals_scope if r['score'] is not None]
                v1_stat_n=sum(r['score'] is not None for r in q['hero_metrics']['rows'] if str(r['league_id'])==c['league_id']) if c['dimension']=='arena' else sum(r['score'] is not None for r in originals)
                rows=[]
                for old in originals_scope:
                    row=base_row(old,model,scope);audit=audit_lookup.get((c['context_id'],old['hero_id']))
                    row['bpRate']=audit['bpRate'] if audit else None
                    row['comparisonN']=len(eligible) if model=='V2' else v1_stat_n
                    row['rankPoolN']=len(eligible) if model=='V2' else len(scored_v1)
                    row['scoreReason']=audit['reason'] if audit else old['scoreReason']
                    if model=='V2' and old['hero_id'] in pool:
                        row.update(pool[old['hero_id']]);row['posteriorRate']=row['wRaw'] if c['dimension']=='arena' else None
                        row.update(scoreReason='独立有效比较池；分位与Z各50%；试验E/B权重',route='rated')
                    elif model=='V1' and old['score'] is not None and (scope=='全部英雄' or len(scored_v1)>=MIN_POOL):
                        row['score']=old['score'];parts=[old.get(k) for k in (['winContribution','pickContribution','banContribution'] if c['dimension']=='arena' else ['dailyWinContribution','dailyPickContribution','dailyBanContribution'])]
                        row.update(E=parts[0]/.6,B=(parts[1]+parts[2])/.4,eContribution=parts[0],bContribution=parts[1]+parts[2],weightE=.6,weightB=.4,
                                   comparisonN=v1_stat_n,scoreReason='V1原三指标分位指数；分路仅筛选总榜分数',route='rated')
                    elif model=='V2' and audit and audit['category']=='完整有效':row['scoreReason']=f'有效比较池不足{MIN_POOL}名，不强行排名'
                    if row['score'] is not None:
                        row['arenaScore' if c['dimension']=='arena' else 'dailyScore']=row['score']
                        row['trust']='低可信度（有效比较池不足10名）' if row['comparisonN']<10 else '描述性指数；非因果强度'
                        row['status']='已评分'
                    else:row['status']='未评分'
                    rows.append(row)
                finish(rows,c,model,scope)
    for c in oldcontexts:
        if c['dimension']!='overall':continue
        for model in ['V1','V2']:
            for scope in scopes:
                originals_scope=[r for r in by_context[c['context_id']] if scope=='全部英雄' or scope in r['roles'].split('/')];rows=[];obs=[]
                for old in originals_scope:
                    row=base_row(old,model,scope);a=lookup.get((model,'arena:'+c['league_id'],scope,old['hero_id']));d=lookup.get((model,'daily:'+c['segment'],scope,old['hero_id']))
                    t=a['score'] if a else None;day=d['score'] if d else None
                    row.update(arenaScore=t,dailyScore=day,arenaPoolN=a['comparisonN'] if a else 0,dailyPoolN=d['comparisonN'] if d else 0)
                    if t is not None and day is not None:
                        row.update(score=SCENE_T_WEIGHT*t+SCENE_D_WEIGHT*day,E=SCENE_T_WEIGHT*a['E']+SCENE_D_WEIGHT*d['E'],B=SCENE_T_WEIGHT*a['B']+SCENE_D_WEIGHT*d['B'],
                                   eContribution=SCENE_T_WEIGHT*a['eContribution']+SCENE_D_WEIGHT*d['eContribution'],bContribution=SCENE_T_WEIGHT*a['bContribution']+SCENE_D_WEIGHT*d['bContribution'],
                                   weightE=a['weightE'],weightB=a['weightB'],route='paired',status='已评分',tWeight=SCENE_T_WEIGHT,dWeight=SCENE_D_WEIGHT,scoreBasis='双场景综合',scoreReason='双场景综合：30%T+70%D；异日期跨场景参考',
                                   uniformScore=SCENE_T_WEIGHT*a['uniformScore']+SCENE_D_WEIGHT*d['uniformScore'] if model=='V2' else None,
                                   trust='跨场景描述指数；观察日期与环境不同')
                    elif day is not None:
                        row.update(score=day,E=d['E'],B=d['B'],eContribution=d['eContribution'],bContribution=d['bContribution'],
                                   weightE=d['weightE'],weightB=d['weightB'],uniformScore=d['uniformScore'],route='daily_fallback',status='仅日常参考',
                                   tWeight=0.,dWeight=1.,scoreBasis='仅日常参考',arenaMissingReason=a['scoreReason'] if a else '赛事无记录',
                                   scoreReason='仅日常参考：100%D；赛事'+(a['scoreReason'] if a else '无记录'),trust='日常单场景替代，非双场景综合估计')
                        observed=deepcopy(d);observed.update(context_id=c['context_id'],route='daily_observation',scoreReason='仅日常有效，观察分数=D，不代表赛事实力',dailyRank=d['rank'],rank=None)
                        obs.append(observed)
                    else:row.update(status='未评分',route='unrated',scoreReason='日常数据不足，无法形成双场景综合分')
                    rows.append(row)
                rankable=sum(r['score'] is not None for r in rows)
                if rankable<MIN_POOL:
                    for row in rows:
                        if row['score'] is not None:row.update(score=None,uniformScore=None,E=None,B=None,eContribution=None,bContribution=None,route='unrated',scoreReason='综合榜有效比较池不足5名，不强行排名')
                for row in rows:row['comparisonN']=rankable;row['rankPoolN']=rankable
                finish(rows,c,model,scope);observations.extend(ranked(obs))
    source=deepcopy(q['strength_rankings']['source']);source.update(title='V1/V2英雄强度模型与覆盖审计',classification='reviewed_derived')
    source['files']+=['hoklab/strength_v2.py','hoklab/coverage_audit.py','data/processed/model_rankings.csv','data/processed/coverage_audit.csv']
    source['metricDefinitions']=[
        {'label':'V1对照','definition':'原赛事与日常分数保持不变。原legacy综合替代结果保存在strength_rankings；新版V1展示使用相同30/70场景策略，仅日常有效者100%D同榜；旧综合分仍保留在原表。V1分路仅过滤全局分数，用于历史对照。'},
        {'label':'V2 E/B','definition':'BP=经同源口径审计的Pick+Ban。P=原始指标平均秩/N；BP的Z使用同池线性q5/q95缩尾，原始BP秩保留。Z=(X−μ)/σ，σ为总体标准差ddof=0；零方差Z=0。N(Z)=clip(.5+Z/4,0,1)，H=.5P+.5N，E=100H(W)，B=100H(BP)，S=wE×E+(1−wE)×B。'},
        {'label':'比较池与门槛','definition':'V2赛事先要求有效计数/BP且≥30场再计算任何均值、σ和P。日常完整同日同分段官方ID；不重复计入李信玩法。至少5名才评分，5–9名标低可信度。日常无样本量，仅用原始胜率；赛事W=(wins+10)/(battles+20)。'},
        {'label':'分路权重','definition':'V2各分路独立重算P/μ/σ：对抗65/35、打野70/30、中路70/30、发育60/40、游走60/40。uniformScore/uniformRank为同一分路池统一65/35对照。分路分不用于跨路总排名。'},
        {'label':'双场景综合','definition':'双有效C=.3T+.7D；仅日常有效时100%D同榜，标注仅日常参考、赛事缺失原因与实际0/100场景权重，不补零。E/B贡献依实际场景权重合成，原P/Z查看各场景；比较人群的证据基础不同。'},
        {'label':'权重与验证','definition':'65/35、分路参数和30/70场景权重是初始试验，不宣称最优。默认V2启用仅表示计算、回归与交互验证通过；不代表未来预测优于V1。'}]
    source['caveats']=[
        'V1原数据/分数保留，新展示按用户最新设置使用30/70或100%D同榜，明确不同评分依据。',
        '当前官方推荐分路不是实际赛事分路；没有可靠逐局位置统计，分路和历史比较需谨慎。',
        '日常来源为第三方公开整理，无场次/精确统计窗口，无法制造区间或验证国服代表性。',
        '赛事与日常公告日期、环境不同，C不是同版本真实综合实力。',
        '日常双禁数组第一项可能超过100%，没有截断或将它用于BP；仅使用页面展示第二项并与公布BP核对。',
        '历史接口与当前榜单同日指标不一致，保持分开，不互补缺失。']
    source['evidenceFlow']=[{'title':'原始来源审计','detail':'原始响应hash校验；官方BP计数/率共同分母一致性诊断、第三方公布BP字段对账。'},
        {'title':'可复算模型','detail':'统一函数score_pool，无英雄白名单加分；所有全局/分路得分均等于E/B加权贡献之和。'}]
    from hoklab.model_validation import build_validation
    validation=build_validation(output,contexts,snapshot)
    gate_path=ROOT/'output/qa/v2-validation-gate.json';gate=json.loads(gate_path.read_text(encoding='utf-8')) if gate_path.exists() else {}
    enabled=gate.get('passed') is True and gate.get('input_fingerprint')==fingerprint()
    release=[{'default_model':'V2' if enabled else 'V1','v2_functional_validation':enabled,'status':'validated_descriptive_experiment' if enabled else 'candidate',
              'input_fingerprint':fingerprint(),'predictive_superiority':'尚未证实；详见时间顺序关联验证','minimum_pool':MIN_POOL,'weight_status':'初始试验参数，未宣称最优'}]
    tables=[('model_rankings',output),('model_contexts',contexts),('daily_observations',observations),('coverage_audit',audits),('coverage_summary',coverage),('bp_contract_audit',bp_contracts),('model_release',release),*validation]
    for name,rows in tables:
        write_table(name,rows);q[name]={'rows':rows,'source':deepcopy(source)}
        if rows:
            columns=sorted(set().union(*(row.keys() for row in rows)))
            with sqlite3.connect(ROOT/'data/processed/hoklab.sqlite') as conn:pd.DataFrame(rows,columns=columns).to_sql(name,conn,index=False,if_exists='replace')
    return {'rankings':len(output),'contexts':len(contexts),'observations':len(observations),'audits':len(audits),'default_model':release[0]['default_model']}
