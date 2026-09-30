import { api, ApiError, getCachedUser } from '/app/assets/js/app-core.js?v=20260917-r8';
import { openChatTool } from '/assets/js/chat-tools.js';
import { bindChatAppearance } from '/assets/js/chat-appearance.js';
import { settingsPage } from '/assets/js/chat-settings-page.js';
import { controlCenter } from '/assets/js/chat-control-center.js';
import { fillModelSelect } from '/assets/js/model-catalog.js';
import { messageActionIcon, positionChatMenu } from '/assets/js/chat-menu.js';
import { readPageCache, writePageCache } from './page-cache.js';

const HOST_CHANNEL = 'homer:dialogue-host:v1';
try { if (localStorage.getItem('ai_xingyue_shell_theme') === 'dark') document.documentElement.setAttribute('data-theme', 'dark'); } catch {}
const DEFAULT_RUNTIME_PATH = '/module/dialogue/';
const LEGACY_RUNTIME_PATH = '/dialogue-core/';
const READY_TIMEOUT_MS = 150_000;
const PREVIEW_CACHE_PREFIX = 'homer.dialogue.preview.v2:';
const HISTORY_CACHE_KEY = 'homer.dialogue.history.v2';
const SETTINGS_CACHE_PREFIX = 'homer.dialogue.settings.v1:';

const frame = document.querySelector('#dialogue-frame');
const launcher = document.querySelector('.launcher');
const title = document.querySelector('#launcher-title');
const detail = document.querySelector('#launcher-detail');
const retry = document.querySelector('#launcher-retry');
const launcherVisual = document.querySelector('#launcher-visual');
const announcer = document.querySelector('#dialogue-announcer');
const previewTitle = document.querySelector('#preview-title');
const previewStatus = document.querySelector('#preview-status');
const previewAvatar = document.querySelector('#preview-avatar');
const previewMessages = document.querySelector('#preview-messages');
const previewComposer = document.querySelector('#preview-composer');
const previewInput = document.querySelector('#preview-input');
const previewSend = document.querySelector('#preview-send');
const menuButton = document.querySelector('#preview-menu');
const settingsButton = document.querySelector('#preview-settings');
const leftDrawer = document.querySelector('#preview-left-drawer');
const rightDrawer = document.querySelector('#preview-settings-drawer');
controlCenter(rightDrawer);
const leftClose = document.querySelector('#preview-left-close');
const rightClose = document.querySelector('#preview-settings-close');
const scrim = document.querySelector('#preview-scrim');
const historyList = document.querySelector('#preview-history-list');
const historyCount = document.querySelector('#preview-history-count');
const toast = document.querySelector('#preview-toast');
const networkDetail = document.querySelector('#preview-network-detail');
const networkRetry = document.querySelector('#preview-network-retry');
const modelButton = document.querySelector('#preview-model-settings');
const modelSummary = document.querySelector('#preview-model-summary');
const modelDialog = document.querySelector('#preview-model-dialog');
// Cached conversation UI and the ready runtime use the same component grammar.
{
  const form=modelDialog.querySelector('form'), group=document.createElement('div');
  group.className='homer-model-fields';
  const labels=[...form.querySelectorAll(':scope > label')];
  labels[0].className='homer-model-select-field';
  const picker=labels[0].querySelector('select');picker.classList.add('homer-model-select');
  const modelLabel=document.createElement('span');modelLabel.className='homer-model-field__label';modelLabel.textContent='当前模型';labels[0].replaceChildren(modelLabel,picker);
  const hints=['数值越高越有变化，越低越稳定。','控制候选词范围，通常保持在 0.8–1。','降低已频繁出现词语再次出现的概率。','鼓励模型尝试尚未出现的新内容。'];
  labels.slice(1).forEach((label,i)=>{
    label.className='homer-model-field';
    label.querySelector('span').classList.add('homer-model-field__head');
    const number=label.querySelector('input[type=number]'),range=label.querySelector('input[type=range]');
    const title=label.querySelector('span>span');title.classList.add('homer-model-field__label');
    number.className='homer-model-field__number';number.setAttribute('aria-label',title.textContent);
    range.className='homer-model-field__range';range.setAttribute('aria-label',title.textContent+'滑块');
    const hint=document.createElement('small');hint.className='homer-model-field__hint';hint.textContent=hints[i];label.append(hint);group.append(label);
  });
  labels[0].after(group);
  const note=document.createElement('p');note.className='homer-sheet-dialog__notice';note.textContent='仅用于当前会话，不改变其他对话的模型设置。';form.querySelector('header').after(note);
  form.querySelector('#preview-model-save').textContent='保存';
}
settingsPage(modelDialog, { shell: modelDialog.querySelector('form'), head: modelDialog.querySelector('header'), footer: modelDialog.querySelector('footer'), title: '模型设置' });
const modelForm = document.querySelector('#preview-model-form');
const modelSelect = document.querySelector('#preview-model-select');
const modelCancel = document.querySelector('#preview-model-cancel');

let readyTimer = 0;
let toastTimer = 0;
let activeTarget = null;
let activeAppId = '';
let activeConversationId = '';
let previewRequestId = 0;
let runtimeReady = false;
let runtimeBound = false;
let runtimeState = null;
let readyHandoffTimer = 0;
let launchRequestId = 0;
let history = [];
let pendingDraft = '';
const pendingCommands = [];
let pendingTool = null;
let prewarming = new URLSearchParams(location.search).get('prewarm') === '1';
let coreReady = false;
let adminPreview = new URLSearchParams(location.search).get('admin_preview') === '1';
let pendingAdminCard = '';
let adminBindPending = false;
let bridgeAvailable = false;
let preparedAdminCard = '';

function prepareAdminCard() {
  if (!bridgeAvailable || !preparedAdminCard) return;
  frame.contentWindow.postMessage({ channel: HOST_CHANNEL, version: 1,
    type: 'prepare-admin-preview', app_id: preparedAdminCard }, location.origin);
  preparedAdminCard = '';
}

