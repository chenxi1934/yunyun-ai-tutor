/* 阶段05 React控制流回归：显式合成HTTP夹具；不冒充真实模型或代码验证。 */
const {chromium, webkit} = require(process.env.YUNYUN_PLAYWRIGHT_MODULE || 'playwright');
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const root = path.resolve('frontend/dist');
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const deferred = () => { let resolve; const promise = new Promise(r => {resolve = r}); return {promise, resolve}; };
const output = {status:'FAIL', evidence:'真实React及浏览器；HTTP后端为控制流夹具，未验证真实模型/Runner', cases:[]};
let snapshots, gates = new Map(), uploads = [], recoveryFixture;
function reset() {
  snapshots = Object.fromEntries(['A','B'].map(id => {
    const lesson = {lesson_id:'lesson-'+id,revision:1,content_hash:'fixture',code_status:'NOT_TESTED',candidate_ready:false,delivery_ready:false,profile_stale:false,curriculum_risks:[],
      plan:{stage:'初中',topic:'循环结构',duration_minutes:45,prerequisites:[],goals:[{id:'goal-'+id,title:'教学目标-'+id,criterion:'仅供界面控制流测试'}],segments:[],examples:[],exercises:[],misconceptions:[]},
      items:{['goal-'+id]:{review_status:'PENDING'}},profile:{facts:[],unknowns:[]},strategies:[]};
    return [id, {session:{id,workspace_id:'w'+id,revision:0,mock:true,created_at:'2026-10-30T00:00:00Z',context:{stage:'初中',grade:'初二'+id,topic:'会话'+id}},
      messages:[{role:'user',content:'会话原有消息-'+id}],runs:[{id:'run-'+id,status:'COMPLETED',steps:1,tool_count:0,error:null}],drafts:[],verification_reports:[],
      approvals:[{id:'approval-'+id,draft_id:null,status:'PENDING',entries:[{path:id.toLowerCase()+'.md',operation:'write',base_hash:'old',content_hash:'new',diff:'审批专属差异-'+id}]}],
      event_cursor:id==='A'?100:2,lessons:[lesson],commits:[],profiles:[],workspace_name:'工作区-'+id,usage:[]}];
  }));
  gates = new Map();uploads = [];recoveryFixture=undefined;
}
function gate(url) {
  const started = deferred(), released = deferred();
  const value = {started:started.promise, release:released.resolve, wait:released.promise, notify:started.resolve};
  gates.set(url, value);return value;
}
function json(res, value, status=200) {res.writeHead(status, {'Content-Type':'application/json'});res.end(JSON.stringify(value));}
const server = http.createServer(async (req,res) => {
  try {
    const url = new URL(req.url,'http://127.0.0.1'), p = url.pathname;
    if (!p.startsWith('/api/')) {
      const file = path.resolve(root, '.'+(p==='/'?'/index.html':p));
      if (!file.startsWith(root+path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) return json(res,{error:{message:'NOT_FOUND'}},404);
      res.writeHead(200,{'Content-Type':({'.js':'application/javascript','.css':'text/css','.html':'text/html'})[path.extname(file)]||'application/octet-stream'});
      fs.createReadStream(file).pipe(res);return;
    }
    const chunks=[];for await(const chunk of req) chunks.push(chunk);const raw=Buffer.concat(chunks);
    if(p==='/api/runtime') return json(res,{mode:'web',mock:true,provider:'mock',model:'TEST_MOCK',runner:'UNAVAILABLE',workspace_name:'界面回归夹具'});
    if(p==='/api/client') return json(res,{});
    if(p==='/api/sessions') return json(res,{sessions:Object.values(snapshots).map(s=>s.session)});
    const match = p.match(/^\/api\/sessions\/([AB])$/);
    if(match) return json(res,snapshots[match[1]]);
    const event = p.match(/^\/api\/sessions\/([AB])\/events$/);
    if(event) {res.writeHead(200,{'Content-Type':'text/event-stream'});res.write(': test fixture\n\n');return;}
    const file = p.match(/^\/api\/workspaces\/w([AB])\/(files|file)$/);
    if(file) {
      const id=file[1],name=id.toLowerCase()+'.md';
      if(file[2]==='files') return json(res,{files:[{path:name,size:10}]});
      const value={path:name,content:'真实界面预览夹具-'+id,hash:hash('fixture-'+id)};
      const g=gates.get(p);if(g){g.notify();await g.wait;gates.delete(p);}return json(res,value);
    }
    if(p==='/api/sessions/B/commits/interrupted-B/recovery' && req.method==='GET') return json(res,{recovery:recoveryFixture});
    const sid=(p.match(/\/sessions\/([AB])\//)||p.match(/\/approvals\/approval-([AB])\//))?.[1];
    if(sid && req.method==='POST') {
      const g=gates.get(p);if(g){g.notify();await g.wait;gates.delete(p);}
      if(p.includes('/class-profiles')) {
        const limit=p.endsWith('/upload')?1048576:1052672;
        if(raw.length>limit)return json(res,{error:{message:'请求内容过大。'}},413);
        if(!p.endsWith('/upload'))return json(res,{error:{message:'文件必须使用原文上传接口'}},422);
        uploads.push({raw,headers:req.headers,format:url.searchParams.get('format')});
        const profile={source_hash:hash(raw),source_format:url.searchParams.get('format'),facts:[],unknowns:[]};
        snapshots[sid].profiles.push({profile});snapshots[sid].session.revision++;snapshots[sid].event_cursor++;
        return json(res,{profile},201);
      }
      if(p.endsWith('/recovery')) {
        const body=JSON.parse(raw);assert.equal(body.snapshot_hash,recoveryFixture.snapshot_hash);assert.equal(body.decision,'rollback');
        snapshots[sid].commits[0].status='ROLLED_BACK';snapshots[sid].approvals[0].status='REJECTED';snapshots[sid].runs[0].error=null;
      }
      if(p.endsWith('/resume')) snapshots[sid].runs[0].status='COMPLETED';
      if(p.endsWith('/decision')) snapshots[sid].approvals[0].status='COMMITTED';
      snapshots[sid].session.revision++;snapshots[sid].event_cursor++;
      return json(res,{mock:true});
    }
    return json(res,{error:{message:'控制流夹具未实现此路径：'+p}},404);
  } catch(e) {json(res,{error:{message:e.message}},500);}
});
async function frame(page) {await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));}
async function open(browser,baseURL) {
  reset();const context=await browser.newContext({baseURL,viewport:{width:1440,height:1000}}),page=await context.newPage();
  page.setDefaultTimeout(10000);page.on('dialog',dialog=>dialog.accept());
  await page.addInitScript(()=>{
    window.__jsonResponses=[];const original=Response.prototype.json;
    Response.prototype.json=async function(...args){const value=await original.apply(this,args);window.__jsonResponses.push(new URL(this.url).pathname);return value;};
  });
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');await page.getByRole('button',{name:'发送需求',exact:true}).waitFor();
  await page.getByRole('button',{name:'会话A',exact:false}).waitFor();
  return {context,page,errors};
}
async function select(page,id,preview=true) {
  await page.getByRole('navigation',{name:'历史会话'}).getByRole('button').filter({hasText:'会话'+id}).click();
  await page.getByText('会话原有消息-'+id,{exact:true}).waitFor();
  if(preview){await page.getByRole('button',{name:'文件与Diff',exact:true}).click();await page.getByRole('button',{name:id.toLowerCase()+'.md',exact:true}).click();await page.locator('.file-preview pre').filter({hasText:'真实界面预览夹具-'+id}).waitFor();}
}
async function assertB(page, approval=true) {
  assert.equal(await page.locator('nav .selected').innerText().then(t=>t.includes('会话B')),true);
  assert.equal(await page.getByText('会话原有消息-B',{exact:true}).count(),1);
  assert.equal(await page.getByText('会话原有消息-A',{exact:true}).count(),0);
  assert.equal(await page.locator('.file-preview pre').innerText(),'真实界面预览夹具-B');
  if(approval) assert((await page.getByRole('region',{name:'正式文件审批'}).innerText()).includes('审批专属差异-B'));
  assert.equal(await page.locator('.approval').filter({hasText:'审批专属差异-A'}).count(),0);
}
async function released(page,g,p) {
  const prior=await page.evaluate(p=>window.__jsonResponses.filter(u=>u===p).length,p);g.release();
  await page.waitForFunction(({p,prior})=>window.__jsonResponses.filter(u=>u===p).length>prior,{p,prior});await frame(page);
}
async function races(browser,engine,baseURL) {
  for(const kind of ['save','verify','approval']) {
    const {context,page,errors}=await open(browser,baseURL);
    try {
      await select(page,'A');
      const p=kind==='save'?'/api/sessions/A/drafts':kind==='verify'?'/api/sessions/A/lessons/lesson-A/verify':'/api/approvals/approval-A/decision';
      const a=gate(p);
      if(kind==='save') {await page.getByRole('button',{name:'修改草稿',exact:true}).click();await page.getByRole('textbox',{name:'文件内容',exact:true}).fill('A修改');await page.getByRole('button',{name:'保存草稿，待审批',exact:true}).click();}
      if(kind==='verify') {await page.getByRole('button',{name:'备课产物',exact:true}).click();await page.getByRole('button',{name:'运行全部代码测试',exact:true}).click();}
      if(kind==='approval') await page.getByRole('button',{name:'确认接受并写入',exact:true}).click();
      await a.started;await select(page,'B');await assertB(page);
      const bp='/api/approvals/approval-B/decision',b=gate(bp);
      await page.getByRole('button',{name:'确认接受并写入',exact:true}).click();await b.started;
      await released(page,a,p);await assertB(page);
      assert.equal(await page.getByRole('button',{name:'确认接受并写入',exact:true}).isDisabled(),true,'A的finally不能清除B的pending');
      assert.equal(await page.getByRole('status').filter({hasText:'正在处理文件审批…'}).count(),1);
      await released(page,b,bp);await assertB(page,false);assert.deepEqual(errors,[]);
      if(kind==='save') await page.screenshot({path:path.resolve('.runtime',`stage05-review-${engine}-session-scope.png`),fullPage:true});
      output.cases.push({engine,case:'迟到A-'+kind+'响应/切换B/保留B执行状态及文件预览',status:'PASS'});
    } finally {for(const g of gates.values()) g.release();await context.close();}
  }
  const {context,page,errors}=await open(browser,baseURL);
  try {
    await select(page,'A',false);await page.getByRole('button',{name:'文件与Diff',exact:true}).click();const p='/api/workspaces/wA/file',a=gate(p);
    await page.getByRole('button',{name:'a.md',exact:true}).click();await a.started;await select(page,'B');await released(page,a,p);await assertB(page);assert.deepEqual(errors,[]);
    output.cases.push({engine,case:'迟到A文件预览不会覆盖B',status:'PASS'});
  } finally {for(const g of gates.values()) g.release();await context.close();}
}
async function lateProfile(browser,engine,baseURL) {
  const {context,page,errors}=await open(browser,baseURL);
  try {
    await select(page,'A');await page.locator('.profile-input summary').click();
    await page.evaluate(()=>{
      const original=File.prototype.text;
      File.prototype.text=async function(){const text=await original.call(this);await new Promise(r=>{window.__releaseProfileText=r});return text;};
    });
    await page.locator('input[type=file]').setInputFiles({name:'class-A.json',mimeType:'application/json',buffer:Buffer.from('{"facts":[],"note":"A独有班情，不应回填B"}')});
    await page.waitForFunction(()=>!!window.__releaseProfileText);
    await select(page,'B');await page.evaluate(()=>window.__releaseProfileText());await frame(page);await assertB(page);
    assert.equal(await page.locator('input[type=file]').inputValue(),'');
    assert.equal(await page.getByRole('textbox',{name:'汇总班情',exact:true}).inputValue(),'');
    assert.equal(await page.getByRole('combobox',{name:'班情格式',exact:true}).inputValue(),'text');
    assert.deepEqual(errors,[]);output.cases.push({engine,case:'迟到A班情读取及原生文件选择不污染B',status:'PASS'});
  } finally {await context.close();}
}
async function recoveryCase(browser,engine,baseURL) {
  const {context,page,errors}=await open(browser,baseURL);
  try {
    snapshots.B.commits=[{id:'interrupted-B',status:'INTERRUPTED',applied:['b.md'],created_at:'2026-10-30T00:00:00Z'}];
    snapshots.B.approvals[0].status='INTERRUPTED';snapshots.B.runs[0].status='INTERRUPTED';
    snapshots.B.runs[0].error={code:'RECOVERY_REQUIRED',message:'正式写入中断，请先对账恢复。'};
    recoveryFixture={commit_id:'interrupted-B',snapshot_hash:hash('bound-disk-snapshot'),can_accept:false,can_reject:false,can_rollback:true,entries:[
      {path:'b.md',state:'AFTER',current_hash:hash('new'),before_hash:hash('old'),after_hash:hash('new'),current_mode:384,before_mode:384,after_mode:384,rollback_diff:'-已写入版本\n+原文件'},
      {path:'c.md',state:'BEFORE',current_hash:null,before_hash:null,after_hash:hash('new-c'),current_mode:null,before_mode:null,after_mode:384,rollback_diff:''}]};
    await select(page,'B');assert.equal(await page.getByRole('button',{name:'继续当前任务',exact:true}).isDisabled(),true);
    await page.getByRole('button',{name:'对账恢复',exact:true}).click();
    const section=page.getByRole('region',{name:'中断提交对账'});await section.waitFor();
    assert.equal(await section.getByRole('button',{name:'确认已完整写入',exact:true}).isDisabled(),true);
    assert.equal(await section.getByRole('button',{name:'确认未写入并拒绝',exact:true}).isDisabled(),true);
    assert((await section.innerText()).includes('已写入审批版本'));assert((await section.innerText()).includes('原文件未变'));
    assert((await section.innerText()).includes('当前权限：600'));
    await page.screenshot({path:path.resolve('.runtime',`stage05-review-${engine}-recovery.png`),fullPage:true});
    await section.getByRole('button',{name:'确认回退已写入文件并拒绝',exact:true}).click();
    await page.getByRole('button',{name:'继续当前任务',exact:true}).waitFor();await frame(page);
    assert.equal(await page.getByRole('button',{name:'继续当前任务',exact:true}).isEnabled(),true);
    assert.equal(await section.count(),0);assert.equal(snapshots.B.commits[0].status,'ROLLED_BACK');
    await page.getByRole('button',{name:'继续当前任务',exact:true}).click();await frame(page);await page.getByText('本轮已结束',{exact:false}).waitFor();
    assert.deepEqual(errors,[]);output.cases.push({engine,case:'中断对账Diff/绑定Hash回退/解除阻断后继续',status:'PASS'});
  } finally {await context.close();}
}
function profileBytes(size) {
  const object={facts:[{type:'infinite_loop',count:3}],note:'中文班情',padding:''};
  object.padding=String.fromCharCode(92,34).repeat(Math.floor((size-Buffer.byteLength(JSON.stringify(object)))/4));
  object.padding+='x'.repeat(size-Buffer.byteLength(JSON.stringify(object)));
  const raw=Buffer.from(JSON.stringify(object));assert.equal(raw.length,size);return raw;
}
async function uploadCases(browser,engine,baseURL) {
  const {context,page,errors}=await open(browser,baseURL);
  try {
    await select(page,'B');await page.locator('.profile-input summary').click();
    const cases=[{name:'class.csv',raw:Buffer.from('type,count,class_size\ninfinite_loop,3,40\n')},{name:'bom.csv',raw:Buffer.from('\ufefftype,count,class_size\ninfinite_loop,3,40\n')},... [540065,1048576].map(size=>({name:'class.json',raw:profileBytes(size)}))];
    for(const item of cases) {
      await page.locator('input[type=file]').setInputFiles({name:item.name,mimeType:'application/octet-stream',buffer:item.raw});
      const response=page.waitForResponse(r=>r.url().includes('/class-profiles/upload?'));
      await page.getByRole('button',{name:'更新当前班情',exact:true}).click();const r=await response;
      assert.equal(r.status(),201);assert.equal((await r.json()).profile.source_hash,hash(item.raw));
      const wire=uploads.at(-1);assert(wire.raw.equals(item.raw));assert.equal(wire.headers['content-type'],'application/octet-stream');
      await page.waitForFunction(()=>!document.querySelector('.composer button[type=submit]').disabled);await frame(page);
      output.cases.push({engine,case:`原文上传${item.name}/${item.raw.length}字节/Hash一致`,status:'PASS'});
    }
    const count=uploads.length;
    await page.locator('input[type=file]').setInputFiles({name:'too-large.json',mimeType:'application/json',buffer:profileBytes(1048577)});
    await page.getByRole('alert').filter({hasText:'上传上限为1 MiB'}).waitFor();assert.equal(uploads.length,count);
    assert.equal(await page.getByRole('button',{name:'更新当前班情',exact:true}).isDisabled(),true);assert.deepEqual(errors,[]);
    output.cases.push({engine,case:'超过1MiB在前端明确拒绝',status:'PASS'});
  } finally {await context.close();}
}
(async()=>{
  fs.mkdirSync('.runtime',{recursive:true});await new Promise(r=>server.listen(0,'127.0.0.1',r));const baseURL=`http://127.0.0.1:${server.address().port}`;
  try {
    for(const engine of (process.env.YUNYUN_REVIEW_ENGINES||'chrome,webkit').split(',')) {
      const browser=await (engine==='chrome'?chromium.launch({headless:true,executablePath:process.env.YUNYUN_CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'}):webkit.launch({headless:true}));
      try {await races(browser,engine,baseURL);await uploadCases(browser,engine,baseURL);await lateProfile(browser,engine,baseURL);await recoveryCase(browser,engine,baseURL);} finally {await browser.close();}
    }
    output.status='PASS';console.log(JSON.stringify({status:output.status,cases:output.cases.length,evidence:output.evidence}));
  } catch(error) {output.error=error.stack;console.error(error.stack);process.exitCode=1;}
  finally {server.closeAllConnections();server.close();fs.writeFileSync('.runtime/stage05-review-browser.json',JSON.stringify(output,null,2));}
})();
