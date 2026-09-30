// Local, account-scoped ranking of already-authorized candidates. No content collection or requests.
const prefix='homer.preferences.v1.';
const defaults=()=>({enabled:true,interests:[],dislikedTags:[],hiddenTags:[],signals:[]});
const tags=value=>[...new Set((Array.isArray(value)?value:[]).filter(v=>typeof v==='string').map(v=>v.trim().slice(0,40)).filter(Boolean))].slice(0,40);
const identity=user=>user?.id?prefix+encodeURIComponent(String(user.id)):null;
const tagKey=value=>String(value||'').normalize('NFKC').trim().toLocaleLowerCase();
export function readPreferences(user){try{const key=identity(user),p=key?JSON.parse(localStorage.getItem(key)||'null'):null;return p?{enabled:p.enabled===true,interests:tags(p.interests),dislikedTags:tags(p.dislikedTags),hiddenTags:tags(p.hiddenTags),signals:Array.isArray(p.signals)?p.signals.filter(s=>s&&Array.isArray(s.tags)&&Number.isFinite(s.at)&&Number.isFinite(s.weight)).slice(-200):[]}:defaults();}catch{return defaults();}}
export function writePreferences(user,value){const key=identity(user);if(!key)return false;try{const next={...readPreferences(user),...value};for(const name of ['interests','dislikedTags','hiddenTags'])next[name]=tags(next[name]);localStorage.setItem(key,JSON.stringify(next));window.dispatchEvent(new CustomEvent('homer:preferences-changed',{detail:{key}}));return true;}catch{return false;}}
export function tagFeedback(user,tag){const p=readPreferences(user),key=tagKey(tag);return p.hiddenTags.some(t=>tagKey(t)===key)?'block':p.dislikedTags.some(t=>tagKey(t)===key)?'dislike':p.interests.some(t=>tagKey(t)===key)?'like':'none';}
export function setTagFeedback(user,tag,action){
 const label=String(tag||'').trim(),key=tagKey(label);if(!key||label.length>40||!['like','dislike','block','none'].includes(action))return false;
 const p=readPreferences(user),field={like:'interests',dislike:'dislikedTags',block:'hiddenTags'}[action];
 for(const name of ['interests','dislikedTags','hiddenTags'])p[name]=p[name].filter(t=>tagKey(t)!==key);
 // Do not silently evict older explicit choices when storage reaches the cap.
 if(field){if(p[field].length>=40)return false;p[field].push(label);}
 return writePreferences(user,p);
}
export function filterRecommendations(items,p){const excluded=new Set((p.hiddenTags||[]).map(tagKey));return items.filter(item=>!itemTags(item).some(t=>excluded.has(tagKey(t))));}
export function filterBlocked(user,items){return filterRecommendations(items,readPreferences(user));}
export function watchPreferences(user,onChange){
 const explicit=()=>{const {signals,...p}=readPreferences(user);return JSON.stringify(p);};
 const key=identity(user);let previous=explicit();
 const check=event=>{if(event?.type==='storage'&&event.key!==key)return;if(event?.detail?.key&&event.detail.key!==key)return;const current=explicit();if(current!==previous){previous=current;onChange();}};
 for(const event of ['storage','homer:preferences-changed','homer:page-visible','pageshow'])window.addEventListener(event,check);
 return ()=>{for(const event of ['storage','homer:preferences-changed','homer:page-visible','pageshow'])window.removeEventListener(event,check);};
}
export function itemTags(item){return tags([...(Array.isArray(item.tags)?item.tags:[]),...(item.topic?[item.topic]:[])]);}
export function recordInterest(user,kind,item,action,now=Date.now()){
 const p=readPreferences(user);if(!p.enabled||!identity(user)||!item?.id)return;
 const weights={view:1,read:2,like:3,save:4,unlike:0,unsave:0};if(!(action in weights))return;
 const key=kind+':'+String(item.id),category=action.replace(/^un/,'');
 const previous=p.signals.find(s=>s.key===key&&s.action===category);
 if(['view','read'].includes(action)&&previous&&now-previous.at<86400000)return;
 const signals=p.signals.filter(s=>!(s.key===key&&s.action===category)&&now-s.at<90*86400000);
 if(weights[action])signals.push({key,action:category,tags:itemTags(item),weight:weights[action],at:now});
 writePreferences(user,{...p,signals:signals.slice(-200)});
}
export function rankRecommendations(items,p,now=Date.now()){
 const candidates=filterRecommendations(items,p);if(!p.enabled)return candidates;
 const interests=new Set((p.interests||[]).map(tagKey)),disliked=new Set((p.dislikedTags||[]).map(tagKey)),weights=new Map();
 for(const s of p.signals||[]){const decay=Math.pow(.5,Math.max(0,now-s.at)/(14*86400000));for(const tag of tags(s.tags)){const t=tagKey(tag);weights.set(t,Math.min(8,(weights.get(t)||0)+s.weight*decay));}}
 const pool=candidates.map((item,index)=>({item,index,score:itemTags(item).reduce((sum,tag)=>{const t=tagKey(tag);return sum+(disliked.has(t)?-40:(interests.has(t)?12:0)+(weights.get(t)||0));},0)}));
 if(pool.some(x=>x.item.pinned))return [...pool.filter(x=>x.item.pinned).map(x=>x.item),...rankRecommendations(pool.filter(x=>!x.item.pinned).map(x=>x.item),p,now)];
 const ordered=[...pool].sort((a,b)=>b.score-a.score||a.index-b.index),result=[],used=new Set();
 // Every fifth slot explores the source order; diversity penalty avoids one author monopolizing a run.
 while(result.length<pool.length){let pick;
  if(result.length%5===4)pick=pool.find(x=>!used.has(x.index)&&x.score>=0);
  if(!pick)pick=ordered.filter(x=>!used.has(x.index)).sort((a,b)=>{const penalty=x=>x.item.user_id&&result.slice(-3).some(y=>y.user_id===x.item.user_id)?5:0;return (b.score-penalty(b))-(a.score-penalty(a))||a.index-b.index;})[0];
  used.add(pick.index);result.push(pick.item);
 }
 return result;
}
export function recommend(user,items){return rankRecommendations(items,readPreferences(user));}

// Count a meaningful foreground read, not a preload or a background tab.
// Store tags/IDs only: never chat text, post bodies or inferred sensitive traits.
export function observeReading(user,kind,item){
 let elapsed=0,start=document.hidden?0:performance.now(),done=false;
 const sample=()=>{if(start){elapsed+=performance.now()-start;start=0;}if(elapsed>=8000&&!done){done=true;recordInterest(user,kind,item,'read');stop();}};
 const visible=()=>{sample();if(!document.hidden&&!done)start=performance.now();};
 const timer=setInterval(()=>{sample();if(!document.hidden&&!done)start=performance.now();},1000);
 const stop=()=>{clearInterval(timer);document.removeEventListener('visibilitychange',visible);window.removeEventListener('pagehide',stop);};
 document.addEventListener('visibilitychange',visible);window.addEventListener('pagehide',stop,{once:true});return stop;
}
