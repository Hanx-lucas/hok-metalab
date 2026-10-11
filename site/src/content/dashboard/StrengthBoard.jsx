import React,{useState} from 'react';
import {DataComponent,DataTable,Dropdown,Dialog,SortableRegion,SortableItem,useDataApp,useDashboardTabs} from '../../data-app-public.jsx';
import './strength-board.css';
import {HeroPortrait,LaneIcon} from './HeroIdentity.jsx';
import zhaoyunArt from '../assets/hero-art/splash-107.webp';
const LANES=['对抗路','打野','中路','发育路','游走'];
const LABELS={overall:'综合强度',arena:'赛事强度',rank:'日常游戏强度'};
const score=v=>v==null?'—':Number(v).toFixed(1);
const pct=v=>v==null?'—':`${(100*v).toFixed(1)}%`;
function Score({value}){return <strong className={value==null?'sb-score sb-score--empty':'sb-score'}>{score(value)}</strong>}
function HeroDetail({row,dimension,context}){
 if(!row)return null;
 return <DataComponent id={`strength-${dimension}-detail`} queryId="strength_rankings" title={`${row.hero} · 强度依据`} kind="custom" displayRows={[row]} sourceRows={[row]}>
 <div className="sb-detail" data-reviewed-rows>
  <div className="sb-detail-heading"><div className="sb-detail-identity"><HeroPortrait id={row.hero_id} name={row.hero} size="large"/><div><span>{row.roles}</span><h3>{row.hero}</h3></div></div><div><Score value={row.score}/><span>{row.rank==null?'未评分':`总榜第 ${row.rank} 名`}</span></div></div>
  <p>{row.scoreReason}</p>
  {dimension!=='daily'&&row.arenaScore!=null&&<section><h4>赛事证据 · {context.event}</h4><dl><div><dt>赛事强度</dt><dd>{score(row.arenaScore)}</dd></div><div><dt>战斗场次</dt><dd>{row.battles??'—'}</dd></div><div><dt>原始胜率</dt><dd>{pct(row.winRate)}</dd></div><div><dt>平滑胜率</dt><dd>{pct(row.posteriorRate)}</dd></div><div><dt>出场率</dt><dd>{pct(row.pickRate)}</dd></div><div><dt>ban率</dt><dd>{pct(row.banRate)}</dd></div></dl>{row.arenaScore!=null&&<p>分数贡献：胜率 {score(row.winContribution)} + 出场 {score(row.pickContribution)} + ban {score(row.banContribution)}。<br/>平滑胜率95%区间 {pct(row.lowerRate)}–{pct(row.upperRate)}。</p>}</section>}
  {dimension!=='arena'&&<section><h4>日常证据 · {context.segment}</h4><dl><div><dt>日常强度</dt><dd>{score(row.dailyScore)}</dd></div><div><dt>胜率</dt><dd>{pct(row.dailyWinRate)}</dd></div><div><dt>出场率</dt><dd>{pct(row.dailyPickRate)}</dd></div><div><dt>ban率</dt><dd>{pct(row.dailyBanRate)}</dd></div></dl>{row.dailyScore!=null&&<p>分数贡献：胜率 {score(row.dailyWinContribution)} + 出场 {score(row.dailyPickContribution)} + ban {score(row.dailyBanContribution)}。</p>}<p>苏苏助手公开整理 · 公告日期 {context.observation_date} · 来源未提供样本场次。</p></section>}
  {dimension==='overall'&&row.score!=null&&<p className="sb-detail-equation">{row.overallBasis==='daily_only'?`${score(row.dailyScore)} × 100% = ${score(row.score)}`:`${score(row.arenaScore)} × 50% + ${score(row.dailyScore)} × 50% = ${score(row.score)}`}<br/><small>{row.overallBasis==='daily_only'?'暂无有效赛事评分，综合强度直接采用日常强度。':'按未舍入分数计算，展示值四舍五入。'}</small></p>}
 </div></DataComponent>;
}
export function DashboardContent(){
 const {queries}=useDataApp();
 const {activeTabId}=useDashboardTabs([{id:'overall',label:'综合强度',aliases:['timeline','models','sources']},{id:'arena',label:'赛事强度',previousLabels:['赛事探索']},{id:'rank',label:'日常游戏强度',previousLabels:['日常与分段']}]);
 const tab=['overall','arena','rank'].includes(activeTabId)?activeTabId:'overall';
 const dimension=tab==='rank'?'daily':tab;
 const summary=queries.summary?.rows?.[0]||{};
 const [event,setEvent]=useState(String(summary.latest_completed_league||'20260003'));
 const [segment,setSegment]=useState('全分段');
 const [search,setSearch]=useState('');const [lane,setLane]=useState('全部分路');
 const [selected,setSelected]=useState(null);const [open,setOpen]=useState(false);
 const contexts=queries.strength_contexts?.rows||[];
 const contextId=dimension==='arena'?`arena:${event}`:`${dimension}:${segment}`;
 const context=contexts.find(c=>c.context_id===contextId)||{};
 const rows=(queries.strength_rankings?.rows||[]).filter(r=>r.context_id===contextId);
 const ranked=rows.filter(r=>r.rank!=null).sort((a,b)=>a.rank-b.rank);
 const top10=ranked.slice(0,10);
 const lanes=(queries.strength_lane_rankings?.rows||[]).filter(r=>r.context_id===contextId);
 const terms=search.trim().toLowerCase();
 const filtered=rows.filter(r=>(lane==='全部分路'||r.roles.split('/').includes(lane))&&(!terms||`${r.hero} ${r.hero_id} ${r.hero_id===507?'光信 暗信':[50701,50702].includes(r.hero_id)?'李信':''}`.toLowerCase().includes(terms))).sort((a,b)=>(a.rank==null)-(b.rank==null)||(a.rank??0)-(b.rank??0)||a.hero_id-b.hero_id);
 const detail=rows.find(r=>r.hero_id===selected);
 const showDetail=r=>{setSelected(r.hero_id);setOpen(true)};
 const prefix=`strength-${dimension}`;
 const eventContexts=contexts.filter(c=>c.dimension==='arena');
 const eventLabels=Object.fromEntries(eventContexts.map(c=>[c.league_id,`${c.event}${c.event_status==='进行中'?' · 进行中':''}`]));
 const reset=()=>{setEvent(String(summary.latest_completed_league));setSegment('全分段');setSearch('');setLane('全部分路')};
 const columns=[{field:'rank',label:'名次',renderCell:v=>v??'—'},
  {field:'hero',label:'英雄',renderCell:(v,r)=><div className="sb-table-hero"><HeroPortrait id={r.hero_id} name={v} size="small"/><div><strong>{v}</strong><small>{r.roles}</small></div></div>},
  {field:'score',label:LABELS[tab],renderCell:v=><Score value={v}/>},
  ...(dimension==='overall'?[{field:'arenaScore',label:'赛事强度',renderCell:score},{field:'dailyScore',label:'日常强度',renderCell:score}]:dimension==='arena'?[{field:'winRate',label:'原始胜率',renderCell:pct},{field:'posteriorRate',label:'平滑胜率',renderCell:pct},{field:'pickRate',label:'出场率',renderCell:pct},{field:'banRate',label:'ban率',renderCell:pct},{field:'battles',label:'场次',renderCell:v=>v??'—'}]:[{field:'dailyWinRate',label:'胜率',renderCell:pct},{field:'dailyPickRate',label:'出场率',renderCell:pct},{field:'dailyBanRate',label:'ban率',renderCell:pct}]),
  {field:'scoreReason',label:'评分依据 / 待补原因'}];
 return <article className="strength-board">
  <header className="sb-opening"><img className="sb-key-art" src={zhaoyunArt} alt="赵云·苍天翔龙官方英雄原画"/><div className="sb-opening-copy"><div className="sb-brand"><span className="sb-brand-seal">王者</span><span>MetaLab 英雄研究</span></div><h1>王者荣耀<br/>英雄强度榜</h1><p>从赛场到峡谷，找到适合你的强势英雄。</p><div className="sb-links"><a href="./reports/index.html">阅读赛事研究报告</a><a href="./downloads/强度榜计算标准.md" download>查看评分标准</a></div></div><span className="sb-art-caption">赵云 · 苍天翔龙</span></header>
  <div className="sb-scope"><div><h2>{LABELS[tab]}</h2><span>{dimension==='arena'?context.event:`${dimension==='overall'?`${context.event} × `:''}${segment} · 日常公告 ${context.observation_date}`}</span></div><div className="sb-controls">{dimension==='arena'?<Dropdown label="赛事" showLabel value={event} choices={eventContexts.map(c=>c.league_id)} choiceLabels={eventLabels} onChange={setEvent}/>:<Dropdown label="日常分段" showLabel value={segment} choices={['全分段','巅峰赛1350+','顶端排位','巅峰千强']} onChange={setSegment}/>}<button className="sb-reset" onClick={reset}>重置</button></div></div>
  <DataComponent id={`${prefix}-scope`} queryId="strength_contexts" title="当前榜单范围" kind="custom" displayRows={context.context_id?[context]:[]} sourceRows={context.context_id?[context]:[]}>
   <div className="sb-summary" data-reviewed-rows><span><b>{context.scored??0}</b> 位已评分 / {context.canonical_heroes??0} 位目录英雄{dimension!=='arena'?' + 2 个李信玩法条目':''}</span><span>{dimension==='overall'?'双场景各50%；赛事缺失时采用100%日常':'强度 = 60% 胜率分位 + 25% 出场分位 + 15% ban分位'}</span></div>
  </DataComponent>
  {dimension==='overall'&&<p className="sb-note"><b>{context.combined_count} 位双场景评分 · {context.daily_only_count} 位日常替代</b>。采用最新已结束赛事与当前日常榜单，时间范围不同，作为跨场景参考。</p>}
  {dimension==='daily'&&<p className="sb-note">日常数据来自苏苏助手公开整理，尚未与营地对账；来源未提供样本量。</p>}
  {dimension==='arena'&&<p className="sb-note">腾讯公开赛事 · {context.event_start}–{context.event_end||'尚未结束'} · {context.event_status} · 至少30场且三项指标有效才参与排名。</p>}
  <SortableRegion id={`${prefix}-layout`} variant="freeform" authoredRevision={1} className="sb-sections">
   <SortableItem id={`${prefix}-top10`} label="总榜 Top 10" kind="custom">
    <DataComponent id={`${prefix}-top10`} queryId="strength_rankings" title="总榜 Top 10" variant="card" kind="custom" displayRows={top10} sourceRows={rows} description="与下方总榜使用相同范围和未舍入分数。点击英雄查看指标与分数贡献。">
     <div className="sb-top10" data-reviewed-rows>{top10.map(r=><button key={r.hero_id} className={`sb-hero-tile ${r.rank===1?'sb-hero-tile--first':''}`} onClick={()=>showDetail(r)} aria-label={`查看${r.hero}的强度数据`}><span className="sb-rank">{String(r.rank).padStart(2,'0')}</span><div className="sb-tile-person"><HeroPortrait id={r.hero_id} name={r.hero}/><div><h3>{r.hero}</h3><span className="sb-role">{r.roles}</span></div></div><Score value={r.score}/>{dimension==='overall'?<small className={r.overallBasis==='daily_only'?'sb-basis sb-basis--daily':'sb-basis'}>{r.overallBasis==='daily_only'?`日常替代 · 100%日常`:`赛事 ${score(r.arenaScore)} · 日常 ${score(r.dailyScore)}`}</small>:<small>胜率 {pct(dimension==='arena'?r.posteriorRate:r.dailyWinRate)}{dimension==='arena'?'（平滑）':''}</small>}</button>)}</div>
     {!top10.length&&<p className="sb-empty">当前赛事缺少有效BP指标或足够场次，暂不能生成强度排名。下方保留全部英雄与已有数据。</p>}
    </DataComponent>
   </SortableItem>
   <SortableItem id={`${prefix}-lanes`} label="各分路 Top 5" kind="custom">
    <DataComponent id={`${prefix}-lanes`} queryId="strength_lane_rankings" title="各分路 Top 5" variant="card" kind="custom" displayRows={lanes} sourceRows={lanes} description="按当前官方推荐分路过滤全局分数，不重新计分；多分路英雄可出现在多个榜单。">
     <div className="sb-lanes" data-reviewed-rows>{LANES.map((l,i)=><section key={l} className="sb-lane"><h3><LaneIcon lane={l}/>{l}</h3><ol>{lanes.filter(r=>r.lane===l).map(r=><li key={r.hero_id}><button onClick={()=>showDetail(r)} aria-label={`查看${l}${r.hero}的强度数据`}><span className="sb-lane-rank">{r.lane_rank}</span><HeroPortrait id={r.hero_id} name={r.hero} size="mini"/><span className="sb-lane-name">{r.hero}</span><Score value={r.score}/></button></li>)}</ol>{!lanes.some(r=>r.lane===l)&&<p className="sb-empty">暂无有效评分</p>}</section>)}</div><p className="sb-footnote">沿用总榜分数 · 当前官方推荐分路 · 多分路英雄可重复出现</p>
    </DataComponent>
   </SortableItem>
   <SortableItem id={`${prefix}-all`} label="全部英雄总榜" kind="table">
    <DataComponent id={`${prefix}-all`} queryId="strength_rankings" title="全部英雄总榜" variant="card" kind="table" displayRows={filtered} sourceRows={filtered} description="已评分英雄按分数排序，未评分条目列在最后；搜索和分路筛选不改变原始名次。点击任意英雄查看证据。">
     <DataTable columns={columns} rows={filtered} searchable={false} label={`${LABELS[tab]}全部英雄总榜`} rowKey="hero_id" selectedRowKey={selected} onRowSelect={showDetail} rowActionLabel={r=>`查看${r.hero}的强度详情`} toolbarControls={<><label className="sb-search"><span>搜索英雄</span><input type="search" placeholder="输入英雄名或ID，例如赵云" value={search} onChange={e=>setSearch(e.target.value)}/></label><Dropdown label="总榜分路" showLabel value={lane} choices={['全部分路',...LANES]} onChange={setLane}/><span className="sb-result-count">{filtered.length} 条结果</span></>}/>
     <p className="sb-footnote">“—” 表示证据不足或未评分，原因见表格。光信/暗信玩法仅保留原始日常数据，不重复参与英雄排名。</p>
    </DataComponent>
   </SortableItem>
  </SortableRegion>
  <details className="sb-method"><summary>计算公式与评分标准</summary><DataComponent id={`${prefix}-method`} queryId="strength_contexts" title="强度计算方法" kind="custom" displayRows={context.context_id?[context]:[]} sourceRows={context.context_id?[context]:[]}><div className="sb-method-grid"><section><h3>赛事强度 T</h3><p>100 × [60% × P(平滑胜率) + 25% × P(出场率) + 15% × P(ban率)]</p><p>平滑胜率 = (胜场 + 10) / (场次 + 20)。至少30场，胜负计数一致且BP有效才排名。</p></section><section><h3>日常强度 D</h3><p>100 × [60% × P(原始胜率) + 25% × P(出场率) + 15% × P(ban率)]</p><p>同日期、同分段计算；三项指标完整才评分。没有样本场次，不计算平滑胜率或置信区间。</p></section><section><h3>综合强度 C</h3><p>双场景有效：50% × T + 50% × D<br/>赛事无有效评分：100% × D</p><p>使用最新已结束赛事与所选日常分段。缺少赛事评分时直接采用日常强度并标记“日常替代”；日常也缺失时不评分。</p></section></div><p>P是同一范围内的分位数（平均秩 / 有效英雄数），越大越靠前；赛事分位数沿用当届原分析完整有效池，30场门槛后不重算。同分按英雄ID稳定排序。分路榜沿用全局分数。</p><p>权重为项目设定，分数是相对表现指标；赛事与日常的观察时间、玩家环境不同，综合分仅供参考。数据来源、指标定义与清洗证据可从每块右上角的来源菜单查看。</p><div className="sb-links"><a href="./downloads/strength_rankings.csv" download>下载完整三维榜单 CSV</a><a href="./downloads/强度榜计算标准.md" download>阅读完整计算标准</a><a href="./reports/index.html">历届赛事变化与模型验证 ↗</a></div></DataComponent></details>
  <Dialog open={open} onClose={()=>setOpen(false)} title={`${detail?.hero||'英雄'} · ${LABELS[tab]}`}><HeroDetail row={detail} dimension={dimension} context={context}/></Dialog>
  <footer className="sb-footer"><span>肖涵 · Python 数据分析作品集</span><span>腾讯公开赛事 · 苏苏助手公开整理 · 非官方评级</span><a href="https://pvp.qq.com/" target="_blank" rel="noreferrer">英雄美术 © 腾讯《王者荣耀》</a></footer>
 </article>;
}
