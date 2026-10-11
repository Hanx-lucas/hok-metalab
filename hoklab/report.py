"""Generate a Chinese research report, original Python figures and interview guide."""
from __future__ import annotations
import json
import math
import sys
from pathlib import Path
from html import escape
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, KeepTogether

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data"/"processed"
DOCS=ROOT/"docs"
OUT=ROOT/"output"
BLUE="#2057d6"
GOLD="#bd7d24"

def current_facts(summary,df,coverage,backtest):
    """Generate findings from the current snapshot rather than frozen example numbers."""
    a,b=summary["top_heroes"][:2]
    bp=max(summary["top_heroes"],key=lambda r:r["banRate"])
    interval_note="区间包含50%" if bp["lowerRate"]<=.5<=bp["upperRate"] else "区间未包含50%，但仅在二项模型假设下解释"
    model={r["model"]:r for r in summary["backtest_summaries"]}
    verdict="岭回归没有超过50%基线，当前特征没有体现稳定的未来预测增益。" if model["岭回归"]["weightedMaePP"]>=model["50%基线"]["weightedMaePP"] else "岭回归的平均误差低于50%基线，但仍需新增届次验证稳定性。"
    overlap=max(a["lowerRate"],b["lowerRate"])<=min(a["upperRate"],b["upperRate"])
    return {
        "years":f"{min(summary['years'])}-{max(summary['years'])}",
        "completed":int(coverage.event_status.eq("已结束").sum()),
        "ongoing":int(coverage.event_status.eq("进行中").sum()),
        "missing_bp":int(df.quality_flags.fillna("").str.contains("bp_not_recorded_all_zero_block").sum()),
        "test_count":backtest.league_id.nunique(),
        "leader_text":f"{a['hero']}与{b['hero']}的综合表现指数居前，平滑胜率分别为{a['posteriorRate']*100:.1f}%和{b['posteriorRate']*100:.1f}%。",
        "bp_text":f"{bp['hero']}的禁用率为{bp['banRate']*100:.1f}%，平滑胜率为{bp['posteriorRate']*100:.1f}%，95%可信区间为{bp['lowerRate']*100:.1f}%-{bp['upperRate']*100:.1f}%；{interval_note}。",
        "leader_intervals":f"{a['hero']}的95%区间为{a['lowerRate']*100:.1f}%-{a['upperRate']*100:.1f}%，{b['hero']}为{b['lowerRate']*100:.1f}%-{b['upperRate']*100:.1f}%；"+("区间重叠，不能据此证明一位显著强于另一位。" if overlap else "区间未重叠，但不是阵容或选手校正后的因果证据。"),
        "verdict":verdict,
    }

