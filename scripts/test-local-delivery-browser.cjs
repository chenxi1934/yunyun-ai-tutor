/* 本机交付入口UI协议夹具；不调用模型、Runner或原生打开程序。 */
const {chromium} = require(process.env.YUNYUN_PLAYWRIGHT_MODULE || 'playwright');
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve('frontend/dist');
let mode = 'pc', failure = false, committed = true, opened = [], locations = 0;
const folder = '/tmp/教师教学资料/' + '长目录名称'.repeat(20) + '/published/lesson';
const location = {directory: folder, entry: folder + '/开始阅读.html', relative_directory: 'published/lesson'};
function snapshot() {
  const lesson = {lesson_id:'lesson', revision:1, code_status:'PASS', delivery_ready:committed,
    profile_stale:false, curriculum_risks:[], plan:{stage:'初中',topic:'循环结构',duration_minutes:45,prerequisites:[],goals:[{id:'goal',title:'合成目标',criterion:'界面协议夹具'}],segments:[],examples:[],exercises:[],misconceptions:[]},
    items:{goal:{review_status:'ACCEPTED'}},profile:{facts:[],unknowns:[]},strategies:[]};
  return {session:{id:'session',workspace_id:'workspace',revision:1,mock:true,created_at:'2026-10-30T00:00:00Z',context:{stage:'初中',grade:'初二',topic:'本机交付界面夹具'}},
    lessons:[lesson],messages:[{role:'user',content:'界面控制流夹具'}],runs:[],drafts:[],verification_reports:[],approvals:[],event_cursor:0,profiles:[],usage:[],workspace_name:'教学资料',
    commits:committed?[{id:'commit',status:'COMMITTED',lesson_id:'lesson',lesson_revision:1,applied:[],created_at:'2026-10-30T00:00:00Z'}]:[]};
}
function json(res,value,status=200){res.writeHead(status,{'Content-Type':'application/json'});res.end(JSON.stringify(value));}
const server=http.createServer(async(req,res)=>{
  const p=new URL(req.url,'http://localhost').pathname;
  if(!p.startsWith('/api/')){
    const file=path.resolve(root,'.'+(p==='/'?'/index.html':p));
    if(!file.startsWith(root+path.sep)||!fs.existsSync(file))return json(res,{},404);
    res.writeHead(200,{'Content-Type':({'.js':'application/javascript','.css':'text/css','.html':'text/html'})[path.extname(file)]||'text/plain'});fs.createReadStream(file).pipe(res);return;
  }
  if(p==='/api/runtime')return json(res,{mode,mock:true,model:'HTTP_UI_FIXTURE',runner:'UNAVAILABLE',workspace_name:'教学资料'});
  if(p==='/api/client')return json(res,{});
  if(p==='/api/sessions')return json(res,{sessions:[snapshot().session]});
  if(p==='/api/sessions/session')return json(res,snapshot());
  if(p.endsWith('/events')){res.writeHead(200,{'Content-Type':'text/event-stream'});res.write(': fixture\n\n');return;}
  if(p.endsWith('/files'))return json(res,{files:[]});
  if(p.endsWith('/local-package')){locations++;return json(res,location);}
  if(p.endsWith('/local-package/open')){
    let body='';for await(const chunk of req)body+=chunk;
    opened.push(JSON.parse(body));return failure?json(res,{error:{message:'未能打开，请使用显示的保存路径手动打开；文件已保留。'}},503):json(res,{opened:true});
  }
  return json(res,{error:{message:'夹具拒绝未实现请求'}},404);
});
(async()=>{
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const browser=await chromium.launch({headless:true,executablePath:process.env.YUNYUN_CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  const results=[];
  try{
    for(const scenario of ['pc','pc-error','web','uncommitted']){
      mode=scenario==='web'?'web':'pc';failure=scenario==='pc-error';committed=scenario!=='uncommitted';opened=[];locations=0;
      const context=await browser.newContext({viewport:{width:1440,height:1000}});const page=await context.newPage();page.setDefaultTimeout(7000);page.on('pageerror',error=>console.error('pageerror',error.message));
      await page.goto('http://127.0.0.1:'+server.address().port);
      await page.getByRole('navigation',{name:'历史会话'}).getByRole('button').click();
      const panel=page.getByRole('complementary',{name:'本机教案保存位置'});
      if(mode==='pc'&&committed){
        await panel.getByRole('button',{name:'开始阅读',exact:true}).waitFor();assert.equal(await panel.getByText(folder,{exact:true}).count(),1);
        await panel.getByRole('button',{name:'开始阅读',exact:true}).click();
        if(failure){await panel.getByRole('alert').waitFor();await panel.getByRole('button',{name:'重新核对',exact:true}).click();await panel.getByRole('button',{name:'开始阅读',exact:true}).waitFor();assert.equal(locations,2);}
        else{await panel.getByRole('button',{name:'打开文件夹',exact:true}).click();assert.deepEqual(opened,[{target:'read'},{target:'folder'}]);}
        assert.equal(await page.getByRole('button',{name:'下载 ZIP（可选）',exact:true}).count(),1);
        await page.setViewportSize({width:390,height:844});assert.equal(await panel.evaluate(e=>e.scrollWidth>e.clientWidth),false);
        await page.screenshot({path:'.runtime/local-delivery-'+scenario+'.png',fullPage:true});
      }else{await page.getByText('界面控制流夹具',{exact:true}).waitFor();assert.equal(await panel.count(),0);assert.equal(locations,0);if(mode==='web')assert.equal(await page.getByRole('button',{name:'下载教案包',exact:true}).count(),1);}
      results.push({scenario,status:'PASS'});await context.close();
    }
  }finally{await browser.close();server.closeAllConnections();server.close();}
  fs.writeFileSync('.runtime/local-delivery-browser.json',JSON.stringify({status:'PASS',scope:'React/Chrome HTTP fixtures only; no real model, Runner or native opener',cases:results},null,2));console.log('PASS',results.length,'UI cases');
})().catch(e=>{console.error(e);server.closeAllConnections();server.close();process.exitCode=1;});