window.addEventListener('homer:prepare-admin-preview', event => {
  preparedAdminCard = String(event.detail?.app_id || '').trim().slice(0, 160);
  prepareAdminCard();
});

function bindPreparedAdminPreview() {
  if (!pendingAdminCard || !coreReady) return;
  const appId = pendingAdminCard;
  pendingAdminCard = '';
  frame.contentWindow.postMessage({ channel: HOST_CHANNEL, version: 1,
    type: 'bind-admin-preview', app_id: appId }, location.origin);
}

function openAdminPreview(appId) {
  if (adminBindPending || pendingAdminCard || navigationPending || pendingDraft || runtimeState?.generating) return;
  // A same-card revisit retains the live preview, including unsaved settings.
  if (adminPreview && runtimeReady && activeAppId === String(appId)) return;
  ++launchRequestId;
  ++previewRequestId;
  pendingCommands.length = 0;
  pendingTool?.dialog.close(); pendingTool = null;
  adminPreview = true;
  activeAppId = String(appId);
  activeConversationId = '';
  const target = new URL(location.href);
  target.searchParams.set('app_id', activeAppId);
  target.searchParams.set('admin_preview', '1');
  for (const key of ['conversation_id', 'conv_id', 'prewarm']) target.searchParams.delete(key);
  window.history.replaceState({}, '', target);
  runtimeReady = false; runtimeState = null;
  adminBindPending = true;
  frame.inert = true;
  closeDrawers(); modelDialog.close();
  pendingAdminCard = activeAppId;
  performance.mark('homer-admin-workspace-click');
  bindPreparedAdminPreview();
  clearReadyTimer();
  readyTimer = window.setTimeout(() => fail(new Error('管理员会话连接超时，请重试。')), READY_TIMEOUT_MS);
}

function bindPreparedConversation() {
  if (adminPreview) { bindPreparedAdminPreview(); return; }
  if (!prewarming || !coreReady || !activeAppId || !activeConversationId) return;
  frame.contentWindow.postMessage({ channel: HOST_CHANNEL, version: 1, type: 'bind-conversation',
    app_id: activeAppId, conversation_id: activeConversationId }, location.origin);
  prewarming = false;
}

function openRuntimeTool(section) {
  pendingTool?.dialog.close();
  if (runtimeReady) {
    postRuntimeCommand('open-settings', { section }, { queue: false });
    document.body.classList.add('is-ready');
    return;
  }
  const dialog = document.createElement('dialog');
  dialog.className = 'homer-chat-tool';
  const heading = document.createElement('h2');
  heading.textContent = ({ memory: '长记忆', mod: 'Mod', preset: '预设开关', attachments: '添加内容', generation: '生成操作' })[section] || '对话工具';
  const status = document.createElement('p');
  status.setAttribute('role', 'status');
  status.textContent = '\u6b63\u5728\u51c6\u5907\u529f\u80fd\u2026';
  const cancel = document.createElement('button');
  cancel.textContent = '取消';
  cancel.type = 'button';
  cancel.onclick = () => dialog.close();
  dialog.append(heading, status, cancel);
  document.body.append(dialog);
  const request = { dialog, section, conversation: activeConversationId };
  pendingTool = request;
  dialog.addEventListener('close', () => {
    if (pendingTool === request) pendingTool = null;
    dialog.remove();
  }, { once: true });
  dialog.showModal();
}

function nativeCall(name, ...args) {
  try {
    const bridge = window.HomerNative;
    // The method must be invoked with the injected object as receiver. A
    // detached reference throws "Java bridge method can't be invoked on a
    // non-injected object", which silently turned every native cache read and
    // write into undefined — so conversation_cache never got a single row.
    return typeof bridge?.[name] === 'function' ? bridge[name](...args) : undefined;
  } catch {
    return undefined;
  }
}

function parseJson(value, fallback) {
  try {
    return JSON.parse(String(value || ''));
  } catch {
    return fallback;
  }
}

function setStatus(nextTitle, nextDetail) {
  title.textContent = nextTitle;
  detail.textContent = nextDetail;
  previewStatus.textContent = nextDetail;
  announcer.textContent = `${nextTitle}。${nextDetail}`;
}

function showToast(message, duration = 1800) {
  const text = String(message || '').trim();
  if (!text) return;
  window.clearTimeout(toastTimer);
  toast.textContent = text;
  toast.hidden = false;
  toastTimer = window.setTimeout(() => { toast.hidden = true; }, duration);
}

function clearReadyTimer() {
  if (!readyTimer) return;
  window.clearTimeout(readyTimer);
  readyTimer = 0;
}

function setDocumentTitle(roleName = '') {
  const clean = String(roleName || '').trim().slice(0, 120);
  document.title = clean ? `${clean} · 惑梦` : '对话 · 惑梦';
}

function closeDrawers() {
  document.body.classList.remove('shell-left-open', 'shell-right-open');
  leftDrawer.setAttribute('aria-hidden', 'true');
  rightDrawer.setAttribute('aria-hidden', 'true');
  scrim.hidden = true;
}

function openDrawer(side) {
  closeDrawers();
  const left = side === 'left';
  document.body.classList.add(left ? 'shell-left-open' : 'shell-right-open');
  (left ? leftDrawer : rightDrawer).setAttribute('aria-hidden', 'false');
  scrim.hidden = false;
}

function postRuntimeCommand(type, payload = {}, { queue = true } = {}) {
  const command = { channel: HOST_CHANNEL, version: 1, type, ...payload };
  if (runtimeReady && frame?.contentWindow) {
    frame.contentWindow.postMessage(command, location.origin);
    return true;
  }
  if (queue) pendingCommands.push({ command, conversationId: activeConversationId });
  return false;
}

function flushRuntimeCommands() {
  if (!runtimeReady || !frame?.contentWindow) return;
  while (pendingCommands.length) {
    const item = pendingCommands.shift();
    if (item.conversationId === activeConversationId) frame.contentWindow.postMessage(item.command, location.origin);
  }
}

