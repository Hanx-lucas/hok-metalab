// Verify only this project's authored local app in a fresh browser session.
const fs=require('fs'),path=require('path'),os=require('os'),assert=require('assert');
const {chromium}=require(path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const root=path.resolve(__dirname,'..'),out=path.join(root,'output/qa');
const q=JSON.parse(fs.readFileSync(path.join(root,'data/reviewed_snapshot.json'),'utf8')).queries;
const contexts=q.strength_contexts.rows,records=q.strength_rankings.rows,lanes=q.strength_lane_rankings.rows;
const latest=String(q.summary.rows[0].latest_completed_league);
const base=(process.env.HOK_QA_BASE_URL||'http://127.0.0.1:4173/').replace(/\/?$/,'/');
let browser;
(async()=>{browser=await chromium.launch({headless:true,channel:'msedge'});const checks=[],errors=[],badResponses=[];try{
 const page=await browser.newPage({viewport:{width:1440,height:1100}});page.setDefaultTimeout(8000);
 page.on('pageerror',e=>errors.push(e.message));page.on('response',r=>{if(r.status()>=400&&!r.url().endsWith('favicon.ico'))badResponses.push({url:r.url(),status:r.status()})});
 const body=()=>page.locator('body').innerText();
 async function record(label,fn){await fn();checks.push({label,passed:true});console.log('PASS',label)}
 async function choose(label,value){await page.getByRole('button',{name:label,exact:true}).click();await page.getByRole('menuitemradio',{name:value,exact:true}).click()}
 async function verifyContext(contextId){
  const c=contexts.find(r=>r.context_id===contextId);assert(c,contextId);
  const ranked=records.filter(r=>r.context_id===contextId&&r.rank!=null).sort((a,b)=>a.rank-b.rank);
  const tiles=page.locator('.sb-hero-tile');assert.equal(await tiles.count(),Math.min(10,ranked.length));
  assert.deepEqual(await tiles.locator('h3').allTextContents(),ranked.slice(0,10).map(r=>r.hero));
  assert.deepEqual(await tiles.locator('.sb-score').allTextContents(),ranked.slice(0,10).map(r=>r.score.toFixed(1)));
  assert((await body()).includes(`${c.scored} 位已评分`));
  const sections=page.locator('.sb-lane');assert.equal(await sections.count(),5);
  for(let i=0;i<5;i++){
   const actual=await sections.nth(i).locator('.sb-lane-name').allTextContents();
   const expected=lanes.filter(r=>r.context_id===contextId&&r.lane===['对抗路','打野','中路','发育路','游走'][i]);
   assert.deepEqual(actual,expected.map(r=>r.hero));assert.deepEqual(await sections.nth(i).locator('.sb-score').allTextContents(),expected.map(r=>r.score.toFixed(1)));
  }
 }
 await page.goto(base+'?view=1&tab=overall',{waitUntil:'networkidle'});
 await record('exactly three dimension tabs and matching default ranking',async()=>{assert.deepEqual(await page.getByRole('tab').allTextContents(),['综合强度','赛事强度','日常游戏强度']);await verifyContext('overall:全分段');assert((await body()).includes('135 条结果'))});
 await record('official hero portraits and banner load without external image services',async()=>{const images=page.locator('.sb-key-art,.sb-top10 .hok-portrait img,.sb-lanes .hok-portrait img');assert.equal(await images.count(),36);await page.locator('.sb-lanes').scrollIntoViewIfNeeded();await page.waitForFunction(()=>[...document.querySelectorAll('.sb-key-art,.sb-top10 .hok-portrait img,.sb-lanes .hok-portrait img')].every(i=>i.complete&&i.naturalWidth>0));const urls=await images.evaluateAll(items=>items.map(i=>i.currentSrc));assert(urls.every(u=>u.startsWith('data:')||u.startsWith(base)), 'Images must be locally packaged');await page.locator('.sb-opening').scrollIntoViewIfNeeded()});
 await record('missing tournament score uses daily 100% with an explicit evidence label',async()=>{const c=contexts.find(r=>r.context_id==='overall:全分段');assert((await body()).includes(`${c.combined_count} 位双场景评分 · ${c.daily_only_count} 位日常替代`));const expected=records.find(r=>r.context_id==='overall:全分段'&&r.hero_id===507);assert.equal(expected.overallBasis,'daily_only');assert.equal(expected.score,expected.dailyScore);await page.getByRole('searchbox').fill('507');const row=page.locator('.strength-board tbody tr').filter({hasText:'李信'}).first();assert((await row.innerText()).includes('日常替代（100%日常强度）'));await row.locator('button').first().click();const text=await page.getByRole('dialog').innerText();assert(text.includes(`${expected.dailyScore.toFixed(1)} × 100% = ${expected.score.toFixed(1)}`));assert(text.includes('日常证据'));assert(!text.includes('赛事证据'));assert(!text.includes('95%区间'));await page.waitForTimeout(350);await page.screenshot({path:path.join(out,'strength-daily-fallback.png')});await page.keyboard.press('Escape');await page.getByRole('searchbox').fill('')});
 await record('composite segment changes top10, all five lanes and full total together',async()=>{await choose('日常分段','巅峰千强');await verifyContext('overall:巅峰千强');await choose('日常分段','全分段')});
 await record('hero search retains the original total rank and opens real component details',async()=>{
  await page.getByRole('searchbox').fill('关羽');assert((await body()).includes('1 条结果'));
  const expected=records.find(r=>r.context_id==='overall:全分段'&&r.hero==='关羽');const row=page.locator('.strength-board tbody tr').filter({hasText:'关羽'}).first();assert((await row.innerText()).includes(expected.score.toFixed(1)));await row.locator('button').first().click();
  const dialog=page.getByRole('dialog');const text=await dialog.innerText();assert(text.includes(`总榜第 ${expected.rank} 名`));assert(text.includes('日常证据'));assert(text.includes('赛事证据'));assert(text.includes('分数贡献'));assert(text.includes('95%区间'));await page.waitForTimeout(350);await page.screenshot({path:path.join(out,'strength-hero-detail.png')});await page.keyboard.press('Escape');
 });
 await record('empty search and source-filtered hero-ID search',async()=>{
  await page.getByRole('searchbox').fill('不存在XYZ');assert((await body()).includes('0 条结果'));
  await page.getByRole('searchbox').fill('107');assert((await body()).includes('1 条结果'));assert((await page.locator('.strength-board tbody').innerText()).includes('赵云'));
  await page.getByRole('button',{name:'全部英雄总榜 actions',exact:true}).click();await page.getByRole('menuitem',{name:'View data source',exact:true}).click();await page.getByText('Data preview',{exact:true}).click();assert(/of 1 results/.test(await body()));await page.keyboard.press('Escape');
 });
 await record('Li Xin variants searchable without duplicated or fabricated scores',async()=>{await page.getByRole('searchbox').fill('李信');assert((await body()).includes('3 条结果'));const text=await page.locator('.strength-board tbody').innerText();assert(text.includes('光信_统御')&&text.includes('暗信_狂暴'));assert(text.includes('玩法条目，不参与综合排名'));await page.getByRole('searchbox').fill('')});
 await record('full total has all entries and lane filter leaves original rankings untouched',async()=>{
  assert(/of 135 results/.test(await body()));await choose('总榜分路','游走');const expected=records.filter(r=>r.context_id==='overall:全分段'&&r.roles.split('/').includes('游走'));assert((await body()).includes(`${expected.length} 条结果`));await choose('总榜分路','全部分路');
 });
 await record('Top10 source panel retains entire actual scoped population and formulas',async()=>{
  await page.getByRole('button',{name:'总榜 Top 10 actions',exact:true}).click();await page.getByRole('menuitem',{name:'View data source',exact:true}).click();await page.getByText('Overview',{exact:true}).click();await page.getByText(/C=0.50×T/).last().waitFor({state:'visible'});assert((await body()).includes('0.50×T'));await page.getByText('Data preview',{exact:true}).click();assert(/of 135 results/.test(await body()));await page.keyboard.press('Escape');
 });
 await record('method disclosure exposes all three definitions without overwhelming the landing',async()=>{const details=page.locator('.sb-method');assert.equal(await details.getAttribute('open'),null);await details.locator('summary').click();const t=await details.innerText();assert(t.includes('赛事强度 T')&&t.includes('日常强度 D')&&t.includes('综合强度 C')&&t.includes('50% × T + 50% × D'));await details.locator('summary').click()});
 await record('tournament page has identical top10 and five lane evidence',async()=>{await page.getByRole('tab',{name:'赛事强度',exact:true}).click();await verifyContext('arena:'+latest);assert(/of 133 results/.test(await body()));await page.screenshot({path:path.join(out,'strength-arena-desktop.png'),fullPage:true})});
 await record('historical event selection and missing BP stay honest',async()=>{await choose('赛事','2026年KPL春季赛');await verifyContext('arena:20260001');await choose('赛事','2019KPL春季赛');await verifyContext('arena:20190001');assert((await body()).includes('暂不能生成强度排名'));assert(/of 133 results/.test(await body()));await page.getByRole('button',{name:'重置',exact:true}).click();await verifyContext('arena:'+latest)});
 await record('ongoing event explicitly identified',async()=>{const c=contexts.find(r=>r.dimension==='arena'&&r.event_status==='进行中');await choose('赛事',c.event+' · 进行中');await verifyContext(c.context_id);assert((await page.locator('.sb-note').innerText()).includes('进行中'));await page.getByRole('button',{name:'重置',exact:true}).click()});
 await record('all four daily populations drive consistent score rankings',async()=>{
  await page.getByRole('tab',{name:'日常游戏强度',exact:true}).click();for(const segment of ['全分段','巅峰赛1350+','顶端排位','巅峰千强']){await choose('日常分段',segment);await verifyContext('daily:'+segment)}await choose('日常分段','全分段');await page.screenshot({path:path.join(out,'strength-daily-desktop.png'),fullPage:true});
  await page.getByRole('searchbox').fill('蒙恬');assert((await body()).includes('1 条结果'));const r=page.locator('.strength-board tbody tr').filter({hasText:'蒙恬'}).first();assert((await r.innerText()).includes('当前分段有指标缺失'));await r.locator('button').first().click();const t=await page.getByRole('dialog').innerText();assert(t.includes('未评分'));assert(!t.includes('95%区间'));assert(t.includes('来源未提供样本场次'));await page.keyboard.press('Escape');await page.getByRole('searchbox').fill('');
 });
 await record('desktop and mobile layouts contain all page content including wide total tables',async()=>{
  await page.getByRole('tab',{name:'综合强度',exact:true}).click();await page.getByRole('button',{name:'重置',exact:true}).click();await page.screenshot({path:path.join(out,'strength-board-desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});for(const [label,contextId] of [['综合强度','overall:全分段'],['赛事强度','arena:'+latest],['日常游戏强度','daily:全分段']]){await page.getByRole('tab',{name:label,exact:true}).click();await verifyContext(contextId);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:path.join(out,`strength-mobile-${contextId.split(':')[0]}.png`),fullPage:true})}
 });
 await record('dark system theme stays readable without hardcoded light surfaces',async()=>{await page.setViewportSize({width:1440,height:1100});await page.emulateMedia({colorScheme:'dark'});await page.waitForTimeout(450);const color=await page.locator('.sb-hero-tile').first().evaluate(e=>({bg:getComputedStyle(e).backgroundColor,text:getComputedStyle(e).color}));assert.notEqual(color.bg,'rgb(255, 255, 255)');assert.notEqual(color.text,'rgb(23, 53, 84)');await page.screenshot({path:path.join(out,'strength-board-dark.png'),fullPage:true});await page.emulateMedia({colorScheme:'light'})});
 await record('detailed tournament report remains available with rendered figures and conclusions',async()=>{await page.goto(base+'reports/index.html',{waitUntil:'networkidle'});const t=await body();assert(t.includes('核心结论')&&t.includes('狂铁、沈梦溪、戈娅')&&t.includes('4.83')&&t.includes('4.95'));assert.equal(await page.locator('.recharts-wrapper').count(),5)});
 await record('new downloadable calculations and existing report links are healthy',async()=>{for(const name of ['strength_rankings.csv','强度榜计算标准.md','研究报告.pdf']){const r=await page.request.get(base+'downloads/'+encodeURIComponent(name));assert.equal(r.status(),200);assert((await r.body()).length>100)}});
 await record('legacy arena and rank URLs resolve into the requested three views',async()=>{for(const tab of ['arena','rank','timeline']){await page.goto(base+'?view=1&tab='+tab,{waitUntil:'networkidle'});assert.equal(await page.getByRole('tab').count(),3);const expected=tab==='rank'?'日常游戏强度':tab==='arena'?'赛事强度':'综合强度';assert.equal((await page.getByRole('tab',{selected:true}).innerText()).trim(),expected)}});
 if(process.env.HOK_QA_FINAL==='1'){
  await record('final build status is complete',async()=>{assert(!(await body()).includes('Updating dashboard'));assert(!(await body()).includes('Creating dashboard'))});
  await record('portable offline artifact loads and all-hero search works',async()=>{const offline=await browser.newPage();offline.on('pageerror',e=>errors.push(e.message));await offline.goto('file:///'+path.join(root,'output/portfolio/index.html').replaceAll('\\','/'),{waitUntil:'load'});await offline.locator('.sb-hero-tile').first().waitFor();assert.equal(await offline.getByRole('tab').count(),3);await offline.getByRole('searchbox').fill('赵云');assert((await offline.locator('body').innerText()).includes('1 条结果'));await offline.close()});
 }
 assert.deepEqual(errors,[]);assert.deepEqual(badResponses,[]);const result={checks,runtimeErrors:errors,badResponses,finalPackage:process.env.HOK_QA_FINAL==='1'};fs.writeFileSync(path.join(out,'strength-board-results.json'),JSON.stringify(result,null,2));console.log(JSON.stringify({checks:checks.length,errors,badResponses}));
 }finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
