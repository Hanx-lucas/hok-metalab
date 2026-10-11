"""Conclusion-first report with season-by-season strength evidence."""
import json
from pathlib import Path
from html import escape
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,Image,PageBreak

ROOT=Path(__file__).resolve().parents[1]
BLUE='#2057d6';NAVY='#173554';AMBER='#bd7d24';TEAL='#258785'
HEAT=['#e7edf8','#aec6ed','#739cde',BLUE,NAVY]

def daily_status():
    path=ROOT/'data/processed/daily_summary.json'
    if not path.exists():return '营地官方直接数据仍待本机授权核验；未取得日常公开样本。'
    s=json.loads(path.read_text(encoding='utf-8'))[0]
    return f"已取得苏苏助手第三方公开样本：{s['current_rows']}条四档当前榜单、{s['history_heroes']}位英雄的{ s['history_complete']:,}条三指标完整历史观察，日期{ s['history_first']}至{ s['history_last']}。无样本场次和S赛季映射，尚未官方对账；当前与历史末日存在差异，分开分析。全英雄历史尚未验证，营地官方直接数据仍待授权核验。"

def evidence():
    read=lambda n:json.loads((ROOT/f'data/processed/{n}.json').read_text(encoding='utf-8'))
    summary=read('summary');rows=read('hero_metrics');seasons=read('season_summary');history=read('strength_history')
    top=sorted([r for r in rows if r['league_id']==summary['latest_completed_league'] and r['score'] is not None and r['battles']>=30],key=lambda r:-r['score'])[:10]
    regular=[r for r in seasons if r['regular'] and r['event_status']=='已结束']
    return summary,rows,regular,history,top

def seasonal_figures(dest,history,top):
    # This function is also a standalone report refresh entry point; do not
    # rely on report.py having configured Chinese fonts in another call.
    plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','SimHei','DejaVu Sans'],
                         'axes.unicode_minus':False,'axes.spines.top':False,'axes.spines.right':False,
                         'axes.edgecolor':'#cad1dc','axes.labelcolor':'#364660','xtick.color':'#647289',
                         'ytick.color':'#647289','grid.color':'#e6ebf2','font.size':10,
                         'figure.facecolor':'white','axes.facecolor':'white','savefig.facecolor':'white'})
    heroes=list(dict.fromkeys(r['hero'] for r in history));events=list(dict.fromkeys(r['seasonLabel'] for r in history))
    lookup={(r['hero'],r['seasonLabel']):r['score'] for r in history}
    cmap=ListedColormap(HEAT);cmap.set_bad('#f1f3f8');norm=BoundaryNorm([0,60,75,85,95,101],cmap.N)
    for label,chosen in [('early',events[:8]),('recent',events[8:])]:
        matrix=np.array([[lookup[(hero,event)] if lookup[(hero,event)] is not None else np.nan for event in chosen] for hero in heroes])
        fig,ax=plt.subplots(figsize=(8.7,6.0))
        ax.imshow(np.ma.masked_invalid(matrix),cmap=cmap,norm=norm,aspect='auto')
        ax.set_xticks(range(len(chosen)),chosen,rotation=35,ha='right');ax.set_yticks(range(len(heroes)),heroes)
        ax.tick_params(length=0);ax.set_title('逐赛季相对强度 · 至少30场',loc='left',fontsize=13,fontweight='bold',pad=18)
        for y,hero in enumerate(heroes):
            for x,event in enumerate(chosen):
                value=lookup[(hero,event)]
                ax.text(x,y,'—' if value is None else f'{value:.0f}',ha='center',va='center',fontsize=10,color='white' if value is not None and value>=85 else NAVY)
        for spine in ax.spines.values():spine.set_visible(False)
        ax.set_xticks(np.arange(-.5,len(chosen),1),minor=True);ax.set_yticks(np.arange(-.5,len(heroes),1),minor=True);ax.grid(which='minor',color='white',linewidth=2);ax.tick_params(which='minor',length=0)
        fig.tight_layout();fig.savefig(dest/f'season_strength_{label}.png',dpi=200);plt.close(fig)
    fig,ax=plt.subplots(figsize=(8.7,4.4))
    for leader,color in zip(top[:2],[BLUE,AMBER]):
        group=[r for r in history if r['hero_id']==leader['hero_id']]
        ax.plot(pd.to_datetime([r['event_start'] for r in group]),[r['score'] for r in group],marker='o',lw=2,color=color,label=leader['hero'])
    ax.set_ylim(0,100);ax.set_ylabel('同届相对指数（0–100）');ax.set_title('最新强势英雄的相对地位如何变化',loc='left',fontsize=13,fontweight='bold',pad=18);ax.legend(frameon=False);ax.grid(axis='y');fig.autofmt_xdate(rotation=0);fig.tight_layout();fig.savefig(dest/'strength_history.png',dpi=200);plt.close(fig)
    fig,ax=plt.subplots(figsize=(8.7,3.4));group=top[:3];positions=np.arange(3);left=np.zeros(3)
    for field,weight,label,color in [('winPercentile',60,'胜率分位贡献',BLUE),('pickPercentile',25,'出场分位贡献',TEAL),('banPercentile',15,'ban分位贡献',AMBER)]:
        values=np.array([r[field]*weight for r in group]);ax.barh(positions,values,left=left,color=color,label=label,height=.5)
        for y,value,base in zip(positions,values,left):
            if value>=8:ax.text(base+value/2,y,f'{value:.1f}',ha='center',va='center',color='white',fontsize=10)
        left+=values
    ax.set_yticks(positions,[r['hero'] for r in group]);ax.invert_yaxis();ax.set_xlim(0,100);ax.set_xlabel('指数贡献分（合计为综合表现指数）');ax.legend(frameon=False,ncol=3,loc='upper center',bbox_to_anchor=(.5,-.22),fontsize=9);ax.set_title('前三名的领先由哪些信号构成',loc='left',fontsize=13,fontweight='bold',pad=18);fig.tight_layout();fig.savefig(dest/'score_decomposition.png',dpi=200);plt.close(fig)