function markReady(roleName = '') {
  clearReadyTimer();
  adminBindPending = false;
  frame.inert = false;
  runtimeReady = true;
  ++previewRequestId;
  window.clearTimeout(readyHandoffTimer);
  setDocumentTitle(roleName);
  flushRuntimeCommands();
  if (pendingTool) {
    const request = pendingTool;
    pendingTool = null;
    request.dialog.close();
    if (request.conversation === activeConversationId) {
      postRuntimeCommand('open-settings', { section: request.section }, { queue: false });
      document.body.classList.add('is-ready');
    }
  }
  postRuntimeCommand('request-state', {}, { queue: false });
  document.body.classList.remove('is-error');
  launcherVisual.src = '/assets/img/brand/launch-loading-1080x1920.png?v=20260901-persistent-pages';
  launcher.setAttribute('aria-busy', 'false');
  const readyConversationId = activeConversationId;
  readyHandoffTimer = window.setTimeout(() => {
    if (!runtimeReady || readyConversationId !== activeConversationId) return;
    closeDrawers();
    modelDialog?.close();
    document.body.classList.remove('has-preview');
    document.body.classList.add('is-ready');
  }, 80);
  announcer.textContent = roleName ? `已进入与${roleName}的对话。` : '对话已准备完成。';
}

function visiblePreviewText(value) {
  const input = String(value || '').trim().slice(0, 60_000);
  if (!input || /<!doctype\s+html|<html[\s>]/i.test(input)) return '';
  const withoutComponents = input
    .replace(/```(?:homer-ui|homer_component)[^\r\n]*\r?\n[\s\S]*?```/gi, '')
    .replace(/\[(?:FLOAT|SIDEBAR|POPUP|BGM|SCENE):[^\]]+\]/gi, '');
  const fragment = new DOMParser().parseFromString(withoutComponents, 'text/html');
  fragment.querySelectorAll('script,style,iframe,object,embed,link,meta').forEach(node => node.remove());
  return String(fragment.body?.textContent || '').replace(/\n{3,}/g, '\n\n').trim().slice(0, 12_000);
}

function safePreviewImage(value) {
  try {
    const source = String(value || '').trim();
    if (!source) return '';
    const target = new URL(source, location.href);
    return ['http:', 'https:'].includes(target.protocol) ? target.href : '';
  } catch {
    return '';
  }
}

function normalizeMessage(message, index = 0) {
  const isUser = message?.role === 'user' || message?.is_user === true;
  const raw = message?.content ?? message?.text ?? message?.mes;
  const content = isUser ? String(raw || '').trim().slice(0, 12_000) : visiblePreviewText(raw);
  if (!content || ((message?.role === 'system' || message?.is_system === true) && !message?.extra?.homer_hidden && !message?.hidden)) return null;
  return {
    id: String(message?.id || message?.extra?.homer_message_id || `local-${index}`).slice(0, 180),
    role: isUser ? 'user' : 'assistant',
    hidden: Boolean(message?.hidden || message?.extra?.homer_hidden),
    collapsed: Boolean(message?.collapsed || message?.extra?.homer_collapsed),
    content,
    created_at: Number(message?.created_at || message?.extra?.homer_created_at || 0),
  };
}

function conversationSnapshot(payload) {
  const data = payload?.data || payload || {};
  const conversation = data?.conversation || {};
  const rawMessages = Array.isArray(data?.messages) ? data.messages : Array.isArray(data?.list) ? data.list : [];
  return {
    conversation_id: String(data?.conversation_id || conversation?.id || activeConversationId).trim().slice(0, 160),
    app_id: String(data?.app_id || conversation?.app_id || activeAppId).trim().slice(0, 160),
    title: String(data?.title || conversation?.app_name || conversation?.title || '角色对话').trim().slice(0, 120),
    avatar: safePreviewImage(data?.avatar || conversation?.app_icon),
    messages: rawMessages.map(normalizeMessage).filter(Boolean).slice(-120),
    updated_at: Date.now(),
  };
}

function readCachedConversation(conversationId) {
  const id = String(conversationId || '').trim();
  if (!id) return null;
  const native = parseJson(nativeCall('readConversationSnapshot', id), null);
  if (native?.conversation_id === id && Array.isArray(native.messages)) return native;
  try {
    const cached = parseJson(localStorage.getItem(scopedKey(`${PREVIEW_CACHE_PREFIX}${id}`)), null);
    if (cached?.conversation_id === id && Array.isArray(cached.messages)) return cached;
    const legacy = parseJson(localStorage.getItem(`homer.dialogue.preview.v1:${id}`), null)
      || parseJson(nativeCall('readLegacySnapshot'), null);
    if (legacy && legacy.conversation_id === id && Array.isArray(legacy.messages)) {
      return {
        conversation_id: id,
        app_id: activeAppId,
        title: String(legacy.title || legacy.roleName || '角色对话'),
        avatar: safePreviewImage(legacy.avatar),
        messages: legacy.messages.map(normalizeMessage).filter(Boolean),
        updated_at: Number(legacy.updated_at || 0),
      };
    }
    return null;
  } catch {
    return null;
  }
}

function writeCachedConversation(snapshot) {
  if (adminPreview) return;
  if (!snapshot?.conversation_id) return;
  const payload = JSON.stringify({ ...snapshot, updated_at: Date.now() });
  nativeCall('saveConversationSnapshot', payload);
  try {
    localStorage.setItem(scopedKey(`${PREVIEW_CACHE_PREFIX}${snapshot.conversation_id}`), payload);
  } catch {
    // Android SQLite remains available when browser storage is full.
  }
  const owner = getCachedUser();
  const cached = readPageCache('histories', owner);
  const list = Array.isArray(cached?.list) ? cached.list : [];
  const previous = list.find(item => String(item.id) === String(snapshot.conversation_id));
  const item = { ...previous, id: snapshot.conversation_id, app_id: snapshot.app_id,
    app_name: snapshot.title || previous?.app_name || '角色对话',
    app_icon: snapshot.avatar || previous?.app_icon || '',
    last_message: snapshot.messages?.at(-1)?.content || previous?.last_message || '', updated_at: Date.now() };
  writePageCache('histories', owner, { list: [item, ...list.filter(row => String(row.id) !== String(item.id))].slice(0, 100) });
}

