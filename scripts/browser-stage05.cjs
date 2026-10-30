/* 真实浏览器验收：使用真实Provider/Runner；审核点击为自动化合成动作。 */
const {chromium, webkit} = require(process.env.YUNYUN_PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs');
const path = require('node:path');
const readline = require('node:readline');
const assert = require('node:assert/strict');
const output = {status:'FAIL', scenarios:[], review_source:'自动化合成教师动作，不代表真实教育审核'};
const evidence = path.resolve('.runtime');
const stem = process.env.YUNYUN_EVIDENCE_PREFIX || 'stage05';
assert(/^[a-zA-Z0-9_-]{1,64}$/.test(stem));
const outputName = process.env.YUNYUN_BROWSER_OUTPUT || `${stem}-browser.json`;
assert(/^[a-zA-Z0-9_-]+\.json$/.test(outputName));
const input = readline.createInterface({input:process.stdin});
async function restart() {const ack=new Promise(r=>input.once('line',r));console.log('RESTART_PC');await ack;}
async function state(page) {
  const sid = await page.evaluate(()=>localStorage.getItem('yunyun_session'));
  assert(sid, '会话必须持久化');
  const r=await page.request.get(`/api/sessions/${sid}`);assert.equal(r.status(),200);return r.json();
}
async function until(fn, label, timeout=240000) {const start=Date.now(); while(Date.now()-start<timeout){const value=await fn();if(value)return value;await new Promise(r=>setTimeout(r,500));}throw Error('超时：'+label);}
async function responseClick(page, locator, suffix) {
  const r=page.waitForResponse(r=>r.request().method()!=='GET' && r.url().endsWith(suffix));
  await locator.click();const result=await r;if(!result.ok())throw Error(await result.text());
}
async function scenario(browser, name, url, stage, className, pc=false) {
  const context=await browser.newContext({baseURL:url,viewport:{width:1440,height:1000},acceptDownloads:true});
  const page=await context.newPage();page.setDefaultTimeout(30000);
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(url+(pc?'/#token='+encodeURIComponent(process.env.YUNYUN_LOCAL_TOKEN):'/'));
  await page.getByRole('button',{name:'发送需求',exact:true}).waitFor();
  await until(async()=>page.getByRole('button',{name:'发送需求',exact:true}).isEnabled(),'连接工作台',30000);
  await page.screenshot({path:path.join(evidence,`${stem}-${name}-welcome.png`),fullPage:true});
  await page.getByRole('combobox',{name:'学段',exact:true}).selectOption(stage);
  if(!pc && className==='B') {
    await page.locator('input[type=file]').setInputFiles(path.resolve('backend/seeds/core/class_B.csv'));
    await until(async()=>await page.getByRole('combobox',{name:'班情格式',exact:true}).inputValue()==='csv','读取班情CSV');
  } else await page.getByRole('button',{name:'使用'+className+'班',exact:true}).click();
  const request=process.env.YUNYUN_ACCEPT_REQUEST || '读取工作区班情与示例，依据已导入班情为本学段备一节45分钟《循环结构》。生成完整结构化教案、2个示例、基础进阶挑战各1题含参考解与评分点，以及有班情依据的错因预警。请真实验证所有示例与参考答案，失败仅修代码并重测；等待教师审核。教学文字务必与实际代码一致。';
  await page.getByRole('textbox',{name:'备课需求',exact:true}).fill(request);
  await responseClick(page,page.getByRole('button',{name:'发送需求',exact:true}),'/messages');
  console.log(JSON.stringify({scenario:name,stage:'sent'}));
  let s=await until(async()=>{const s=await state(page);const run=s.runs.at(-1); if(run && ['FAILED','STOPPED'].includes(run.status)) throw Error(JSON.stringify(run.error));return run?.status==='COMPLETED'?s:false;},name+'真实生成',360000);
  assert(s.lessons.length);let lesson=s.lessons.at(-1);assert.equal(lesson.code_status,'PASS');assert(!lesson.delivery_ready);
  const pathDenials=[];
  for(const attempt of ['../README.md','/etc/passwd','.env','../teacher-other/file.md','a/../../file.md','C:\\Windows\\system.ini','file:///etc/passwd']) {
    const denied=await page.request.get(`/api/workspaces/${s.session.workspace_id}/file?path=${encodeURIComponent(attempt)}`);
    assert.equal(denied.status(),403);assert.equal((await denied.json()).error.code,'PATH_DENIED');
    pathDenials.push({path:attempt,status:denied.status()});
  }
  if(!pc) {
    assert.equal((await page.request.post('/api/local-workspace/dialog',{data:{}})).status(),403);
    assert.equal((await page.request.post('/api/sessions',{data:{root_path:'/etc'}})).status(),422);
    assert.equal((await page.request.post('/api/sessions',{data:{},headers:{Origin:'https://untrusted.invalid'}})).status(),403);
  } else assert.equal((await page.request.post('/api/client',{data:{}})).status(),403);
  const initialCases=s.verification_reports.flatMap(r=>r.cases).length;assert(initialCases>=15);
  assert.equal(s.session.mock,false);
  assert(s.tool_calls.some(c=>c.name==='get_education_context'));
  assert(s.tool_calls.some(c=>c.name==='propose_lesson'));
  assert(s.tool_calls.some(c=>c.name==='verify_lesson'));
  fs.writeFileSync(path.join(evidence,`${stem}-${name}-generated.json`),JSON.stringify(s,null,2));
  if(process.env.YUNYUN_FINAL_ACCEPTANCE) {
    assert(s.tool_calls.some(c=>c.name==='list_files'&&c.result?.ok));
    assert(s.tool_calls.some(c=>c.name==='read_file'&&c.result?.ok));
    if(pc) assert(s.messages.some(m=>m.role==='assistant'&&typeof m.content==='string'&&m.content.includes(process.env.YUNYUN_ACCEPT_MARKER)), '回复必须使用只在真实文件中的随机标记');
    const baseline=s.tool_calls.find(c=>c.name==='get_education_context'&&c.result?.ok).result.data.suggested_plan;
    assert(lesson.plan.segments.filter(i=>i.activity!==baseline.segments.find(b=>b.id===i.id)?.activity).length>=2, '模型至少实际改写两个课堂活动');
    assert(lesson.plan.examples.filter(i=>i.explanation!==baseline.examples.find(b=>b.id===i.id)?.explanation).length>=2, '模型至少实际改写两个示例讲解');
  }
  assert.equal(lesson.plan.examples.length,2);assert.equal(lesson.plan.exercises.length,3);
  assert.equal(lesson.plan.segments.reduce((n,i)=>n+i.minutes,0),45);
  assert.deepEqual(lesson.plan.exercises.map(e=>e.level).sort(),['基础','进阶','挑战'].sort());
  assert(lesson.plan.exercises.every(e=>e.scoring.reduce((n,p)=>n+p.points,0)===100));
  if(!pc && className==='B') assert.equal(s.profiles.at(-1).profile.source_format,'csv');
  const frozenSpecs=JSON.parse(JSON.stringify(s.test_specs));
  console.log(JSON.stringify({scenario:name,stage:'generated',cases:initialCases}));
  await page.getByRole('tab',{name:'分层练习',exact:true}).click();
  if(!pc && name==='web-chrome-B') {
    const item=lesson.plan.exercises[0], original=item.code;
    let article=page.getByRole('article',{name:item.title,exact:true});
    await article.getByRole('button',{name:'继续修改',exact:true}).click();
    const oldRevision=lesson.revision;
    await article.getByRole('spinbutton',{name:'分值',exact:true}).first().fill(String(item.scoring[0].points+1));
    const invalid=page.waitForResponse(r=>r.request().method()==='PATCH'&&r.url().endsWith('/items'));
    await article.getByRole('button',{name:'保存新版本',exact:true}).click();
    assert.equal((await invalid).status(),422);
    await page.getByRole('alert').filter({hasText:'修订破坏结构'}).waitFor();
    assert.equal((await state(page)).lessons.at(-1).revision,oldRevision);
    await page.screenshot({path:path.join(evidence,`${stem}-${name}-validation-error.png`),fullPage:true});
    await article.getByRole('spinbutton',{name:'分值',exact:true}).first().fill(String(item.scoring[0].points));
    await article.getByRole('textbox',{name:'Python代码',exact:true}).fill('print("intentional-wrong")\n');
    await responseClick(page,article.getByRole('button',{name:'保存新版本',exact:true}),'/items');
    await until(async()=>{const x=await state(page);return x.lessons.at(-1).revision>lesson.revision;},'代码修改失效');
    const delayedVerify=async route=>{await new Promise(r=>setTimeout(r,800));await route.continue();};
    await page.route('**/verify',delayedVerify);
    const running=responseClick(page,page.getByRole('button',{name:'运行全部代码测试',exact:true}),'/verify');
    await page.getByRole('status').filter({hasText:'正在执行真实代码测试'}).waitFor();
    await page.getByRole('region',{name:'代码验证反馈'}).getByRole('status').filter({hasText:'正在检查并测试代码'}).waitFor();
    assert.equal(await page.getByRole('button',{name:'正在测试…',exact:true}).isEnabled(),false);
    await page.screenshot({path:path.join(evidence,`${stem}-${name}-verifying.png`),fullPage:true});
    await running;await page.unroute('**/verify',delayedVerify);
    s=await state(page);lesson=s.lessons.at(-1);assert.equal(lesson.items[item.id].verification_status,'OUTPUT_MISMATCH');
    const bad=s.verification_reports.find(r=>r.draft_id===lesson.items[item.id].draft_id);assert(bad.cases.some(c=>c.actual!==c.expected));
    await article.locator('.report > summary').filter({hasText:'OUTPUT_MISMATCH'}).last().waitFor();
    assert.equal(await article.getByRole('button',{name:'接受',exact:true}).isEnabled(),false);
    const rejected=await page.request.get(`/api/sessions/${s.session.id}/lessons/${lesson.lesson_id}/package`);
    assert.equal(rejected.status(),409);
    const beforeApprovals=s.approvals.length;
    const denied=await page.request.post(`/api/sessions/${s.session.id}/lessons/${lesson.lesson_id}/delivery`,{data:{expected_revision:s.session.revision}});
    assert.equal(denied.status(),409);assert.equal((await state(page)).approvals.length,beforeApprovals);
    await article.locator('.report').last().locator('summary').first().click();
    await page.screenshot({path:path.join(evidence,`${stem}-${name}-failure.png`),fullPage:true});
    await article.getByRole('button',{name:'继续修改',exact:true}).click();
    await article.getByRole('textbox',{name:'Python代码',exact:true}).fill(original);
    await responseClick(page,article.getByRole('button',{name:'保存新版本',exact:true}),'/items');
    await responseClick(page,page.getByRole('button',{name:'运行全部代码测试',exact:true}),'/verify');
    s=await state(page);lesson=s.lessons.at(-1);assert.equal(lesson.code_status,'PASS');
    assert(s.verification_reports.some(r=>r.status==='OUTPUT_MISMATCH'));
    assert.deepEqual(s.test_specs,frozenSpecs);
    output.failure_repair={blocked_package:409,blocked_delivery:409,validation_error_display:'PASS',loading_display:'PASS',status:'PASS',failed_case:bad.cases.find(c=>c.status!=='PASS'),test_spec_unchanged:true};
  }
  await page.getByRole('textbox',{name:'审核说明（可选）',exact:true}).fill('自动化合成审核动作，仅检验交付流程，不代表人工教育审核');
  for (const [tab,items] of [['教案',[...(lesson.plan.overview||[]),...lesson.plan.goals,...lesson.plan.segments]],['示例代码',lesson.plan.examples],['分层练习',lesson.plan.exercises],['错因预警',lesson.plan.misconceptions]]) {
    await page.getByRole('tab',{name:tab,exact:true}).click();
    for(const item of items){
      const article=page.getByRole('article',{name:item.title,exact:true});
      await responseClick(page,article.getByRole('button',{name:'接受',exact:true}),'/reviews');
      await until(async()=>{const x=await state(page);return x.lessons.at(-1).items[item.id].review_status==='ACCEPTED';},'逐项审核');
    }
  }
  s=await state(page);lesson=s.lessons.at(-1);assert(lesson.delivery_ready);
  const prepare=page.getByRole('button',{name:'审核交付文件 Diff',exact:true});
  await responseClick(page,prepare,'/delivery');
  await page.getByRole('button',{name:'拒绝本次变更',exact:true}).last().waitFor();
  const pending=await state(page), pendingApproval=pending.approvals.at(-1);
  assert(pendingApproval.entries.length>=14);assert(pendingApproval.entries.every(e=>e.base_hash===null));
  if(pc) {
    const before=JSON.stringify(pending.approvals);
    await restart();await page.reload();await page.getByRole('button',{name:'拒绝本次变更',exact:true}).last().waitFor();
    assert.equal(JSON.stringify((await state(page)).approvals),before);
    output.pc_pending_restart='PASS';
  }
  await responseClick(page,page.getByRole('button',{name:'拒绝本次变更',exact:true}).last(),'/decision');
  assert.equal((await state(page)).commits.length,0);
  if(pc)assert(!fs.existsSync(path.join(process.env.YUNYUN_PC_WORKSPACE,'published',lesson.lesson_id,'lesson.md')));
  await responseClick(page,prepare,'/delivery');
  await responseClick(page,page.getByRole('button',{name:'确认接受并写入',exact:true}).last(),'/decision');
  s=await state(page);assert.equal(s.commits.at(-1).status,'COMMITTED');
  if(pc){
    assert(fs.existsSync(path.join(process.env.YUNYUN_PC_WORKSPACE,'published',lesson.lesson_id,'lesson.md')));
    await restart();await page.reload();await until(async()=>{const x=await state(page);return x.commits.at(-1)?.status==='COMMITTED';},'已提交会话重启');
    output.pc_committed_restart='PASS';
  }
  await page.getByRole('tab',{name:'错因预警',exact:true}).click();
  for(const item of lesson.plan.misconceptions){
    const warning=page.getByRole('article',{name:item.title,exact:true});
    await warning.getByText(item.trigger,{exact:true}).waitFor();
    await warning.getByText(item.teaching_intervention,{exact:true}).waitFor();
  }
  const delayDownload=async route=>{await new Promise(r=>setTimeout(r,800));await route.continue();};
  await page.route('**/package',delayDownload);
  const event=page.waitForEvent('download');
  await page.getByRole('button',{name:'下载教案包',exact:true}).click();
  await page.getByRole('status').filter({hasText:'正在打包下载教案'}).waitFor();
  const download=await event;await page.unroute('**/package',delayDownload);
  await download.saveAs(path.join(evidence,`${stem}-${name}.zip`));
  await page.screenshot({path:path.join(evidence,`${stem}-${name}-complete.png`),fullPage:true});
  if(pc) {
    await page.getByRole('button',{name:'文件与Diff',exact:true}).click();
    const published=`published/${lesson.lesson_id}/lesson.md`;
    await page.getByRole('button',{name:published,exact:true}).click();
    await page.locator('.file-preview').getByRole('heading',{name:published,exact:true}).waitFor();
    assert((await page.locator('.file-preview').innerText()).includes('教学目标'));
    await page.getByRole('button',{name:'formal.md',exact:true}).click();
    await page.locator('.file-preview').getByRole('heading',{name:'formal.md',exact:true}).waitFor();
    const target=path.join(process.env.YUNYUN_PC_WORKSPACE,'formal.md');
    const before=fs.readFileSync(target), changed=before.toString()+'阶段05全新工作区验收：教师确认后的修改。\n';
    await page.getByRole('button',{name:'修改草稿',exact:true}).click();
    await page.getByRole('textbox',{name:'文件内容',exact:true}).fill(changed);
    await responseClick(page,page.getByRole('button',{name:'保存草稿，待审批',exact:true}),'/drafts');
    const change=page.locator('.draft').filter({hasText:'formal.md'});
    await responseClick(page,change.getByRole('button',{name:'审核此文件变更',exact:true}),'/publish-draft');
    await page.screenshot({path:path.join(evidence,`${stem}-${name}-overwrite-diff.png`),fullPage:true});
    await responseClick(page,page.getByRole('button',{name:'拒绝本次变更',exact:true}).last(),'/decision');
    assert.deepEqual(fs.readFileSync(target),before);
    await responseClick(page,change.getByRole('button',{name:'审核此文件变更',exact:true}),'/publish-draft');
    await responseClick(page,page.getByRole('button',{name:'确认接受并写入',exact:true}).last(),'/decision');
    assert.equal(fs.readFileSync(target).toString(),changed);
    const mtime=fs.statSync(target).mtimeMs;
    await restart();await page.reload();
    const recovered=await state(page);assert.equal(recovered.session.id,s.session.id);
    assert.equal(recovered.commits.length,2);assert.equal(fs.statSync(target).mtimeMs,mtime);
    assert.equal(fs.readFileSync(target).toString(),changed);
    output.pc_existing_file={status:'PASS',path:target,rejected_bytes_unchanged:true,accepted_bytes_match:true,restart_no_rewrite:true};
  }
  const id=s.session.id;await page.reload();assert.equal((await state(page)).session.id,id);
  const other=await browser.newContext({baseURL:url,extraHTTPHeaders:pc?{'Authorization':'Bearer '+process.env.YUNYUN_LOCAL_TOKEN}:{}});await other.request.post('/api/client',{data:{}});const denied=await other.request.get(new URL('/api/sessions/'+id,url).href);assert.equal(denied.status(),404);
  assert.equal((await other.request.get(`/api/workspaces/${s.session.workspace_id}/files`)).status(),404);
  assert.equal((await other.request.post(`/api/sessions/${id}/drafts`,{data:{path:'README.md',content:'unauthorized',base_hash:null,operation:'write',expected_revision:s.session.revision}})).status(),404);
  await other.close();
  assert.deepEqual(errors,[]);
  const finalState=await state(page);
  fs.writeFileSync(path.join(evidence,`${stem}-${name}-final.json`),JSON.stringify(finalState,null,2));
  assert(finalState.usage.some(u=>u.status==='USAGE_ESTIMATE'&&u.provider_request_id&&u.input_tokens>0));
  const usage={requests:finalState.usage.filter(u=>u.status==='USAGE_ESTIMATE').length,
    input_tokens:finalState.usage.reduce((n,u)=>n+(u.input_tokens||0),0),
    output_tokens:finalState.usage.reduce((n,u)=>n+(u.output_tokens||0),0),
    cny_estimate:finalState.usage.reduce((n,u)=>n+(u.cny??0),0),
    unknown_usage_requests:finalState.usage.filter(u=>['USAGE_UNKNOWN','RESERVED_UNKNOWN'].includes(u.status)).length};
  output.scenarios.push({name,status:'PASS',session_id:id,stage,className,request,usage,lesson:lesson.plan,files:s.commits.at(-1).applied.length,cases:initialCases,refresh:'PASS',cookie_isolation:'PASS',javascript_errors:errors,synthetic_review:true,paths_denied:pathDenials,tool_names:s.tool_calls.map(c=>c.name),runner_identity:s.verification_reports.at(-1)?.runner_policy_hash,csv_upload:!pc&&className==='B'?'PASS':'NOT_APPLICABLE',download_loading:'PASS'});
  fs.writeFileSync(path.join(evidence,outputName),JSON.stringify(output,null,2));
  await context.close();
}
(async()=>{
 let chrome, safari;
 try {
   const selected=process.env.YUNYUN_BROWSER_SCENARIO || 'all';
   assert(['all','pc-chrome-A','web-chrome-B','web-webkit-university'].includes(selected));
   if(['all','pc-chrome-A','web-chrome-B'].includes(selected)) {
     chrome=await chromium.launch({executablePath:process.env.YUNYUN_CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
     if(selected!=='pc-chrome-A') await scenario(chrome,'web-chrome-B',process.env.YUNYUN_WEB_URL,'初中','B');
     if(selected!=='web-chrome-B') await scenario(chrome,'pc-chrome-A',process.env.YUNYUN_PC_URL,'初中','A',true);
   }
   if(['all','web-webkit-university'].includes(selected)) {
     safari=await webkit.launch({headless:true,timeout:30000});
     await scenario(safari,'web-webkit-university',process.env.YUNYUN_WEB_URL,'大学','A');
   }
   output.status='PASS';console.log(JSON.stringify({status:'PASS',scenarios:output.scenarios.map(s=>s.name)}));
 } finally {if(chrome)await chrome.close();if(safari)await safari.close();}
})().catch(e=>{output.error=String(e.stack);console.error(e.stack);process.exitCode=1;}).finally(()=>{fs.writeFileSync(path.join(evidence,outputName),JSON.stringify(output,null,2));input.close();});
