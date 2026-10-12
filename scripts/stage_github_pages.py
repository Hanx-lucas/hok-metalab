"""Prepare a reviewed, allow-listed GitHub Pages repository; never push automatically."""
from pathlib import Path
import hashlib,json,shutil,re
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/github-pages-repository'
DOCS=['V2模型验证报告.md','数据来源与历史扩展审计.md','强度榜计算标准.md','GitHub公开部署.md','项目说明与面试指南.md','数据字典.md','研究报告.md','替代数据源核验.md','技能与开源参考.md','验收记录.md']
CSV=['model_rankings','model_contexts','daily_observations','coverage_audit','coverage_summary','bp_contract_audit','model_release','model_comparison','model_sensitivity','model_representatives','lane_coverage','model_temporal_validation','model_temporal_pairs','model_temporal_exclusions','model_validation_summary','hero_metrics','coverage','quality_issues','sensitivity','backtest','backtest_exclusions','season_summary','season_leaders','strength_history','daily_current','daily_history','daily_coverage','daily_reconciliation','daily_summary','strength_rankings','strength_contexts','strength_lane_rankings','strength_analysis_points','strength_analysis_history','strength_analysis_drivers']

def copy(source,target):
    target=OUT/target
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source,target)

def app(source,target):
    manifest=json.loads((source/'data-app-build.json').read_text(encoding='utf-8'))
    snapshot=json.loads((source/manifest['snapshot']['path']).read_text(encoding='utf-8'))
    assert snapshot.get('buildStatus')=='complete','Publish only completed app builds'
    for key in ['html','snapshot']:
        entry=manifest[key];filename=entry['path']
        assert Path(filename).name==filename,'Unexpected nonlocal build reference'
        assert hashlib.sha256((source/filename).read_bytes()).hexdigest()==entry['sha256']
        copy(source/filename,Path(target)/filename)
    copy(source/'data-app-build.json',Path(target)/'data-app-build.json')
    # Delete only old generated snapshot files in this specific publication folder.
    for old in (OUT/target).glob('snapshot.*.json'):
        assert old.resolve().is_relative_to(OUT.resolve())
        if old.name!=manifest['snapshot']['path']:old.unlink()

OUT.mkdir(parents=True,exist_ok=True)
app(ROOT/'site/dist','docs')
app(ROOT/'report-app/dist','docs/reports')
(OUT/'docs/.nojekyll').write_text('',encoding='utf-8')
for name in DOCS:copy(ROOT/'docs'/name,Path('docs/downloads')/name)
for name in CSV:copy(ROOT/'data/processed'/f'{name}.csv',Path('docs/downloads')/f'{name}.csv')
for name in ['source_manifest.json','daily_source_manifest.json','summary.json']:
    copy(ROOT/'data/processed'/name,Path('docs/downloads')/name)
copy(ROOT/'output/pdf/研究报告.pdf','docs/downloads/研究报告.pdf')
copy(ROOT/'site/src/content/assets/hero-art/manifest.json','docs/downloads/hero_art_manifest.json')
# Author's analysis code, tests and anonymous public cache support reproducibility.
for folder in ['hoklab','tests']:
    for p in (ROOT/folder).glob('*.py'):copy(p,p.relative_to(ROOT))
for p in (ROOT/'tests/fixtures').glob('*.json'):copy(p,p.relative_to(ROOT))
for folder in ['site','report-app']:
    copy(ROOT/folder/'src/data.json',Path(folder)/'src/data.json')
for name in ['v2-validation-gate.json','model-upgrade-results.json']:
    copy(ROOT/'output/qa'/name,Path('research/validation')/name)
for name in ['run.py','requirements.txt','requirements-lock.txt']:
    copy(ROOT/name,name)
for name in ['validate_v2.py','write_v2_docs.py','model_upgrade_qa.cjs','prepare_daily_sources.py','configure_camp.py','prepare_hero_art.py','stage_github_pages.py','build_web.py','serve_portfolio.ps1','strength_board_qa.cjs','strength_analysis_qa.cjs']:
    copy(ROOT/'scripts'/name,Path('scripts')/name)
for p in (ROOT/'data/raw').glob('*.json'):
    if p.name.startswith(('heroes.','leagues.','league_')):copy(p,p.relative_to(ROOT))
for p in (ROOT/'data/raw/alternative').glob('susu_*.json'):copy(p,p.relative_to(ROOT))
copy(ROOT/'data/reviewed_snapshot.json','data/reviewed_snapshot.json')
for p in (ROOT/'data/processed').glob('*'):
    if p.is_file() and p.suffix in ['.csv','.json','.sqlite'] and not p.name.startswith('camp'):
        copy(p,p.relative_to(ROOT))
for folder in ['site','report-app']:
    for p in (ROOT/folder/'src/content').rglob('*'):
        if p.is_file():copy(p,p.relative_to(ROOT))
    copy(ROOT/folder/'src/theme.css',Path(folder)/'src/theme.css')
# Keep references to third-party design guidance with its original license.
for name in ['frontend_design_skill.txt','frontend_design_license.txt','frontend_skill_repo.json']:
    copy(ROOT/'research'/name,Path('research')/name)
copy(ROOT/'output/qa/strength-board-desktop.png','assets/preview.png')
(OUT/'.gitattributes').write_text('* -text\n',encoding='utf-8')
(OUT/'.gitignore').write_text('.venv/\n.deps/\n__pycache__/\n*.pyc\nprivate/\n.env*\noutput/\n**/.data-app-offline/\nnode_modules/\n*.log\n',encoding='utf-8')
# Publish the current author README, with repository-relative documentation links.
readme=(ROOT/'README.md').read_text(encoding='utf-8')
readme=readme.replace('原课程项目保留在上一级目录。','原课程项目单独留档，本公开仓库保留可复现的分析升级。')
readme=readme.replace('(docs/', '(docs/downloads/')
(OUT/'README.md').write_text(readme,encoding='utf-8')
# Check what will be committed, not the user's unrelated original project folder.
files=[p for p in OUT.rglob('*') if p.is_file() and not any(x in ['.git','__pycache__','.venv','.deps'] for x in p.relative_to(OUT).parts)]
for p in files:
    assert p.stat().st_size<95_000_000,p.name
    assert not any(x.lower() in ['private','.env','camp_headers.json'] for x in p.relative_to(OUT).parts)
    if p.suffix in ['.py','.jsx','.css','.json','.md','.txt','.html','.csv']:
        text=p.read_text(encoding='utf-8-sig')
        patterns=[r'15905'+r'195290',r'241098181@'+r'smail\.nju\.edu\.cn',r'gh[pousr]_[A-Za-z0-9]{20,}',r'github_pat_[A-Za-z0-9_]{40,}']
        assert not any(re.search(pattern,text) for pattern in patterns),f'Private value detected in {p.relative_to(OUT)}'
review={'files':len(files),'bytes':sum(p.stat().st_size for p in files),'destination':'output/github-pages-repository','snapshot_hashes_verified':True,'credential_files_included':False}
(ROOT/'output/github-publication-review.json').write_text(json.dumps(review,indent=2),encoding='utf-8')
print(json.dumps(review))
