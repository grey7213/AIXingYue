// Administrator announcements only. Both entry points share the daily mute.
const PREFIX='homer.notice.v1.',memory=new Map();let dialog,pending=false;
function read(k){try{return localStorage.getItem(k)||''}catch{return memory.get(k)||''}}
function write(k,v){memory.set(k,v);try{localStorage.setItem(k,v)}catch{}}
function owner(){try{const u=JSON.parse(localStorage.getItem('ai_xingyue_user')||'null');return String(u?.id||u?.user_id||u?.email||'guest')}catch{return 'guest'}}
export function localDay(d=new Date()){return d.getFullYear()+'-'+(d.getMonth()+1)+'-'+d.getDate()}
function key(s,u=owner()){return PREFIX+encodeURIComponent(u)+'.'+s}
function visit(){try{const v=window.HomerNative?.getAppVisitId?.();if(v)return String(v)}catch{}try{let v=sessionStorage.getItem(PREFIX+'visit');if(!v){v=crypto.randomUUID();sessionStorage.setItem(PREFIX+'visit',v)}return v}catch{return 'document'}}
function quiet(u,v){return read(key('muted',u))===localDay()||read(key('shown',u))===v+':'+localDay()}
function node(tag,text,cls){const e=document.createElement(tag);if(text)e.textContent=text;if(cls)e.className=cls;return e}
async function fetchNotices(signal){const r=await fetch('/console/api/public/notifications',{credentials:'include',cache:'no-store',signal});if(!r.ok)throw Error('公告暂时无法获取');const b=await r.json();return (b?.data?.list||b?.list||[]).filter(n=>n&&n.enabled!==false&&typeof n.title==='string'&&typeof n.content==='string')}
function show(u,items=null){
 if(dialog?.open)return;
 const sheet=node('dialog',null,'homer-announcements');dialog=sheet;sheet.setAttribute('aria-label','站内公告');
 const head=node('header'),title=node('h2','站内公告'),x=node('button','×');x.type='button';x.setAttribute('aria-label','关闭公告');x.onclick=()=>sheet.close();head.append(title,x);
 const content=node('section');content.setAttribute('aria-live','polite');
 const foot=node('footer'),mute=node('button','今日不再显示'),close=node('button','我知道了'),retry=node('button','重新读取');
 for(const b of [mute,close,retry])b.type='button';retry.hidden=true;
 mute.onclick=()=>{write(key('muted',u),localDay());sheet.close()};close.onclick=()=>sheet.close();foot.append(mute,close);
 sheet.append(head,content,retry,foot);document.body.append(sheet);sheet.showModal();
 let controller,revision=0;sheet.addEventListener('close',()=>{controller?.abort();sheet.remove();if(dialog===sheet)dialog=null},{once:true});
 const render=list=>{content.replaceChildren();for(const item of list){const a=node('article');a.append(node('h3',item.title),node('p',item.content));content.append(a)}if(!list.length)content.append(node('h3','暂无公告'),node('p','管理员发布的公告会显示在这里。'));mute.disabled=!list.length};
 const load=async()=>{const id=++revision;controller?.abort();controller=new AbortController();const timer=setTimeout(()=>controller.abort(),8000);retry.hidden=true;content.textContent='正在读取公告…';try{const list=await fetchNotices(controller.signal);if(sheet.open&&owner()===u&&id===revision)render(list)}catch{if(sheet.open&&id===revision){content.textContent='未能读取公告，请检查网络后重试。';retry.hidden=false}}finally{clearTimeout(timer)}};
 retry.onclick=load;if(items)render(items);else void load();return sheet;
}
export function openCurrentNotifications(){return show(owner())}
export async function checkStartupNotifications(){
 if(window.top!==window||!location.pathname.startsWith('/app/')||document.visibilityState==='hidden'||pending||dialog?.open)return;
 const u=owner(),v=visit();if(quiet(u,v))return;pending=true;const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),5000);
 try{const list=await fetchNotices(controller.signal);if(u!==owner()||v!==visit()||document.visibilityState==='hidden'||quiet(u,v)||dialog?.open)return;if(list.length){show(u,list);write(key('shown',u),v+':'+localDay())}}catch{}finally{clearTimeout(timer);pending=false}
}
if(!window.__homerNoticesInstalled){
 window.__homerNoticesInstalled=true;
 const css=node('link');css.rel='stylesheet';css.href='/assets/css/announcements.css';document.head.append(css);
 window.addEventListener('homer:app-enter',()=>void checkStartupNotifications());document.addEventListener('visibilitychange',()=>void checkStartupNotifications());window.addEventListener('homer-account-cleared',()=>dialog?.close());
 document.addEventListener('click',e=>{if(e.target instanceof Element&&e.target.closest('[data-open-notifications]'))openCurrentNotifications()});
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>void checkStartupNotifications(),{once:true});else setTimeout(()=>void checkStartupNotifications(),0);
}