function readCachedHistory() {
  const native = parseJson(nativeCall('readConversationHistory'), []);
  let local = [];
  try { local = parseJson(localStorage.getItem(scopedKey(HISTORY_CACHE_KEY)), []); } catch { local = []; }
  const merged = new Map();
  for (const item of [...(Array.isArray(native) ? native : []), ...(Array.isArray(local) ? local : [])]) {
    const id = String(item?.id || item?.conversation_id || '');
    if (!id) continue;
    const existing = merged.get(id);
    if (!existing || Number(item?.updated_at || 0) >= Number(existing?.updated_at || 0)) merged.set(id, item);
  }
  return [...merged.values()].sort((a, b) => Number(b?.updated_at || 0) - Number(a?.updated_at || 0));
}

function writeCachedHistory(items) {
  try { localStorage.setItem(scopedKey(HISTORY_CACHE_KEY), JSON.stringify(items.slice(0, 100))); } catch {}
}

function scopedKey(key) {
  const user = getCachedUser();
  const owner = String(user?.id || user?.user_id || user?.email || '').trim();
  return `${key}:owner:${encodeURIComponent(owner || 'anonymous')}`;
}

function renderMessages(messages, { pending = '' } = {}) {
  previewMessages.replaceChildren();
  for (const [index, message] of messages.entries()) {
    const normalized = normalizeMessage(message, index);
    if (!normalized) continue;
    const bubble = document.createElement('article');
    bubble.className = `preview-message${normalized.role === 'user' ? ' is-user' : ''}`;
    bubble.dataset.messageId = normalized.id;
    bubble.dataset.hidden = String(normalized.hidden);
    bubble.dataset.collapsed = String(normalized.collapsed);
    bubble.textContent = normalized.content;
    previewMessages.append(bubble);
  }
  if (pending) {
    const bubble = document.createElement('article');
    bubble.className = 'preview-message is-user is-pending';
    bubble.textContent = pending;
    previewMessages.append(bubble);
  }
  if (!previewMessages.childElementCount) {
    const empty = document.createElement('p');
    empty.className = 'preview-empty';
    empty.textContent = '这段会话还没有消息。';
    previewMessages.append(empty);
  }
  requestAnimationFrame(() => { previewMessages.scrollTop = previewMessages.scrollHeight; });
}

function renderConversation(payload, { save = true } = {}) {
  const snapshot = payload?.conversation_id && Array.isArray(payload?.messages) ? payload : conversationSnapshot(payload);
  if (!snapshot.conversation_id) snapshot.conversation_id = activeConversationId;
  if (!snapshot.app_id) snapshot.app_id = activeAppId;
  activeConversationId = snapshot.conversation_id || activeConversationId;
  activeAppId = snapshot.app_id || activeAppId;
  appearance.refresh();
  previewTitle.textContent = snapshot.title || '角色对话';
  document.querySelector('#preview-settings-title').textContent = previewTitle.textContent;
  document.querySelector('#preview-settings-avatar').src = snapshot.avatar || '/assets/img/apk/avatar.webp';
  setDocumentTitle(snapshot.title);
  if (snapshot.avatar) previewAvatar.src = snapshot.avatar;
  renderMessages(snapshot.messages || [], { pending: pendingDraft });
  if (save) writeCachedConversation(snapshot);
  const current = history.find(item => String(item?.id || '') === activeConversationId);
  if (current) {
    current.title = snapshot.title;
    current.app_name = snapshot.title;
    current.app_icon = snapshot.avatar;
    current.last_message = snapshot.messages?.at(-1)?.content || current.last_message || '';
    current.updated_at = Date.now();
  }
  renderHistory();
}

function renderHistory() {
  historyCount.textContent = String(history.length);
  historyList.replaceChildren();
  for (const conversation of history) {
    const id = String(conversation?.id || conversation?.conversation_id || '');
    const appId = String(conversation?.app_id || '');
    if (!id || !appId) continue;
    const roleName = String(conversation?.app_name || conversation?.title || '角色对话');
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `preview-history-button${id === activeConversationId ? ' is-active' : ''}`;
    button.dataset.conversationId = id;
    button.dataset.appId = appId;
    const avatar = document.createElement('span');
    avatar.className = 'preview-history-avatar';
    const image = safePreviewImage(conversation?.app_icon) || new URL('/assets/img/apk/avatar.webp?v=20260901-persistent-pages', location.href).href;
    avatar.style.backgroundImage = `url("${image.replaceAll('"', '%22')}")`;
    const strong = document.createElement('strong');
    strong.textContent = roleName;
    const small = document.createElement('small');
    small.textContent = String(conversation?.last_message || '这段会话还没有消息。').slice(0, 50);
    button.append(avatar, strong, small);
    historyList.append(button);
  }
}

function renderCachedConversation(conversationId) {
  const cached = readCachedConversation(conversationId);
  if (!cached) return false;
  renderConversation(cached, { save: false });
  return true;
}

async function loadQuickPreview(conversationId) {
  const id = String(conversationId || '').trim();
  if (!id) return;
  const requestId = ++previewRequestId;
  renderCachedConversation(id);
  try {
    const response = await api.messages(id, { limit: 120 });
    if (requestId !== previewRequestId || id !== activeConversationId || runtimeReady) return;
    const data = response?.data || response || {};
    const returnedId = String(data.conversation_id || data.conversation?.id || id);
    if (returnedId !== id) return;
    renderConversation(response);
  } catch {
    // Local cache stays usable without the network.
  }
}

function showShell() {
  window.clearTimeout(readyHandoffTimer);
  document.body.classList.remove('is-ready', 'is-error');
  document.body.classList.add('has-preview');
  launcher.setAttribute('aria-busy', 'false');
}

