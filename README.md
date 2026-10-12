# HoK MetaLab · 王者荣耀英雄强度分析

[公开作品集](https://hanx-lucas.github.io/hok-metalab/) · [GitHub源码](https://github.com/Hanx-lucas/hok-metalab) · [网页报告](https://hanx-lucas.github.io/hok-metalab/reports/index.html)

作者：Lucas。沿用原Python数据管线与React游戏主题的升级项目。新版本在`upgrade/v2-strength-audit`独立分支，合并前线上main保持原发布。

## 评分与交互

- 保留V1原分位T/D与原始派生档案；新增V2试验模型，通过精确输入/代码指纹下的功能验证后默认启用。
- V2实战E（胜率）与BP优先级B（审计后的Pick+Ban）分别采用50%平均并列秩分位＋50%Z-score映射。BP仅对Z使用本池5/95%缩尾；总榜65%E/35%B，分路独立统计池与65/70/70/60/60%的试验E权重，不跨路排序。
- KPL先筛至少30场、计数与BP有效，再计算V2统计池；继续Beta(10,10)。日常用公布原始胜率，没有样本量就不制造贝叶斯平滑或区间。
- 按最新展示设定：双场景综合C=30%T+70%D；缺有效赛事评分时用100%D，放入同一综合榜并标注“仅日常参考”及赛事未评分原因。T缺失保留null，不补零，不把单场景条目称为双场景估计。日期/环境不同，不代表同版本真实实力。
- 三个入口、总榜Top10、五分路Top5、完整英雄搜索及头像保留；新增V1/V2切换、分路/日常分段切换、E/B权重调节、四象限、贡献瀑布和P/Z/N/统计池计算明细。图表与排名共用处理管线的model_rankings。

[完整计算标准](docs/downloads/强度榜计算标准.md) · [V2模型验证](docs/downloads/V2模型验证报告.md) · [来源与缺失明细](docs/downloads/数据来源与历史扩展审计.md) · [技术与面试指南](docs/downloads/项目说明与面试指南.md)

## 数据与验证边界

腾讯官方公开赛事2019–2026年33届、2754条英雄×赛事观察，32届已结束、1届进行中。当前官方目录133名英雄；最新已结束KPL为56名至少30场、43名不足、34名无统计记录。

苏苏助手为第三方公开整理，不冒称腾讯官方：当前四档538条（含李信玩法条目）；133目录英雄完整覆盖120/128/123/108，缺胜率13/5/10/25，均有记录。历史仅赵云、关羽、鲁班大师、蒙恬4英雄39344条，33805条三项完整；16组当前与历史同日对照有12组不一致，保持分开，不跨接口补缺。完整133英雄日常历史、官方对账与游戏S赛季映射未取得。

新增覆盖审计4921行，区分完全无记录、胜率缺失、其他缺失、场次不足和口径异常。营地需要本机有效授权；SuSu历史文档包含认证参数，批量规则未明确；Fun尚无可复现且接入规则明确的公共API。本次没有扩大133英雄匿名批量抓取，没有绕过认证、个人战绩或国际服替代数据。

跨届时间验证：上一届结束严格早于下一届开始，排除重叠窗口；12个转移窗口、480条全英雄配对。V1平均下一届胜率Spearman约0.176，V2约0.181，差异很小；不能证明预测优势、因果战力、最优权重或上分收益。五分路当前官方推荐位置不代表历史实际比赛位置。

## 实现与复现

Python、Pandas、NumPy、SciPy、scikit-learn、SQLite、Matplotlib、ReportLab；React/Recharts与Codex Data Analytics公共组件。Pages托管已构建静态HTML/内容寻址JSON，无服务器、无登录。公共运行时来自外部框架，不冒称本项目自研。

```powershell
python -m venv .venv
# 激活环境后
python -m pip install -r requirements-lock.txt
python run.py --offline
python scripts/validate_v2.py
python scripts/prepare_daily_sources.py
python scripts/write_v2_docs.py
python scripts/build_web.py
# 从项目根目录启动，避免Windows锁住dist
python -m http.server 4175 --bind 127.0.0.1 --directory site/dist
# 安装Playwright与Edge后，在另一终端设置预览地址及HOK_QA_FINAL=1
node scripts/model_upgrade_qa.cjs
python scripts/stage_github_pages.py
```

源码的网页重建需要Data Analytics官方构建工具，仓库不复制受保护运行时源文件。已构建`docs/`可直接托管；本地`site/dist`用于HTTP预览，`output/portfolio/index.html`可离线打开，完整便携包由build_web生成。

原始匿名响应与URL/日期/SHA256在data/raw；CSV/JSON/SQLite在data/processed，完整reviewed_snapshot包含所有查询。各网页只打包自身使用的查询，选中查询保留全部行/字段，sourceSnapshotSha256关联完整档案。旧UI QA脚本保留历史，新的交互检查使用model_upgrade_qa。Python基准固定当前响应，刷新真实数据后应审阅并更新覆盖及回归夹具，不能默默忽略回归失败。

`run.py --refresh`刷新腾讯；`prepare_daily_sources.py --refresh`仅刷新已验证的9个日常请求、2秒间隔、遇认证/访问限制停止。默认离线重放缓存，不使用或公开token/cookie。原课程手工Excel单独留档，不参与新版评分；V1历史PDF明确标记，网页报告另有V2验证附篇。

## 发布与归属

main的/docs为现有GitHub Pages目录。新分支完成数据、模型、文档和网页验收后才可合并发布；不能仅手改显示JSON或上传HTML而遗漏snapshot及data-app-build.json。网站展示构建快照，不自动刷新。最终验收与限制见[验收记录](docs/downloads/验收记录.md)。

英雄头像与赵云原画版权归腾讯《王者荣耀》，用于非商业作品集，来源与hash保留美术清单。日常来源[苏苏助手](https://pvp.91m.top/ranking)，声明与历史API限制见来源审计。前端设计参考Anthropic frontend-design，文本与许可证保留research；各依赖归其作者，见[技能与开源参考](docs/downloads/技能与开源参考.md)。