def figures(df,summary,backtest):
    dest=OUT/"figures";dest.mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({"font.sans-serif":["Microsoft YaHei","SimHei","DejaVu Sans"],"axes.unicode_minus":False,"axes.spines.top":False,"axes.spines.right":False,"axes.edgecolor":"#cad1dc","axes.labelcolor":"#364660","xtick.color":"#647289","ytick.color":"#364660","grid.color":"#e6ebf2","font.size":10,"figure.facecolor":"white","axes.facecolor":"white","savefig.facecolor":"white"})
    latest=df[(df.league_id==int(summary["latest_completed_league"])) & df.score.notna() & (df.battles>=30)].sort_values("score",ascending=False).head(10).iloc[::-1]
    fig,ax=plt.subplots(figsize=(8.7,4.5))
    y=np.arange(len(latest));p=latest.posteriorRate.to_numpy()*100
    ax.errorbar(p,y,xerr=np.array([p-latest.lowerRate.to_numpy()*100,latest.upperRate.to_numpy()*100-p]),fmt="o",color=BLUE,ecolor="#7b9fe0",capsize=3,markersize=6)
    ax.axvline(50,color="#8390a2",ls="--",lw=1)
    ax.set_yticks(y,latest.hero);ax.set_xlim(25,80);ax.set_xlabel("平滑胜率 / 95%可信区间（%）")
    ax.grid(axis="x");ax.set_axisbelow(True)
    for i,(_,r) in enumerate(latest.iterrows()):ax.text(79,i,f"n={int(r.battles)}",ha="right",va="center",fontsize=8,color="#647289")
    ax.set_title(summary["latest_completed_event"]+" · 综合指数前十",loc="left",pad=15,fontsize=13,fontweight="bold")
    fig.tight_layout();fig.savefig(dest/"posterior_intervals.png",dpi=190);plt.close(fig)
    fig,ax=plt.subplots(figsize=(8.7,4.5));y=np.arange(len(latest))
    ax.barh(y-.18,latest.pickRate*100,.32,color=BLUE,label="出场率")
    ax.barh(y+.18,latest.banRate*100,.32,color=GOLD,label="禁用率")
    ax.set_yticks(y,latest.hero);ax.set_xlim(0,100);ax.set_xlabel("公布比例（%），两种指标分别比较")
    ax.grid(axis="x");ax.set_axisbelow(True);ax.legend(frameon=False,loc="lower right")
    ax.set_title("高胜率与高禁用，提供不同的信息",loc="left",pad=15,fontsize=13,fontweight="bold")
    fig.tight_layout();fig.savefig(dest/"bp_comparison.png",dpi=190);plt.close(fig)
    fig,ax=plt.subplots(figsize=(8.7,4.4))
    names=["赵云","关羽"]
    events=df[df.event.str.contains(r"KPL.*[春夏秋]季赛",regex=True)&~df.event.str.contains("季前")&df.event_status.eq("已结束")].sort_values("event_start")[['league_id','event_start']].drop_duplicates()
    for hero,col in zip(names,[BLUE,GOLD]):
        h=events.merge(df[df.hero.eq(hero)][['league_id','posteriorRate']],on="league_id",how="left")
        ax.plot(pd.to_datetime(h.event_start),h.posteriorRate*100,marker="o",color=col,label=hero,lw=1.8)
    ax.set_ylim(30,70);ax.axhline(50,color="#8390a2",ls="--",lw=1);ax.set_ylabel("平滑胜率（%）");ax.legend(frameon=False)
    ax.grid(axis="y");ax.set_title("常规KPL届次间的表现持续性",loc="left",fontsize=13,fontweight="bold",pad=15)
    fig.autofmt_xdate(rotation=0);fig.tight_layout();fig.savefig(dest/"hero_history.png",dpi=190);plt.close(fig)
    fig,ax=plt.subplots(figsize=(8.7,4.5))
    bm=backtest.groupby("model")[["weightedMaePP","maePP"]].mean().sort_values("weightedMaePP")
    model_colors={'50%基线':'#8f8f8f','岭回归':BLUE,'上一届平滑胜率':GOLD,'近三届合并平滑':'#258785'}
    ax.barh(np.arange(len(bm)),bm.weightedMaePP,color=[model_colors[m] for m in bm.index])
    ax.set_yticks(np.arange(len(bm)),bm.index);ax.invert_yaxis();ax.set_xlim(0,7);ax.set_xlabel("跨测试赛事平均的场次加权 MAE（百分点）；越小越好")
    for i,v in enumerate(bm.weightedMaePP):ax.text(v+.1,i,f"{v:.2f}",va="center")
    ax.grid(axis="x");ax.set_axisbelow(True);ax.set_title("复杂模型没有稳定优于50%基线",loc="left",fontsize=13,fontweight="bold",pad=15)
    fig.tight_layout();fig.savefig(dest/"backtest_comparison.png",dpi=190);plt.close(fig)
    fig,ax=plt.subplots(figsize=(8.7,4.5));group=df[df.league_id.eq(int(summary["latest_completed_league"]))&df.score.notna()]
    ax.scatter(group.pickRate*100,group.posteriorRate*100,s=15+np.minimum(group.battles,300)*.13,color=BLUE,alpha=.65,edgecolor="white",lw=.5)
    for hero in ["赵云","关羽","鲁班大师","戈娅"]:
        selected=group[group.hero.eq(hero)]
        if not selected.empty:
            r=selected.iloc[0];ax.annotate(hero,(r.pickRate*100,r.posteriorRate*100),xytext=(5,7),textcoords="offset points",fontsize=9)
    ax.set_xlim(0,40);ax.set_ylim(30,70);ax.axhline(50,color="#8390a2",ls="--",lw=1)
    ax.set_xlabel("出场率（%）");ax.set_ylabel("平滑胜率（%）");ax.grid(alpha=.5);ax.set_axisbelow(True)
    ax.set_title("热度与表现不是同一个维度",loc="left",fontsize=13,fontweight="bold",pad=15)
    fig.tight_layout();fig.savefig(dest/"win_pick_landscape.png",dpi=190);plt.close(fig)
    return dest