function showConversationSwitchShell(message) {
  const appId = String(message?.app_id || '').trim();
  const conversationId = String(message?.conversation_id || '').trim();
  if (!appId || !conversationId) return;
  // Android can reveal the prepared document just before its navigation event
  // arrives. An immediate tool tap belongs to this first binding, not to an
  // empty conversation id. Already-scoped requests never transfer between chats.
  if (prewarming && pendingTool && !pendingTool.conversation) pendingTool.conversation = conversationId;
  // Ignore the acknowledgement of a switch already reflected in the host.
  if (!runtimeReady && conversationId === activeConversationId && activeAppId === appId) return;
  clearReadyTimer();
  runtimeReady = false;
  runtimeState = null;
  pendingDraft = '';
  previewSend.disabled = false;
  previewInput.value = '';
  closeDrawers();
  updateVisibleConversationUrl(appId, conversationId);
  showShell();
  const cached = renderCachedConversation(conversationId);
  if (!cached) {
    const target = history.find(item => String(item?.id || item?.conversation_id || '') === conversationId);
    renderConversation({
      conversation_id: conversationId,
      app_id: appId,
      title: String(message?.role_name || target?.app_name || target?.title || '角色对话'),
      avatar: target?.app_icon || '',
      messages: [],
    }, { save: false });
  }
  updateModelSummary();
  void loadQuickPreview(conversationId);
}

function fail(error) {
  clearReadyTimer();
  adminBindPending = false;
  runtimeReady = false;
  console.error('对话能力启动失败', error);
  showShell();
  document.body.classList.add('is-error');
  launcherVisual.src = '/assets/img/brand/network-error-512.png?v=20260901-persistent-pages';
  networkDetail.textContent = error?.message || '本地会话仍可阅读，恢复网络后可以继续对话。';
  if (error instanceof ApiError && Number(error.code) === 401) {
    const next = location.pathname + location.search + location.hash;
    location.replace('/app/login.html?next=' + encodeURIComponent(next));
    return;
  }
  showToast(error?.message || '对话能力暂时无法连接，本地历史仍可使用。', 3200);
}

function normalizeRuntimeUrl(value) {
  const target = new URL(String(value || DEFAULT_RUNTIME_PATH), location.href);
  if (target.origin !== location.origin) throw new Error('对话服务必须通过站点内部地址访问。');
  if (target.pathname === LEGACY_RUNTIME_PATH.slice(0, -1) || target.pathname.startsWith(LEGACY_RUNTIME_PATH)) target.pathname = DEFAULT_RUNTIME_PATH;
  if (!target.pathname.endsWith('/')) target.pathname += '/';
  return target;
}

function runtimeTarget(appId, conversationId, runtimePath = DEFAULT_RUNTIME_PATH) {
  const target = normalizeRuntimeUrl(runtimePath);
  target.searchParams.set('homer_app_id', appId);
  target.searchParams.set('homer_conversation_id', conversationId);
  target.searchParams.set('homer_site_origin', location.origin);
  target.searchParams.set('homer_embed', '1');
  target.searchParams.set('homer_host_channel', HOST_CHANNEL);
  return target;
}

function updateVisibleConversationUrl(appId, conversationId) {
  const safeAppId = String(appId || '').trim().slice(0, 160);
  const safeConversationId = String(conversationId || '').trim().slice(0, 160);
  if (!safeAppId || !safeConversationId) return;
  activeAppId = safeAppId;
  activeConversationId = safeConversationId;
  appearance.refresh();
  const next = new URL(location.href);
  next.searchParams.set('app_id', safeAppId);
  next.searchParams.set('conversation_id', safeConversationId);
  next.searchParams.delete('conv_id');
  next.searchParams.delete('prewarm');
  if (adminPreview) next.searchParams.set('admin_preview', '1');
  else next.searchParams.delete('admin_preview');
  window.history.replaceState({ app_id: safeAppId, conversation_id: safeConversationId }, '', next);
}

async function loadHistory() {
  history = readCachedHistory();
  renderHistory();
  try {
    const response = await api.conversations();
    const list = response?.data?.list || response?.list || [];
    if (Array.isArray(list)) {
      history = list.slice(0, 100);
      writeCachedHistory(history);
      renderHistory();
    }
  } catch {
    // Cached history stays available.
  }
}

async function resolveLaunchTarget(requestId, href = location.href) {
  const params = new URL(href, location.href).searchParams;
  let appId = String(params.get('app_id') || '').trim();
  let conversationId = String(params.get('conversation_id') || params.get('conv_id') || '').trim();
  if (appId && conversationId) {
    updateVisibleConversationUrl(appId, conversationId);
    void loadQuickPreview(conversationId);
    return runtimeTarget(appId, conversationId);
  }
  if (requestId !== launchRequestId) return null;
  if (!appId) {
    const response = await api.conversations();
    if (requestId !== launchRequestId) return null;
    const conversations = response?.data?.list || response?.list || [];
    const selected = conversationId ? conversations.find(item => String(item?.id || '') === conversationId) : conversations[0];
    appId = String(selected?.app_id || '').trim();
    conversationId = String(selected?.id || conversationId || '').trim();
  }
  if (!appId) throw new Error('还没有可进入的角色会话，请先从探索页选择一张角色卡。');
  const response = await api.dialogueSession(appId, conversationId, { launchOnly: true });
  if (requestId !== launchRequestId) return null;
  const payload = response?.data || response || {};
  const launch = payload?.launch;
  if (!launch?.app_id || !launch?.conversation_id) throw new Error('后端没有返回可启动的角色会话。');
  updateVisibleConversationUrl(String(launch.app_id), String(launch.conversation_id));
  if (!conversationId) writeCachedConversation({ conversation_id: launch.conversation_id, app_id: launch.app_id, messages: [], title: payload?.character?.name || '' });
  void loadQuickPreview(String(launch.conversation_id));
  return runtimeTarget(String(launch.app_id), String(launch.conversation_id));
}

