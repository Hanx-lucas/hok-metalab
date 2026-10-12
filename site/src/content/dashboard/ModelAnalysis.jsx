import React,{useState} from 'react';
import {EvidenceChart,DataComponent,ChartTooltip,Dropdown} from '../../data-app-public.jsx';
import {fmt} from './HeroModelDetail.jsx';
import './strength-analysis.css';
const SEGMENTS=['全分段','巅峰赛1350+','顶端排位','巅峰千强'];
const COLORS={'双高 · E≥50/B≥50':'var(--chart-1)','实战高 · E≥50/B<50':'var(--chart-3)','BP高 · E<50/B≥50':'var(--chart-2)','双低 · E<50/B<50':'var(--chart-4)'};
const BANDS=[{max:60,color:'#e6ede4',label:'<60'},{max:75,color:'#b4c7b2',label:'60–75'},{max:85,color:'#7da381',label:'75–85'},{max:95,color:'#497857',label:'85–95'},{color:'#274d36',label:'95–100'}];
const quadrant=r=>r.E>=50?(r.B>=50?'双高 · E≥50/B≥50':'实战高 · E≥50/B<50'):(r.B>=50?'BP高 · E<50/B≥50':'双低 · E<50/B<50');
function EBTooltip({active,payload=[]}){const row=payload[0]?.payload;if(!active||!row)return null;return <ChartTooltip active label={row.hero} headerValue={`${fmt(row.score)}分`} details={[{label:'实战表现 E',value:fmt(row.E)},{label:'BP优先级 B',value:fmt(row.B)},{label:'比较池',value:`${row.comparisonN}名`},{label:'当前榜名次',value:row.rank},{label:'象限',value:row.quadrant}]}/>}
export function ModelAnalysis({rows,context,allRows,contexts,scope,model,dimension,derive,onHero}){
 const [chosen,setChosen]=useState(null);const rated=rows.filter(r=>r.score!=null),top=rated.slice(0,10),focus=top.find(r=>r.hero_id===Number(chosen))||top[0];
 const prefix=`model-${model}-${dimension}-${scope}`;
 const points=rated.map(r=>({...r,quadrant:quadrant(r)}));
 const drivers=focus?[{...focus,driver:'实战E贡献',contribution:focus.eContribution},{...focus,driver:'BP贡献',contribution:focus.bContribution}]:[];
 const ids=top.map(r=>r.hero_id),names=top.map(r=>r.hero);
 const profiles=dimension==='arena'?[]:allRows.filter(r=>r.model===model&&r.scope===scope&&r.dimension===dimension&&ids.includes(r.hero_id)).map(derive);
 const ended=new Set(contexts.filter(c=>c.model===model&&c.scope===scope&&c.dimension==='arena'&&c.event_status==='已结束'&&/KPL(春|夏|秋)季赛/.test(c.event)&&!c.event.includes('季前')).map(c=>c.context_id));
 const history=dimension==='arena'?allRows.filter(r=>r.model===model&&r.scope===scope&&ended.has(r.context_id)&&ids.slice(0,3).includes(r.hero_id)).map(r=>({...derive(r),eventStart:contexts.find(c=>c.context_id===r.context_id&&c.model===model&&c.scope===scope)?.event_start})).sort((a,b)=>a.eventStart.localeCompare(b.eventStart)):[];
 return <section className="sb-analysis" aria-label="模型强度解读">
 <div className="sb-analysis-heading"><h2>强度解读</h2><span>实战表现 × BP优先级 · {scope}</span></div>
 {!rated.length?<DataComponent id={`${prefix}-empty`} queryId="model_rankings" title="当前比较池不足以评分" kind="custom" sourceRows={rows} displayRows={[]}><p className="sb-empty">缺失、场次不足或同分路有效池不足5名，保留原始指标，不强行排名。</p></DataComponent>:<>
 <div className="sb-chart-grid">
  <EvidenceChart id={`${prefix}-contributions`} queryId="model_rankings" title="评分是怎样形成的" variant="card" rows={drivers} sourceRows={focus?[focus]:[]} height={340} dataInputs={{beginning:0,ending:focus?.score}} spec={{type:'waterfall',x:'driver',y:'contribution',stackable:false,valueDecimals:1,xTickLabelLayout:'angled',yLabel:'累计强度分'}} description="分数等于E/B贡献之和，起点0和终点总分来自审阅指标；公式分解不代表因果效果。">
  <div className="sb-analysis-selector"><Dropdown label="分析英雄" showLabel value={String(focus?.hero_id)} choices={top.map(r=>String(r.hero_id))} choiceLabels={Object.fromEntries(top.map(r=>[String(r.hero_id),r.hero]))} onChange={setChosen}/></div><p className="sb-chart-note">{focus?.hero} · E贡献 {fmt(focus?.eContribution)} + BP贡献 {fmt(focus?.bContribution)} = {fmt(focus?.score)} 分。{model==='V1'?'V1的60/25/15三项按60%胜率与40%禁选项等价分解。':'V2分位与Z各50%，E/B权重属于初始试验。'}</p>
  </EvidenceChart>
  <EvidenceChart id={`${prefix}-quadrants`} queryId="model_rankings" title="实战表现与BP优先级 · 四象限" variant="card" rows={points} sourceRows={rows} height={340} spec={{type:'scatter',x:'E',y:'B',series:'quadrant',stackable:false,xLabel:'实战表现 E（分）',yLabel:'BP优先级 B（分）',valueDecimals:1,colors:COLORS}} chartOptions={{tooltipContent:<EBTooltip/>,getMarkActions:({row})=>row?.hero_id?[{label:`查看${row.hero}的强度依据`,onSelect:()=>onHero(row)}]:[]}} description="以E/B得分50划分四组，不是50%胜率阈值。点大小一致，未知日常样本量不生成气泡或区间。">
  <div className="sb-quadrant-counts">{Object.keys(COLORS).map(name=><span key={name}><i style={{background:COLORS[name]}}/>{name.split(' · ')[0]} <b>{points.filter(r=>r.quadrant===name).length}</b></span>)}</div><p className="sb-chart-note">E/B均以50分划分高低，不是50%胜率。仅绘制当前榜可评分英雄；综合图包含双场景30/70及日常100%参考项；评分依据请点开详情。{model==='V1'?'V1的E为胜率分位、B为出场/ban的原权重等价分解，与V2口径有别。':''}</p>
  </EvidenceChart>
 </div>
 {dimension==='arena'?<EvidenceChart id={`${prefix}-history`} queryId="model_rankings" title="当前前三英雄的历届赛事强度" variant="card" rows={history} sourceRows={history} height={300} spec={{type:'line',x:'eventStart',y:'score',series:'hero',stackable:false,valueDecimals:1,yLabel:'同届相对分数',colors:Object.fromEntries(names.slice(0,3).map((name,i)=>[name,`var(--chart-${i+1})`]))}}><p className="sb-chart-note">已结束常规KPL春夏秋季赛，按真实开始日期；未评分处断开。使用当前模型与本比较范围，当前推荐位置不代表历史实际比赛位置，变化不直接证明版本因果。</p></EvidenceChart>:<EvidenceChart id={`${prefix}-segments`} queryId="model_rankings" title="当前前十英雄的四档分段对照" variant="card" rows={profiles} sourceRows={profiles} height={450} spec={{type:'heatmap',x:'segment',y:'score',series:'hero',categoryOrder:SEGMENTS,seriesOrder:names,reverseRows:true,rowHeight:32,colorDomain:[0,100],colorBands:BANDS,showValues:true,valueDecimals:1,missingValues:'gap'}}><p className="sb-chart-note">列从左至右：全分段、巅峰赛1350+、顶端排位、巅峰千强。各分段独立评分；缺失保持空白，不能当成零或同一玩家的上分收益。</p></EvidenceChart>}
 </>}
 </section>;
}
