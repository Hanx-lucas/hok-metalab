import React,{useState} from 'react';
import {DataComponent,DataTable,EvidenceChart,Dropdown,RichNarrative} from '../../data-app-public.jsx';
import './season-strength.css';
const pct=v=>v==null?'—':`${(v*100).toFixed(1)}%`;
const num=v=>v==null?'—':v.toFixed(1);
export function EventVerdict({rows,event,id='event-verdict'}){
 const eligible=rows.filter(r=>r.battles>=30&&r.posteriorRate!=null);
 const scored=eligible.filter(r=>r.score!=null).sort((a,b)=>b.score-a.score);
 const ranked=scored.length?scored:[...eligible].sort((a,b)=>b.posteriorRate-a.posteriorRate);
 const top=ranked.slice(0,3),leader=top[0];
 if(!leader)return <div className="strength-unavailable">当前筛选没有至少30场的一致计数记录，暂不能给出有样本支持的强势结论。</div>;
 const pressure=[...scored].sort((a,b)=>b.banRate-a.banRate)[0];
 const verdict=scored.length?`优先关注 ${top.map(r=>r.hero).join('、')}`:`${leader.hero}的胜率证据居前，三维强度暂不可判定`;
 const evidence=scored.length?`榜首${leader.hero}：指数${num(leader.score)}，${leader.battles}场，平滑胜率${pct(leader.posteriorRate)}，95%区间${pct(leader.lowerRate)}—${pct(leader.upperRate)}。`:`${leader.hero}：${leader.battles}场，平滑胜率${pct(leader.posteriorRate)}，95%区间${pct(leader.lowerRate)}—${pct(leader.upperRate)}。出场率与ban率缺失，不计算综合指数。`;
 const explanation=scored.length?`榜首的胜率分位贡献${num(60*leader.winPercentile)}分，出场贡献${num(25*leader.pickPercentile)}分，禁用贡献${num(15*leader.banPercentile)}分。${pressure?`${pressure.hero}的ban率${pct(pressure.banRate)}，代表BP压力；` : ''}这是${event||'当前赛事'}的相对表现判断。`:'结论仅来自当届胜率与样本量，不能把缺失BP当成零，也不能据此得出完整强度榜。';
 return <DataComponent id={id} title="本届强势结论与证据" queryId="hero_metrics" kind="custom" sourceRows={eligible} displayRows={top}>
  <div className="strength-verdict" data-reviewed-rows><div><span>结论</span><h3>{verdict}</h3></div><div><span>证据</span><p>{evidence}</p></div><div><span>解释</span><p>{explanation}</p></div></div>
  <p className="strength-footnote">统一筛选至少30场；按既有指数排序，未重算分位数。名次先后不等于显著强弱差异；进行中赛事只代表当前快照。</p>
 </DataComponent>;
}
export function SeasonStrength({queries,prefix='season',report=false}){
 const summaries=queries.season_summary?.rows||[],matrix=queries.strength_history?.rows||[];
 const [scope,setScope]=useState('regular');
 const selected=summaries.filter(e=>report||scope==='regular'?e.regular&&e.event_status==='已结束':true);
 const categories=[...new Set(matrix.map(r=>r.seasonLabel))],heroes=[...new Set(matrix.map(r=>r.hero))];
 const winners=selected.filter(e=>e.basis==='综合指数');
 const counts={};winners.forEach(e=>counts[e.leader]=(counts[e.leader]||0)+1);
 const recurring=Object.entries(counts).sort((a,b)=>b[1]-a[1])[0];
 const selectedLeaders=(queries.season_leaders?.rows||[]).filter(r=>r.basis==='综合指数'&&r.event_status==='已结束'&&selected.some(e=>e.league_id===r.league_id));
 const top5Counts={};selectedLeaders.forEach(r=>top5Counts[r.hero]=(top5Counts[r.hero]||0)+1);
 const repeatTop5=Object.entries(top5Counts).sort((a,b)=>b[1]-a[1])[0];
 return <section className="season-strength">
  {!report&&<div className="strength-controls"><h2>每届赛事，谁更强</h2><Dropdown label="榜单范围" showLabel value={scope} choices={['regular','all_events']} choiceLabels={{regular:'已结束常规KPL赛季',all_events:'全部已采集赛事'}} onChange={setScope}/></div>}
  <DataComponent id={`${prefix}-leaders`} queryId="season_summary" title="逐赛季强势英雄：每届前三" kind="table" variant="card" sourceRows={selected} displayRows={selected}>
   <DataTable rows={selected} searchable={!report} pageSize={report?16:8} columns={[
    {field:'event',label:'赛季 / 赛事'},{field:'basis',label:'判断依据'},{field:'leader',label:'第一'},{field:'runner_up',label:'第二'},{field:'third',label:'第三'},
    {field:'score',label:'第一名指数',renderCell:num},{field:'battles',label:'第一名场次'},{field:'posteriorRate',label:'平滑胜率',renderCell:pct},{field:'event_status',label:'状态'}
   ]}/>
  </DataComponent>
  <p className="strength-footnote">“第一”表示至少30场英雄中的既定指数排名。2019年BP缺失，仅列平滑胜率前三，无法回答完整三维强度；未采集到的赛事不补造。</p>
  <div className="strength-map-scroll"><div className="strength-map-wide">
   <EvidenceChart id={`${prefix}-heatmap`} title="逐赛季相对强度变化：颜色越深，同届综合表现越靠前" variant="card" queryId="strength_history" rows={matrix} sourceRows={matrix} height={535}
    spec={{type:'heatmap',x:'seasonLabel',y:'score',yLabel:'英雄',series:'hero',categoryOrder:categories,seriesOrder:heroes,colorDomain:[0,100],showValues:true,valueDecimals:1,reverseRows:true,rowHeight:32,markRadius:4,missingValues:'gap',showLegend:false,
     colorBands:[{max:60,color:'#e7edf8',label:'<60'},{max:75,color:'#aec6ed',label:'60–75'},{max:85,color:'#739cde',label:'75–85'},{max:95,color:'#2057d6',label:'85–95'},{color:'#173554',label:'95–100'}],
     tooltipFields:[{field:'event',label:'赛事'},{field:'battles',label:'场次'},{field:'rank',label:'同届全部有效英雄名次'},{field:'posteriorRate',label:'平滑胜率'}]}}/>
  </div></div>
  <p className="strength-footnote">空白表示缺失或少于30场；手机端可左右滑动查看完整赛季。</p>
  <DataComponent id={`${prefix}-reading`} title="持续强势与图表解读" queryId="strength_history" queryIds={["strength_history","season_summary","season_leaders"]} sourceRowsByQuery={{strength_history:matrix,season_summary:selected,season_leaders:selectedLeaders}} kind="narrative">
  <RichNarrative id={`${prefix}:reading`} value={`**如何读图：** 最新完整赛季前三，加上历史赛季前五出现较多的英雄，合计 ${heroes.length} 位；身份按英雄ID关联。图中 ${categories.length} 个已结束常规KPL赛季的指数都在同届计算，表示相对地位，不表示跨赛季绝对战力。${recurring?`${recurring[0]}在当前范围中 ${recurring[1]} 届完整三维榜单居首。`:''}${repeatTop5?`${repeatTop5[0]}有 ${repeatTop5[1]} 次进入前五，是跨届重复强势的证据。`:''}\n\n**解释边界：** 表现轮换可能来自版本、战队、选手、阵容和BP环境。本项目没有逐局控制变量，因此可以指出谁在当届表现强、地位如何变化，不能直接归因于某次加强或保证日常上分。`}/>
  </DataComponent>
 </section>;
}