def documentation(summary,df,coverage,backtest):
    DOCS.mkdir(exist_ok=True)
    models=pd.DataFrame(summary['backtest_summaries']).set_index('model')
    facts=current_facts(summary,df,coverage,backtest)
    metrics="\n".join(f"| {m} | {r.maePP:.2f} | {r.weightedMaePP:.2f} | {r.brier:.4f} |" for m,r in models.iterrows())
    top="\n".join(f"| {i+1} | {r['hero']} | {r['score']:.1f} | {r['posteriorRate']*100:.1f}% | {r['lowerRate']*100:.1f}% - {r['upperRate']*100:.1f}% | {r['battles']} |" for i,r in enumerate(summary['top_heroes']))
    memo=f"""# 王者荣耀英雄表现与版本生态研究

作者：肖涵 · 项目升级：2026-10-11 · 数据为本次采集快照，进行中的赛事另标。

## 摘要

- 通过腾讯公开赛事目录逐届抓取，得到2019-2026年{summary['official_events']}届赛事、{summary['official_heroes']}个历史英雄ID、{summary['official_rows']}条英雄×赛事观察。其中{facts["completed"]}届已结束、{facts["ongoing"]}届进行中；赛事届次不等同游戏S赛季。
- {summary['latest_completed_event']}中，{facts["leader_text"]}{facts["bp_text"]}禁选压力与胜率证据需要分别解读。
- 基于{facts["test_count"]}个测试赛事的扩展窗口回测，50%基线的平均场次加权MAE为{models.loc['50%基线','weightedMaePP']:.2f}个百分点，岭回归为{models.loc['岭回归','weightedMaePP']:.2f}个百分点。当前特征没有体现稳定的未来预测增益。
- 全分段、巅峰赛1350+与顶端排位数据仍需用户自己的营地授权；当前缺少授权和历史快照，不能报告分段差异。

## 数据与质量

数据来自腾讯的公开赛事英雄汇总接口，不是逐局原始对局。原始JSON、请求URL、UTC采集时间、HTTP状态与SHA256保存在data/raw目录；规范化数据和异常清单写入CSV、JSON及SQLite。复合主键为league_id与hero_id。

全库包含{summary['hero_appearances']:,}次英雄战斗记录。同一局会贡献多名英雄记录，部分赛局存在源口径差异，因此不能声称抓取了这些数量的独立比赛。官方胜率与BP使用不同统计块，pick_num不一定等于battle_count，不以BP场次替换胜率分母。

早期赛事有{facts["missing_bp"]}条记录，其BP字段整块为零而战斗场次为正：识别为未记录BP，在分析中设为null。{summary["incoherent_rows"]}条记录的胜场与负场不合计，保留原始观察但不用于贝叶斯胜率建模。全部{summary["quality_issue_count"]}项质量标记为多项检查结果，不能当作相同数量的独立坏记录。明确的数据异常分类见数据字典。

官方目录中的分路标签是采集时的推荐分路。历史分析仅把它作为当前标签，不能声称识别了英雄过去每局所走的分路。多分路英雄筛选可以重叠，不能将不同分路筛选的场次相加。

## 建模方法

1. 使用Beta(10,10)先验：平滑胜率=(胜场+10)/(战斗场次+20)。这等于20场、胜率50%的先验信息；先验由研究者设定，不称为经验贝叶斯。
2. 由Beta后验的2.5%与97.5%分位数得到95%可信区间，并计算Pr(p>0.5)。区间依赖独立同分布二项假设，没有控制战队、选手、全局BP及同局相关性。
3. 在同一赛事的有效英雄内分别计算平滑胜率、出场率、禁用率分位数，形成0-100综合表现指数：100×(0.60×胜率分位+0.25×出场分位+0.15×禁用分位)。权重是可解释设定，不是从真实标签学到的最优权重；指数不是胜率预测或因果强度。
4. 使用Pareto支配关系识别不能在胜率、出场、禁用三个维度同时被其他英雄超越的观察；存储pareto字段。Pareto优越仍不代表因果更强。
5. 使用1000组Dirichlet(12,5,3)权重，输出排名10%-90%情景范围和前十占比；用0、10、20、50、100先验等效场次检验Spearman排名相关。情景范围不是抽样置信区间。

## 最新完整赛事结果

| 排名 | 英雄 | 表现指数 | 平滑胜率 | 95%可信区间 | 战斗场次 |
|---|---|---|---|---|---|
{top}

{facts["leader_intervals"]}{facts["bp_text"]}高禁用可能与机制、阵容或全局BP有关，现有聚合数据无法区分原因。

## 历史趋势与预测验证

默认比较同类常规KPL春夏秋季赛，使用官方目录开始日期；缺失英雄不补零，不对赛事间日期插值。各届的版本、参赛队伍与BP规则可能改变，跨届趋势不是同环境的控制实验。

预测任务为：已知上一届的英雄聚合数据，预测下一届同一英雄的胜率。只取已结束的常规KPL春夏秋季赛，排除季前赛、挑战者杯和年度总决赛。目录结束窗口必须早于目标开始窗口；2025春夏目录窗口重叠，保守排除该过渡，另存backtest_exclusions。当前响应为回顾性快照，不是预测时点的历史不可变快照。使用扩展训练窗口，每个测试点以前的过渡届次训练，至少3个训练过渡，不随机拆分。

岭回归特征为上一届平滑胜率、出场率、禁用率、log(1+场次)、过去至多三届合并平滑胜率。StandardScaler只在训练数据拟合，Ridge alpha固定10；训练权重为sqrt(下一届场次)，仅来自已发生的训练目标。测试集不参与拟合、参数选择或标准化。当前回测依赖目录窗口与回顾性汇总，不能称为已验证的在线预测。

| 模型 | 英雄等权MAE (pp) | 场次加权MAE (pp) | Brier |
|---|---|---|---|
{metrics}

上表为每届测试指标的算术平均，测试届次权重相同。场次加权MAE在单届内按英雄battle_count加权。Brier从胜负计数计算，衡量对英雄出场胜负的平均概率误差；同局英雄观测相关，不能解释为独立样本的严格显著性检验。

{facts["verdict"]}应将回测视为模型检验结果，不包装成已验证的预测器。可能的改进方向需要逐局阵容、选手、战队、蓝红方、版本和BP规则；不应仅凭聚合表叠加模型复杂度。

## 日常数据与分段分析的边界

原项目S37-S39的127条手工记录独立保留，分类为user_manual_unverified。它们未记录分段、采集日期和样本量；不生成虚假的统计区间，不与官方职业赛事加权合并。

已实现camp授权采集适配器，使用本机private/camp_headers.json或环境变量读取用户自己的授权头，抓取全分段、巅峰赛1350+与顶端排位当前快照。认证头只存私密目录，不进入网页和交付包。返回的updateTime保留，但未提供赛季字段时不自行贴游戏S赛季标签。当前快照采集代码不代表多赛季分段历史已采集成功。

## 可视化与复现

网页分为综合强度、赛事强度、日常游戏强度，分别展示Top10、分路Top5、完整搜索总榜与英雄详情；综合双场景各50%、赛事缺失时采用100%日常强度，公式和边界见《强度榜计算标准.md》。报告提供同一批证据的阅读视图，PDF与Python静态图表可离线展示。安装依赖后运行python run.py --offline可复现全部数据计算；python run.py --refresh更新公开赛事快照。

## 来源与参考

- 腾讯赛事目录：https://prod.comp.smoba.qq.com/leaguesite/leagues/open
- 腾讯英雄汇总：https://prod.comp.smoba.qq.com/leaguesite/league/hero/settle_list/open?league_id=20260003
- 腾讯英雄目录：https://pvp.qq.com/web201605/js/herolist.json
- 公开接口发现线索：https://github.com/leirong/wzry-database-server （使用其接口地址作线索，实际数据直接从腾讯获取）
- 营地认证与字段文档：https://github.com/dxawdc/honor-of-kings-companion-api/blob/master/docs/api_reference.md （当前未执行授权采集）
- 前端设计参考：https://github.com/anthropics/skills/tree/main/skills/frontend-design （只读取技能文本；未运行仓库代码；许可证保留）
"""
    (DOCS/"研究报告.md").write_text(memo,encoding="utf-8")
    guide=f"""# 项目说明与面试指南

## 项目定位与当前状态

项目名称：王者荣耀英雄表现与版本生态分析平台（HoK MetaLab）。原项目为2025年的Python课程项目；本次在2026年10月工程化升级。项目创建和优化由AI辅助完成，面试时只陈述自己已理解、能复现和解释的部分。

已完成：真实官方赛事采集、清洗与质量审计、Bayes平滑、多维表现指数、Pareto标记、权重和先验敏感性、按时间回测、交互网页、研究报告和可运行代码。待用户授权：王者营地不同分段真实快照。公开历史分段快照当前仍缺，不能写成已完成的全量多赛季分段采集。

## 简历表述（建议使用）

**基于Python的王者荣耀英雄表现与版本生态分析平台**

- **数据工程：** 基于腾讯公开赛事接口构建低频采集与缓存管线，覆盖2019-2026年{summary['official_events']}届赛事、{summary['official_heroes']}个历史英雄ID与{summary['official_rows']:,}条英雄×赛事观察；保存原始JSON、SHA256和采集日志，规范化写入SQLite/CSV，并识别BP缺失及计数口径异常。
- **建模分析：** 采用Beta-Binomial平滑修正职业赛事小样本波动，结合胜率、出场率与禁用率构建可解释表现指数，开展1000组权重情景和先验敏感性分析；通过扩展时间窗口对岭回归及历史基线进行回测，明确预测能力边界。
- **作品展示：** 搭建React交互分析网页，支持三维强度榜、分路榜、全英雄搜索、证据详情及数据溯源，输出研究报告与PDF，实现数据采集至可视化的复现流程。

字数更短的版本：

基于Python抓取2019-2026年{summary['official_events']}届王者荣耀赛事{summary['official_rows']:,}条英雄聚合记录，完成数据质量审计、贝叶斯平滑和多维表现评价，采用严格时间回测评估模型；搭建React交互作品集及研究报告，支持英雄对比、趋势分析和数据溯源。

不要写：抓取11万场真实对局、完整覆盖所有分段和多赛季、预测准确率提升X%、模型帮助胜率提升X%、独立研发所有前端基础设施、已实现成本收益优化。现有证据不支持这些说法。

## 技术栈与职责

| 层级 | 技术 | 做了什么 |
|---|---|---|
| 采集 | Python urllib、JSON、时间间隔、退避重试 | 从官方目录发现真实赛事ID，逐届请求；缓存命中校验hash；401/403停止；不拼造赛季ID |
| 数据治理 | Pandas、NumPy、openpyxl、SHA256 | 百分比规范化、复合主键、空值保留、胜负计数校验、手工记录隔离、字段血缘 |
| 数据存储 | SQLite、CSV、JSON | 保存原始响应、规范化观察、异常清单、指标、回测及来源manifest |
| 统计分析 | SciPy Beta分布 | 后验均值、95%可信区间、超过50%的模型概率 |
| 指数评价 | Pandas分位数、NumPy | 三维加权指数、Pareto支配、Dirichlet权重情景、Spearman先验敏感性 |
| 验证 | scikit-learn StandardScaler + Ridge | 扩展时间窗口，3个基线；MAE、场次加权MAE、Brier |
| 网页 | React、Recharts、共享Data运行时、CSS | 三维榜单、Top10、分路Top5、英雄搜索、详情、来源菜单与响应式布局；没有新增FastAPI服务 |
| 报告 | Matplotlib、ReportLab | 独立Python图表及逐季强度热力图、研究PDF与Markdown报告 |
| 检验 | unittest、Playwright + Edge、Poppler | 验证计算不变量、网页实际渲染与交互、手机布局、PDF页面 |

Data插件提供共享页面壳、图表、编辑和来源查看基础设施；本项目实现内容层、Python分析管线与作品设计，不将这些基础设施描述为自己从零研发。

## 两分钟面试陈述

“原来我只手工收集了少量营地榜单，用出场率乘胜率分析。升级时我首先解决了来源可验证的问题：从官方赛事目录获取真实ID，低频采集33届赛事，保存原始JSON与hash，并把数据粒度明确为英雄×赛事。我发现2019年BP字段整块为零、部分胜负计数不一致，因此不直接把零当观察，也不人为补场次。\n\n建模时用Beta先验收缩小样本，再将平滑胜率、出场率和禁用率的同届分位数组合成表现指数；权重不是事实，所以我做了1000组权重情景和先验敏感性。最后按时间预测下一届，与50%及历史基线比较。岭回归没有稳定超过50%基线，这让我明确区分描述表现与预测胜率。网页和报告用于展示这些结果，所有结果都能追溯回原始响应。”

## 常见追问

**为什么不用出场率×胜率？** 两者相乘会使热门英雄机械地领先，无法区分高胜低选、小样本偶然值与高禁选压力。新指数仍包含热度，但通过分位数、明确权重和独立维度可解释其含义，不将它视为绝对英雄强度。

**为什么Beta(10,10)？** 与二项似然共轭，先验均值50%、等效20场；样本少时收缩明显，样本多时数据占主导。20是可解释的研究设定，因此额外检验0、10、20、50、100；不能称其为数据自动学习的经验贝叶斯先验。

**95%可信区间和胜率有何不同？** 胜率是样本表现，后验区间是给定先验与二项假设后的参数不确定性。同局和同队存在相关性，本项目未建分层模型，区间可能偏乐观。

**禁用率越高越强吗？** 不能保证。机制、阵容相性、全局BP和心理预期都可能影响禁用。禁用率是禁选压力信号，必须与胜率和场次一起观察。

**1000次模拟是什么？** 固定观察数据，只抽取权重；进入前十的占比反映对主观权重的敏感性。不是1000场模拟真实对局，也不是英雄胜率的置信度。

**如何防止数据泄漏？** 测试下一届，只使用已发生的过去届次训练；StandardScaler拟合训练数据；历史合并不含测试目标；alpha固定，不用测试集调参。新英雄或缺失BP导致不适用的记录明确排除，回测只代表有历史交集的英雄。

**模型效果如何？** {facts["test_count"]}个测试赛事平均场次加权MAE：50%基线{models.loc['50%基线','weightedMaePP']:.2f}pp，岭回归{models.loc['岭回归','weightedMaePP']:.2f}pp。复杂模型没超过基线，不声称有已验证预测能力；下一步需要逐局和版本特征。

**日常分段和职业赛能直接比吗？** 分母、玩家能力、选手、BP规则与时间窗口不同。日常接口未提供样本量时不能与职业赛相同地做统计推断；应先获取同期分段快照、核对口径，再作描述比较。现在未获取授权，不报告该结论。

**这个项目如何持续更新？** 默认校验缓存避免重复请求；--refresh抓取新快照，分析后更新应用内容快照并重建。没有创建无人值守自动任务；机器关闭不会自动更新。

**可进一步做什么？** 获得逐局合法数据后，加入版本、选手、战队、蓝红方和阵容，做分层logistic模型、英雄相性及分段校正。历史分段需要历史快照或授权数据供应商，不可用当前榜单冒充。

## 三分钟现场演示

1. 打开综合强度，说明双场景各50%及赛事缺失时100%日常替代，依次展示Top10、五个分路Top5与全部英雄总榜。
2. 搜索赵云并打开英雄详情，说明两个场景的原始指标、分数贡献和观察日期差异。
3. 切换赛事强度，选择历届赛事；解释至少30场的门槛、贝叶斯平滑与未评分原因。
4. 切换日常游戏强度与四档分段，说明第三方来源、未知样本量和分段差异。
5. 展开计算标准并打开来源菜单；最后进入赛事研究报告，展示逐赛事变化与回测结果。
6. 日常与分段页面明确缺口，不展示伪造的真实榜单。

## 后续需要补充的事项

- 决定是否提供自己账号的授权营地会话或合法导出的榜单快照，补充全分段/1350+/顶端排位；不把登录凭据发到公开代码仓库。
- 若要完整历史分段，提供已有历史快照或确定可用的授权数据源。本次没有获得历史分段。
- 决定作品集是否公开上线、使用GitHub Pages等平台及公开范围；目前已完成本地可展示产物。
- 阅读并亲自复现核心代码，再选择上面的简历表述。新升级日期写2026年10月，不把升级功能倒写成2025年已完成。
"""
    (DOCS/"项目说明与面试指南.md").write_text(guide,encoding="utf-8")
    dictionary="""# 数据字典与口径

粒度：一行一个hero_id × league_id；赛事ID为届次，不等同游戏S赛季。历史与当前英雄名都保留，身份以ID关联。

| 字段 | 单位/含义 | 处理 |
|---|---|---|
| hero_id / league_id | 官方英雄ID / 官方赛事ID | 复合唯一键 |
| event_start / event_end | 官方赛事窗口 | 不当作每场日期；进行中截止未完成 |
| battles / wins / losses | 统计块的战斗/胜/负场次 | wins+losses=battles且胜率一致才允许贝叶斯推断 |
| picks / bans | BP统计块计数 | 不用picks替换battles；与战斗场次不同另记标记 |
| winRate | 官方原始0-1胜率 | 表示已观察表现 |
| pickRate / banRate | 官方BP块0-1比例 | 分母由源口径决定；整块占位零转null |
| posteriorRate | (wins+10)/(battles+20) | Beta(10,10)后验均值 |
| lowerRate / upperRate | 95%可信区间 | Beta后验分位数；简化二项模型，非因果区间 |
| probAbove50 | 后验Pr(p>0.5) | 条件于先验和模型假设 |
| winPercentile / pickPercentile / banPercentile | 同赛事可建模英雄中rank(pct=True) | 平均并列名次除以有效英雄数 |
| score | 100×(0.60winPercentile+0.25pickPercentile+0.15banPercentile) | 同赛事相对表现；不是跨赛事绝对量 |
| top10WeightShare | 1000组权重情景进入前十占比 | 不作胜率概率，数据固定 |
| rankP10 / rankP90 | 权重情景排名分位数 | 不作统计置信区间 |
| pareto | 三维无支配标记 | 同届下有无其他英雄三维不差且至少一维更好 |
| roles / role | 当前官方推荐分路集合 / 首个标签 | 不是历史每局真实分路；多分路筛选可重叠 |
| kda / gold | 官方平均KDA / 平均经济 | 保留用于画像；不直接把它们解释为强度 |
| bp_games_inferred | picks/pickRate中位数四舍五入 | 仅诊断，不作为精确独立比赛总数 |
| source_class | official_public_aggregate / user_manual_unverified / authorized_camp_aggregate | 来源分类不混用 |
| retrieved_at | UTC采集完成时间 | 不等于数据观察截止；原始meta保存准确时间 |

质量标记：bp_not_recorded_all_zero_block=全赛事BP整块占位零；outcome_counts_inconsistent=胜负不合计或计数异常；win_rate_count_mismatch=公布胜率与胜场/战斗场次不符；bp_pick_differs_from_battle_count=两个统计块口径不同；invalid_*或bp_sum_over_one=范围异常。

2019年385条BP占位记录保留胜率数据，BP三维指数为null。20条计数不一致记录保留原始指标，但后验为空。没有BP数据不等于出场率0%。

回测MAE单位为百分点。weightedMaePP单届内以目标battles加权；报告表格取测试届次等权平均。Brier单届以胜负次数计算，不能将同局多英雄当作独立样本用于显著性检验。
"""
    (DOCS/"数据字典.md").write_text(dictionary,encoding="utf-8")
    return memo

