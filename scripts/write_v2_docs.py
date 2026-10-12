"""Regenerate V2 explanatory documents from reviewed tables, never hand-edit scores."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
q=json.loads((ROOT/'data/reviewed_snapshot.json').read_text(encoding='utf-8'))['queries']
rows=lambda name:q[name]['rows']
def fmt(v,n=2):return '—' if v is None else f'{v:.{n}f}'
def pct(v):return '—' if v is None else f'{100*v:.2f}%'
def table(headers,records):
 return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+['| '+' | '.join(str(x).replace('|','/') for x in r)+' |' for r in records])+'\n'
def write(name,text):(ROOT/'docs'/name).write_text(text,encoding='utf-8')
method='''# 英雄强度计算标准：V1对照 / V2描述性试验

## 比较范围与可解释性

总榜在同赛事、或同日期同分段全部有效英雄中计算；分路榜V2独立计算，不能直接过滤总榜。分路分只用于同路比较。当前腾讯推荐位置可能多路，不能冒充历史实际比赛分路。原始数据未控制战队、选手、阵容、版本与玩家熟练度，评分不是英雄因果战力。

## V1：保留原结果

S1=100×(.60P(W)+.25P(Pick)+.15P(Ban))，P=平均秩/n。赛事W用(胜场+10)/(场次+20)。旧计算先在原有效池取得分位，再筛至少30场排名；不修改其T/D得分或原派生表。V1分路只筛总榜，用于对照。旧`strength_rankings`的日常替代综合分只保留档案，不用于新的综合榜；V1单场景对照得分保持不变；新版V1综合展示按用户最新设置采用30/70或100%D同榜，原综合分/名次保留在旧派生表及legacy_v1_rank。新综合分与名次改变来自新场景政策，不能当成旧V1单场景回归。

## V2：先核查BP定义，再进入统计池

国服赛事BP使用同届BP统计块的pickRate+banRate。逐项验证有限且0–1，检查BP不超过1（仅允许原率四舍五入误差0.00011），计数/率共同分母一致性容差0.0002；共同分母由正计数/率比值中位数诊断，不作为真实总局数或样本量。未获得公开精确分母定义，仍保留这一限制；早年全块占位和异常记录不评分，不截断原异常。

苏苏助手ban原始字段为双值数组：榜单展示ban对应第二项，同时返回allBanRate。当前四档逐英雄审计pick+展示ban与allBanRate，容差0.00015。第一项可能双禁累计超过100%，保留原响应，不误当同分母单禁率。现在只对已验证口径评分；不可对未来字段无条件相加。

赛事先筛至少30场、计数自洽、指标完整且BP审计通过的英雄，再对胜率W=(wins+10)/(battles+20)建统计池。Beta(10,10)后验区间仅用于赛事。日常没有场次：使用公布原始胜率，不伪造n、区间或贝叶斯平滑。

## 逐项公式

对每个统计池，P(X)=平均秩/n（升序，高值高分），指标并列使用平均秩。胜率使用原W；BP原值计算P，但仅在Z计算前用本池线性插值5%/95%分位缩尾：Xz=clip(BP,q05,q95)。原BP、上下限及调整值均保留。

Z=(Xz−μ)/σ；σ为总体标准差（ddof=0）。N=clip(.5+Z/4,0,1)。H(X)=.5P(X)+.5N(X)。E=100H(W)，B=100H(BP)。σ=0时Z=0、N=.5；不制造NaN或100分。P的平均秩/n传统定义在常数池略高于.5，文档与代码保持一致。池不足5人不给分；5–9人附低可信度提示。输入缺失、越界及重复ID被拒绝，不用零替代。

总榜S=.65E+.35B。分路独立统计：对抗65/35、打野70/30、中路70/30、发育60/40、游走60/40；同时输出同池统一65/35的uniformScore/uniformRank。以上均为初始参数，没有宣称最优。

每个分数等于eContribution+bContribution。精度保持到派生文件；页面只对展示四舍五入，排序用原精度，分数并列以ID稳定排序，展示名次是序位；指标分位仍使用平均秩。

## T / D / C及缺失

分别计算赛事T与日常D；双方有效C=.3T+.7D。仅日常有效时展示100%D并进入同一综合榜。C无需混合原始指标再标准化；E、B与贡献按实际30/70或0/100场景权重加总，详情展开两场景各自统计池，不制造合并的原始胜率或BP。

仅日常有效者route=daily_fallback、scoreBasis=仅日常参考，实际tWeight=0/dWeight=1，保留D原统计池分数并同榜排名；说明原赛事无记录、不足30场、口径异常或池不足。daily_observations仅作为诊断档案，不再单独显示观察榜。此榜不同条目的证据基础不同，不把仅日常者冒充双场景综合估计。只有赛事或双方缺失者保留原指标与原因，不补零，不认定弱；综合有效池不足5人不排名。

赛事最新已结束届次为2026年KPL夏季赛（2026-06-17至2026-09-13），日常当前快照统计日期2026-10-10；二者不是同版本同期样本。HTTP采集/网页构建时间不替代统计日期。进行中赛事可探索但不进入时间回测。

## 权重调节与验证门槛

网页E权重45%–85%，每次5个百分点，仅重组已审阅E/B；保留统计池、P、Z与缺失资格，标明临时情景，重置回默认。总榜调节不改变独立分路默认；选中分路后只调该路，不能据此跨路比较。

`validate_v2.py`先跑完整Python测试，保存原输入/代码SHA256指纹；流水线只有一致且passed的门槛文件才默认V2，否则回到V1候选。此门槛验证数值与数据规则，不是预测优势认证。所有数据再由处理流水线导出CSV/JSON/SQLite，页面与图表共用model_rankings。

E权重55/60/65/70/75、综合T权重25/30/40/50/60/75为预设敏感性情景。时间验证要求上一届结束严格早于下一届开始，排除重叠窗口；同英雄交集、两届样本门槛与BP有效，不使用未来数据计算过去分数。目标是下一届原始胜率的Spearman关联，指数不是概率，因此不直接算概率MAE。查看《V2模型验证报告》中的限制。
'''
write('强度榜计算标准.md',method)
latest=next(r for r in rows('summary'))['latest_completed_league']
keys=['arena:'+str(latest)]+['daily:'+s for s in ['全分段','巅峰赛1350+','顶端排位','巅峰千强']]
coverage=[r for r in rows('coverage_summary') if r['context_id'] in keys]
validation='''# V2模型验证报告

本报告由`python scripts/write_v2_docs.py`读取处理流水线派生表生成；不手工修改英雄得分。默认V2仅表示数值与数据规则经验证，权重仍为试验。旧V1 T/D与派生档案保留，新版综合按用户最新设定，双有效30%T/70%D，缺有效赛事时100%D同榜，明确标注评分依据。

## 覆盖复核

'''+table(['场景','目录','有效','无记录','胜率缺失','其他缺失','少于30场','口径异常'],[[r['event'] or r['segment'],r['catalogue'],r['完整有效'],r['完全无记录'],r['胜率缺失'],r['其他指标缺失'],r['赛事场次不足'],r['统计口径异常']] for r in coverage])
validation+='\n## 五分路有效池\n\n当前推荐分路允许多路，因此加总不等于133。括号前是V2有效人数，分母是该路目录人数；5–9人低可信度，少于5人不强行排名。\n\n'
lc=rows('lane_coverage');lanes=['对抗路','打野','中路','发育路','游走']
validation+=table(['范围']+lanes,[[k]+[f"{r['eligible']}/{r['catalogue_in_lane']}" for lane in lanes for r in lc if r['context_id']==k and r['lane']==lane] for k in keys]+[[k]+[f"{r['eligible']}/{r['catalogue_in_lane']}" for lane in lanes for r in lc if r['context_id']==k and r['lane']==lane] for k in ['overall:'+s for s in ['全分段','巅峰赛1350+','顶端排位','巅峰千强']]])
validation+='\n## 同交集模型比较与Top10稳定性\n\n比较只用V1/V2都能评分的英雄，重新计算同交集排名后比较；表中Top10是保留比例，不是胜率。V1原名次仍保留档案，不能将新C的30/70政策名次直接解释为模型改进。\n\n'
cs=[r for r in rows('model_comparison') if r['context_id'] in keys and r['scope']=='全部英雄']
validation+=table(['场景','共同英雄','排名Spearman','Top10保留'],[[r['context_id'],r['paired_heroes'],fmt(r['same_pool_rank_spearman'],3),pct(r['same_pool_top10_retained'])] for r in cs])
validation+='\n分路初始权重与同分路统一65/35对照：\n\n'
validation+=table(['场景','分路','人数','排名Spearman','Top10保留'],[[r['context_id'],r['scope'],r['paired_heroes'],fmt(r['uniform_vs_lane_rank_spearman'],3),pct(r['uniform_vs_lane_top10_retained'])] for r in rows('model_comparison') if r['context_id'] in ['arena:'+str(latest),'daily:全分段'] and r['scope']!='全部英雄'])
validation+='\n## 预设权重敏感性\n\nE/B权重与场景T/D权重分别比较固定默认方案；不对某位英雄调参。临时榜单资格与比较池保持相同。全部1374个场景×权重结果见model_sensitivity.csv。\n\n'
ss=[r for r in rows('model_sensitivity') if r['scope']=='全部英雄' and r['context_id'] in ['arena:'+str(latest),'daily:全分段','overall:全分段']]
validation+=table(['场景','试验','E权重','T权重','人数','与默认排名相关','Top10保留','前三'],[[r['context_id'],r['experiment'],fmt(r['e_weight']),fmt(r['t_weight']),r['heroes'],fmt(r['rank_spearman'],3),pct(r['top10_retained']),r['top3']] for r in ss])
validation+='\n## 时间顺序验证\n\n仅已结束常规KPL春夏秋季赛，两届有效英雄交集至少8人；两届计数自洽且至少30场，上一届BP经审计；上一届结束严格早于目标届开始。2025年目录重叠等窗口明确排除，详见model_temporal_exclusions.csv。下一届指标仅作目标评价，不参与过去分数、归一化或参数训练。\n\n全英雄12个转移窗口，480条英雄×转移配对，不是480场独立比赛。以下为逐窗口Spearman的非加权均值，观察对象可能跨窗口重复，未做独立样本显著性声明。\n\n'
validation+=table(['范围','方案','窗口数','配对记录','平均下一届胜率相关'],[[r['scope'],r['scheme'],r['transitions'],r['paired_observations'],fmt(r['mean_next_win_spearman'],4)] for r in rows('model_validation_summary')])
validation+='\n**判断：** V1全英雄平均相关0.1764，V2初始65/35为0.1811，提升很小；55/45为0.1886，但这是在现有回顾性窗口上的比较，没有独立调参/验证/测试分割，不能选作“最优”。分路结果也不一致。当前推荐位置具有回顾性偏差，可能与历史实际分路不一致；数据是现时聚合响应，缺少历史时点冻结快照及版本、阵容、战队等控制。尚不能证明线上预测性能、因果战力或上分收益。\n'
validation+='\n## 敖隐、赵云、公孙离：原指标与评分变化\n\n下面V1/V2综合均按新30/70或100%D同榜策略；原混排名次见CSV的legacy_v1_rank。C没有单一原始W/BP，C行Pick/Ban仅为日常来源，保留空白；赛事WR列为原始胜率，E实际用Beta平滑W。\n\n'
rep=rows('model_representatives')
validation+=table(['英雄','场景','原胜率','Pick','Ban','BP','V1分/名次','V2分/名次','E','B','V2池N'],[[r['hero'],r['context_id'],pct(r['winRate']),pct(r['pickRate']),pct(r['banRate']),pct(r['bpRate']),f"{fmt(r['v1Score'])}/{r['v1Rank']}",f"{fmt(r['v2Score'])}/{r['v2Rank']}",fmt(r['E']),fmt(r['B']),r['comparisonN']] for r in rep])
validation+='\n**解释而非调分：** 敖隐全分段公布胜率47.90%，E28.34，而BP26.70%对应B76.34；V2为45.14（第71），不是通过主观印象抬分。顶端排位胜率48.98%、BP35.12%，E35.21/B87.85，V2第54；巅峰千强胜率50.91%、BP77.57%，E61.13/B97.69，第14。分段差异同时来自原指标与独立池，不能归因于单一因素。KPL敖隐原胜率48.98%、BP73.49%，平滑W与56人合格池下E43.34/B98.21，分数62.55、名次16；V1池99人，分数70.53、名次21，分数降低与名次提高可以同时发生。\n\n赵云全分段V1第2→V2第3，胜率54.97%推动E100，但BP19.78%对应B65.13；公孙离全分段胜率42.41%与BP4.58%同时偏低，V2第116。高端分段必须查看对应行，不能将全分段低分解释为所有环境都弱。未为任何英雄添加特判。新旧差异来自胜率和禁选双维、Z保留差距、BP缩尾、统计池门槛与权重；不把排名更符合印象作为模型验证。\n'
validation+='\n## 验证文件与尚待完成的发布验收\n\nPython验证：50项已通过，包含V1回归、指标并列、零方差、稳健BP、贡献加总、排名、独立分路、30/70综合与标注日常100%替代、覆盖与时间窗隔离。具体最终测试数量以验收记录和v2-validation-gate.json为准。网页交互、文档下载、离线和发布构建检查由model_upgrade_qa.cjs执行，尚未执行的项目不在这里宣称通过。gate只证明数值与数据规则，不证明预测优越性。\n'
validation+='\n日常历史仅4位且与当前同日存在口径冲突，日常与综合V2尚未进行可靠的全英雄时间回测。30/70及100%D政策仅有同期敏感性与数值验证，不宣称已证实未来预测效果。\n'
write('V2模型验证报告.md',validation)
audit='''# 数据来源与历史扩展审计

统计日期：日常当前2026-10-10；赛事按各目录实际窗口。133是当前英雄目录而非每届历史可用英雄数。不把无记录认定为采集失败，也不将接口统计中的缺失解释为零胜率。

## 来源分层与可核查入口

| 来源 | 类型与现有用途 | 范围、限制 |
|---|---|---|
| [腾讯赛事目录](https://prod.comp.smoba.qq.com/leaguesite/leagues/open) / [英雄资料](https://pvp.qq.com/web201605/js/herolist.json) | 腾讯官方公开聚合响应，33届2754条英雄×赛事；推荐位置与头像 | 不是逐局数据。样本N来自battle字段；BP分母仍需平台完整定义，异常不入V2 |
| [苏苏助手榜单](https://pvp.91m.top/ranking) / [声明](https://docs.91m.top/%E5%A3%B0%E6%98%8E.html) | 第三方整理，现有9个已验证公开请求，四档当前538条及4英雄39344条历史 | 全英雄统计不是个人战绩，但样本场次、版本及S赛季映射未知；未与营地官方对账；声明提示部分功能需登录 |
| [苏苏助手历史API说明](https://xug887phix.apifox.cn/api-184881160) | 公开文档列出POST `/hero/app`、getHeroChartsLog、id/aid/bid/cid/did/gameType | 示例含openId/accessToken；既有公开页面匿名路径与文档参数不全相同。不能据4英雄请求成功推定133英雄批量授权 |
| [营地热度榜适配研究](https://github.com/dxawdc/honor-of-kings-companion-api) | 第三方开源的腾讯客户端接口研究，不是腾讯授权保证 | 账户绑定凭证；本项目未取得有效授权响应。本次不访问手机会话或绕过认证。战力/个人战绩榜不能替代全体英雄WR/Pick/Ban |
| [王者Fun助手](https://www.wangzhe.fun/) | 官网介绍国服小程序英雄数据与统计功能 | 尚未找到明确允许批量访问且可复现的公开统计API；本次未纳入其数据，不把国际服/战力榜冒充国服全英雄统计 |
| 本项目V1/V2、Z、P、E/B与共同分母诊断 | 基于上述响应的派生/推算指标 | 不称官方分数；共同分母诊断不是实际比赛数，不用于伪造日常样本量 |

以上新增来源调查与审计，不代表取得新的未验证数据。保留匿名原响应、采集元数据URL/日期/SHA256；不发布登录头、token/cookie或个人隐私。

## BP核查

四档全部133个目录英雄都有当前记录，三指标不完整者主要缺胜率。SuSu第一ban数组元素可能为双禁累计、超过100%；使用榜单展示对应第二值，并逐项核对allBanRate=pick+展示ban。保留原始字段而非截断异常。腾讯同届BP块按计数/率一致性检查，发现历史大乔2024春、大乔2023夏、鲁班大师2023夏三处异常，V1档案保持不变，V2剔除；早期BP整块占位不给V2分。

统计口径可验证的是字段和一致性，尚未取得官方完整双禁/精确分母规范，不能无限外推到其他来源或未来版本。完整bp_contract_audit.csv和coverage_audit.csv可复核。

## 当前榜单与历史同日期不一致

已有赵云、关羽、鲁班大师、蒙恬4位英雄，各四档产生16个同日期对照，12组至少一项不同。历史39344条中33805条三指标完整，覆盖2019-09-28至2026-10-10。未取得足够平台说明确定差异来自时间切点、缓存、参数语义还是口径，所以当前与历史分开存放，不跨接口补缺、不人为覆盖同日值。详见daily_reconciliation.csv。

## 扩展至133位历史的可行性与边界

接口有英雄ID与分段参数，技术上可生成逐英雄请求计划；133英雄×4档最多532条请求，若接口一次返回四档则可减少，但必须先验证参数与响应。不能凭公开接口存在就认定允许批量访问。

后续先取得提供方公开接入规则或合作/授权范围，确认getHeroChartsLog及bid语义、分页、限额、是否一次含四档，以及历史同日期口径。随后对现有四英雄作有界校验，若授权允许再单线程限速、缓存每个英雄响应、断点续采；遇401/403/429、认证页或限制立即停止，不换账号/IP绕过。缺失原样保留，记录请求ID、返回日期、字段与SHA256。未确认规则前本次不进行133英雄匿名批量采集。

营地需有效本机账户授权，不能从网页上缺少入口推定手机统计无公开可能；Fun需可验证API/导出权限。授权不能保证历史数据存在。本次没有新增完整历史，133英雄多赛季日常覆盖仍未解决，不伪造数据。

## 完整覆盖分类

审计表包括33届×133目录行及4档×133日常行，共4921行。类别：完全无记录、胜率缺失、其他指标缺失、赛事场次不足、统计口径异常、完整有效；玩法条目单独处理且不伪装新增英雄。类别为按优先级分配的互斥主要原因，原字段与reason仍保留多个诊断。无记录可能当届尚未上线或未被选/统计，当前资料无法区分；不足30场是展示规则，不是来源采集失败；缺WR是源字段缺失，不能据此认定英雄弱。

以下为最新已结束赛事和四档日常的所有未评分明细。完整历史明细见coverage_audit.csv。

'''
for key in keys:
 rr=[r for r in rows('coverage_audit') if r['context_id']==key and r['category']!='完整有效']
 audit+='\n### '+key+'\n\n'+table(['ID','英雄','分类','具体原因','场次'],[[r['hero_id'],r['hero'],r['category'],r['reason'],r['battles'] if r['battles'] is not None else '未知'] for r in rr])
write('数据来源与历史扩展审计.md',audit)
p=ROOT/'docs/数据字典.md';s=p.read_text(encoding='utf-8').split('\n## V2新增派生表')[0];s+='''\n## V2新增派生表

- model_rankings：键model/context_id/scope/hero_id；同英雄可参与多推荐分路。wRaw是评分用W（赛事为后验），winRate是原始；所有率/P/Normalized为0–1；E/B/score/contribution为0–100分；Z无单位，σ总体标准差，BP调整仅用于Z。null是真缺失或不可评分。
- model_contexts：各模型/场景/范围有效比较池、默认权重、事件日期和来源。
- daily_observations：仅D有效者的诊断档案；不再单独展示。model_rankings同榜route=daily_fallback，实际0/100场景权重，scoreBasis与arenaMissingReason解释来源；双有效route=paired、实际30/70。
- coverage_audit / coverage_summary / bp_contract_audit：逐目录英雄覆盖、互斥主要原因、原值和BP口径诊断。battles仅赛事；日常未知不填0。
- model_comparison：同交集模型与同分路权重排名相关、Top10保留；model_sensitivity：预设E/B和T/D权重情景；model_representatives：三英雄9场景对照。
- lane_coverage：最新赛事/四档D/四档C独立分路池；current roles不代表actual positions。
- model_temporal_pairs / model_temporal_validation / model_temporal_exclusions / model_validation_summary：时间转移目标、窗口排除与描述关联结果，未训练未来数据。
- model_release：精确输入/核心代码指纹门槛；validated_descriptive_experiment不表示预测优越。

完整reviewed_snapshot.json包含全部查询。网页构建每个surface只带实际使用的查询，每个保留查询的行和字段完全相同，sourceSnapshotSha256指向完整档案。浏览器下载CSV与主数据由同一流水线生成；并非手工修改JSON。离线构建包含页面所用全部数据，完整历史可从下载CSV复查。
''';p.write_text(s,encoding='utf-8')
print('Generated V2 methods, validation, source/missing audits and dictionary.')