function allowedNavigationPath(value) {
  try {
    const target = new URL(String(value || ''), location.href);
    if (target.origin !== location.origin) return '';
    // 运行时抽屉的导航项现在改发 navigate 消息而不是自己跳转（主站是
    // frame-ancestors 'none'，在 dialogue iframe 里加载 /dashboard.html 会被浏览器
    // 拒绝、直接黑屏）。所以这里必须接住整站两个非 /app/ 页面。
    const appPage = target.pathname === '/app' || target.pathname.startsWith('/app/');
    const standalonePage = ['/dashboard.html', '/admin.html'].includes(target.pathname);
    return appPage || standalonePage ? target.pathname + target.search + target.hash : '';
  } catch {
    return '';
  }
}

function cacheRuntimeState(state) {
  if (Boolean(state?.admin_preview) !== adminPreview) return;
  if (String(state?.conversation_id || '') !== activeConversationId) return;
  runtimeState = state;
  if (adminPreview) { updateModelSummary(state); return; }
  const snapshot = conversationSnapshot(state);
  if (snapshot.messages.some(item => item.role === 'user' && item.content === pendingDraft)) {
    pendingDraft = '';
    previewSend.disabled = false;
  }
  writeCachedConversation(snapshot);
  if (Array.isArray(state?.conversations) && state.conversations.length) {
    history = state.conversations;
    writeCachedHistory(history);
  }
  try {
    localStorage.setItem(scopedKey(`${SETTINGS_CACHE_PREFIX}${snapshot.conversation_id}`), JSON.stringify({
      models: state?.models || [],
      model_default_id: state?.model_default_id || '',
      model_settings: state?.model_settings || {},
    }));
  } catch {}
  if (!document.body.classList.contains('is-ready')) renderConversation(snapshot, { save: false });
  renderHistory();
  updateModelSummary(state);
}

function handleRuntimeMessage(event) {
  if (event.origin !== location.origin || event.source !== frame.contentWindow) return;
  const message = event.data;
  if (!message || message.channel !== HOST_CHANNEL || message.version !== 1) return;
  if (message.type === 'bridge-available') {
    bridgeAvailable = true;
    prepareAdminCard();
    return;
  }
  if (message.type === 'core-ready') {
    coreReady = true;
    bridgeAvailable = true;
    bindPreparedConversation();
    return;
  }
  if (message.type === 'ready') {
    if (Boolean(message.admin_preview) !== adminPreview || String(message.app_id || '') !== activeAppId) return;
    if (activeConversationId && String(message.conversation_id || '') !== activeConversationId) return;
    coreReady = true;
    bridgeAvailable = true;
    prewarming = false;
    runtimeBound = true;
    updateVisibleConversationUrl(message.app_id, message.conversation_id);
    markReady(message.role_name || message.title || '');
    if (adminPreview) performance.mark('homer-admin-workspace-ready');
    return;
  }
  if (message.type === 'conversation-switching' || message.type === 'conversation-switch-failed') {
    if (message.type === 'conversation-switch-failed') adminPreview = Boolean(message.admin_preview);
    if (adminPreview) updateVisibleConversationUrl(message.app_id, message.conversation_id);
    else showConversationSwitchShell(message);
    if (message.type === 'conversation-switch-failed') {
      pendingCommands.length = 0;
      markReady(message.role_name || '');
      showToast('未能切换，已返回原会话');
    }
    return;
  }
  if (message.type === 'state') {
    cacheRuntimeState(message.state || {});
    return;
  }
  if (message.type === 'title') {
    setDocumentTitle(message.role_name || message.title || '');
    return;
  }
  if (message.type === 'conversation' && runtimeReady) {
    if (Boolean(message.admin_preview) !== adminPreview) return;
    updateVisibleConversationUrl(message.app_id, message.conversation_id);
    return;
  }
  if (message.type === 'navigate') {
    const target = allowedNavigationPath(message.target);
    if (target) location.assign(target);
    return;
  }
  if (message.type === 'command-error') {
    if (adminPreview && !runtimeReady) { fail(new Error(message.message || '管理员会话连接失败')); return; }
    pendingCommands.length = 0;
    if (pendingDraft) {
      previewInput.value = pendingDraft;
      pendingDraft = '';
      previewSend.disabled = false;
    }
    renderCachedConversation(activeConversationId);
    showToast(message.message || '操作失败');
    return;
  }
  if (message.type === 'error') fail(new Error(String(message.message || '对话模块启动失败。')));
}

function modelData() {
  if (runtimeState?.models) return runtimeState;
  try { return parseJson(localStorage.getItem(scopedKey(`${SETTINGS_CACHE_PREFIX}${activeConversationId}`)), {}); } catch { return {}; }
}

function updateModelSummary(state = modelData()) {
  const settings = state?.model_settings || {};
  const selected = (state?.models || []).find(item => String(item?.id || '') === String(settings.model_id || ''));
  modelSummary.textContent = String(selected?.name || selected?.model || '当前会话模型');
}

function openModelDialog() {
  closeDrawers();
  const data = modelData();
  const settings = { temperature: 1, top_p: 1, frequency_penalty: 0, presence_penalty: 0, ...(data?.model_settings || {}) };
  fillModelSelect(modelSelect, data?.models || [], settings.model_id);
  if (!modelSelect.options.length) {
    const option = document.createElement('option');
    option.value = String(settings.model_id || '');
    option.textContent = '使用网站当前模型';
    modelSelect.append(option);
  }
  modelSelect.value = String(settings.model_id || modelSelect.options[0]?.value || '');
  for (const key of ['temperature', 'top_p', 'frequency_penalty', 'presence_penalty']) {
    const number = modelForm.querySelector(`[data-model-number="${key}"]`);
    const range = modelForm.querySelector(`[data-model-range="${key}"]`);
    number.value = String(settings[key]);
    range.value = String(settings[key]);
  }
  modelDialog.showModal();
}

