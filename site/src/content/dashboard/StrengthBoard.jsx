import React,{useState,useMemo,useEffect} from 'react';
import {DataComponent,DataTable,Dropdown,Dialog,Slider,SortableRegion,SortableItem,useDataApp,useDashboardTabs} from '../../data-app-public.jsx';
import {HeroPortrait,LaneIcon} from './HeroIdentity.jsx';
import {HeroModelDetail,fmt,pct} from './HeroModelDetail.jsx';
import {ModelAnalysis} from './ModelAnalysis.jsx';
import './strength-board.css';
import './model-upgrade.css';
import zhaoyunArt from '../assets/hero-art/splash-107.webp';
const LANES=['对抗路','打野','中路','发育路','游走'];
const LABELS={overall:'综合强度',arena:'赛事强度',rank:'日常游戏强度'};
const Score=({value})=><strong className={value==null?'sb-score sb-score--empty':'sb-score'}>{fmt(value)}</strong>;
const ranked=rows=>rows.slice().sort((a,b)=>(a.score==null)-(b.score==null)||(b.score??0)-(a.score??0)||a.hero_id-b.hero_id).map((r,i)=>({...r,rank:r.score==null?null:i+1}));
export function DashboardContent(){
 const {queries}=useDataApp();
 const {activeTabId}=useDashboardTabs([{id:'overall',label:'综合强度',aliases:['timeline','models','sources']},{id:'arena',label:'赛事强度',previousLabels:['赛事探索']},{id:'rank',label:'日常游戏强度',previousLabels:['日常与分段']}]);
 const tab=['overall','arena','rank'].includes(activeTabId)?activeTabId:'overall',dimension=tab==='rank'?'daily':tab;
 const summary=queries.summary?.rows?.[0]||{},release=queries.model_release?.rows?.[0]||{};
 const [model,setModel]=useState(release.default_model||'V1'),[event,setEvent]=useState(String(summary.latest_completed_league||'20260003')),[segment,setSegment]=useState('全分段');
 const [scope,setScope]=useState('全部英雄'),[customWeight,setCustomWeight]=useState(null),[search,setSearch]=useState(''),[selected,setSelected]=useState(null),[category,setCategory]=useState('全部问题');
 const contexts=queries.model_contexts?.rows||[],allRows=queries.model_rankings?.rows||[];
 const contextId=dimension==='arena'?`arena:${event}`:`${dimension}:${segment}`;
 const context=contexts.find(c=>c.model===model&&c.context_id===contextId&&c.scope===scope)||{},globalContext=contexts.find(c=>c.model===model&&c.context_id===contextId&&c.scope==='全部英雄')||{};
 const lookup=useMemo(()=>new Map(allRows.map(r=>[`${r.model}|${r.context_id}|${r.scope}|${r.hero_id}`,r])),[allRows]);
 const weight=customWeight??context.weightE??.65;
 useEffect(()=>{setCustomWeight(null);setSelected(null)},[model,scope,contextId]);
 const derive=r=>{
  if(r.model!=='V2'||customWeight==null||r.scope!==scope||r.score==null)return r;
  const eContribution=customWeight*r.E,bContribution=(1-customWeight)*r.B;
  let arenaScore=r.arenaScore,dailyScore=r.dailyScore;
  if(r.dimension==='overall'){
   const a=lookup.get(`${r.model}|arena:${r.league_id}|${r.scope}|${r.hero_id}`),d=lookup.get(`${r.model}|daily:${r.segment}|${r.scope}|${r.hero_id}`);
   arenaScore=a?.score!=null?customWeight*a.E+(1-customWeight)*a.B:null;dailyScore=d?.score!=null?customWeight*d.E+(1-customWeight)*d.B:null;
  }else if(r.dimension==='arena')arenaScore=eContribution+bContribution;else dailyScore=eContribution+bContribution;
  return {...r,score:eContribution+bContribution,eContribution,bContribution,arenaScore,dailyScore,weightE:customWeight,weightB:1-customWeight,temporaryWeightScenario:true};
 };
 const atScope=s=>ranked(allRows.filter(r=>r.model===model&&r.context_id===contextId&&r.scope===s).map(derive));
 const rows=atScope(scope),globalRows=scope==='全部英雄'?rows:atScope('全部英雄'),top10=globalRows.filter(r=>r.score!=null).slice(0,10);
 const laneRows=Object.fromEntries(LANES.map(l=>[l,atScope(l)]));
 const terms=search.trim().toLowerCase(),matches=r=>!terms||`${r.hero} ${r.hero_id} ${r.hero_id===507?'光信 暗信':[50701,50702].includes(r.hero_id)?'李信':''}`.toLowerCase().includes(terms);
 const filtered=rows.filter(matches);
 const eventContexts=contexts.filter(c=>c.model===model&&c.dimension==='arena'&&c.scope==='全部英雄');
 const eventLabels=Object.fromEntries(eventContexts.map(c=>[c.league_id,`${c.event}${c.event_status==='进行中'?' · 进行中':''}`]));
 const auditRows=(queries.coverage_audit?.rows||[]).filter(r=>dimension==='overall'?(r.context_id===`daily:${segment}`||r.context_id===`arena:${globalContext.league_id}`):r.context_id===contextId);
 const auditFiltered=auditRows.filter(r=>r.category!=='完整有效'&&matches(r)&&(category==='全部问题'||r.category===category));
 const auditSummaries=(queries.coverage_summary?.rows||[]).filter(r=>dimension==='overall'?(r.context_id===`daily:${segment}`||r.context_id===`arena:${globalContext.league_id}`):r.context_id===contextId);
 const prefix=`strength-${dimension}`,boardTitle=scope==='全部英雄'?'全部英雄总榜':`${scope}独立强度榜`;
 const reset=()=>{setEvent(String(summary.latest_completed_league));setSegment('全分段');setScope('全部英雄');setSearch('');setCustomWeight(null);setCategory('全部问题')};
 const getScene=(r,dim)=>{
  const key=dim==='arena'?`arena:${globalContext.league_id||r.league_id}`:`daily:${r.segment||segment}`;
  const scene=lookup.get(`${r.model}|${key}|${r.scope}|${r.hero_id}`);
  return scene?derive(scene):null;
 };
 const heroCell=(v,r)=><div className="sb-table-hero"><HeroPortrait id={r.hero_id} name={v} size="small"/><div><strong>{v}</strong><small>{r.roles}</small></div></div>;
 const columns=[{field:'rank',label:'本榜名次',renderCell:v=>v??'—'},{field:'hero',label:'英雄',renderCell:heroCell},{field:'score',label:'强度分',renderCell:v=><Score value={v}/>},
  {field:'E',label:'实战E',renderCell:fmt},{field:'B',label:'BP优先级B',renderCell:fmt},
  ...(dimension==='overall'?[{field:'scoreBasis',label:'评分依据',renderCell:(v,r)=>r.route==='daily_fallback'?'仅日常 100%D':r.route==='paired'?'双场景 30%T/70%D':'—'},{field:'arenaScore',label:'赛事T',renderCell:fmt},{field:'dailyScore',label:'日常D',renderCell:fmt}]:dimension==='arena'?[
   {field:'posteriorRate',label:'平滑胜率',renderCell:pct},{field:'pickRate',label:'出场率',renderCell:pct},{field:'banRate',label:'禁用率',renderCell:pct},{field:'bpRate',label:'审计BP',renderCell:pct},{field:'battles',label:'场次'}]:[
   {field:'dailyWinRate',label:'原始胜率',renderCell:pct},{field:'dailyPickRate',label:'出场率',renderCell:pct},{field:'dailyBanRate',label:'禁用率',renderCell:pct},{field:'bpRate',label:'审计BP',renderCell:pct}]),{field:'scoreReason',label:'评分依据 / 未评分原因'}];
 return <article className="strength-board">
 <header className="sb-opening"><img className="sb-key-art" src={zhaoyunArt} alt="赵云·苍天翔龙官方英雄原画"/><div className="sb-opening-copy"><div className="sb-brand"><span className="sb-brand-seal">王者</span><span>MetaLab 英雄研究</span></div><h1>王者荣耀<br/>英雄强度榜</h1><p>从赛场到峡谷，看懂强度与禁选优先级。</p><div className="sb-links"><a href="./reports/index.html">阅读赛事研究报告</a><a href="./downloads/V2模型验证报告.md" download>阅读V1/V2验证</a></div></div><span className="sb-art-caption">赵云 · 苍天翔龙</span></header>
 <div className="sb-scope"><div><h2>{LABELS[tab]}</h2><span>{dimension==='arena'?context.event:`${dimension==='overall'?`${context.event} × `:''}${segment} · 日常公告 ${context.observation_date}`}</span></div><div className="sb-controls"><Dropdown label="评分模型" showLabel value={model} choices={['V2','V1']} choiceLabels={{V2:'V2 · 分位＋Z（试验）',V1:'V1 · 原分位对照'}} onChange={setModel}/>{dimension==='arena'?<Dropdown label="赛事" showLabel value={event} choices={eventContexts.map(c=>c.league_id)} choiceLabels={eventLabels} onChange={setEvent}/>:<Dropdown label="日常分段" showLabel value={segment} choices={['全分段','巅峰赛1350+','顶端排位','巅峰千强']} onChange={setSegment}/>}<button className="sb-reset" onClick={reset}>重置</button></div></div>
 <DataComponent id={`${prefix}-scope`} queryId="model_contexts" title="当前全英雄榜范围" kind="custom" sourceRows={[globalContext]} displayRows={[globalContext]}>
 <div className="sb-summary" data-reviewed-rows><span><b>{globalContext.scored??0}</b> 位全英雄榜已评分 / 133 位目录英雄</span><span>{dimension==='overall'?'双场景30%T/70%D；缺赛事时100%D同榜':model==='V2'?'S = 65% × 实战E + 35% × BP优先级B':'V1 = 60%胜率分位 + 25%出场分位 + 15%ban分位'}</span></div></DataComponent>
 {dimension==='overall'?<p className="sb-note"><b>{globalContext.combined_count} 位双场景 · {globalContext.daily_only_count} 位仅日常参考</b>，一起排序并标记依据。赛事 {context.event_start}—{context.event_end} 与日常公告 {context.observation_date} 的环境和日期不同，不代表同版本真实综合实力。</p>:dimension==='daily'?<p className="sb-note">苏苏助手第三方公开整理，未与营地对账，无样本量；日常不做Beta平滑或置信区间。</p>:<p className="sb-note">腾讯公开赛事 · {context.event_start}—{context.event_end||'尚未结束'} · {context.event_status}。V2先排除不足30场及口径异常，再计算比较池。</p>}
 <SortableRegion id={`${prefix}-layout`} variant="freeform" authoredRevision={3} className="sb-sections">
 <SortableItem id={`${prefix}-top10`} label="总榜 Top 10" kind="custom"><DataComponent id={`${prefix}-top10`} queryId="model_rankings" title="总榜 Top 10" variant="card" kind="custom" displayRows={top10} sourceRows={globalRows} description="同场景全英雄统一权重；综合双有效30%T/70%D，仅日常有效100%D同榜并标记。分路不影响横向总榜。">
 <div className="sb-top10" data-reviewed-rows>{top10.map(r=><button key={r.hero_id} className={`sb-hero-tile ${r.rank===1?'sb-hero-tile--first':''}`} onClick={()=>setSelected(r)} aria-label={`查看${r.hero}的强度数据`}><span className="sb-rank">{String(r.rank).padStart(2,'0')}</span><div className="sb-tile-person"><HeroPortrait id={r.hero_id} name={r.hero}/><div><h3>{r.hero}</h3><span className="sb-role">{r.roles}</span></div></div><Score value={r.score}/><small>{dimension==='overall'?r.route==='daily_fallback'?`仅日常 100%D ${fmt(r.dailyScore)}`:`双场景 · T ${fmt(r.arenaScore)} / D ${fmt(r.dailyScore)}`:`E ${fmt(r.E)} · B ${fmt(r.B)}`}</small></button>)}</div>{!top10.length&&<p className="sb-empty">数据不满足排名条件；原始指标和未评分原因保留在总表。</p>}</DataComponent></SortableItem>
 <SortableItem id={`${prefix}-lanes`} label="各分路 Top 5" kind="custom"><DataComponent id={`${prefix}-lanes`} queryId="model_rankings" title="各分路 Top 5" variant="card" kind="custom" displayRows={LANES.flatMap(l=>laneRows[l].filter(r=>r.score!=null).slice(0,5))} sourceRows={LANES.flatMap(l=>laneRows[l])} description="V2各分路独立重算分位、均值、σ；V1仅沿用全局分筛选对照。推荐位置不是实际比赛位置，多分路英雄可以重复。">
 <div className="sb-lanes" data-reviewed-rows>{LANES.map(l=>{const lc=contexts.find(c=>c.model===model&&c.context_id===contextId&&c.scope===l)||{};return <section key={l} className="sb-lane"><h3><LaneIcon lane={l}/>{l}</h3><small className="sb-lane-meta">{lc.scored||0} 名 · {model==='V2'?`E${Math.round(lc.weightE*100)}/B${Math.round(lc.weightB*100)}`:'V1全局对照'}</small><ol>{laneRows[l].filter(r=>r.score!=null).slice(0,5).map(r=><li key={r.hero_id}><button onClick={()=>setSelected(r)} aria-label={`查看${l}${r.hero}的强度数据`}><span className="sb-lane-rank">{r.rank}</span><HeroPortrait id={r.hero_id} name={r.hero} size="mini"/><span className="sb-lane-name">{r.hero}</span><Score value={r.score}/></button></li>)}</ol>{!lc.scored&&<p className="sb-empty">有效比较池不足，不强行排名</p>}{lc.scored>0&&lc.scored<10&&<p className="sb-footnote">低可信度：不足10名</p>}</section>})}</div><p className="sb-footnote">V2独立分路分不可直接跨路比较；权重是待验证参数。官方推荐位置可能重叠，数量之和不等于独立英雄数。</p></DataComponent></SortableItem>
 <SortableItem id={`${prefix}-all`} label="全英雄与分路排行榜" kind="table"><DataComponent id={`${prefix}-all`} queryId="model_rankings" title={boardTitle} variant="card" kind="table" displayRows={filtered} sourceRows={filtered} description="选中分路后使用该分路独立V2统计池；搜索不改变名次。临时权重只重组审阅E/B，既有分位与Z保持不变。">
 <div className="sb-model-toolbar"><Dropdown label="排行榜" showLabel value={scope} choices={['全部英雄',...LANES]} choiceLabels={{全部英雄:'全英雄综合总榜',...Object.fromEntries(LANES.map(l=>[l,`${l}强度榜`]))}} onChange={setScope}/>{model==='V2'&&<div className="sb-weight-control"><Slider label="实战E权重" min={45} max={85} step={5} value={Math.round(weight*100)} formatValue={v=>`${v}% E / ${100-v}% B`} onChange={v=>setCustomWeight(Number(v)/100)} showBounds={false}/><button className="sb-reset" onClick={()=>setCustomWeight(null)}>恢复默认权重</button></div>}</div>
 <p className="sb-model-context">{model} · {scope} · {context.scored||0} 名可排名。{model==='V2'?`${customWeight==null?'默认试验参数':'临时权重情景'}：E ${Math.round(weight*100)}% / B ${100-Math.round(weight*100)}%。`:'保持V1原分数；分路是全局筛选对照。'}{context.trust}</p>
 <DataTable columns={columns} rows={filtered} searchable={false} label={boardTitle} rowKey="hero_id" selectedRowKey={selected?.hero_id} onRowSelect={setSelected} rowActionLabel={r=>`查看${r.hero}的强度详情`} toolbarControls={<><label className="sb-search"><span>搜索英雄</span><input type="search" placeholder="英雄名或ID，例如敖隐" value={search} onChange={e=>setSearch(e.target.value)}/></label><span className="sb-result-count">{filtered.length} 条结果</span></>}/>
 <p className="sb-footnote">“—”表示不能评分，保留具体原因；未评分者不认定为弱。李信两个玩法条目只展示原始数据，不重复排名。</p></DataComponent></SortableItem>
 <SortableItem id={`${prefix}-analysis`} label="强度解读" kind="custom"><ModelAnalysis key={`${model}|${contextId}|${scope}`} rows={rows} context={context} contexts={contexts} allRows={allRows} scope={scope} model={model} dimension={dimension} derive={derive} onHero={setSelected}/></SortableItem>
 </SortableRegion>
 <details className="sb-method"><summary>数据覆盖与未评分原因审计</summary><DataComponent id={`${prefix}-audit`} queryId="coverage_audit" title="逐英雄覆盖审计" kind="table" sourceRows={auditFiltered} displayRows={auditFiltered}>
 <div className="sb-audit-summary">{auditSummaries.map(c=><p key={c.context_id}>{c.event||c.segment}：完整 {c['完整有效']} /133 · 无记录 {c['完全无记录']} · 缺胜率 {c['胜率缺失']} · 缺其他 {c['其他指标缺失']} · 不足30场 {c['赛事场次不足']} · 口径异常 {c['统计口径异常']}</p>)}</div>
 <DataTable columns={[{field:'hero',label:'英雄',renderCell:heroCell},{field:'dimension',label:'场景',renderCell:v=>v==='arena'?'赛事':'日常'},{field:'category',label:'分类'},{field:'reason',label:'具体原因'},{field:'date',label:'日期'},{field:'battles',label:'赛事场次'}]} rows={auditFiltered} searchable={false} label="逐英雄覆盖审计" toolbarControls={<Dropdown label="缺失分类" showLabel value={category} choices={['全部问题','完全无记录','胜率缺失','其他指标缺失','赛事场次不足','统计口径异常']} onChange={setCategory}/>}/>
 <div className="sb-links"><a href="./downloads/coverage_audit.csv" download>下载全部英雄缺失明细</a><a href="./downloads/数据来源与历史扩展审计.md" download>来源与历史扩展限制</a></div></DataComponent></details>
 <details className="sb-method"><summary>计算公式、比较池与模型验证</summary><DataComponent id={`${prefix}-method`} queryId="model_contexts" title="模型计算标准" kind="custom" sourceRows={[context]} displayRows={[context]}>
 <div className="sb-method-grid"><section><h3>V1 · 原分位模型</h3><p>60P(胜率)+25P(出场)+15P(ban)。原赛事与日常得分完整保留；V1分路沿用全局分数作对照。</p></section><section><h3>V2 · 实战E / 禁选B</h3><p>Z=(X−μ)/σ；N=clip(.5+Z/4,0,1)；H=.5P+.5N；E=100H(W)，B=100H(BP)。全英雄 S=.65E+.35B。</p><p>BP先审计再相加，Z使用5/95%缩尾BP，原始BP用于平均秩。σ为总体标准差；零方差Z=0。至少5名才评分。</p></section><section><h3>双场景与独立分路</h3><p>C=.3T+.7D；仅日常有效时100%D进入同一综合榜，明确标注评分依据和赛事未评分原因。V2分路独立重算P/μ/σ；对抗65/35、打野70/30、中路70/30、发育60/40、游走60/40。</p></section></div><p>赛事W继续Beta(10,10)，30场门槛先于V2统计池。日常没有样本量，直接用公布胜率。参数属于待检验试验；时间顺序关联尚不能证明预测能力或最优权重。</p><div className="sb-links"><a href="./downloads/强度榜计算标准.md" download>完整方法</a><a href="./downloads/model_rankings.csv" download>默认评分与因子CSV</a><a href="./downloads/V2模型验证报告.md" download>新旧对照与回测</a><a href="./reports/index.html">历史赛事研究报告 ↗</a></div></DataComponent></details>
 <Dialog expanded open={selected!=null} onClose={()=>setSelected(null)} title={`${selected?.hero||'英雄'} · ${model}强度依据`}><HeroModelDetail row={selected} contexts={contexts} getScene={getScene}/></Dialog>
 <footer className="sb-footer"><span>肖涵 · Python数据分析作品集</span><span>腾讯公开赛事 · 苏苏助手第三方整理 · 实验模型非官方评级</span><a href="https://pvp.qq.com/" target="_blank" rel="noreferrer">英雄美术 © 腾讯《王者荣耀》</a></footer>
 </article>;
}
