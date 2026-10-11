import React from "react";
import { DataComponent, DataTable, EvidenceChart, ReportSection, RichNarrative, useDataApp } from "../../data-app-public.jsx";
import "./research.css";

const pct = v => v == null ? "—" : `${(v * 100).toFixed(1)}%`;
const decimal = (v, n = 2) => v == null ? "—" : Number(v).toFixed(n);
function Chart({ id, title, rows, sourceRows = rows, queryId = "hero_metrics", spec, height = 360 }) {
  return <EvidenceChart id={id} title={title} variant="card" queryId={queryId} rows={rows} sourceRows={sourceRows}
    height={height} spec={{ stackable: false, valueDecimals: 1, colors: { [spec.y]: "var(--chart-1)" }, ...spec }} />;
}
function Prose({ id, title, rows, queryId = "hero_metrics", queryIds, sourceRowsByQuery, sourcePreviews, value }) {
  return <ReportSection id={id} title={title} queryId={queryId} queryIds={queryIds} sourceRows={rows}
    sourceRowsByQuery={sourceRowsByQuery} showHeading={false}>
    <RichNarrative id={`${id}:body`} value={value} sourcePreviews={sourcePreviews} />
  </ReportSection>;
}
export function ReportContent() {
  const { queries, appTitle, canEdit, mode, setAppTitle } = useDataApp();
  const rows = queries.hero_metrics?.rows || [];
  const coverage = queries.coverage?.rows || [];
  const summary = queries.summary?.rows[0] || {};
  const backtest = queries.backtest?.rows || [];
  const latest = rows.filter(r => r.league_id === summary.latest_completed_league);
  const top = latest.filter(r => r.score != null).sort((a, b) => b.score - a.score).slice(0, 10);
  const regular = coverage.filter(e => /KPL.*[春夏秋]季赛/.test(e.event) && !e.event.includes("季前"));
  const history = rows.filter(r => ["赵云", "关羽"].includes(r.hero) && regular.some(e => e.league_id === r.league_id))
    .sort((a, b) => a.event_start.localeCompare(b.event_start));
  const historyDisplay = regular.flatMap(e => ["赵云", "关羽"].map(hero => {
    const row = history.find(r => r.hero === hero && r.league_id === e.league_id);
    return row || { event_start: e.event_start, hero, posteriorRate: null };
  }));
  const comparison = summary.backtest_summaries || [];
  const baseline = comparison.find(r => r.model === "50%基线");
  const ridge = comparison.find(r => r.model === "岭回归");
  const testCount = new Set(backtest.map(r => r.league_id)).size;
  const master = "https://prod.comp.smoba.qq.com/leaguesite/leagues/open";
  return <article className="hok-research" aria-label="王者荣耀英雄表现研究报告">
    <header className="research-opening">
      <span className="research-eyebrow">HoK MetaLab / 研究报告</span>
      <h1 data-data-app-title contentEditable={canEdit && mode === "edit"} suppressContentEditableWarning
        onBlur={canEdit && mode === "edit" ? e => setAppTitle(e.currentTarget.textContent.trim() || appTitle) : undefined}>{appTitle}</h1>
      <RichNarrative id="research:deck" value="王者荣耀英雄表现与版本生态研究 · 肖涵的 Python 数据分析作品集" />
      <div className="research-links"><a href="../index.html">返回交互作品集</a><a href="../downloads/研究报告.pdf" download>下载 PDF</a><a href="../downloads/项目说明与面试指南.md" download>技术与面试指南</a></div>
    </header>
    <Prose id="research-summary" title="研究摘要" rows={rows}
      queryIds={["hero_metrics", "coverage", "backtest"]} sourceRowsByQuery={{ hero_metrics: rows, coverage, backtest }}
      value={`## 研究摘要\n\n- 腾讯公开接口提供 ${summary.official_events} 届赛事、${summary.official_rows?.toLocaleString("zh-CN")} 条英雄与赛事观察。它们覆盖 2019–2026 年，包含 ${summary.official_heroes} 个历史英雄 ID；赛事届次与游戏 S 赛季分别记录。\n- 最新完整赛事 **${summary.latest_completed_event}** 中，赵云与关羽的平滑胜率为 ${pct(top.find(r => r.hero === "赵云")?.posteriorRate)} 和 ${pct(top.find(r => r.hero === "关羽")?.posteriorRate)}。鲁班大师禁用率高，但胜率区间仍包含 50%，需要区分表现与禁选压力。\n- ${testCount} 个未来赛事的时间回测中，50% 基线平均场次加权 MAE 为 **${decimal(baseline?.weightedMaePP)} 个百分点**，岭回归为 **${decimal(ridge?.weightedMaePP)} 个百分点**。现有聚合特征没有证明复杂模型具有稳定的预测增益。\n- 日常全分段、巅峰 1350+ 与顶端排位还需要用户授权及历史快照。当前没有这些真实记录，无法报告职业与日常的分段差异。`} />
    <Prose id="research-quality" title="来源与质量" rows={coverage} queryId="coverage"
      queryIds={["coverage", "quality_issues"]} sourceRowsByQuery={{ coverage, quality_issues: queries.quality_issues?.rows || [] }}
      value={`## 先确认数据能回答什么\n\n记录粒度是英雄 × 赛事。全库 ${summary.hero_appearances?.toLocaleString("zh-CN")} 次英雄战斗记录会在同局重复计数，**不能称为独立比赛局数**。原始响应保留 URL、UTC 采集时间和 SHA256，能够核对处理前后的记录。\n\n2019 年的 385 条记录有整块为零的 BP 占位字段。分析保留它们的胜率，将出场率和禁用率记为缺失；另外 ${summary.incoherent_rows} 条胜负计数不一致的记录保留原值，排除后验和指数计算。战斗场次与 BP 选用场次不混用。${summary.quality_issue_count} 项质量标记包含同一记录的多个检查结果。\n\n${coverage.filter(e => e.event_status === "已结束").length} 届已结束，${coverage.filter(e => e.event_status === "进行中").length} 届仍在进行。进行中快照可探索，但不能代表最终全届表现。当前官方推荐分路用于浏览，不代表历史每局的实际位置。`} />
    <Prose id="research-index-method" title="样本量与指数" rows={latest}
      value={`## 先修正样本量，再观察多维表现\n\n原项目的“出场率 × 胜率”容易让热门英雄机械领先。新分析用 Beta(10,10) 先验修正小样本：平滑胜率 = (胜场 + 10) / (战斗场次 + 20)，95% 可信区间取后验分布的 2.5% 与 97.5% 分位数。20 场是分析者设定的先验强度，另做敏感性检验。\n\n综合表现指数 = 100 × (60% 平滑胜率分位 + 25% 出场率分位 + 15% 禁用率分位)。分位数在同届有效英雄中计算；**指数是相对表现，不是因果强度或下一版本胜率**。它将不同信号组合起来，保留每个信号单独查看的入口。`} />
    <Chart id="research-ranking" title={`${summary.latest_completed_event} · 综合表现指数前十`} rows={top} sourceRows={latest}
      spec={{ type: "horizontalBar", x: "hero", y: "score", yLabel: "相对表现指数（0–100）" }} />
    <DataComponent id="research-intervals" title="前十英雄的后验区间与样本" queryId="hero_metrics" kind="table" variant="card" displayRows={top} sourceRows={top}>
      <DataTable rows={top} searchable={false} pageSize={10} columns={[
        { field: "hero", label: "英雄" }, { field: "posteriorRate", label: "平滑胜率", renderCell: pct },
        { field: "lowerRate", label: "95%下界", renderCell: pct }, { field: "upperRate", label: "95%上界", renderCell: pct },
        { field: "battles", label: "战斗场次" }, { field: "banRate", label: "禁用率", renderCell: pct },
      ]} />
    </DataComponent>
    <Prose id="research-interval-reading" title="可信区间解释" rows={top.slice(0, 3)}
      value="赵云与关羽的区间重叠，不能由指数排序证明一位显著强于另一位。二项模型未校正同局、战队和全局 BP 相关性，区间需要在这些简化假设下解释。鲁班大师的高禁用率提供 BP 压力信号，其胜率仍有明显不确定性。" />
    <Chart id="research-bp" title="禁选压力与胜率证据分别观察" rows={top.slice(0, 8)} sourceRows={top.slice(0, 8)}
      spec={{ type: "horizontalBar", x: "hero", y: "pickRate", fields: ["pickRate", "banRate"],
        legend: { labels: { pickRate: "出场率", banRate: "禁用率" } }, colors: { pickRate: "var(--chart-1)", banRate: "var(--chart-2)" } }} />
    <Prose id="research-stability" title="权重敏感性" rows={top}
      value="## 权重变化会怎样改变榜单\n\n固定数据，以 1000 组 Dirichlet(12,5,3) 权重重新计算排名，输出进入前十的占比与排名情景范围。这些量描述主观权重的敏感性，不是抽样置信度。先验强度另外检验 0、10、20、50、100 场，并比较 Spearman 排名相关性。\n\nPareto 标记找出是否存在三维都不差且至少一维更好的英雄，用于识别不同表现类型。交互作品集可以修改胜率权重，观察排名如何变化。" />
    <Prose id="research-history-method" title="历史趋势" rows={history}
      value="## 跨届趋势保留真实时间与环境差异\n\n图中只比较常规 KPL 春夏秋季赛，横轴使用官方目录开始日期，缺失英雄保留为空。胜率变化不自动意味着英雄加强或削弱：选手、战队、对手、阵容和 BP 规则都可能影响表现。现有聚合数据不能控制这些因素。" />
    <Chart id="research-history" title="赵云与关羽的跨届平滑胜率" rows={historyDisplay} sourceRows={history}
      spec={{ type: "line", x: "event_start", y: "posteriorRate", series: "hero", colors: { "赵云": "var(--chart-1)", "关羽": "var(--chart-2)" } }} />
    <Prose id="research-backtest-method" title="时间回测方法" rows={backtest} queryId="backtest"
      value="## 用下一届数据检验预测能力\n\n使用过去常规 KPL 赛季预测下一届，目录结束窗口必须早于目标开始窗口。2025 年春夏目录窗口有重叠，保守排除该过渡并保留排除记录。扩展训练窗口至少包含三个历史过渡。StandardScaler 只拟合训练集；岭回归 alpha 固定为 10，测试集不参与调参。当前响应为回顾性快照，没有真实历史时点的不可变快照，因此不能将此回测视为线上预测验证。特征包括上一届平滑胜率、出场率、禁用率、log 战斗场次，以及过去三届合并平滑胜率。\n\n回测仅代表前后届有历史交集且特征完整的英雄，不覆盖新英雄或缺失 BP 的记录。单届 MAE 按目标英雄战斗场次加权，下图再对测试赛事等权平均。Brier 分数评估概率误差，不能把同局多个英雄当作独立样本来检验显著性。" />
    <Chart id="research-backtest" queryId="backtest" title="复杂模型没有稳定优于简单基线" rows={[...comparison].sort((a, b) => a.weightedMaePP - b.weightedMaePP)} sourceRows={backtest}
      spec={{ type: "horizontalBar", x: "model", y: "weightedMaePP", valueDecimals: 2, yLabel: "平均场次加权 MAE（百分点），越小越好" }} height={300} />
    <Prose id="research-implication" title="结果的实际含义" rows={backtest} queryId="backtest"
      value={`50% 基线平均误差为 ${decimal(baseline?.weightedMaePP)} 个百分点，岭回归为 ${decimal(ridge?.weightedMaePP)} 个百分点。当前成果适合描述英雄表现、解释禁选热度并审计预测边界；没有已验证的上分效果。下一步需要逐局 BP、阵容、版本、选手与战队特征，才能讨论分层模型和英雄相性。`} />
    <Prose id="research-manual" title="日常分段与原始项目" rows={queries.legacy_manual?.rows || []} queryId="legacy_manual"
      value={`## 日常分段还需要新增真实证据\n\n原项目 S37–S39 的 ${summary.legacy_rows} 条手工记录保留为单独来源。用户说明它们来自当时的营地榜单，但采样日期、分段和样本量未记录，没有独立核验；不能与官方赛事合并成全量真实样本。\n\n营地采集器已经支持通过用户自己的有效会话读取全分段、巅峰 1350+ 与顶端排位。当前未接入授权数据，历史分段必须来自历史快照或合法供应商；修改标签无法产生历史数据。现有证据也不足以验证金币成本、装备收益和上分收益。`} />
    <Prose id="research-reproduce" title="技术与复现" rows={coverage} queryId="coverage" sourcePreviews={{
      "https://prod.comp.smoba.qq.com/leaguesite/leagues/open":{title:"腾讯公开赛事目录",summary:"本次直接读取的官方目录提供赛事ID、状态与开始/结束窗口；发现2025春夏窗口重叠，因此采用保守排除规则。",approvedForReport:true},
      "https://pvp.qq.com/web201605/js/herolist.json":{title:"腾讯官方英雄目录",summary:"提供当前英雄ID、姓名与推荐分路。它不提供历史每局分路，也不等同营地不同分段榜单。",approvedForReport:true},
      "https://github.com/leirong/wzry-database-server":{title:"公开接口发现线索",summary:"读取其采集代码确认腾讯公开接口地址；实际分析数据直接向腾讯请求，没有以仓库镜像冒充直接采集。",approvedForReport:true},
      "https://github.com/anthropics/skills/tree/main/skills/frontend-design":{title:"Anthropic frontend-design",summary:"阅读该技能的设计指导，应用于页面视觉方向、排版、响应式与交互。技能与原许可证快照保存在research目录。",approvedForReport:true}
    }}
      value={`## 可以复现，也可以继续扩展\n\n- **采集与存储：** Python urllib，低频请求、缓存校验和退避重试；原始 JSON、规范化 CSV/JSON 与 SQLite。\n- **统计与验证：** Pandas、NumPy、SciPy、scikit-learn，贝叶斯平滑、权重情景、先验敏感性和严格时间回测。\n- **呈现与检查：** React、Recharts 共享运行时与项目内容层；Matplotlib、ReportLab；unittest、Playwright 与 PDF 渲染检查。\n\n安装依赖后执行 \`python run.py --offline --report\` 可从已保存的原始响应重建分析和报告。执行 \`python scripts/build_web.py\` 重建网页与便携包。完整步骤、技能来源和面试问答见下载的项目文档。\n\n公开数据来自[腾讯赛事目录](${master})和[官方英雄目录](https://pvp.qq.com/web201605/js/herolist.json)。接口发现参考 [wzry-database-server](https://github.com/leirong/wzry-database-server)；页面设计参考 [Anthropic frontend-design](https://github.com/anthropics/skills/tree/main/skills/frontend-design)。`}/>
    <footer className="research-footer"><a href="../index.html">打开完整交互探索</a><span>腾讯公开赛事汇总 · 非官方个人作品</span></footer>
  </article>;
}