def pdf_report(summary,df,backtest,figure_dir):
    dest=OUT/"pdf";dest.mkdir(parents=True,exist_ok=True)
    facts=current_facts(summary,df,pd.read_csv(DATA/"coverage.csv"),backtest)
    font=Path("C:/Windows/Fonts/msyh.ttc")
    if not font.exists():
        font=Path("C:/Windows/Fonts/simsun.ttc")
    pdfmetrics.registerFont(TTFont("Chinese",str(font)))
    styles={"body":ParagraphStyle("body",fontName="Chinese",fontSize=10.2,leading=17,textColor=colors.HexColor("#364660"),wordWrap="CJK",spaceAfter=9),"title":ParagraphStyle("title",fontName="Chinese",fontSize=30,leading=43,textColor=colors.HexColor("#173554"),spaceAfter=20),"h1":ParagraphStyle("h1",fontName="Chinese",fontSize=20,leading=30,textColor=colors.HexColor(BLUE),spaceAfter=14),"h2":ParagraphStyle("h2",fontName="Chinese",fontSize=13,leading=20,textColor=colors.HexColor("#173554"),spaceAfter=10),"small":ParagraphStyle("small",fontName="Chinese",fontSize=8,leading=12,textColor=colors.HexColor("#647289"),wordWrap="CJK",spaceAfter=8)}
    story=[]
    def p(text,style="body"):
        story.append(Paragraph(escape(str(text)).replace("\n","<br/>"),styles[style]))
    def picture(filename,width=480):
        from PIL import Image as PILImage
        w,h=PILImage.open(figure_dir/filename).size
        story.append(Image(str(figure_dir/filename),width=width,height=width*h/w));story.append(Spacer(1,9))
    def table(rows,widths):
        wrapped=[[Paragraph(escape(str(x)),styles["small"]) for x in row] for row in rows]
        t=Table(wrapped,colWidths=widths,repeatRows=1,hAlign="LEFT")
        t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#eaf0fc")),("LINEBELOW",(0,0),(-1,0),1,colors.HexColor(BLUE)),("LINEBELOW",(0,1),(-1,-1),.3,colors.HexColor("#dfe6ef")),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),7),("RIGHTPADDING",(0,0),(-1,-1),7),("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),4)]));story.append(t);story.append(Spacer(1,12))
    def page(title):story.append(PageBreak());p(title,"h1")
    p("HoK MetaLab","small");story.append(Spacer(1,28))
    p("英雄表现榜单，\n为什么不能直接预测下一版本","title")
    p("王者荣耀英雄表现与版本生态研究","h2")
    p("肖涵 | Python数据分析作品集 | 2026年10月11日","small")
    story.append(Spacer(1,16));p("研究摘要","h1")
    p(f"通过腾讯公开接口，采集2019-2026年{summary['official_events']}届赛事、{summary['official_heroes']}个历史英雄ID和{summary['official_rows']:,}条英雄与赛事观察。{facts["completed"]}届已结束，{facts["ongoing"]}届仍在进行。赛事届次与游戏S赛季分别记录，未声称覆盖所有日常赛季。")
    p("最新完整赛事中，"+facts["leader_text"]+"表现、热门程度和禁选压力应分别观察。")
    p(f"{facts['test_count']}个测试赛事的严格时间回测中，50%基线平均场次加权MAE为{summary['backtest_summaries'][0]['weightedMaePP']:.2f}个百分点，岭回归为{next(r['weightedMaePP'] for r in summary['backtest_summaries'] if r['model']=='岭回归'):.2f}个百分点。当前模型没有体现稳定的未来预测增益。")
    p("日常全分段、1350+巅峰与顶端排位需要用户自己的授权榜单快照。当前未获得授权和历史快照，报告不填造这些数据。")
    p("阅读路径：先看证据与质量，再看表现指数及区间，最后检验模型、讨论边界与复现方法。","small")
    page("来源与数据质量")
    p(f"原始JSON、URL、UTC采集时间、HTTP状态与SHA256均留档。主键为官方赛事ID与英雄ID。全库{summary['hero_appearances']:,}次英雄战斗记录会在同一局重复计数，不能称为独立比赛局数。")
    table([["数据范围","已得到的证据","主要限制"],["官方赛事",f"{summary['official_events']}届；{summary['official_rows']:,}条聚合观察","不是逐局阵容或玩家日志"],["早期BP",f"{facts['missing_bp']}条整块占位零识别为缺失","保留胜率，BP指数不计算"],["胜负计数",f"{summary['incoherent_rows']}条不一致记录标记保留","不参与后验胜率建模"],["原项目手工数据",f"S37-S39共{summary['legacy_rows']}条","未独立核验，日期/分段/场次缺失"],["营地分段榜单","已实现授权适配器","没有已授权或历史快照"]],[105,195,180])
    p(f"胜率统计块的battle_count与BP统计块的pick_num可能不同。分析保留两个分母的语义，不用BP选用数替换胜率场次。{summary['quality_issue_count']}项质量标记包含一行多个检查结果，不是相同数量的独立坏记录。")
    p("分路为当前官方目录的推荐标签。它帮助浏览英雄，不能说明历史每局真实位置；多分路英雄筛选可重叠，不可简单相加。")
    p("进行中赛事单列展示。最新完整赛事为"+summary["latest_completed_event"]+"；未结束届次只代表采集时快照。")
    page("先修正样本量，再评价表现")
    p("平滑胜率 = (胜场 + 10) / (战斗场次 + 20)，先验为Beta(10,10)。先验均值50%、等效20场，由分析者设定；不称为经验贝叶斯。95%可信区间为后验2.5%与97.5%分位数。")
    p("综合表现指数 = 100 × (0.60 × 平滑胜率分位 + 0.25 × 出场率分位 + 0.15 × 禁用率分位)。分位数只在同届有效英雄中计算，0-100为相对指数。权重不是客观事实，指数不等于未来胜率或因果强度。")
    picture("posterior_intervals.png")
    p("同局、同队与全局BP存在相关性；这里的二项模型没有校正这些因素，区间只在简化假设下成立。赵云和关羽的区间重叠，不能据此证明一位显著强于另一位。","small")
    page("禁选压力与胜率证据分别解读")
    picture("bp_comparison.png")
    p(facts["bp_text"]+"高禁用提供独立的BP压力信号，但不能仅凭禁用解释其因果强度。机制、阵容和全局BP规则可能影响禁选；当前数据不能分解这些原因。")
    p("以1000组Dirichlet(12,5,3)权重重算排名，输出前十占比及排名情景范围。该比例描述权重敏感性，不是实战胜率或抽样置信度。先验等效场次0、10、20、50、100另做排名相关检验。")
    p("Pareto标记记录三维上是否存在同时不差且至少一维更好的英雄。它用于发现不同表现类型，同样不提供因果结论。")
    page("跨届趋势需要保留时间与环境差异")
    picture("hero_history.png")
    p("默认仅比较常规KPL春夏秋季赛，横轴为官方目录开始日期。缺失英雄保持为空，赛事间不插值。历史英雄身份以官方ID关联；图示选择赵云与关羽观察同类赛事的表现持续性。")
    p("胜率变化不自动等于英雄加强或削弱。参赛战队、选手实力、对手、阵容和全局BP规则也会改变观察表现；现有聚合表不能控制这些混杂。")
    p("2019年BP缺失时不画成出场率0%。对原项目S37-S39的手工榜单保留原样来源，在网页中独立呈现；不把它们合并成全量职业与日常样本。")
    page("用未来届次检验预测，而不是随机切分")
    picture("backtest_comparison.png")
    table([["模型","平均加权MAE(pp)","平均Brier"]]+[[r['model'],f"{r['weightedMaePP']:.2f}",f"{r['brier']:.4f}"] for r in summary['backtest_summaries']],[210,140,130])
    p("只取已结束常规KPL赛季，目录结束窗口需早于目标开始窗口；2025春夏目录重叠过渡排除。按目录日期使用扩展训练窗口；至少3个历史过渡训练，测试下一届。标准化在训练集拟合；alpha固定10，测试集不参与拟合或调参。表中为测试届次等权平均，单届MAE内部按英雄目标场次加权。","small")
    p("上一届胜率、BP热度、log场次与近三届平滑均值不足以稳定预测下一届。岭回归没有超过50%基线，当前成果应定位为可解释表现分析与预测能力审计。","small")
    page("可复现工程与下一步")
    p("采集：Python urllib、官方真实赛事目录、低频请求、退避重试、401/403停止、SHA256缓存校验。数据治理：Pandas、NumPy、openpyxl；存储：原始JSON、规范化CSV/JSON与SQLite。")
    p("分析：SciPy Beta后验与敏感性；scikit-learn扩展时间回测。网页：React与Recharts共享数据运行时，项目实现作品内容层、交互设计与数据溯源绑定。报告：Matplotlib原生图表与ReportLab PDF。")
    p("复现：安装requirements.txt后运行 python run.py --offline；更新公开数据运行 python run.py --refresh。run.py默认使用本项目缓存，不创建无人值守计划。网页静态产物和离线报告都可直接带到面试现场。")
    p("下一步需要实际新增证据：获取用户自己授权的日常分段快照、同期历史快照及逐局BP/阵容/选手/战队数据。再讨论分层模型、英雄相性和分段校正。当前聚合数据不支持成本收益、装备效果或上分收益因果验证。")
    p("公开来源与参考","h2")
    for label,url in [("腾讯赛事目录","https://prod.comp.smoba.qq.com/leaguesite/leagues/open"),("腾讯赛事英雄汇总","https://prod.comp.smoba.qq.com/leaguesite/league/hero/settle_list/open?league_id=20260003"),("腾讯英雄目录","https://pvp.qq.com/web201605/js/herolist.json"),("接口发现线索","https://github.com/leirong/wzry-database-server"),("营地接口文档（未执行授权采集）","https://github.com/dxawdc/honor-of-kings-companion-api"),("前端技能参考与许可证","https://github.com/anthropics/skills/tree/main/skills/frontend-design")]:p(label+"\n"+url,"small")
    def chrome(canvas,doc):
        canvas.saveState();canvas.setStrokeColor(colors.HexColor("#dfe6ef"));canvas.line(46,42,A4[0]-46,42);canvas.setFillColor(colors.HexColor("#647289"));canvas.setFont("Chinese",8);canvas.drawString(46,28,"HoK MetaLab | 肖涵 | 2026-10-11");canvas.drawRightString(A4[0]-46,28,str(doc.page));canvas.restoreState()
    path=dest/"研究报告.pdf"
    SimpleDocTemplate(str(path),pagesize=A4,rightMargin=46,leftMargin=46,topMargin=46,bottomMargin=56,title="王者荣耀英雄表现与版本生态研究",author="肖涵").build(story,onFirstPage=chrome,onLaterPages=chrome)
    return path

