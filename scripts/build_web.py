"""Build the canonical Data apps, then package HTTP and portable offline copies."""
from __future__ import annotations
import hashlib
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]

def resolve_tools(node=None, plugin=None):
    bundled = Path.home()/".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe"
    node = node or (str(bundled) if bundled.exists() else shutil.which("node"))
    if not node:
        raise SystemExit("Node.js is required. Pass --node /absolute/path/to/node.")
    if plugin:
        script = Path(plugin)/"scripts/data-app.mjs"
    else:
        codex = Path(os.environ.get("CODEX_HOME", str(Path.home()/".codex")))
        candidates = list((codex/"plugins/cache/openai-curated-remote/data-analytics").glob("*/scripts/data-app.mjs"))
        def version(p):
            return tuple(int(n) for n in p.parent.parent.name.split(".") if n.isdigit())
        if not candidates:
            raise SystemExit("Data Analytics plugin is required for rebuilding. Ready-built offline HTML needs no plugin.")
        script = max(candidates,key=version)
    if not script.exists():
        raise SystemExit(f"Missing official build script: {script}")
    return str(node), str(script)

def sync_snapshots(build_status='complete'):
    snapshot = json.loads((ROOT/"data/reviewed_snapshot.json").read_text(encoding="utf-8"))
    if snapshot["queries"]["summary"]["rows"][0]["prior"] != 20:
        raise SystemExit("The authored report expects prior=20; revise report wording before changing its prior.")
    leaders=snapshot['queries']['summary']['rows'][0]['top_heroes'][:2]
    report_title="V2英雄强度模型，计算依据与历史验证"
    for folder, surface, title in [("site","dashboard","王者荣耀 · MetaLab"),
        ("report-app","report",report_title)]:
        dest = ROOT/folder/"src/data.json"
        existing = json.loads(dest.read_text(encoding="utf-8"))
        # Keep complete rows/fields for every query used by the surface; omit unused archives.
        names = ({'summary','model_release','model_contexts','model_rankings','daily_observations',
                  'coverage_audit','coverage_summary','daily_summary'} if surface == 'dashboard' else
                 {'summary','hero_metrics','coverage','quality_issues','season_summary','season_leaders',
                  'strength_history','backtest','camp','daily_summary','model_validation_summary',
                  'model_representatives','model_comparison','lane_coverage','model_release'})
        reviewed = {**snapshot, "id":existing["id"], "surface":surface, "title":title, "buildStatus":build_status,
                    'queries':{k:v for k,v in snapshot['queries'].items() if k in names},
                    'sourceSnapshotSha256':hashlib.sha256((ROOT/'data/reviewed_snapshot.json').read_bytes()).hexdigest()}
        assert names <= set(reviewed['queries']), 'A required source query is absent'
        if "legacyPresentationTitle" in existing:
            reviewed["legacyPresentationTitle"] = existing["legacyPresentationTitle"]
        if surface == "report":
            reviewed["report"] = {}  # No common observation cutoff inferred from retrieval times.
        dest.write_text(json.dumps(reviewed,ensure_ascii=False,allow_nan=False),encoding="utf-8")

def downloads(destination):
    destination.mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/"site/src/content/assets/hero-art/manifest.json",destination/"hero_art_manifest.json")
    shutil.copy2(ROOT/"data/processed/daily_source_manifest.json",destination/"daily_source_manifest.json")
    for folder, patterns in [(ROOT/"docs",["*.md"]),(ROOT/"data/processed",["*.csv","source_manifest.json","summary.json","hoklab.sqlite"]),(ROOT/"output/pdf",["*.pdf"])]:
        for pattern in patterns:
            for source in folder.glob(pattern):
                shutil.copy2(source,destination/source.name)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node")
    parser.add_argument("--data-plugin", default=os.environ.get("DATA_PLUGIN_ROOT"))
    parser.add_argument('--updating',action='store_true',help='Preview unfinished edits without packaging a final ZIP')
    args=parser.parse_args()
    node, script=resolve_tools(args.node,args.data_plugin)
    # One authored palette and shared seasonal evidence view for both surfaces.
    shutil.copy2(ROOT/'site/src/theme.css',ROOT/'report-app/src/theme.css')
    shutil.copytree(ROOT/'site/src/content/shared',ROOT/'report-app/src/content/shared',dirs_exist_ok=True)
    sync_snapshots('updating' if args.updating else 'complete')
    for folder in ["site","report-app"]:
        project=ROOT/folder
        subprocess.run([node,script,"build","--project-dir",str(project),"--separate-data"],check=True)
        export=project/".data-app-offline/exports/index.html"
        subprocess.run([node,script,"export-offline","--project-dir",str(project),"--output",str(export)],check=True)
    web=ROOT/"site/dist"
    shutil.copy2(ROOT/"site/.data-app-offline/exports/index.html",web/"portable.html")
    shutil.copytree(ROOT/"report-app/dist",web/"reports",dirs_exist_ok=True)
    downloads(web/"downloads")
    if args.updating:
        print(f'Updating preview: {web}')
        return
    portable=ROOT/"output/portfolio"
    (portable/"reports").mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/"site/.data-app-offline/exports/index.html",portable/"index.html")
    shutil.copy2(ROOT/"report-app/.data-app-offline/exports/index.html",portable/"reports/index.html")
    downloads(portable/"downloads")
    shutil.copytree(ROOT/"output/figures",portable/"figures",dirs_exist_ok=True)
    (portable/"README.txt").write_text("HoK MetaLab 便携作品集\n\n三维榜单：综合强度、赛事强度、日常游戏强度。各含Top10、分路Top5、完整搜索总榜与英雄详情，以及评分贡献瀑布图、表现散点图、分段热力图和历届赛事折线图；V2为通过功能验证的试验默认模型，V1保留对照。综合双有效30%T/70%D，缺有效赛事时100%D同榜并明确依据，日常缺失留空。\n双击 index.html 即可离线探索；报告、PDF、CSV与项目说明均在文件夹内。\n数据来自带日期的公开快照；构建时间不代表数据统计日期，不会自动刷新。\n请完整复制文件夹。需要联网公开部署时请使用项目 site/dist 目录。\n已补充苏苏助手公开日常样本（当前四档、四英雄历史），尚未官方对账；营地官方授权仍待核验，原手工记录单独标记。\n",encoding="utf-8")
    archive=ROOT/"output/HoK-MetaLab-作品集.zip"
    with zipfile.ZipFile(archive,"w",compression=zipfile.ZIP_DEFLATED) as z:
        for file in sorted(portable.rglob("*")):
            if file.is_file():
                z.write(file,"HoK-MetaLab/"+file.relative_to(portable).as_posix())
    print(f"HTTP website: {web}\nPortable website: {portable}\nZIP: {archive}")

if __name__=="__main__":main()
