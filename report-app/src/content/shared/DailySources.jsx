import React,{useState} from 'react';
import {DataComponent,DataTable,EvidenceChart,Dropdown} from '../../data-app-public.jsx';
import './DailySources.css';

const pct=v=>v==null?'—':`${(100*v).toFixed(2)}%`;
const segments=['全分段','巅峰赛1350+','顶端排位','巅峰千强'];
const colors=Object.fromEntries(segments.map((s,i)=>[s,`var(--chart-${i+1})`]));
const metrics={winRate:'胜率',pickRate:'出场率',banRate:'禁用率'};
const columns=[{field:'hero',label:'英雄'},{field:'segment',label:'分段'},{field:'date',label:'日期'},...Object.entries(metrics).map(([field,label])=>({field,label,renderCell:pct}))];

export function DailySources({queries}){
 const current=queries.daily_current?.rows||[],history=queries.daily_history?.rows||[],summary=queries.daily_summary?.rows?.[0];
 const [segment,setSegment]=useState('全分段'),[hero,setHero]=useState('赵云'),[measure,setMeasure]=useState('winRate'),[window,setWindow]=useState('180');
 if(!summary)return null;
 const pool=current.filter(r=>r.segment===segment),ranked=pool.filter(r=>r.winRate!=null&&r.pickRate>=.01).sort((a,b)=>b.winRate-a.winRate).slice(0,12);
 const comparison=current.filter(r=>r.hero===hero);
 const cutoff=window==='history_start'?summary.history_first:new Date(Date.parse(summary.history_last+'T00:00:00Z')-(Number(window)-1)*86400000).toISOString().slice(0,10);
 const scoped=history.filter(r=>r.hero===hero&&r.date>=cutoff);
 // Explicit null breaks at absent dates: lines must not conceal upstream gaps.
 const plotted=[];
 for(const s of segments){
  const group=scoped.filter(r=>r.segment===s).sort((a,b)=>a.date.localeCompare(b.date));
  group.forEach((r,i)=>{
   if(i&&Date.parse(r.date)-Date.parse(group[i-1].date)>86400000)plotted.push({hero,segment:s,date:new Date(Date.parse(group[i-1].date)+86400000).toISOString().slice(0,10),[measure]:null});
   plotted.push(r);
  });
 }
 return <section className="lab-daily-source">
  <div className="lab-scope"><h2>日常分段数据已取得公开样本</h2><span>苏苏助手数据站 · 第三方补充</span></div>
  <DataComponent id="daily-source-coverage" title="日常数据覆盖" queryId="daily_summary" kind="custom" sourceRows={[summary]} displayRows={[summary]}>
   <div className="lab-statrow" data-reviewed-rows><div><strong>{summary.current_rows}</strong><span>4档当前榜单记录</span></div><div><strong>{summary.history_heroes} 位</strong><span>已验证历史英雄</span></div><div><strong>{summary.history_complete.toLocaleString('zh-CN')}</strong><span>三指标完整历史观察</span></div></div>
   <p>当前榜单日期 {summary.observation_date}；历史样本 {summary.history_first} 至 {summary.history_last}。当前 {summary.current_complete} 条记录具备三指标，缺失保持为空。</p>
  </DataComponent>
  <div className="lab-alert">数据由苏苏助手数据站整理，尚未与王者营地独立对账。未提供样本场次、胜负计数与S赛季映射，以下只作描述探索。历史仅包含赵云、关羽、鲁班大师、蒙恬；并非全英雄历年榜单。</div>
  <p className="lab-note">当前榜单与历史末日的其他分段数值存在差异，暂不确定更新或统计窗口原因；两个端点分开展示，不填补、合并或平均。来源还包含英雄形态、玩法变体条目。</p>
  <div className="lab-controls"><Dropdown label="日常分段" showLabel value={segment} choices={segments} onChange={setSegment}/><Dropdown label="历史样本英雄" showLabel value={hero} choices={['赵云','关羽','鲁班大师','蒙恬']} onChange={setHero}/><Dropdown label="日常观察指标" showLabel value={measure} choices={Object.keys(metrics)} choiceLabels={metrics} onChange={setMeasure}/><Dropdown label="历史范围" showLabel value={window} choices={['90','180','365','history_start']} choiceLabels={{90:'最近90日',180:'最近180日',365:'最近365日',history_start:'全部已取得历史'}} onChange={setWindow}/></div>
  <div className="lab-grid-equal"><EvidenceChart id="daily-win-ranking" title={`${segment}：公布胜率前十二`} queryId="daily_current" rows={ranked} sourceRows={pool} variant="card" height={360} spec={{type:'horizontalBar',x:'hero',y:'winRate',yLabel:'公布胜率',stackable:false,valueDecimals:1,colors:{winRate:'var(--chart-1)'}}}/><EvidenceChart id="daily-hero-segments" title={`${hero}：四档${metrics[measure]}`} queryId="daily_current" rows={comparison} sourceRows={comparison} variant="card" height={360} spec={{type:'horizontalBar',x:'segment',y:measure,stackable:false,valueDecimals:1,colors:{[measure]:'var(--chart-2)'}}}/></div>
  <p className="lab-note">胜率榜限定公布出场率 ≥1% 且胜率非缺失；这只是展示门槛，不是足量样本检验，也不等于综合强度排名。榜单有各自采样与时间窗口，不能直接当作全服逐局数据。</p>
  <EvidenceChart id="daily-history-trend" title={`${hero}：历史${metrics[measure]}的分段差异`} queryId="daily_history" rows={plotted} sourceRows={scoped} variant="card" height={380} spec={{type:'line',x:'date',y:measure,series:'segment',stackable:false,valueDecimals:1,colors,yLabel:metrics[measure]}}/>
  <p className="lab-note">按提供者的真实日期绘图。缺失指标、断档日期留空；没有补成0或填入S赛季。该历史可能包含统计规则变化，曲线变化不能直接归因于英雄加强。</p>
  <DataComponent id="daily-current-table" title={`${segment}：全部当前记录`} queryId="daily_current" kind="table" variant="card" sourceRows={pool} displayRows={pool}><DataTable rows={pool} columns={columns}/></DataComponent>
  <div className="lab-route"><a className="lab-link" href="./downloads/daily_current.csv" download>下载4档榜单</a><a className="lab-link" href="./downloads/daily_history.csv" download>下载4英雄历史</a><a className="lab-link" href="./downloads/替代数据源核验.md">查看来源与限制</a><a className="lab-link" href="https://pvp.91m.top/ranking" target="_blank" rel="noreferrer">苏苏助手原始榜单</a></div>
 </section>;
}