def build_report():
    OUT.mkdir(exist_ok=True)
    summary=json.loads((DATA/"summary.json").read_text(encoding="utf-8"));df=pd.read_csv(DATA/"hero_metrics.csv");coverage=pd.read_csv(DATA/"coverage.csv");backtest=pd.read_csv(DATA/"backtest.csv")
    if summary['prior'] != 20:
        raise ValueError("Authored report methods require prior=20; revise its methods before changing prior")
    documentation(summary,df,coverage,backtest)
    daily_path=DATA/'daily_summary.json'
    if daily_path.exists():
        daily=json.loads(daily_path.read_text(encoding='utf-8'))[0]
        note=(f"\n## 日常第三方公开来源补充\n\n苏苏助手公开样本：{daily['current_rows']}条四档当前榜单、"
              f"{daily['history_heroes']}位英雄的{daily['history_rows']:,}条日期记录，其中{daily['history_complete']:,}条三指标完整。"
              "尚未官方对账，无样本场次及S赛季映射，当前与历史末日存在差异，独立于KPL模型与营地授权表。"
              "详见《替代数据源核验.md》与daily_current/daily_history/daily_coverage/daily_reconciliation。"
              "缺失不补0；不由日均指标计算没有分母的赛季整体胜率，不宣称全英雄完整历史。\n")
        for filename in ['项目说明与面试指南.md','数据字典.md']:
            path=DOCS/filename
            text=path.read_text(encoding='utf-8')
            text=text.replace('现在未获取授权，不报告该结论。','现有第三方公开样本仅作独立描述探索，尚未官方对账。')
            text=text.replace('本次没有获得历史分段。','本次已取得第三方4英雄历史，完整全英雄历史尚未验证。')
            text=text.replace('6. 日常与分段页面明确缺口，不展示伪造的真实榜单。','6. 日常与分段切换公开四档榜单及4英雄历史，说明第三方来源与口径限制。')
            path.write_text(text+note,encoding='utf-8')
    paths=figures(df,summary,backtest)
    from .report_v2 import revise_report
    print(revise_report(paths))

if __name__=="__main__":build_report()