async function switchConversation(appId, conversationId) {
  const nextAppId = String(appId || '').trim();
  const nextConversationId = String(conversationId || '').trim();
  if (!nextAppId || !nextConversationId) {
    closeDrawers();
    return;
  }
  if (!adminPreview && nextConversationId === activeConversationId && nextAppId === activeAppId) {
    closeDrawers();
    return;
  }
  if (pendingDraft || runtimeState?.generating) {
    showToast('当前消息处理完成后再切换会话');
    return;
  }
  activeAppId = nextAppId;
  activeConversationId = nextConversationId;
  adminPreview = false;
  updateVisibleConversationUrl(nextAppId, nextConversationId);
  const wasReady = runtimeReady;
  ++launchRequestId;
  pendingCommands.length = 0;
  if (wasReady || runtimeBound) {
    frame.contentWindow.postMessage({ channel: HOST_CHANNEL, version: 1, type: 'switch-conversation', app_id: nextAppId, conversation_id: nextConversationId }, location.origin);
    showConversationSwitchShell({ app_id: nextAppId, conversation_id: nextConversationId });
    return;
  }
  showConversationSwitchShell({ app_id: nextAppId, conversation_id: nextConversationId });
  if (prewarming) {
    bindPreparedConversation();
    return;
  }
  activeTarget = runtimeTarget(nextAppId, nextConversationId);
  frame.src = activeTarget.href;
}

async function start() {
  const requestId = ++launchRequestId;
  clearReadyTimer();
  runtimeReady = false;
  if (adminPreview) {
    const appId = new URLSearchParams(location.search).get('app_id') || activeAppId;
    if (!appId) { fail(new Error('请从管理后台选择测试角色。')); return; }
    if (!coreReady) {
      prewarming = true;
      activeTarget = runtimeTarget('', '');
      activeTarget.searchParams.set('homer_prewarm', '1');
      frame.src = activeTarget.href;
    }
    pendingAdminCard = '';
    openAdminPreview(appId);
    return;
  }
  if (prewarming) {
    activeTarget = runtimeTarget('', '');
    activeTarget.searchParams.set('homer_prewarm', '1');
    frame.src = activeTarget.href;
    return;
  }
  launcherVisual.src = '/assets/img/brand/launch-loading-1080x1920.png?v=20260901-persistent-pages';
  showShell();
  history = readCachedHistory();
  renderHistory();
  void loadHistory();
  const params = new URLSearchParams(location.search);
  activeAppId = String(params.get('app_id') || '').trim();
  activeConversationId = String(params.get('conversation_id') || params.get('conv_id') || '').trim();
  if (activeConversationId) renderCachedConversation(activeConversationId);
  frame.removeAttribute('src');
  try {
    const target = await resolveLaunchTarget(requestId);
    if (requestId !== launchRequestId) return;
    activeTarget = target;
    frame.src = activeTarget.href;
    readyTimer = window.setTimeout(() => fail(new Error('后台对话能力连接超时，本地历史仍可使用。')), READY_TIMEOUT_MS);
  } catch (error) {
    if (requestId === launchRequestId) fail(error);
  }
}

window.addEventListener('message', handleRuntimeMessage);
// Android keeps this document alive when a different history item is opened.
// A cancelled event means navigation was handled, including a busy-chat refusal.
let navigationPending = false;
window.addEventListener('homer:navigate-conversation', event => {
  try {
    const target = new URL(String(event.detail?.url || ''), location.href);
    const appId = target.searchParams.get('app_id');
    const conversationId = target.searchParams.get('conversation_id') || target.searchParams.get('conv_id');
    if (target.origin !== location.origin || target.pathname !== '/app/chat.html' || !appId) return;
    event.preventDefault();
    if (adminBindPending || navigationPending || pendingDraft || runtimeState?.generating) return;
    if (target.searchParams.get('admin_preview') === '1') { openAdminPreview(appId); return; }
    if (conversationId) { void switchConversation(appId, conversationId); return; }
    navigationPending = true;
    const requestId = ++launchRequestId;
    const oldApp = activeAppId, oldConversation = activeConversationId;
    void resolveLaunchTarget(requestId, target.href).then(resolved => {
      if (!resolved) return;
      const nextApp = resolved.searchParams.get('homer_app_id');
      const nextConversation = resolved.searchParams.get('homer_conversation_id');
      activeAppId = oldApp; activeConversationId = oldConversation;
      return switchConversation(nextApp, nextConversation);
    }).catch(error => { showToast(error.message || '创建会话失败，请重试'); })
      .finally(() => { navigationPending = false; });
  } catch { /* The native container falls back to normal navigation. */ }
});
frame.addEventListener('error', () => fail(new Error('对话能力连接失败。')));
retry.addEventListener('click', () => void start());
networkRetry.addEventListener('click', () => void start());
previewAvatar.addEventListener('error', () => {
  const fallback = new URL('/assets/img/apk/avatar.webp?v=20260901-persistent-pages', location.href).href;
  if (previewAvatar.src !== fallback) previewAvatar.src = fallback;
});
menuButton.addEventListener('click', () => openDrawer('left'));
settingsButton.addEventListener('click', () => openDrawer('right'));
leftClose.addEventListener('click', closeDrawers);
rightClose.addEventListener('click', closeDrawers);
scrim.addEventListener('click', closeDrawers);
historyList.addEventListener('click', event => {
  const button = event.target.closest('[data-conversation-id]');
  if (!button) return;
  void switchConversation(button.dataset.appId, button.dataset.conversationId);
});
modelButton.addEventListener('click', openModelDialog);
document.querySelector('#preview-settings-avatar').addEventListener('error', event => {
  const fallback = new URL('/assets/img/apk/avatar.webp', location.href).href;
  if (event.target.src !== fallback) event.target.src = fallback;
});
const appearance = bindChatAppearance(() => ({ owner: getCachedUser()?.id || getCachedUser()?.user_id, conversation: activeConversationId }));
document.querySelector('#preview-appearance').addEventListener('click', () => { closeDrawers(); appearance.open(); });
for (const button of document.querySelectorAll('[data-chat-tool]')) {
  button.addEventListener('click', () => {
    closeDrawers();
    openChatTool(button.dataset.chatTool, { container: previewMessages, selector: '.preview-message', isUser: element => element.classList.contains('is-user'), title: previewTitle.textContent });
  });
}
modelCancel.addEventListener('click', () => modelDialog.close());
for (const section of document.querySelectorAll('[data-runtime-section]')) {
  section.addEventListener('click', () => {
    closeDrawers();
    openRuntimeTool(section.dataset.runtimeSection);
  });
}
for (const range of modelForm.querySelectorAll('[data-model-range]')) {
  range.addEventListener('input', () => {
    modelForm.querySelector(`[data-model-number="${range.dataset.modelRange}"]`).value = range.value;
  });
}
for (const number of modelForm.querySelectorAll('[data-model-number]')) {
  number.addEventListener('input', () => {
    modelForm.querySelector(`[data-model-range="${number.dataset.modelNumber}"]`).value = number.value;
  });
}
modelForm.addEventListener('submit', event => {
  event.preventDefault();
  const settings = { model_id: modelSelect.value };
  for (const key of ['temperature', 'top_p', 'frequency_penalty', 'presence_penalty']) {
    settings[key] = Number(modelForm.querySelector(`[data-model-number="${key}"]`).value);
  }
  const data = modelData();
  data.model_settings = settings;
  runtimeState = { ...(runtimeState || {}), ...data };
  try { if (!adminPreview) localStorage.setItem(scopedKey(`${SETTINGS_CACHE_PREFIX}${activeConversationId}`), JSON.stringify(data)); } catch {}
  postRuntimeCommand('model-settings', { settings });
  updateModelSummary(data);
  modelDialog.close();
  showToast('模型参数已保存到本次会话');
});
previewComposer.addEventListener('submit', event => {
  event.preventDefault();
  const content = String(previewInput.value || '').trim().slice(0, 10_000);
  if (!content || pendingDraft) return;
  pendingDraft = content;
  previewInput.value = '';
  previewSend.disabled = true;
  const cached = readCachedConversation(activeConversationId) || conversationSnapshot({});
  renderMessages(cached.messages || [], { pending: content });
  writeCachedConversation({ ...cached, messages: cached.messages || [] });
  postRuntimeCommand('draft', { content, submit: true });
});
previewInput.addEventListener('input', () => {
  previewInput.style.height = 'auto';
  previewInput.style.height = `${Math.min(128, previewInput.scrollHeight)}px`;
});

