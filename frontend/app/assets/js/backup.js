import { api, getToken } from './app-core.js';
import { injectLayout } from './layout.js?v=20260917-r8';

injectLayout('me');
const $ = id => document.getElementById(id);
const base = '/console/api/web/user-backup/';
let selected = null, busy = false, generation = 0, owner = '';
function status(id, text, kind = '') {
  $(id).textContent = text;
  $(id).className = kind ? `backup-${kind}` : '';
}
function setBusy(value) {
  busy = value;
  $('backup-file').disabled = value || !owner;
  $('backup-download').disabled = value || !owner;
  $('backup-restore').disabled = value || !selected;
}
async function identity() {
  const r = await api.profile();
  const u = r?.data || r;
  if (!u?.id) throw new Error('登录已失效，请重新登录');
  if (owner && String(u.id) !== owner) throw new Error('账号已切换，请刷新页面后重新选择备份');
  owner = String(u.id);
}
async function upload(action, file, persona = false) {
  await identity();
  const headers = { 'Content-Type': 'application/zip', 'X-Homer-Backup': '1' };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const r = await fetch(base + action + (persona ? '?persona=1' : ''), {method:'POST',headers,body:file,credentials:'include'});
  const data = await r.json().catch(() => null);
  if (!r.ok || data?.result === 'failure') throw new Error(data?.message || `操作失败（${r.status}）`);
  return data.data;
}
$('backup-download').addEventListener('click', async () => {
  if (busy) return;
  setBusy(true);
  status('backup-download-state', '正在准备备份…');
  try {
    await identity();
    // Native 354+ handles this exact authenticated URL with DownloadManager.
    // Browsers use Blob only after inspecting HTTP status, so failures are visible.
    if (typeof window.HomerNative?.downloadUserBackup === 'function') {
      window.HomerNative.downloadUserBackup();
      status('backup-download-state', '已请求系统下载，请查看系统提示和下载通知。');
    } else {
      if (/HomerAndroid\//.test(navigator.userAgent)) throw new Error('请升级到 1.18.1 或更新客户端后下载，也可在手机浏览器登录网页版使用');
      const headers = {};
      const token = getToken(); if (token) headers.Authorization = `Bearer ${token}`;
      const r = await fetch(base + 'download', {credentials:'include',headers});
      if (!r.ok) { const e = await r.json().catch(() => null); throw new Error(e?.message || `下载失败（${r.status}）`); }
      if (!(r.headers.get('content-type') || '').includes('application/zip')) throw new Error('服务器未返回有效备份');
      const blob = await r.blob();
      const filename = /filename="([^"]+)"/.exec(r.headers.get('content-disposition') || '')?.[1] || 'homer-backup.zip';
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a'); a.href=url; a.download=filename; document.body.append(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
      status('backup-download-state', '备份已生成，请确认文件已保存到设备。');
    }
  } catch(e) { status('backup-download-state', e.message, 'error'); }
  finally { setBusy(false); }
});
$('backup-file').addEventListener('change', async event => {
  const file = event.target.files?.[0];
  const serial = ++generation;
  selected = null; $('backup-preview').hidden = true; $('backup-history').hidden = true;
  status('backup-result', ''); $('backup-persona').checked=false;
  if (!file) return;
  if (file.size > 30*1024*1024 || !file.size) { status('backup-result','请选择不超过 30 MB 的备份文件','error'); return; }
  setBusy(true); status('backup-result','正在校验备份，尚未写入任何内容…');
  try {
    const data = await upload('preview', file);
    if (serial !== generation) return;
    selected=file;
    $('backup-filename').textContent=file.name;
    const date = new Date(data.captured_at);
    $('backup-time').textContent=Number.isFinite(date.valueOf()) ? `备份时间：${date.toLocaleString('zh-CN')}` : '备份时间未提供';
    $('backup-counts').replaceChildren();
    for (const [key,label] of [['roles','角色'],['versions','角色版本'],['conversations','会话'],['messages','消息'],['memories','记忆']]) {
      const div=document.createElement('div'),dt=document.createElement('dt'),dd=document.createElement('dd');
      dt.textContent=label; dd.textContent=Number(data[key] || 0).toLocaleString('zh-CN'); div.append(dt,dd); $('backup-counts').append(div);
    }
    $('backup-preview').hidden=false; status('backup-result','校验通过。确认后会创建私有副本。');
  } catch(e) { status('backup-result',e.message,'error'); }
  finally { setBusy(false); }
});
$('backup-restore').addEventListener('click', async () => {
  if (busy || !selected) return;
  setBusy(true); status('backup-result','正在导入，请保持页面打开…');
  try {
    const result=await upload('restore',selected,$('backup-persona').checked);
    status('backup-result', result.already_imported ? '这份备份已导入，没有重复创建内容。' : `导入完成：${result.roles} 个角色、${result.versions} 个版本、${result.conversations} 段会话、${result.messages} 条消息。${result.persona_restored?'人设已恢复。':''}${result.unavailable_roles?`其中 ${result.unavailable_roles} 个原角色不可用，聊天已保存在私有存档角色下。`:''}`, 'success');
    $('backup-history').hidden=false;
    selected=null;
  } catch(e) { status('backup-result',e.message,'error'); }
  finally { setBusy(false); }
});
identity().then(() => { status('backup-status',''); setBusy(false); }).catch(e => {
  status('backup-status',e.message + '。请返回设置确认登录。','error'); setBusy(false);
});
