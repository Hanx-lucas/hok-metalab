import React from 'react';
import {DataComponent,DataTable,EvidenceChart,ReportSection,RichNarrative,useDataApp} from '../../data-app-public.jsx';
import {SeasonStrength} from '../shared/SeasonStrength.jsx';
import './research.css';
const pct=v=>v==null?'—':`${(v*100).toFixed(1)}%`;
const fixed=(v,n=1)=>v==null?'—':v.toFixed(n);
function Prose({id,title,rows,queryId='hero_metrics',queryIds,sourceRowsByQuery,sourcePreviews,value}){
 return <ReportSection id={id} title={title} queryId={queryId} queryIds={queryIds} sourceRows={rows} sourceRowsByQuery={sourceRowsByQuery} showHeading={false}><RichNarrative id={`${id}:body`} value={value} sourcePreviews={sourcePreviews}/></ReportSection>;
}
function Chart({id,title,rows,sourceRows=rows,queryId='hero_metrics',spec,height=360}){
 return <EvidenceChart id={id} title={title} variant="card" queryId={queryId} rows={rows} sourceRows={sourceRows} height={height} spec={{stackable:false,valueDecimals:1,colors:{[spec.y]:'var(--chart-1)'},...spec}}/>;
}
export function ReportContent(){
 const {queries,appTitle,canEdit,mode,setAppTitle}=useDataApp();
 const rows=queries.hero_metrics?.rows||[],coverage=queries.coverage?.rows||[],summary=queries.summary?.rows[0]||{};
 const latest=rows.filter(r=>r.league_id===summary.latest_completed_league);
 const top=latest.filter(r=>r.score!=null&&r.battles>=30).sort((a,b)=>b.score-a.score).slice(0,10);
 const [a,b,c]=top,pressure=[...top].sort((x,y)=>y.banRate-x.banRate)[0];
 const seasons=(queries.season_summary?.rows||[]).filter(e=>e.regular&&e.event_status==='已结束');
 const previous=seasons.at(-2),backtest=queries.backtest?.rows||[],models=summary.backtest_summaries||[];
 const baseline=models.find(r=>r.model==='50%基线'),ridge=models.find(r=>r.model==='岭回归');
 const history=(queries.strength_history?.rows||[]).filter(r=>[a?.hero_id,b?.hero_id].includes(r.hero_id));
 const camp=queries.camp?.rows||[],daily=queries.daily_summary?.rows?.[0];const titleParts=appTitle.split('，');
 return <article className="hok-research" aria-label="王者荣耀英雄强度结论研究报告">
  <header className="research-opening"><span className="research-eyebrow">HoK MetaLab / 英雄强度研究</span>
   <h1 data-data-app-title contentEditable={canEdit&&mode==='edit'} suppressContentEditableWarning onBlur={canEdit&&mode==='edit'?e=>setAppTitle(e.currentTarget.textContent.trim()||appTitle):undefined}>{titleParts.length===2?<><span className="research-title-line">{titleParts[0]}，</span><span className="research-title-line">{titleParts[1]}</span></>:appTitle}</h1>
   <RichNarrative id="research:deck" value="先回答谁强，再展示逐赛季证据与判断依据 · 肖涵的 Python 数据分析作品集"/>
   <div className="research-links"><a href="../index.html">返回交互作品集</a><a href="../downloads/研究报告.pdf" download>下载PDF</a><a href="../downloads/项目说明与面试指南.md" download>技术与面试指南</a></div>
  </header>
  <Prose id="research-summary" title="核心结论" rows={latest} queryIds={['hero_metrics','season_summary']} sourceRowsByQuery={{hero_metrics:latest,season_summary:seasons}}
   value={`## 核心结论\n\n**${summary.latest_completed_event}：${a?.hero}与${b?.hero}是综合表现最强的两位，${c?.hero}是前三中的BP压力型英雄。** “强”指本届至少30场英雄的多维相对表现，结合平滑胜率、出场率和ban率。\n\n**证据：** ${a?.hero}指数${fixed(a?.score)}、${a?.battles}场、平滑胜率${pct(a?.posteriorRate)}；${b?.hero}指数${fixed(b?.score)}、${b?.battles}场、平滑胜率${pct(b?.posteriorRate)}。${pressure?.hero}ban率${pct(pressure?.banRate)}，其胜率区间为${pct(pressure?.lowerRate)}—${pct(pressure?.upperRate)}。\n\n**跨赛季判断：** ${previous?.event}前三为${previous?.leader}、${previous?.runner_up}、${previous?.third}，与最新赛季不同。逐赛季表和热力图展示实际轮换，不给出脱离赛季的永久最强榜。`}/>
  <Chart id="research-ranking" title={`${summary.latest_completed_event} · 至少30场的综合表现前十`} rows={top} sourceRows={latest} spec={{type:'horizontalBar',x:'hero',y:'score',yLabel:'同届相对指数（0–100）'}}/>
  <DataComponent id="research-intervals" title="结论的数字证据：前三与前十" queryId="hero_metrics" kind="table" variant="card" displayRows={top} sourceRows={top}>
   <DataTable rows={top} searchable={false} pageSize={10} columns={[{field:'hero',label:'英雄'},{field:'score',label:'指数',renderCell:v=>fixed(v)},{field:'battles',label:'场次'},
    {field:'posteriorRate',label:'平滑胜率',renderCell:pct},{field:'lowerRate',label:'95%下界',renderCell:pct},{field:'upperRate',label:'95%上界',renderCell:pct},
    {field:'pickRate',label:'出场率',renderCell:pct},{field:'banRate',label:'ban率',renderCell:pct},{field:'top10WeightShare',label:'权重情景前十占比',renderCell:pct}]}/>
  </DataComponent>
  <Prose id="research-interval-reading" title="为什么这样判断" rows={top}
   value={`## 领先来自什么信号\n\n**胜率与热度共同领先：** ${a?.hero}的胜率分位贡献${fixed(60*a?.winPercentile)}分、出场贡献${fixed(25*a?.pickPercentile)}分、ban贡献${fixed(15*a?.banPercentile)}分；${b?.hero}对应为${fixed(60*b?.winPercentile)}、${fixed(25*b?.pickPercentile)}、${fixed(15*b?.banPercentile)}分。三部分合计就是综合指数，说明哪些信号推动了排名。\n\n**区分表现与BP压力：** ${pressure?.hero}ban率${pct(pressure?.banRate)}，说明职业队伍高度重视其禁选；高ban本身不能证明它比${a?.hero}更容易赢。${a?.hero}与${b?.hero}的95%区间重叠，指数先后也不能当作胜率差异的显著性检验。\n\n**稳健性：** 1000组权重情景的前十占比，回答改变主观权重后名次是否稳定；它不是实战胜率或抽样置信度。`}/>
  <Chart id="research-bp" title="强势英雄的出场与BP压力分别观察" rows={top.slice(0,6)} sourceRows={top} spec={{type:'horizontalBar',x:'hero',y:'pickRate',fields:['pickRate','banRate'],colors:{pickRate:'var(--chart-1)',banRate:'var(--chart-2)'},legend:{labels:{pickRate:'出场率',banRate:'ban率'}}}}/>
  <Prose id="research-history-method" title="逐赛季谁强" rows={seasons} queryId="season_summary" value={`## 逐赛季强势英雄会轮换\n\n以下${seasons.length}个已结束常规KPL春夏秋季赛统一筛选至少30场，再按既定综合指数选前三。2019年BP整块缺失，只比较平滑胜率，单独注明判断依据。没有取得的届次不补齐，也不将赛事标签替换成游戏S赛季。`}/>
  <SeasonStrength queries={queries} prefix="research-season" report/>
  <Chart id="research-history" title={`${a?.hero}与${b?.hero}的逐赛季相对强度变化`} queryId="strength_history" rows={history} sourceRows={history} spec={{type:'line',x:'event_start',y:'score',series:'hero',colors:{[a?.hero]:'var(--chart-1)',[b?.hero]:'var(--chart-2)'},yLabel:'同届相对表现指数（0–100）'}}/>
  <Prose id="research-index-method" title="强度判断口径" rows={latest} value="## 三种信号如何合成判断\n\n先用Beta(10,10)修正小样本：平滑胜率=(胜场+10)/(场次+20)，95%区间取后验分位数。综合指数=100×(60%平滑胜率分位+25%出场率分位+15%ban率分位)，分位数在同届有效英雄中计算。\n\n报告筛选至少30场，筛选不重算指数。30场是展示门槛，不是显著性阈值；先验与权重是分析设定，另做敏感性检验。高指数表示当届多维表现强，不表示校正了战队、阵容和版本后的固有战力。"/>
  <Prose id="research-quality" title="数据质量与范围" rows={coverage} queryId="coverage" queryIds={['coverage','quality_issues']} sourceRowsByQuery={{coverage,quality_issues:queries.quality_issues?.rows||[]}} value={`## 证据覆盖范围与质量\n\n腾讯接口提供2019–2026年${summary.official_events}届赛事、${summary.official_rows?.toLocaleString('zh-CN')}条英雄×赛事记录，${summary.official_heroes}个历史英雄ID。${summary.hero_appearances?.toLocaleString('zh-CN')}次英雄战斗记录同局重复计数，不是独立比赛数。\n\n385条早期BP占位记录转为缺失；${summary.incoherent_rows}条计数异常记录不进入后验与指数。${summary.quality_issue_count}项质量标记可能重复命中同一观察。原始响应、URL、时间和SHA256保留；当前官方推荐分路不代表历史实战位置。`}/>
  <Prose id="research-backtest-method" title="预测能力检验" rows={backtest} queryId="backtest" value={`## 能判断本届表现，尚不能可靠预测下一届\n\n${summary.backtest_event_count}个测试赛事的时间回测，50%基线平均加权MAE为${fixed(baseline?.weightedMaePP,2)}个百分点，岭回归为${fixed(ridge?.weightedMaePP,2)}个百分点。复杂模型没有稳定超过基线，不宣称已经验证上分或未来版本预测效果。\n\n训练目标目录结束必须早于测试开始；2025春夏目录重叠过渡保守排除。StandardScaler只拟合训练集，alpha固定10。当前响应是回顾性快照，没有历史时点不可变数据，不能作为线上预测验证。`}/>
  <Chart id="research-backtest" title="预测误差：50%基线仍优于岭回归" queryId="backtest" rows={[...models].sort((x,y)=>x.weightedMaePP-y.weightedMaePP)} sourceRows={backtest} spec={{type:'horizontalBar',x:'model',y:'weightedMaePP',yLabel:'加权MAE（百分点，越小越好）'}} height={290}/>
  {daily?<Prose id="research-daily-public" title="日常分段公开样本" rows={[daily]} queryId="daily_summary" value={`## 日常分段已有公开样本，尚未官方对账\n\n苏苏助手提供${daily.current_rows}条四档当前榜单；${daily.history_heroes}位英雄的历史样本覆盖${daily.history_first}至${daily.history_last}，其中${daily.history_complete.toLocaleString('zh-CN')}条三指标完整。作品集“日常游戏强度”支持四档分段、分路和英雄查询，四英雄历史样本保留在下载数据中。\n\n这是一份独立第三方补充：没有样本场次与S赛季映射，未与营地官方对账。当前榜单与历史末日存在差异，分开呈现，不套用职业赛后验。历史仅验证4英雄，不代表全英雄多赛季完整覆盖；营地官方直接数据仍待本机授权核验。`}/>: <Prose id="research-manual" title="日常分段状态" rows={camp} queryId="camp" value={camp.length?`## 日常数据按分段单独解释\n\n已取得${camp.length}条授权榜单观察，详见作品集日常与分段。未提供场次和历史赛季映射时只做同期描述比较，不套用职业赛后验。`:'## 日常分段待授权实测\n\n本机授权入口可配置自己的营地请求头，接入当前全分段、巅峰1350+与顶端排位榜单。适配器未实测成功前，不声称已取得数据。授权只能解决当前快照，多赛季历史仍需实际历史响应。原手工S37–S39记录单列未核验，不能替代真实分段证据。'}/>}
  <Prose id="research-final-verdict" title="最后的判断" rows={top} queryIds={['hero_metrics','season_summary']} sourceRowsByQuery={{hero_metrics:top,season_summary:seasons}} value={`## 结论如何使用\n\n**结论：** ${summary.latest_completed_event}先关注${a?.hero}、${b?.hero}，把${pressure?.hero}作为BP压力型英雄单独判断。逐届研究先定位当届榜单，再看历史持续性。\n\n**证据：** 综合指数确定优先对象，再用场次、胜率区间与BP检查判断；权重前十占比帮助识别依赖特定权重的脆弱名次。\n\n**解释：** 这是已观察职业表现的总结。要形成日常分段推荐或解释版本加强，需要同期营地及逐局版本、阵容、选手和战队证据。`}/>
  <Prose id="research-reproduce" title="来源与复现" rows={coverage} queryId="coverage" sourcePreviews={{"https://prod.comp.smoba.qq.com/leaguesite/leagues/open":{title:"腾讯公开赛事目录",summary:"本次直接采集的目录提供赛事ID、状态与起止窗口；逐季表仅覆盖实际取得的届次。",approvedForReport:true},"https://pvp.qq.com/web201605/js/herolist.json":{title:"腾讯官方英雄目录",summary:"直接读取的当前英雄资料用于ID和推荐分路关联，不提供历史实战分路。",approvedForReport:true}}} value="## 来源与复现\n\n数据来自[腾讯赛事目录](https://prod.comp.smoba.qq.com/leaguesite/leagues/open)与[官方英雄目录](https://pvp.qq.com/web201605/js/herolist.json)。技术细节见项目说明和数据字典。\n\nPython/Pandas/SciPy/scikit-learn/SQLite完成分析；React/Recharts呈现交互；Matplotlib/ReportLab生成图表和PDF。运行 `python run.py --offline --report`，再运行 `python scripts/build_web.py` 重建网页与离线包。"/>
  <footer className="research-footer"><a href="../index.html">打开交互探索</a><span>腾讯公开赛事汇总 · 非官方个人作品</span></footer>
 </article>;
}