// The local conversation shell is already fully interactive at this point.
// Tell the Android container to reveal it now; the heavier dialogue runtime
// continues warming in the background and reports its own readiness later.
document.documentElement.dataset.homerShellReady = 'true';
nativeCall('notifyShellReady', location.href);

void start();
// The cached first frame exposes the same message actions as the live runtime.
let previewPressTimer = null;
let previewPressOrigin = null;
function openPreviewMessageMenu(bubble) {
  if (!bubble?.dataset.messageId) return;
  document.querySelector('#preview-message-actions')?.remove();
  const menu = document.createElement('dialog');
  menu.id = 'preview-message-actions'; menu.className = 'preview-message-actions'; menu.setAttribute('aria-label', '消息操作');
  const actions = [['copy','复制'],['edit','改写'],['rollback','回溯'],['delete','删除'],['hide',bubble.dataset.hidden === 'true' ? '取消隐藏' : '隐藏'],['select','多选'],['collapse',bubble.dataset.collapsed === 'true' ? '展开' : '折叠']];
  for (const [action,label] of actions) {
    const button = document.createElement('button'); button.type = 'button';
    const mark = messageActionIcon(action);
    const text = document.createElement('span'); text.textContent = label; button.append(mark,text);
    button.addEventListener('click', async () => {
      menu.close();
      if (action === 'copy') {
        try { await navigator.clipboard.writeText(bubble.textContent); showToast('已复制这条消息'); }
        catch { showToast('复制失败，请重试'); }
      } else {
        postRuntimeCommand('message-action', { action, message_id: bubble.dataset.messageId });
        if (runtimeReady) document.body.classList.add('is-ready');
      }
    }); menu.append(button);
  }
  const reposition=()=>positionChatMenu(menu,bubble,{header:document.querySelector('.preview-header'),composer:previewComposer,isUser:bubble.classList.contains('is-user'),pressY:previewPressOrigin?.y});
  menu.addEventListener('close',()=>{window.removeEventListener('resize',reposition);window.visualViewport?.removeEventListener('resize',reposition);previewMessages.removeEventListener('scroll',closeMenu);menu.remove();},{once:true});
  const closeMenu=()=>menu.close();
  menu.addEventListener('click',event=>{if(event.target !== menu)return;const r=menu.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)menu.close();});
  document.body.append(menu); menu.showModal();
  reposition();window.addEventListener('resize',reposition);window.visualViewport?.addEventListener('resize',reposition);previewMessages.addEventListener('scroll',closeMenu,{once:true});
}
previewMessages.addEventListener('contextmenu',event=>{
  const bubble=event.target.closest('.preview-message'); if(!bubble)return;
  event.preventDefault();openPreviewMessageMenu(bubble);
});
previewMessages.addEventListener('pointerdown',event=>{
  if(event.button>0)return;const bubble=event.target.closest('.preview-message');if(!bubble)return;
  previewPressOrigin={x:event.clientX,y:event.clientY};
  clearTimeout(previewPressTimer);previewPressTimer=setTimeout(()=>openPreviewMessageMenu(bubble),500);
},{passive:true});
previewMessages.addEventListener('pointermove',event=>{
  if(previewPressOrigin && Math.hypot(event.clientX-previewPressOrigin.x,event.clientY-previewPressOrigin.y)>10)clearTimeout(previewPressTimer);
},{passive:true});
for(const name of ['pointerup','pointercancel'])previewMessages.addEventListener(name,()=>{clearTimeout(previewPressTimer);previewPressOrigin=null;});