def revise_report(figure_dir):
    summary,rows,seasons,history,top=evidence();a,b,c=top[:3];previous=seasons[-2]
    seasonal_figures(figure_dir,history,top)
    pct=lambda v:f'{v*100:.1f}%'; models={r['model']:r for r in summary['backtest_summaries']}
    counts={}
    for e in seasons:
        if e['basis']=='综合指数':counts[e['leader']]=counts.get(e['leader'],0)+1
    recurring=max(counts,key=counts.get)
    winner_table='\n'.join(f"| {e['event']} | {e['basis']} | {e['leader']} | {e['runner_up']} | {e['third']} |" for e in seasons)
    latest_table='\n'.join(f"| {i+1} | {r['hero']} | {r['score']:.1f} | {r['battles']} | {pct(r['posteriorRate'])} | {pct(r['lowerRate'])} - {pct(r['upperRate'])} | {pct(r['banRate'])} | {pct(r['top10WeightShare'])} |" for i,r in enumerate(top))
    memo=f'''# {a['hero']}与{b['hero']}领跑夏季赛，强势英雄随赛季更替

## 核心结论：最新完整赛事谁强

**结论：** {summary['latest_completed_event']}中，至少30场英雄的综合表现前三为{a['hero']}、{b['hero']}、{c['hero']}。{a['hero']}与{b['hero']}同时具有胜率与BP信号，{c['hero']}更需要作为BP压力型英雄观察。

**证据：** {a['hero']}指数{a['score']:.1f}、{a['battles']}场、平滑胜率{pct(a['posteriorRate'])}；{b['hero']}指数{b['score']:.1f}、{b['battles']}场、平滑胜率{pct(b['posteriorRate'])}。{c['hero']}ban率{pct(c['banRate'])}，后验区间{pct(c['lowerRate'])}-{pct(c['upperRate'])}。

**解释：** 综合指数衡量本届相对表现；高ban表示禁选压力，并不直接表示更高赢面。赵云和关羽区间重叠，名次先后不是显著性检验。

| 名次 | 英雄 | 指数 | 场次 | 平滑胜率 | 95%区间 | ban率 | 权重前十占比 |
|---|---|---|---|---|---|---|---|
{latest_table}

## 每个已采集常规赛季谁强

统一筛选至少30场，筛选不重算原指数。2019年仅有胜率证据，不能与三维排名混用。未采集的届次不补造，KPL届次不等同游戏S赛季。

| 赛季 | 判断依据 | 第一 | 第二 | 第三 |
|---|---|---|---|---|
{winner_table}

**结论：** 最近春季前三为{previous['leader']}、{previous['runner_up']}、{previous['third']}，与夏季不同。{recurring}在{counts[recurring]}届完整三维榜单中居首，是重复领先的证据；不是永久最强结论。

**证据：** 逐季热力图与相对指数曲线，见PDF和交互网页。热力图挑选最新前三与历史前五频次较高的12位英雄，以ID关联，低于30场或BP缺失保持空白。

**解释：** 只能描述相对地位轮换。缺少逐局版本、阵容、选手和战队信息，不能把变化直接归因于一次加强/削弱。

## 建模与数据口径

Beta(10,10)先验：平滑胜率=(胜场+10)/(场次+20)，区间取后验2.5%与97.5%分位数。指数=100×(60%胜率分位+25%出场分位+15%ban分位)。分位数在同赛事有效英雄中计算，先验和权重是分析设定。1000组权重情景只描述主观权重敏感性；30场是展示门槛，不是显著性门槛。

真实赛事数据覆盖2019-2026年{summary['official_events']}届、{summary['official_rows']}条英雄×赛事记录。{summary['hero_appearances']}次英雄战斗记录会同局重复计数，不是独立比赛数。385条早期BP占位转缺失，{summary['incoherent_rows']}条计数异常不用于后验与指数。原始JSON、URL、时间、SHA256保留。

## 预测审计

{summary['backtest_event_count']}届时间回测，50%基线加权MAE为{models['50%基线']['weightedMaePP']:.2f}pp，岭回归为{models['岭回归']['weightedMaePP']:.2f}pp。当前模型适合解释当届表现，尚无稳定未来预测增益。训练窗口结束须早于测试开始，2025春夏目录重叠过渡排除。当前数据是回顾快照，不是历史时点在线预测验证。

## 日常数据与最终应用

{daily_status()} 交互页面提供四档分段与4英雄历史探索，原手工S37-S39仍独立标注未核验。详见《替代数据源核验.md》。

**最终判断：** 职业赛事先关注当届高指数、场次充足且权重稳健的英雄；再分别核对胜率区间与BP压力。当前不能将这个榜单直接当作所有日常段位的上分建议。

来源：[腾讯赛事目录](https://prod.comp.smoba.qq.com/leaguesite/leagues/open)、[腾讯英雄目录](https://pvp.qq.com/web201605/js/herolist.json)。复现：`python run.py --offline --report`，再运行`python scripts/build_web.py`。
'''
    (ROOT/'docs/研究报告.md').write_text(memo,encoding='utf-8')
    font=Path('C:/Windows/Fonts/msyh.ttc');pdfmetrics.registerFont(TTFont('Chinese',str(font)))
    styles={key:ParagraphStyle(key,fontName='Chinese',fontSize=size,leading=leading,textColor=colors.HexColor(color),wordWrap='CJK',spaceAfter=gap) for key,size,leading,color,gap in [('body',10,17,'#364660',9),('title',27,39,NAVY,20),('h1',19,29,NAVY,16),('h2',12,20,BLUE,10),('small',8,12,'#5b6d85',8)]}
    story=[]
    def p(text,style='body'):story.append(Paragraph(escape(str(text)).replace('\n','<br/>'),styles[style]))
    def page(title):story.append(PageBreak());p(title,'h1')
    def pic(name,width=480):
        from PIL import Image as PILImage
        w,h=PILImage.open(figure_dir/name).size;story.append(Image(str(figure_dir/name),width=width,height=width*h/w));story.append(Spacer(1,10))
    def table(values,widths):
        t=Table([[Paragraph(escape(str(x)),styles['small']) for x in row] for row in values],colWidths=widths,repeatRows=1,hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e7edf8')),('LINEBELOW',(0,0),(-1,0),1,colors.HexColor(BLUE)),('LINEBELOW',(0,1),(-1,-1),.3,colors.HexColor('#dfe7f2')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),6)]));story.append(t);story.append(Spacer(1,12))
    p('HoK MetaLab | 肖涵 | 英雄强度研究','small');story.append(Spacer(1,26))
    p(f"{a['hero']}与{b['hero']}领跑夏季赛，\n强势英雄随赛季更替",'title')
    p('结论 - 证据 - 解释','h2');p(summary['latest_completed_event']+' | 最新完整赛事','small')
    p(f"结论：至少30场英雄中，综合表现前三为{a['hero']}、{b['hero']}、{c['hero']}。前两位的胜率与BP共同领先，第三位更突出禁选压力。")
    table([['英雄','指数','场次','平滑胜率','ban率']]+[[r['hero'],f"{r['score']:.1f}",r['battles'],pct(r['posteriorRate']),pct(r['banRate'])] for r in top[:3]],[100,90,90,100,100])
    p(f"解释：{a['hero']}和{b['hero']}的95%区间重叠，不能把指数第一、第二解读为显著强弱差异。{c['hero']}ban率高，但其胜率区间包含50%，应区分赢面与BP压力。")
    p(f"跨赛季：{previous['event']}前三为{previous['leader']}、{previous['runner_up']}、{previous['third']}，强势阵容并非固定。报告用逐季前三表、强度热力图和趋势曲线给出完整证据。")
    p('主榜判断范围是已采集职业赛事；赛事届次不等同游戏S赛季。日常第三方公开样本见末页与交互作品集。','small')
    page('胜率与禁选：两类证据放在一起')
    pic('posterior_intervals.png',465);pic('bp_comparison.png',465)
    p('证据：平滑胜率及区间评价观察赢面，出场与ban率反映选择和禁用压力。高ban是独立信号，不能单凭它断言英雄更容易赢。至少30场门槛只用于展示，不保证显著性。','small')
    page('逐赛季谁强：实际取得的常规KPL榜单')
    table([['赛季','第一','第二','第三','判断依据']]+[[e['event'],e['leader'],e['runner_up'],e['third'],e['basis']] for e in seasons],[138,79,79,79,105])
    p(f"结论：{recurring}在{counts[recurring]}届完整三维榜单居首；最近春夏的前三全部更替。表内统一筛选至少30场，再按既定指数排序，不重算分位数。")
    p('2019年缺少BP，前三只按平滑胜率比较。未取得的届次不填造，因此不能将表解读为所有KPL赛季或所有日常S赛季。','small')
    page('相对强度变化图：历史阶段')
    pic('season_strength_early.png');p('色阶：浅蓝<60，随后为60-75、75-85、85-95，深蓝95-100。数值为同届相对指数；灰色破折号表示BP缺失、观察缺失或低于30场。','small')
    p('图示英雄由最新前三与历史前五出现频次选取，共12位，以ID关联。反复深色说明在多个赛事中相对靠前，颜色变化表示地位轮换，不是绝对战力跨版本比较。')
    page('相对强度变化图：近期阶段')
    pic('season_strength_recent.png');p('与前页使用同一英雄顺序、阈值和色阶。持续强势与短期领先应分别判断。','small')
    p(f"近期结论：{previous['event']}领跑者为{previous['leader']}，{summary['latest_completed_event']}领跑者为{a['hero']}。主导者变化有实际榜单证据，但当前聚合数据不足以归因于某次版本调整。")
    page('为什么领先：趋势与贡献分解')
    pic('strength_history.png',450);pic('score_decomposition.png',450)
    p('解释：贡献分解直接对应指数公式，说明胜率、出场与ban信号各贡献多少。时间曲线使用官方目录开始日期，缺失保持空白；连接线只辅助阅读。','small')
    page('判断本届表现与预测未来是两件事')
    pic('backtest_comparison.png',465)
    table([['模型','加权MAE(pp)','Brier']]+[[r['model'],f"{r['weightedMaePP']:.2f}",f"{r['brier']:.4f}"] for r in summary['backtest_summaries']],[240,120,120])
    p(f"结论：{summary['backtest_event_count']}个测试赛事中，岭回归未超过50%基线，尚不能声称稳定的未来预测或上分收益。")
    p('证据与解释：训练目标结束早于测试开始；2025春夏目录重叠过渡排除。扩展窗口至少3个过渡，标准化只拟合训练集，alpha固定10。聚合特征缺少版本、阵容和选手环境，当前快照也不是真实历史时点数据。','small')
    page('方法、质量与可复现性')
    p('方法：Beta(10,10)先验，平滑胜率=(胜场+10)/(场次+20)。指数=100×(60%胜率分位+25%出场分位+15%ban分位)，分位数在同届有效英雄中计算。至少30场榜单筛选不改变指数公式。')
    p('1000组Dirichlet(12,5,3)权重情景评估前十稳健性，不是模拟对局或胜率置信度。另用0、10、20、50、100场先验做Spearman排名敏感性。后验区间依赖简化二项假设，没有校正同局和战队相关性。')
    p(f"真实证据：2019-2026年{summary['official_events']}届赛事、{summary['official_heroes']}个历史英雄ID、{summary['official_rows']}条英雄×赛事。{summary['hero_appearances']:,}次英雄战斗记录会同局重复计数，不是独立比赛数量。")
    p(f"质量：385条早期BP占位转缺失，{summary['incoherent_rows']}条计数异常不进入后验与指数。{summary['quality_issue_count']}项质量标记可能同时命中一行。胜率战斗场次与BP选用场次不混作分母。当前推荐分路不代表历史每局位置。")
    p('工程：urllib低频采集与SHA256缓存；Pandas、SciPy、scikit-learn分析；JSON/CSV/SQLite存储；React/Recharts交互；Matplotlib/ReportLab报告。原始响应、URL和时间均留档。')
    p('复现：python run.py --offline --report；python scripts/build_web.py。网页和报告使用同一主题色与逐季证据组件；正式交付包不包含授权私密目录。')
    page('最后的结论：如何使用这份研究')
    p(f"结论：{summary['latest_completed_event']}先关注{a['hero']}、{b['hero']}；将{c['hero']}单独作为BP压力型英雄研究。其他赛季使用当届榜单，不直接沿用最新排名。")
    p('证据：依次查看综合指数、场次、胜率区间、出场/ban率、权重稳健度及跨届热力图。多种信号同时支持，比单看一张胜率榜更有说服力。')
    p('解释：已观察职业表现强，不等于英雄在所有分段都强。不以原手工S37-S39替代真实日常证据。')
    p(daily_status(),'small')
    p('后续真正需要的证据是同期营地分段与逐局版本、阵容、选手/战队信息；到位后才能进一步研究英雄相性、分段迁移与版本效应。')
    p('公开来源与接口参考','h2')
    for label,url in [('腾讯赛事目录','https://prod.comp.smoba.qq.com/leaguesite/leagues/open'),('官方英雄目录','https://pvp.qq.com/web201605/js/herolist.json'),('赛事接口发现','https://github.com/leirong/wzry-database-server'),('日常第三方来源：苏苏助手（尚未官方对账）','https://pvp.91m.top/ranking'),('营地接口文档（待授权实测）','https://github.com/dxawdc/honor-of-kings-companion-api'),('前端技能与许可证','https://github.com/anthropics/skills/tree/main/skills/frontend-design')]:p(label+'\n'+url,'small')
    def chrome(canvas,doc):
        canvas.saveState();canvas.setStrokeColor(colors.HexColor('#dfe7f2'));canvas.line(46,42,A4[0]-46,42);canvas.setFillColor(colors.HexColor('#5b6d85'));canvas.setFont('Chinese',8);canvas.drawString(46,28,'HoK MetaLab | 肖涵 | 2026-10-11');canvas.drawRightString(A4[0]-46,28,str(doc.page));canvas.restoreState()
    target=ROOT/'output/pdf/研究报告.pdf'
    SimpleDocTemplate(str(target),pagesize=A4,rightMargin=46,leftMargin=46,topMargin=46,bottomMargin=56,title=f"{a['hero']}与{b['hero']}领跑夏季赛，强势英雄随赛季更替",author='肖涵').build(story,onFirstPage=chrome,onLaterPages=chrome)
    return target
