import React from 'react';
import {DataComponent} from '../../data-app-public.jsx';
import {HeroPortrait} from './HeroIdentity.jsx';
export const fmt=v=>v==null?'—':Number(v).toFixed(1);
export const pct=v=>v==null?'—':`${(100*v).toFixed(2)}%`;
const precise=v=>v==null?'—':Number(v).toFixed(4);
const Metric=({label,value})=><div><dt>{label}</dt><dd>{value}</dd></div>;
function SceneEvidence({row,context}){
 if(!row)return <p>此场景无记录。缺失不代表弱，也不补零。</p>;
 const arena=row.dimension==='arena',w=arena?row.winRate:row.dailyWinRate,p=arena?row.pickRate:row.dailyPickRate,b=arena?row.banRate:row.dailyBanRate;
 return <DataComponent id={`model-detail-${row.model}-${row.dimension}-evidence`} queryId={row.route==='daily_observation'?'daily_observations':'model_rankings'} title={`${arena?'赛事':'日常'}证据 · ${context?.event||row.segment||'—'}`} kind="custom" sourceRows={[row]} displayRows={[row]}>
 <section className="sb-model-evidence" data-reviewed-rows>
  <h4>{arena?'腾讯公开赛事':'苏苏助手第三方公开整理'} · {arena?`${context?.event_start}—${context?.event_end||'进行中'}`:`公告 ${context?.observation_date}`}</h4>
  <dl><Metric label="原始胜率" value={pct(w)}/><Metric label="出场率" value={pct(p)}/><Metric label="展示禁用率" value={pct(b)}/><Metric label="审计通过的BP=出场+禁用" value={pct(row.bpRate)}/>{arena&&<Metric label="正式赛事战斗场次" value={row.battles??'—'}/>}<Metric label="有效比较池" value={`${row.comparisonN??0} 名`}/></dl>
  <p>{row.scoreReason}</p>
  {row.model==='V2'&&row.score!=null?<>
   <div className="sb-factor-grid">
    <div><h4>实战表现 E · 胜率</h4><dl><Metric label={arena?'Beta(10,10)平滑W':'建模W（原始胜率）'} value={pct(row.wRaw)}/><Metric label="平均秩分位 P(W)" value={precise(row.wPercentile)}/><Metric label="比较池 μ / σ" value={`${precise(row.wMean)} / ${precise(row.wStd)}`}/><Metric label="Z-score" value={precise(row.wZ)}/><Metric label="标准化 N(Z)" value={precise(row.wNormalized)}/><Metric label="E=100×(.5P+.5N)" value={fmt(row.E)}/></dl></div>
    <div><h4>BP优先级 B · 禁选</h4><dl><Metric label="原始BP（秩使用此值）" value={pct(row.bpRate)}/><Metric label="5% / 95%缩尾界限" value={`${pct(row.bpLow)} / ${pct(row.bpHigh)}`}/><Metric label="缩尾BP（Z使用此值）" value={pct(row.bpAdjusted)}/><Metric label="平均秩分位 P(BP)" value={precise(row.bpPercentile)}/><Metric label="缩尾池 μ / σ" value={`${precise(row.bpMean)} / ${precise(row.bpStd)}`}/><Metric label="Z-score / N(Z)" value={`${precise(row.bpZ)} / ${precise(row.bpNormalized)}`}/><Metric label="B=100×(.5P+.5N)" value={fmt(row.B)}/></dl></div>
   </div>
   <p className="sb-detail-equation">E {fmt(row.E)} × {Math.round(100*row.weightE)}% + B {fmt(row.B)} × {Math.round(100*row.weightB)}%<br/>{fmt(row.eContribution)} + {fmt(row.bContribution)} = <b>{fmt(row.score)} 分</b></p>
  </>:row.model==='V1'&&row.score!=null?<p>V1三项贡献：{fmt(arena?row.winContribution:row.dailyWinContribution)} + {fmt(arena?row.pickContribution:row.dailyPickContribution)} + {fmt(arena?row.banContribution:row.dailyBanContribution)} = {fmt(row.score)} 分。原始分位池与计算结果保留。</p>:null}
  {arena&&row.lowerRate!=null?<p>Beta胜率95%区间：{pct(row.lowerRate)}—{pct(row.upperRate)}（简化模型的可信区间，非因果结论）。</p>:!arena?<p>来源没有样本量或精确统计窗口；不构造贝叶斯平滑与置信区间。</p>:null}
 </section></DataComponent>;
}
export function HeroModelDetail({row,contexts,getScene}){
 if(!row)return null;
 const context=contexts.find(c=>c.context_id===row.context_id&&c.model===row.model&&c.scope===row.scope);
 const sceneRows=row.dimension==='overall'?[getScene(row,'arena'),getScene(row,'daily')]:[row];
 return <DataComponent id="model-hero-detail" queryId={row.route==='daily_observation'?'daily_observations':'model_rankings'} title={`${row.hero} · 模型与计算依据`} kind="custom" displayRows={[row]} sourceRows={[row]}>
 <div className="sb-detail">
  <div className="sb-detail-heading"><div className="sb-detail-identity"><HeroPortrait id={row.hero_id} name={row.hero} size="large"/><div><span>{row.model} · {row.scope} · 官方推荐 {row.roles}</span><h3>{row.hero}</h3></div></div><div><strong className="sb-score">{fmt(row.score)}</strong><span>{row.rank==null?'未进入此榜':`${row.route==='daily_observation'?'日常观察榜':'当前榜单'}第 ${row.rank} 名`}</span></div></div>
  <p>{row.scoreReason}。{row.trust}</p>
  {row.scope!=='全部英雄'&&<p>分路分仅用于本分路比较；官方推荐位置不是实际逐局比赛位置。V2独立重算比较池，V1是原总榜筛选对照。</p>}
  {row.route==='daily_observation'&&<p className="sb-detail-equation">独立观察分 = D {fmt(row.dailyScore)}；没有有效T，不形成综合分。</p>}
  {row.route==='daily_fallback'&&<p className="sb-detail-equation">仅日常参考：综合榜展示分 = 100% × D {fmt(row.dailyScore)} = {fmt(row.score)}<br/><small>赛事未形成有效T：{row.arenaMissingReason}。不补赛事零分；此条不是双场景综合估计。</small></p>}
  {row.dimension==='overall'&&row.route==='paired'&&<p className="sb-detail-equation">T {fmt(row.arenaScore)} × 30% + D {fmt(row.dailyScore)} × 70% = C {fmt(row.score)}<br/><small>综合同榜 {row.comparisonN} 名；赛事统计池 {row.arenaPoolN} 名 / 日常统计池 {row.dailyPoolN} 名。时间和环境不同。</small></p>}
  {sceneRows.filter(Boolean).map(scene=><SceneEvidence key={scene.dimension} row={scene} context={contexts.find(c=>c.context_id===scene.context_id&&c.model===scene.model&&c.scope===scene.scope)}/>)}
  <p>分位数采用平均并列秩/N；总体标准差ddof=0，零方差令Z=0、N=.5。至少5名才评分，5—9名提示低可信度。所有贡献按未舍入值加总。</p>
 </div></DataComponent>;
}
