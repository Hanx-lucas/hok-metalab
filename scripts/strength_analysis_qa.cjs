// Exercise only the authored HoK application in a fresh browser.
const fs=require('fs'),path=require('path'),os=require('os'),assert=require('assert');
const {chromium}=require(path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const root=path.resolve(__dirname,'..'),out=path.join(root,'output/qa');
const q=JSON.parse(fs.readFileSync(path.join(root,'data/reviewed_snapshot.json'),'utf8')).queries;
const base=(process.env.HOK_QA_BASE_URL||'http://127.0.0.1:4173/').replace(/\/?$/,'/');
(async()=>{const browser=await chromium.launch({channel:'msedge',headless:true});const errors=[],badResponses=[],checks=[];
try {const page=await browser.newPage({viewport:{width:1440,height:1100}});page.setDefaultTimeout(10000);
page.on('pageerror',e=>errors.push(e.message));page.on('response',r=>{if(r.status()>=400&&!r.url().endsWith('favicon.ico'))badResponses.push({url:r.url(),status:r.status()})});
const body=()=>page.locator('body').innerText(),component=(dimension,suffix)=>page.locator(`[data-component-id="strength-${dimension}-analysis-${suffix}"]`);
async function check(label,fn){await fn();checks.push({label,passed:true});console.log('PASS',label)}
async function choose(label,value){await page.getByRole('button',{name:label,exact:true}).click();await page.getByRole('menuitemradio',{name:value,exact:true}).click()}
async function sourcePreview(title,count){await page.getByRole('button',{name:title+' actions',exact:true}).click();await page.getByRole('menuitem',{name:'View data source',exact:true}).click();await page.getByText('Overview',{exact:true}).click();assert((await body()).includes('评分贡献'));await page.getByText('Data preview',{exact:true}).click();assert((await body()).includes(`of ${count} results`));await page.keyboard.press('Escape')}
await page.goto(base+'?view=1&tab=overall',{waitUntil:'networkidle'});
for(const [dimension,label,context] of [['overall','综合强度','overall:全分段'],['arena','赛事强度','arena:'+q.summary.rows[0].latest_completed_league],['daily','日常游戏强度','daily:全分段']]){
await check(dimension+' reviewed waterfall, scatter counts and third chart render',async()=>{
await page.getByRole('tab',{name:label,exact:true}).click();await page.locator('.sb-analysis').scrollIntoViewIfNeeded();await page.waitForTimeout(250);
const region=page.locator('.sb-analysis');assert.equal(await region.locator('.recharts-wrapper').count(),3);
const values=q.strength_analysis_points.rows.filter(r=>r.context_id===context).sort((a,b)=>a.rank-b.rank),focus=values[0];
const waterfall=component(dimension,'contributions');const text=await waterfall.innerText();assert(text.includes(focus.hero));assert(text.includes(focus.score.toFixed(1)+'分'));
assert(text.includes('Beginning')&&text.includes('Ending'));assert.equal(await waterfall.locator('.recharts-label-list .recharts-label').count(),5);
const labels=await waterfall.locator('.recharts-label-list .recharts-label').allTextContents();assert.equal(Number(labels.at(-1)),Number(focus.score.toFixed(1)));
const expected=dimension==='overall'?values.filter(r=>r.arenaScore!=null&&r.dailyScore!=null):values;
const scatter=component(dimension,'relationship');assert.equal(await scatter.locator('.recharts-symbols').count(),expected.length);
await scatter.locator('.recharts-symbols').first().hover();await page.waitForTimeout(200);const tip=await scatter.locator('.recharts-tooltip-wrapper').innerText();assert(tip.includes(expected[0].hero));assert(tip.includes(expected[0].score.toFixed(1)+'分'));
if(dimension==='overall'){assert(tip.includes(expected[0].arenaScore.toFixed(1)));assert(tip.includes(expected[0].dailyScore.toFixed(1)));}
else{assert(tip.includes((100*expected[0].winRate).toFixed(1)+'%'));assert(tip.includes((100*expected[0].banRate).toFixed(1)+'%'));if(dimension==='daily')assert(!tip.includes('战斗场次'))}
if(dimension==='arena')assert.equal(await component(dimension,'history').locator('.recharts-line-curve').count(),3);
else {const heatmap=component(dimension,'segments');assert.equal(await heatmap.locator('[data-heatmap-cell]').count(),40);assert((await heatmap.innerText()).includes('巅峰千强'));}
await page.mouse.move(0,0);await region.screenshot({path:path.join(out,'analysis-'+dimension+'.png')});
});
}
await check('waterfall hero selection preserves daily-only score and scoped source',async()=>{
await page.getByRole('tab',{name:'综合强度',exact:true}).click();await choose('分析英雄','李信');const expected=q.strength_analysis_points.rows.find(r=>r.context_id==='overall:全分段'&&r.hero_id===507);
assert.equal(expected.arenaScore,null);assert.equal(expected.score,expected.dailyScore);const waterfall=component('overall','contributions');assert((await waterfall.innerText()).includes(expected.score.toFixed(1)+'分'));const labels=await waterfall.locator('.recharts-label-list .recharts-label').allTextContents();assert.equal(Number(labels.at(-1)),Number(expected.score.toFixed(1)));await sourcePreview('英雄强度评分的形成过程',3);
});
await check('scene source retains all rated heroes including unpaired entries',async()=>{await sourcePreview('赛事与日常的相对表现对照',q.strength_analysis_points.rows.filter(r=>r.context_id==='overall:全分段').length)});
await check('scatter mark opens the selected hero evidence',async()=>{const scatter=component('overall','relationship'),point=scatter.locator('.recharts-symbols').first();await point.click();await page.getByRole('button',{name:'查看赵云的强度依据',exact:true}).click();const dialog=page.getByRole('dialog');assert((await dialog.innerText()).includes('赵云'));assert((await dialog.innerText()).includes('赛事证据'));assert((await dialog.innerText()).includes('日常证据'));await page.keyboard.press('Escape')});
await check('segment controls update chart population and top hero',async()=>{await choose('日常分段','巅峰千强');const expected=q.strength_analysis_points.rows.filter(r=>r.context_id==='overall:巅峰千强').sort((a,b)=>a.rank-b.rank);assert((await component('overall','contributions').innerText()).includes(expected[0].hero));assert.equal(await component('overall','relationship').locator('.recharts-symbols').count(),expected.filter(r=>r.arenaScore!=null).length);await choose('日常分段','全分段')});
await check('unrated historical events expose an honest empty view',async()=>{await page.getByRole('tab',{name:'赛事强度',exact:true}).click();await choose('赛事','2019KPL春季赛');assert.equal(await page.locator('.sb-analysis .recharts-wrapper').count(),0);assert((await page.locator('.sb-analysis').innerText()).includes('暂无可分析'));await page.getByRole('button',{name:'重置',exact:true}).click()});
await check('mobile charts stay within page and hero controls remain usable',async()=>{await page.setViewportSize({width:390,height:844});for(const [dimension,label] of [['overall','综合强度'],['arena','赛事强度'],['daily','日常游戏强度']]){await page.getByRole('tab',{name:label,exact:true}).click();await page.locator('.sb-analysis').scrollIntoViewIfNeeded();assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));const plot=component(dimension,'relationship').locator('.recharts-wrapper');const bounds=await plot.boundingBox();assert(bounds.width>250&&bounds.width<=390);await page.locator('.sb-analysis').screenshot({path:path.join(out,'analysis-mobile-'+dimension+'.png')});}await choose('分析英雄','伽罗');assert((await component('daily','contributions').innerText()).includes('伽罗'))});
await check('dark mode renders the new charts and accessible values',async()=>{await page.setViewportSize({width:1440,height:1100});await page.emulateMedia({colorScheme:'dark'});await page.locator('.sb-analysis').scrollIntoViewIfNeeded();await page.locator('.sb-analysis').screenshot({path:path.join(out,'analysis-dark.png')});assert.equal(await page.locator('.sb-analysis .recharts-wrapper').count(),3);await page.emulateMedia({colorScheme:'light'})});
await check('three analytical CSV downloads are served',async()=>{for(const name of ['strength_analysis_points','strength_analysis_drivers','strength_analysis_history']){const response=await page.request.get(base+'downloads/'+name+'.csv');assert.equal(response.status(),200);assert((await response.body()).length>100)}});
if(process.env.HOK_QA_FINAL==='1')await check('offline package contains the same new charts',async()=>{const offline=await browser.newPage();offline.on('pageerror',e=>errors.push(e.message));await offline.goto('file:///'+path.join(root,'output/portfolio/index.html').replaceAll('\\','/'));await offline.locator('.sb-analysis').waitFor();assert.equal(await offline.locator('.sb-analysis .recharts-wrapper').count(),3);await offline.close()});
assert.deepEqual(errors,[]);assert.deepEqual(badResponses,[]);fs.writeFileSync(path.join(out,'strength-analysis-results.json'),JSON.stringify({baseUrl:base,checks,runtimeErrors:errors,badResponses},null,2));console.log(JSON.stringify({checks:checks.length,errors,badResponses}));
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
