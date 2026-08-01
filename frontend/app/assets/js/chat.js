import { api, ApiError } from '/app/assets/js/app-core.js?v=20260729-dialogue-runtime';

const HOST_CHANNEL = 'homer:dialogue-host:v1';
const DEFAULT_RUNTIME_PATH = '/module/dialogue/';
const LEGACY_RUNTIME_PATH = '/dialogue-core/';
const READY_TIMEOUT_MS = 150_000;

const frame = document.querySelector('#dialogue-frame');
const launcher = document.querySelector('.launcher');
const title = document.querySelector('#launcher-title');
const detail = document.querySelector('#launcher-detail');
const retry = document.querySelector('#launcher-retry');
const announcer = document.querySelector('#dialogue-announcer');

let readyTimer = 0;
let activeTarget = null;

function setStatus(nextTitle, nextDetail) {
  title.textContent = nextTitle;
  detail.textContent = nextDetail;
  announcer.textContent = `${nextTitle}。${nextDetail}`;
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

function markReady(roleName = '') {
  clearReadyTimer();
  setDocumentTitle(roleName);
  document.body.classList.remove('is-error');
  document.body.classList.add('is-ready');
  launcher.setAttribute('aria-busy', 'false');
  announcer.textContent = roleName ? `已进入与${roleName}的对话。` : '对话已准备完成。';
}

function fail(error) {
  clearReadyTimer();
  console.error('对话启动失败', error);
  document.body.classList.remove('is-ready');
  document.body.classList.add('is-error');
  launcher.setAttribute('aria-busy', 'false');
  setDocumentTitle();
  if (error instanceof ApiError && Number(error.code) === 401) {
    const next = location.pathname + location.search + location.hash;
    location.replace('/app/login.html?next=' + encodeURIComponent(next));
    return;
  }
  setStatus(
    '对话暂时无法连接',
    error?.message || '对话服务暂时不可用，请稍后重试。',
  );
}

async function readPublicSettings() {
  const response = await fetch('/console/api/public/site-settings', {
    credentials: 'include',
    cache: 'no-store',
  });
  if (!response.ok) throw new Error(`站点设置读取失败（${response.status}）`);
  const body = await response.json();
  return body?.data || body || {};
}

function normalizeRuntimeUrl(value) {
  const target = new URL(String(value || DEFAULT_RUNTIME_PATH), location.href);
  if (target.origin !== location.origin) {
    throw new Error('对话服务必须通过站点内部地址访问。');
  }
  if (
    target.pathname === LEGACY_RUNTIME_PATH.slice(0, -1)
    || target.pathname.startsWith(LEGACY_RUNTIME_PATH)
  ) {
    target.pathname = DEFAULT_RUNTIME_PATH;
  }
  if (!target.pathname.endsWith('/')) target.pathname += '/';
  return target;
}

function updateVisibleConversationUrl(appId, conversationId) {
  const safeAppId = String(appId || '').trim().slice(0, 160);
  const safeConversationId = String(conversationId || '').trim().slice(0, 160);
  if (!safeAppId || !safeConversationId) return;
  const next = new URL(location.href);
  next.searchParams.set('app_id', safeAppId);
  next.searchParams.set('conversation_id', safeConversationId);
  next.searchParams.delete('conv_id');
  window.history.replaceState(
    { app_id: safeAppId, conversation_id: safeConversationId },
    '',
    next,
  );
}

async function resolveLaunchTarget() {
  setStatus('正在确认身份', '沿用你现有的惑梦登录状态…');
  const profilePromise = api.profile();
  const settingsPromise = readPublicSettings();

  const params = new URLSearchParams(location.search);
  let appId = String(params.get('app_id') || '').trim();
  let conversationId = String(
    params.get('conversation_id') || params.get('conv_id') || '',
  ).trim();

  if (!appId) {
    await profilePromise;
    setStatus('正在读取存档', '查找当前账号最近使用的角色与会话…');
    const response = await api.conversations();
    const conversations = response?.data?.list || response?.list || [];
    const selected = conversationId
      ? conversations.find(item => String(item?.id || '') === conversationId)
      : conversations[0];
    appId = String(selected?.app_id || '').trim();
    conversationId = String(selected?.id || conversationId || '').trim();
  }

  if (!appId) {
    throw new Error('还没有可进入的角色会话，请先从探索页选择一张角色卡。');
  }

  setStatus('正在装载角色卡', '同步角色、世界书、正则、脚本与当前对话…');
  await profilePromise;
  const [settings, response] = await Promise.all([
    settingsPromise,
    api.dialogueSession(appId, conversationId, { launchOnly: true }),
  ]);
  const payload = response?.data || response || {};
  const launch = payload?.launch;
  if (!launch?.app_id || !launch?.conversation_id) {
    throw new Error('后端没有返回可启动的角色会话。');
  }

  const runtimeUrl = settings?.runtime?.dialogue_url
    || payload?.runtime?.public_url
    || DEFAULT_RUNTIME_PATH;
  const target = normalizeRuntimeUrl(runtimeUrl);
  target.searchParams.set('homer_app_id', String(launch.app_id));
  target.searchParams.set('homer_conversation_id', String(launch.conversation_id));
  target.searchParams.set('homer_site_origin', location.origin);
  target.searchParams.set('homer_embed', '1');
  target.searchParams.set('homer_host_channel', HOST_CHANNEL);
  updateVisibleConversationUrl(String(launch.app_id), String(launch.conversation_id));
  return target;
}

function allowedNavigationPath(value) {
  try {
    const target = new URL(String(value || ''), location.href);
    if (target.origin !== location.origin) return '';
    const allowed = ['/app/', '/app/login.html', '/app/histories.html', '/app/explore.html'];
    if (!allowed.some(path => target.pathname === path || target.pathname.startsWith(path))) {
      return '';
    }
    return target.pathname + target.search + target.hash;
  } catch {
    return '';
  }
}

function handleRuntimeMessage(event) {
  if (event.origin !== location.origin || event.source !== frame.contentWindow) return;
  const message = event.data;
  if (!message || message.channel !== HOST_CHANNEL || message.version !== 1) return;

  if (message.type === 'ready') {
    updateVisibleConversationUrl(message.app_id, message.conversation_id);
    markReady(message.role_name || message.title || '');
    return;
  }
  if (message.type === 'title') {
    setDocumentTitle(message.role_name || message.title || '');
    return;
  }
  if (message.type === 'loading') {
    if (!document.body.classList.contains('is-ready')) {
      setStatus('加载中', String(message.message || '正在准备对话…'));
    }
    return;
  }
  if (message.type === 'conversation') {
    updateVisibleConversationUrl(message.app_id, message.conversation_id);
    setDocumentTitle(message.role_name || message.title || '');
    return;
  }
  if (message.type === 'navigate') {
    const target = allowedNavigationPath(message.target);
    if (target) location.assign(target);
    return;
  }
  if (message.type === 'error') {
    fail(new Error(String(message.message || '对话模块启动失败。')));
  }
}

async function start() {
  clearReadyTimer();
  document.body.classList.remove('is-ready', 'is-error');
  launcher.setAttribute('aria-busy', 'true');
  frame.removeAttribute('src');
  try {
    activeTarget = await resolveLaunchTarget();
    setStatus('加载中', '正在进入对话…');
    frame.src = activeTarget.href;
    readyTimer = window.setTimeout(() => {
      fail(new Error('对话准备时间过长，请重新连接。'));
    }, READY_TIMEOUT_MS);
  } catch (error) {
    fail(error);
  }
}

window.addEventListener('message', handleRuntimeMessage);
frame.addEventListener('error', () => fail(new Error('对话模块加载失败。')));
retry.addEventListener('click', () => void start());
void start();
