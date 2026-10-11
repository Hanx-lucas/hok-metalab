import React,{useState} from 'react';
import {EvidenceChart,DataComponent,ChartTooltip,Dropdown} from '../../data-app-public.jsx';
import './strength-analysis.css';
const SEGMENTS=['全分段','巅峰赛1350+','顶端排位','巅峰千强'];
const GREEN_BANDS=[{max:60,color:'#e6ede4',label:'<60'},{max:75,color:'#b4c7b2',label:'60–75'},{max:85,color:'#7da381',label:'75–85'},{max:95,color:'#497857',label:'85–95'},{color:'#274d36',label:'95–100'}];
const PRESSURE_COLORS={'低于5%':'var(--chart-3)','5%至20%':'var(--chart-1)','20%及以上':'var(--chart-2)'};
const decimal=v=>v==null?'—':Number(v).toFixed(1);
const percent=v=>v==null?'—':`${(100*v).toFixed(1)}%`;
function AnalysisTooltip({active,payload=[],dimension}){
 const row=payload[0]?.payload;if(!active||!row)return null;
 const details=dimension==='overall'?[
  {label:'赛事强度 T',value:decimal(row.arenaScore)},{label:'日常强度 D',value:decimal(row.dailyScore)},{label:'D−T',value:decimal(row.sceneGap)},{label:'推荐分路',value:row.roles}]:[
  {label:dimension==='arena'?'平滑胜率':'原始胜率',value:percent(row.winRate)},{label:'出场率',value:percent(row.pickRate)},{label:'ban率',value:percent(row.banRate)},...(dimension==='arena'?[{label:'战斗场次',value:row.battles}]:[]),{label:'推荐分路',value:row.roles}];
 return <ChartTooltip active={active} label={row.hero||row.name} headerValue={`${decimal(row.score)}分`} details={details}/>;
}
export function StrengthAnalysis({queries,dimension,context,top10,onHero}){
 const prefix=`strength-${dimension}-analysis`;
 const [chosenHero,setChosenHero]=useState(null);
 const points=(queries.strength_analysis_points?.rows||[]).filter(r=>r.context_id===context.context_id);
 const top=points.filter(r=>r.rank<=10).sort((a,b)=>a.rank-b.rank);
 const all=queries.strength_rankings?.rows||[];
 const focus=top.find(r=>r.hero_id===Number(chosenHero))||top[0];
 const drivers=(queries.strength_analysis_drivers?.rows||[]).filter(r=>r.context_id===context.context_id&&r.hero_id===focus?.hero_id);
 const chooseMark=({row})=>row?.hero_id?[{label:`查看${row.hero}的强度依据`,onSelect:()=>onHero(row)}]:[];
 const common={variant:'card',queryId:'strength_analysis_points',chartOptions:{getMarkActions:chooseMark}};
 const scene=dimension==='overall';
 const scatter=scene?points.filter(r=>r.arenaScore!=null&&r.dailyScore!=null):points;
 const heroes=top10.map(r=>r.hero_id),names=top10.map(r=>r.hero);
 const profiles=dimension==='arena'?[]:all.filter(r=>r.dimension===dimension&&heroes.includes(r.hero_id));
 const trendHeroes=heroes.slice(0,3);
 const history=dimension==='arena'?(queries.strength_analysis_history?.rows||[]).filter(r=>trendHeroes.includes(r.hero_id)):[];
 return <section className="sb-analysis" aria-label="强度解读图表">
  <div className="sb-analysis-heading"><h2>强度解读</h2><span>拆解分数 · 对照表现 · 观察变化</span></div>
  {!top.length?<DataComponent id={`${prefix}-empty`} title="当前赛事暂无可分析的三维评分" queryId="strength_rankings" kind="custom" displayRows={[]} sourceRows={all.filter(r=>r.context_id===context.context_id)}><p className="sb-empty">当前赛事缺少有效BP或足够场次，无法提供评分贡献与完整三维对照。已有指标仍保留在全部英雄总榜。</p></DataComponent>:<>
  <div className="sb-chart-grid">
   <EvidenceChart id={`${prefix}-contributions`} title="英雄强度评分的形成过程" variant="card" queryId="strength_analysis_drivers" height={380} rows={drivers} sourceRows={drivers} dataInputs={{beginning:0,ending:focus?.score}}
    description="三个驱动值依次累加，最后一列是总分；综合按对应50/50或100%日常规则分解。这是评分公式的分解，不代表因果作用。"
    spec={{type:'waterfall',x:'driver',y:'contribution',stackable:false,xTickLabelLayout:'angled',valueDecimals:1,yLabel:'累计强度分',colors:{contribution:'var(--chart-3)'}}}>
     <div className="sb-analysis-selector"><Dropdown label="分析英雄" showLabel value={String(focus?.hero_id)} choices={top.map(r=>String(r.hero_id))} choiceLabels={Object.fromEntries(top.map(r=>[String(r.hero_id),r.hero]))} onChange={setChosenHero}/></div>
     <p className="sb-chart-note"><b>{focus?.hero} · {Number(focus?.score).toFixed(1)}分</b> · 最后一列为累计总分。{scene?'综合贡献按双场景50/50或100%日常替代计算。':'三个驱动的满分分别为60、25、15分。'}</p>
   </EvidenceChart>
   <EvidenceChart {...common} id={`${prefix}-relationship`} title={scene?'赛事与日常的相对表现对照':'胜率与出场热度的关系'} height={380} rows={scatter} sourceRows={points} chartOptions={{getMarkActions:chooseMark,tooltipContent:<AnalysisTooltip kind="relationship" dimension={dimension}/>}}
    description={scene?'仅比较双方都有评分的英雄；横纵坐标都是各自人群的相对强度，观察日期和对局环境不同，不是同版本胜率比较。':'每个点为一位已评分英雄，颜色表示ban率分组；项目阈值用于描述热度，不是官方分级。悬停或点击查看英雄证据。'}
    spec={scene?{type:'scatter',x:'arenaScore',y:'dailyScore',stackable:false,xLabel:'赛事强度 T',yLabel:'日常强度 D',valueDecimals:1,colors:{dailyScore:'var(--chart-3)'},
     tooltipFields:[{field:'hero',label:'英雄'},{field:'score',label:'综合分'},{field:'sceneGap',label:'D−T'},{field:'roles',label:'推荐分路'}]}:
     {type:'scatter',x:'pickRate',y:'winRate',series:'banPressure',stackable:false,startAtZero:false,xLabel:'出场率',yLabel:dimension==='arena'?'平滑胜率':'原始胜率',valueDecimals:1,
      colors:PRESSURE_COLORS,tooltipFields:[{field:'hero',label:'英雄'},{field:'banRate',label:'ban率'},{field:'score',label:'强度分'},...(dimension==='arena'?[{field:'battles',label:'战斗场次'}]:[])]}}>
     <p className="sb-chart-note">{scene?`${scatter.length}位具备双场景评分；${context.daily_only_count}位日常替代英雄不进入该对照图。两个轴表示各自榜单中的相对位置。`:'纵轴从当前数据最小值开始；点大小一致。颜色按ban率低于5%、5%至20%、20%及以上划分。'}</p>
   </EvidenceChart>
  </div>
  {dimension==='arena'?<EvidenceChart id={`${prefix}-history`} title="本届前三英雄的历届强度变化" variant="card" queryId="strength_analysis_history" height={320} rows={history} sourceRows={history}
   spec={{type:'line',x:'eventStart',y:'score',series:'hero',stackable:false,valueDecimals:1,yLabel:'同届相对强度',colors:Object.fromEntries(names.slice(0,3).map((n,i)=>[n,`var(--chart-${i+1})`])),
    tooltipFields:[{field:'event',label:'赛事'},{field:'battles',label:'场次'}]}}>
    <p className="sb-chart-note">只展示已结束常规KPL春夏秋季赛，按真实起始日期排列。缺失、异常或不足30场处断开；曲线表示相对地位变化，不能直接归因于版本加强。</p>
   </EvidenceChart>:<EvidenceChart id={`${prefix}-segments`} title="当前Top 10在四档分段中的相对强度" variant="card" queryId="strength_rankings" height={450} rows={profiles} sourceRows={profiles}
   spec={{type:'heatmap',x:'segment',y:'score',series:'hero',categoryOrder:SEGMENTS,seriesOrder:names,reverseRows:true,rowHeight:32,colorDomain:[0,100],colorBands:GREEN_BANDS,showValues:true,valueDecimals:1,missingValues:'gap',
    tooltipFields:[{field:'rank',label:'该分段总榜名次'},{field:'scoreReason',label:'评分依据'}]}}>
    <p className="sb-chart-note">列从左至右：全分段、巅峰赛1350+、顶端排位、巅峰千强。固定当前Top 10英雄，对照同一公告日期的四档榜单；各分段独立计算相对分数。空白表示不能评分，不等于零；分段差异不代表同一玩家的上分收益。</p>
   </EvidenceChart>}
  </>}
 </section>;
}
