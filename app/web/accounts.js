let account={id:'local',username:'本地访客'};
const accountButton=document.createElement('button');accountButton.className='btn secondary';accountButton.style.fontSize='12px';accountButton.textContent='登录 / 注册';
const accountHost=document.querySelector('.topbar,.video-header');if(accountHost)accountHost.append(accountButton);
const authDialog=document.createElement('dialog');authDialog.innerHTML='<h2>你的账户</h2><p class="small muted">本机账户，密码至少10位。登录后可保存个人内容。</p><form id="auth-form"><input name="username" placeholder="用户名（英文、数字、下划线）" required minlength="3" maxlength="40" style="width:100%;margin:10px 0"><input name="password" type="password" placeholder="密码，至少10位" required minlength="10" maxlength="128" style="width:100%;margin:10px 0"><div class="row"><button class="btn" type="submit">登录</button><button class="btn secondary" type="button" id="register-account">注册</button><button class="btn secondary" type="button" id="auth-close">取消</button></div></form>';
document.body.append(authDialog);
async function refreshAccount(){account=await api('/auth/me');accountButton.textContent=account.id==='local'?'登录 / 注册':account.username+' · 退出';}
accountButton.onclick=guard(async()=>{if(account.id==='local')authDialog.showModal();else{await post('/auth/logout',{});location.reload();}});
document.querySelector('#auth-close').onclick=()=>authDialog.close();
async function authenticate(route){const form=new FormData(document.querySelector('#auth-form'));await post('/auth/'+route,Object.fromEntries(form));location.reload();}
document.querySelector('#auth-form').onsubmit=guard(async e=>{e.preventDefault();await authenticate('login');});document.querySelector('#register-account').onclick=guard(()=>authenticate('register'));
guard(refreshAccount)();
