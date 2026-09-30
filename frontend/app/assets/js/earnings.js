import {api,requireAuth} from './app-core.js';
const $=id=>document.getElementById(id);
const points=n=>Number.isSafeInteger(n)&&n>=0?n.toLocaleString('zh-CN'):'—';
let revision=0;
async function load(){
 const version=++revision;$('refresh-earnings').disabled=true;$('earnings-status').textContent='正在读取收益…';
 try{
  const result=await api.earnings();if(version!==revision)return;const data=result?.data??result;
  if(data?.unit!=='积分'||!Array.isArray(data.cards))throw Error('收益服务暂未接入，请更新服务端后重试。');
  $('creator-total').textContent=points(data.creator_points);$('invite-total').textContent=points(data.invite_points)+(Number.isSafeInteger(data.invite_points)?' 积分':'');$('invite-state').textContent=data.invite_points==null?'尚未接入邀请结算':'累计获得的邀请积分';
  $('earnings-list').replaceChildren();$('earnings-status').textContent=data.cards.length?'':'还没有角色卡收益。有人使用你的角色卡后，已结算收益会出现在这里。';
  for(const card of data.cards){const row=document.createElement('li'),name=document.createElement('span'),value=document.createElement('strong');name.textContent=card.name||'未命名角色卡';value.textContent=points(card.points)+' 积分';row.append(name,value);$('earnings-list').append(row);}
 }catch(error){$('earnings-status').textContent=error.status===404||error.code===404?'收益服务暂未接入，请更新服务端后重试。':error.message||'未能读取收益，请检查网络后刷新。';}
 finally{if(version===revision)$('refresh-earnings').disabled=false;}
}
$('refresh-earnings').onclick=load;if(requireAuth())void load();
