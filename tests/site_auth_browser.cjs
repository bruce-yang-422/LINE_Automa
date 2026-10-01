// Real cookies and existing permissions in a temporary local fixture. No LINE requests.
const fs=require('fs'),path=require('path'),{spawn}=require('child_process'),assert=require('assert');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'@playwright/test');
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
(async()=>{
  const dir=path.resolve('line-oa-archive/instance');fs.mkdirSync(dir,{recursive:true});
  const stateFile=path.join(dir,`auth-fixture-${Date.now()}.json`),stopFile=stateFile.replace(/\.json$/,'.stop');
  const child=spawn(path.resolve('.venv/Scripts/python.exe'),['tests/workspace_fixture.py',stateFile,'--password-auth'],{windowsHide:true,stdio:['ignore','ignore','pipe']});
  let stderr='',browser;child.stderr.on('data',data=>stderr+=data);
  try{
    for(let i=0;i<100&&!fs.existsSync(stateFile);i++){if(child.exitCode!==null)throw Error(stderr);await delay(100);}
    const access=JSON.parse(fs.readFileSync(stateFile,'utf8')),base=`http://127.0.0.1:${access.port}`;
    browser=await chromium.launch({channel:'chrome',headless:true});
    const control=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
    control.on('pageerror',error=>errors.push(error.message));
    await control.goto(`${base}/#${access.token}`);await control.getByRole('heading',{name:'今天的工作，一目了然'}).waitFor();
    await control.locator('nav [data-view="organizations"]').click();
    await control.locator('summary',{hasText:'平台管理員帳號'}).click();
    await control.locator('[data-security="invite"][data-email="admin@example.test"]').click();
    await control.locator('[data-security="create-invite"]').click();
    const link=await control.locator('#activation-link').inputValue();
    const context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage();
    page.on('pageerror',error=>errors.push(error.message));
    await page.goto(link);await page.getByRole('heading',{name:'設定你的登入密碼'}).waitFor();
    assert(!page.url().includes('#'),'Activation token remains in address bar');
    const password='A memorable browser testing sentence!';
    await page.locator('#login-password').fill(password);await page.locator('#login-confirm').fill(password);
    await page.locator('#login-submit').click();await page.getByText('密碼已設定，請返回登入使用 Email 與新密碼。').waitFor();
    await page.locator('#login-back').click();
    await page.screenshot({path:path.join(dir,'login-light-desktop.png'),fullPage:true});
    await page.locator('#login-email').fill('admin@example.test');await page.locator('#login-password').fill('wrong password');
    await page.locator('#login-submit').click();await page.locator('#login-notice.error').waitFor();
    await page.locator('#login-password').fill(password);await page.locator('#login-remember').check();await page.locator('#login-submit').click();
    await page.getByRole('heading',{name:'今天的工作，一目了然'}).waitFor();
    const cookies=await context.cookies();assert(cookies.some(c=>c.name==='line_local_session'&&c.httpOnly&&c.expires>Date.now()/1000));
    assert.equal(await page.evaluate(()=>sessionStorage.getItem('lineAdminToken')),null);
    await page.reload();await page.getByRole('heading',{name:'今天的工作，一目了然'}).waitFor();
    const second=await context.newPage();await second.goto(base);await second.getByRole('heading',{name:'今天的工作，一目了然'}).waitFor();
    await page.locator('#account-security').click();
    await page.locator('#password-form [name=current_password]').fill(password);
    await page.locator('#password-form [name=password]').fill('A changed browser testing sentence!');
    await page.locator('#password-form [name=confirm]').fill('A changed browser testing sentence!');
    await page.locator('#password-form [type=submit]').click();await page.waitForURL('**/login');
    await second.reload();await second.waitForURL('**/login');
    await page.locator('#login-email').fill('admin@example.test');await page.locator('#login-password').fill('A changed browser testing sentence!');await page.locator('#login-submit').click();
    await page.getByRole('heading',{name:'今天的工作，一目了然'}).waitFor();
    await page.locator('#logout').click();await page.waitForURL('**/login');
    assert.equal((await page.request.get(base+'/api/session')).status(),401);
    await page.setViewportSize({width:390,height:844});await page.emulateMedia({colorScheme:'dark'});assert.equal(await page.evaluate(()=>getComputedStyle(document.documentElement).colorScheme),'light');
    await page.screenshot({path:path.join(dir,'login-mobile.png'),fullPage:true});
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await page.getByRole('button',{name:'顯示密碼',exact:true}).click();assert.equal(await page.locator('#login-password').getAttribute('type'),'text');
    await page.getByText('首次登入或忘記密碼？',{exact:true}).click();
    assert.deepEqual(errors,[]);
    console.log(JSON.stringify({activation:'passed',login:'passed',remember:'passed',password_change:'passed',logout:'passed',mobile:'passed',browser_errors:0,real_line_requests:0}));
  }finally{
    if(browser)await browser.close();fs.writeFileSync(stopFile,'stop');
    for(let i=0;i<50&&child.exitCode===null;i++)await delay(100);
    if(child.exitCode===null)child.kill();
    for(const f of [stateFile,stopFile])if(fs.existsSync(f))fs.unlinkSync(f);
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
