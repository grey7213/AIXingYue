import { tagFeedback, setTagFeedback } from './recommendations.js';

// One delegated handler: Alpine can replace tags without adding duplicate listeners.
export function installTagFeedback(root, getUser) {
 let timer=0, origin=null, held=false, moved=false, menu=null, toast=null;
 const cancel=()=>{clearTimeout(timer);timer=0;origin=null;};
 function notice(text,undo){
  toast?.remove();toast=document.createElement('div');toast.className='tag-feedback-toast';toast.setAttribute('role','status');
  const copy=document.createElement('span');copy.textContent=text;toast.append(copy);
  if(undo){const button=document.createElement('button');button.type='button';button.textContent='撤销';button.onclick=()=>{if(undo())toast.remove();else copy.textContent='未能撤销，请检查本机存储空间。';};toast.append(button);}
  const dismiss=document.createElement('button');dismiss.type='button';dismiss.textContent='×';dismiss.setAttribute('aria-label','关闭提示');dismiss.onclick=()=>toast.remove();toast.append(dismiss);document.body.append(toast);
 }
 function open(anchor){
  cancel();const user=getUser(),tag=anchor.dataset.feedbackTag;if(!user?.id||!tag)return;
  menu?.close();menu=document.createElement('dialog');menu.className='tag-feedback-menu';menu.setAttribute('aria-label',`标签：${tag}`);
  const title=document.createElement('header'),label=document.createElement('strong'),close=document.createElement('button');label.textContent=tag;close.type='button';close.textContent='×';close.setAttribute('aria-label','关闭标签菜单');close.onclick=()=>menu.close();title.append(label,close);menu.append(title);
  const current=tagFeedback(user,tag);
  for(const [action,name,description,icon] of [['like','点赞','多推荐此类内容','♡'],['dislike','不感兴趣','减少此类推荐','−'],['block','屏蔽','不再展示带此标签的推荐','⊘']]){
   const button=document.createElement('button');button.type='button';button.dataset.feedbackAction=action;button.setAttribute('aria-pressed',String(current===action));
   const symbol=document.createElement('span');symbol.className='tag-feedback-icon';symbol.textContent=icon;symbol.setAttribute('aria-hidden','true');
   const copy=document.createElement('span'),strong=document.createElement('strong'),small=document.createElement('small'),check=document.createElement('span');strong.textContent=current===action?{like:'取消点赞',dislike:'恢复兴趣',block:'取消屏蔽'}[action]:name;small.textContent=description;copy.append(strong,small);check.textContent=current===action?'✓':'';check.setAttribute('aria-hidden','true');button.append(symbol,copy,check);
   button.onclick=()=>{
    if(String(getUser()?.id)!==String(user.id)){menu.close();return;}
    const before=tagFeedback(user,tag),next=before===action?'none':action;
    if(!setTagFeedback(user,tag,next)){notice('未保存：请检查本机存储空间，或在内容偏好中整理标签（每类最多 40 个）。');return;}
    menu.close();anchor.dataset.feedbackState=next;
    notice(next==='none'?`已恢复「${tag}」的默认推荐`:{like:`已点赞「${tag}」，推荐会优先考虑`,dislike:`将减少「${tag}」相关推荐`,block:`已屏蔽「${tag}」相关推荐`}[next],()=>String(getUser()?.id)===String(user.id)&&setTagFeedback(user,tag,before));
   };menu.append(button);
  }
  const bounds=anchor.getBoundingClientRect();document.body.append(menu);menu.showModal();
  const width=menu.offsetWidth,height=menu.offsetHeight;menu.style.left=Math.max(12,Math.min(innerWidth-width-12,bounds.left))+'px';menu.style.top=Math.max(12,Math.min(innerHeight-height-12,bounds.bottom+8))+'px';
  menu.addEventListener('click',event=>{if(event.target===menu){if(held){held=false;return;}const r=menu.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)menu.close();}});
  const activeMenu=menu;
  menu.addEventListener('close',()=>{activeMenu.remove();if(anchor.isConnected)anchor.focus({preventScroll:true});},{once:true});
 }
 root.addEventListener('pointerdown',event=>{const anchor=event.target.closest('[data-feedback-tag]');if(!anchor||event.button!==0)return;held=false;moved=false;origin={x:event.clientX,y:event.clientY};timer=setTimeout(()=>{held=true;open(anchor);},460);},{passive:true});
 root.addEventListener('pointermove',event=>{if(origin&&Math.hypot(event.clientX-origin.x,event.clientY-origin.y)>8){moved=true;cancel();}},{passive:true});
 for(const event of ['pointerup','pointercancel','scroll'])root.addEventListener(event,cancel,{passive:true,capture:true});
 root.addEventListener('click',event=>{const anchor=event.target.closest('[data-feedback-tag]');if(!anchor)return;event.preventDefault();if(held||moved){held=false;moved=false;return;}open(anchor);});
 root.addEventListener('contextmenu',event=>{const anchor=event.target.closest('[data-feedback-tag]');if(anchor){event.preventDefault();if(!held)open(anchor);}});
 window.addEventListener('homer-account-cleared',()=>{cancel();menu?.close();toast?.remove();});
}
