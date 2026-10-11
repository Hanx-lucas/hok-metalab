# GitHub Pages公开部署

项目发布为公开GitHub仓库中的静态网站。页面不依赖本机4173端口；完成部署后，读者可直接用公开HTTPS链接访问。

## 发布内容

- `docs/index.html`与内容寻址JSON：综合、赛事、日常三维榜单。
- `docs/reports/`：逐届赛事变化、结论与模型验证。
- `docs/downloads/`：计算标准、公开数据CSV、来源清单与PDF。
- Python分析源码、测试、匿名公开原始响应、页面内容源码和参考归属。

网站采用当前构建快照，不在GitHub运行Python或自动抓取数据。公开更新流程为：本机刷新并验证数据 → 完成网页构建 → 更新发布目录 → 提交并推送。

## 技术方式

1. `python scripts/build_web.py`输出完成状态的静态网站与离线包。
2. `python scripts/stage_github_pages.py`按明确清单生成`output/github-pages-repository/`，并检验HTML及JSON快照SHA-256。
3. 在该目录初始化Git并推送到自己的公开仓库。
4. 仓库Settings → Pages → Deploy from a branch → main → `/docs`。`.nojekyll`用于直接发布静态文件。

普通访客不需要安装Python、Node、Codex或登录。网页只读取随发布包提供的JSON快照；第三方源站波动不会直接影响已发布页面。

## 归属与数据口径

赛事数据来自腾讯公开汇总；日常来自苏苏助手公开整理，尚未与营地官方数据对账；当前目录英雄头像和赵云原画版权归腾讯。所有非官方评级及观察日期在网页中标明。营地私人授权、服务日志、原简历以及电脑配置不纳入发布目录。
