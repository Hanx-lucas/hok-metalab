// Project-owned local/review builds only; fresh isolated Edge context, no user session.
const fs=require('fs'),path=require('path'),os=require('os'),assert=require('assert');
const {chromium}=require(path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const root=path.resolve(__dirname,'..'),out=path.join(root,'output/qa');
const q=JSON.parse(fs.readFileSync(path.join(root,'data/reviewed_snapshot.json'),'utf8')).queries;
const base=(process.env.HOK_QA_BASE_URL||'http://127.0.0.1:4175/').replace(/\/?$/,'/');
const lanes=['对抗路','打野','中路','发育路','游走'],segments=['全分段','巅峰赛1350+','顶端排位','巅峰千强'];
const latest=String(q.summary.rows[0].latest_completed_league);
const records=q.model_rankings.rows;let page;const checks=[],errors=[],badResponses=[];
const get=(model,id,scope='全部英雄')=>records.filter(r=>r.model===model&&r.context_id===id&&r.scope===scope);
const rated=rows=>rows.filter(r=>r.score!=null).sort((a,b)=>b.score-a.score||a.hero_id-b.hero_id);
const component=id=>page.locator(`[data-component-id="${id}"]`);
async function check(label,fn){await fn();checks.push({label,passed:true});console.log('PASS',label)}
async function choose(label,value){await page.getByRole('button',{name:label,exact:true}).click();await page.getByRole('menuitemradio',{name:value,exact:true}).click()}
async function verify(model,id){
 const expected=rated(get(model,id));const tiles=page.locator('.sb-hero-tile');
 assert.deepEqual(await tiles.locator('h3').allTextContents(),expected.slice(0,10).map(r=>r.hero));
 assert.deepEqual(await tiles.locator('.sb-score').allTextContents(),expected.slice(0,10).map(r=>r.score.toFixed(1)));
 const sections=page.locator('.sb-lane');assert.equal(await sections.count(),5);
 for(let i=0;i<5;i++)assert.deepEqual(await sections.nth(i).locator('.sb-lane-name').allTextContents(),rated(get(model,id,lanes[i])).slice(0,5).map(r=>r.hero));
 assert.equal(await component(`model-${model}-${id.split(':')[0]}-全部英雄-quadrants`).locator('.recharts-symbols').count(),expected.length);
}
(async()=>{const browser=await chromium.launch({headless:true,channel:'msedge'});try{
 page=await browser.newPage({viewport:{width:1440,height:1100}});page.setDefaultTimeout(15000);
 page.on('pageerror',e=>errors.push(e.message));page.on('response',r=>{if(r.status()>=400&&!r.url().endsWith('favicon.ico'))badResponses.push({url:r.url(),status:r.status()})});
 const start=Date.now();await page.goto(base+'?view=1&tab=overall');await page.locator('.sb-hero-tile').first().waitFor({timeout:30000});const firstReadyMs=Date.now()-start;
 await check('V2 gated default; 30/70 and labeled daily-only fallback share composite board',async()=>{assert.equal(q.model_release.rows[0].default_model,'V2');await verify('V2','overall:全分段');assert((await component('strength-overall-scope').innerText()).includes('120'));const r=rated(get('V2','overall:全分段')).find(r=>r.hero_id===507);assert(r);assert.equal(r.score,r.dailyScore);assert.equal(r.arenaScore,null);assert.equal(r.scoreBasis,'仅日常参考');assert((await page.locator('.sb-note').first().innerText()).includes('69 位仅日常参考'));});
 for(const model of ['V2','V1']){
 await choose('评分模型',model==='V2'?'V2 · 分位＋Z（试验）':'V1 · 原分位对照');
 for(const s of segments){await choose('日常分段',s);await check(`${model} composite ${s}: Top10 / independent lanes / same-source scatter`,()=>verify(model,'overall:'+s));}
 await page.getByRole('tab',{name:'日常游戏强度',exact:true}).click();
 for(const s of segments){await choose('日常分段',s);await check(`${model} daily ${s}: Top10 / lane Top5 / valid scatter`,()=>verify(model,'daily:'+s));}
 await page.getByRole('tab',{name:'赛事强度',exact:true}).click();await page.getByRole('button',{name:'重置',exact:true}).click();
 await check(`${model} latest KPL: sample gate / Top10 / lanes`,()=>verify(model,'arena:'+latest));
 await page.getByRole('tab',{name:'综合强度',exact:true}).click();
 }
 await choose('评分模型','V2 · 分位＋Z（试验）');await page.getByRole('button',{name:'重置',exact:true}).click();
 for(const l of lanes){await choose('排行榜',l+'强度榜');await check(`V2 ${l} board uses its own comparison pool`,async()=>{const r=rated(get('V2','overall:全分段',l))[0];const c=component('strength-overall-all');assert((await c.innerText()).includes(r.score.toFixed(1)));assert((await c.innerText()).includes(l+'独立强度榜'));assert.equal(await component(`model-V2-overall-${l}-quadrants`).locator('.recharts-symbols').count(),rated(get('V2','overall:全分段',l)).length);});}
 await choose('排行榜','全英雄综合总榜');
 await check('weight slider reorders full precision; no null resurrection; reset matches archive',async()=>{await page.getByRole('slider').focus();await page.keyboard.press('End');await page.locator('.sb-model-context').filter({hasText:'临时权重情景'}).waitFor();const expected=get('V2','overall:全分段').filter(r=>r.score!=null).sort((a,b)=>(.85*b.E+.15*b.B)-(.85*a.E+.15*a.B)||a.hero_id-b.hero_id);assert.deepEqual(await page.locator('.sb-hero-tile h3').allTextContents(),expected.slice(0,10).map(r=>r.hero));assert.deepEqual(await page.locator('.sb-hero-tile .sb-score').allTextContents(),expected.slice(0,10).map(r=>(.85*r.E+.15*r.B).toFixed(1)));await page.getByRole('button',{name:'恢复默认权重',exact:true}).click();await verify('V2','overall:全分段');});
 await page.getByRole('tab',{name:'日常游戏强度',exact:true}).click();
 for(const s of segments){await choose('日常分段',s);for(const id of [519,107,199]){
 const r=get('V2','daily:'+s).find(r=>r.hero_id===id);await check(`${s} ${r.hero}: original rates, P/Z/N, contributions and pool are inspectable`,async()=>{await page.getByRole('searchbox').fill(r.hero);await page.getByRole('button',{name:`查看${r.hero}的强度详情`,exact:true}).click();const d=page.getByRole('dialog'),t=await d.innerText();assert(t.includes((100*r.dailyWinRate).toFixed(2)+'%'));assert(t.includes(r.score.toFixed(1)+' 分'));assert(t.includes(r.wZ.toFixed(4)));assert(t.includes(r.bpZ.toFixed(4)));assert(t.includes(r.comparisonN+' 名'));assert(t.includes('来源没有样本量'));await page.keyboard.press('Escape');await page.getByRole('searchbox').fill('');});
 }}
 await choose('日常分段','全分段');await page.getByRole('searchbox').fill('敖隐');
 await check('source inspector honors searched one-row source',async()=>{await page.getByRole('button',{name:'全部英雄总榜 actions',exact:true}).click();await page.getByRole('menuitem',{name:'View data source',exact:true}).click();await page.getByText('Data preview',{exact:true}).click();assert((await page.locator('body').innerText()).includes('of 1 results'));await page.keyboard.press('Escape');});
 await page.getByRole('searchbox').fill('');
 await check('coverage category exposes missing WR without zero; all 133 source records accounted',async()=>{await page.getByText('数据覆盖与未评分原因审计',{exact:true}).click();await choose('缺失分类','胜率缺失');const c=component('strength-daily-audit');assert((await c.innerText()).includes('缺胜率 13'));assert((await c.innerText()).includes('of 13 results'));await page.getByText('数据覆盖与未评分原因审计',{exact:true}).click();});
 await check('waterfall endpoint equals scored hero and four quadrants classify index 50',async()=>{const f=rated(get('V2','daily:全分段'))[0],c=component('model-V2-daily-全部英雄-contributions');assert((await c.innerText()).includes(f.score.toFixed(1)+' 分'));const labels=await c.locator('.recharts-label-list .recharts-label').allTextContents();assert.equal(Number(labels.at(-1)),Number(f.score.toFixed(1)));assert.equal(await page.locator('.sb-quadrant-counts span').count(),4);});
 await page.getByRole('tab',{name:'赛事强度',exact:true}).click();await choose('赛事','2019KPL春季赛');
 await check('BP-missing old event is honest empty V2, not WR-only fabricated score',async()=>{assert.equal(await page.locator('.sb-hero-tile').count(),0);assert.equal(await page.locator('.sb-analysis .recharts-wrapper').count(),0);assert((await page.locator('.sb-analysis').innerText()).includes('不足'));});
 await page.getByRole('button',{name:'重置',exact:true}).click();
 await check('KPL hero evidence uses Beta W and raw W separately; no low-sample pool',async()=>{await page.getByRole('searchbox').fill('敖隐');await page.getByRole('button',{name:'查看敖隐的强度详情',exact:true}).click();const t=await page.getByRole('dialog').innerText(),r=get('V2','arena:'+latest).find(r=>r.hero_id===519);assert(t.includes('Beta(10,10)平滑W'));assert(t.includes(r.wZ.toFixed(4)));assert(t.includes('56 名'));assert(t.includes('95%区间'));await page.keyboard.press('Escape');await page.getByRole('searchbox').fill('');});
 await page.getByRole('tab',{name:'综合强度',exact:true}).click();
 await check('daily-only LiXin shares composite board but shows 100%D and missing T reason',async()=>{await page.getByRole('searchbox').fill('李信');await page.getByRole('button',{name:'查看李信的强度详情',exact:true}).click();const t=await page.getByRole('dialog').innerText();assert(t.includes('此条不是双场景综合估计'));assert(t.includes('100% × D'));assert(t.includes('不补赛事零分'));await page.keyboard.press('Escape');await page.getByRole('searchbox').fill('');});
 for(const width of [390,320]){await page.setViewportSize({width,height:844});for(const [dim,label] of [['overall','综合强度'],['arena','赛事强度'],['daily','日常游戏强度']]){await page.getByRole('tab',{name:label,exact:true}).click();await page.locator('.sb-analysis').scrollIntoViewIfNeeded();await check(`mobile ${width}px ${dim}: page fits; three charts and slider usable`,async()=>{assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert.equal(await page.locator('.sb-analysis .recharts-wrapper').count(),3);assert.equal(await page.getByRole('slider').count(),1);});if(width===390)await page.locator('.sb-analysis').screenshot({path:path.join(out,'v2-mobile-'+dim+'.png')});}}
 await page.setViewportSize({width:1440,height:1100});await page.getByRole('tab',{name:'综合强度',exact:true}).click();await page.locator('.sb-hero-tile').first().scrollIntoViewIfNeeded();
 await check('hero artwork and portraits load from reviewed local assets',async()=>{const images=page.locator('.sb-top10 img');assert.equal(await images.count(),10);for(const img of await images.all())assert(await img.evaluate(el=>el.complete&&el.naturalWidth>0));});
 await page.screenshot({path:path.join(out,'strength-board-desktop.png'),fullPage:true});await page.emulateMedia({colorScheme:'dark'});await page.locator('.sb-analysis').scrollIntoViewIfNeeded();await page.locator('.sb-analysis').screenshot({path:path.join(out,'v2-dark-analysis.png')});await page.emulateMedia({colorScheme:'light'});
 await check('V2 documentation and all key evidence CSV downloads are served',async()=>{for(const name of ['model_rankings.csv','coverage_audit.csv','model_temporal_validation.csv','model_sensitivity.csv','V2模型验证报告.md','数据来源与历史扩展审计.md','强度榜计算标准.md']){const response=await page.request.get(base+'downloads/'+encodeURIComponent(name));assert.equal(response.status(),200,name);assert((await response.body()).length>100);}});
 await page.goto(base+'reports/index.html?view=1');await page.locator('.hok-research').waitFor();
 await check('report distinguishes V2 verification from archived V1/PDF findings',async()=>{const t=await page.locator('.hok-research').innerText();assert(t.includes('V2：可核对的描述性试验模型'));assert(t.includes('以下为保留的V1历史研究'));assert(t.includes('V1历史研究PDF'));assert(t.includes('0.181'));});await page.screenshot({path:path.join(out,'v2-report-desktop.png'),fullPage:true});
 if(process.env.HOK_QA_FINAL==='1')await check('portable offline build renders same V2 default and three charts',async()=>{const p=await browser.newPage();p.on('pageerror',e=>errors.push(e.message));await p.goto('file:///'+path.join(root,'output/portfolio/index.html').replaceAll('\\','/'));await p.locator('.sb-hero-tile').first().waitFor();assert.deepEqual(await p.locator('.sb-hero-tile h3').allTextContents(),rated(get('V2','overall:全分段')).slice(0,10).map(r=>r.hero));assert.equal(await p.locator('.sb-analysis .recharts-wrapper').count(),3);await p.close();});
 assert.deepEqual(errors,[]);assert.deepEqual(badResponses,[]);
 fs.writeFileSync(path.join(out,'model-upgrade-results.json'),JSON.stringify({baseUrl:base,checks,runtimeErrors:errors,badResponses,firstReadyMs,totalElapsedMs:Date.now()-start,finalPackage:process.env.HOK_QA_FINAL==='1'},null,2));console.log(JSON.stringify({checks:checks.length,errors,badResponses}));
 }finally{await browser.close()}})().catch(e=>{fs.writeFileSync(path.join(out,'model-upgrade-failure.json'),JSON.stringify({checks,errors,badResponses,failure:String(e.stack)},null,2));console.error(e);process.exitCode=1});
