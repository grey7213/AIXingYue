// AI星月 Web App 共享核心 - 在所有 /app/*.html 顶部加载
import { api as baseApi, getToken, setToken, clearAuth, getCachedUser, setCachedUser, formatDateTime, ApiError } from '/assets/js/api.js';

// 扩展共享 api 实例（增加 chat / explore / conversation 方法）
async function rawRequest(path, opts = {}) {
  const headers = { Accept: 'application/json', ...(opts.headers || {}) };
  if (opts.body && !(opts.body instanceof FormData)) headers['Content-Type'] = 'application/json';
  const token = getToken();
  if (token && opts.auth !== false) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(path, {
    method: opts.method || 'GET',
    headers,
    body: opts.body ? (opts.body instanceof FormData ? opts.body : JSON.stringify(opts.body)) : undefined,
  });
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = { raw: text }; }
  if (!res.ok) throw new ApiError((data && (data.message || data.msg)) || `HTTP ${res.status}`, res.status, data);
  if (data && data.result === 'failure') throw new ApiError(data.message || data.msg || '请求失败', parseInt(data.code) || res.status, data);
  return data;
}

async function sseRequest(path, payload, handlers = {}) {
  const headers = { Accept: 'text/event-stream', 'Content-Type': 'application/json' };
  const token = getToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(path, { method: 'POST', headers, body: JSON.stringify(payload || {}) });
  if (!res.ok || !res.body) {
    let message = `HTTP ${res.status}`;
    try {
      const data = await res.json();
      message = data?.message || data?.msg || message;
    } catch {}
    throw new ApiError(message, res.status);
  }
  const decoder = new TextDecoder('utf-8');
  const reader = res.body.getReader();
  let buffer = '';
  let finalPayload = null;

  const dispatch = (block) => {
    const lines = block.split(/\r?\n/);
    let event = 'message';
    const dataLines = [];
    for (const line of lines) {
      if (line.startsWith('event:')) event = line.slice(6).trim() || 'message';
      if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart());
    }
    if (!dataLines.length) return;
    let data = dataLines.join('\n');
    try { data = JSON.parse(data); } catch {}
    if (event === 'start') handlers.onStart?.(data);
    else if (event === 'delta') handlers.onDelta?.(data?.content ?? String(data ?? ''));
    else if (event === 'message_end') { finalPayload = data; handlers.onEnd?.(data); }
    else if (event === 'error') {
      const msg = data?.message || '流式生成失败';
      handlers.onError?.(msg);
      throw new ApiError(msg, 500, data);
    }
    else handlers.onEvent?.(event, data);
  };

  while (true) {
    const { value, done } = await reader.read();
    if (value) {
      buffer += decoder.decode(value, { stream: !done });
      let idx;
      while ((idx = buffer.indexOf('\n\n')) >= 0) {
        const block = buffer.slice(0, idx).trim();
        buffer = buffer.slice(idx + 2);
        if (block) dispatch(block);
      }
    }
    if (done) break;
  }
  const tail = buffer.trim();
  if (tail) dispatch(tail);
  return finalPayload;
}

export const api = {
  ...baseApi,
  // 探索
  exploreSearch: (params = {}) => {
    const qs = new URLSearchParams(params);
    return rawRequest(`/go/api/explore/search?${qs}`, { auth: false });
  },
  recommendedPosts: () => rawRequest('/go/api/posts/recommended'),
  tagGroups: () => rawRequest('/go/api/explore/tag-groups'),
  installedApps: () => rawRequest('/console/api/installed-apps'),
  appDetails: (appId) => rawRequest(`/console/api/apps/${encodeURIComponent(appId)}`),
  homeStats: () => rawRequest('/console/api/web/home-stats'),
  favorites: (params = {}) => {
    const qs = new URLSearchParams(params);
    return rawRequest(`/console/api/web/favorites?${qs}`);
  },
  toggleFavorite: (appId) => rawRequest(`/console/api/web/favorites/${encodeURIComponent(appId)}/toggle`, { method: 'POST', body: {} }),
  logs: (params = {}) => {
    const qs = new URLSearchParams(params);
    return rawRequest(`/console/api/web/logs?${qs}`);
  },
  credits: () => rawRequest('/console/api/user/credits'),
  depositMeta: () => rawRequest('/console/api/web/deposit-meta'),
  redeemCode: (code) => rawRequest('/console/api/web/redeem-code', { method: 'POST', body: { code } }),
  redemptions: (params = {}) => {
    const qs = new URLSearchParams(params);
    return rawRequest(`/console/api/web/redemptions?${qs}`);
  },
  rewards: () => rawRequest('/console/api/web/rewards'),
  claimDailyReward: () => rawRequest('/console/api/web/rewards/daily', { method: 'POST', body: {} }),
  imageChat: (payload) => rawRequest('/console/api/web/image-chat', { method: 'POST', body: payload }),
  myApps: (params = {}) => {
    const qs = new URLSearchParams(params);
    return rawRequest(`/console/api/web/my-apps?${qs}`);
  },
  myAppsCount: () => rawRequest('/console/api/web/my-apps-count'),
  modelPresets: () => rawRequest('/console/api/web/model-presets'),
  providerTemplates: () => rawRequest('/console/api/web/provider-templates'),
  userModelPresets: () => rawRequest('/console/api/web/user-model-presets'),
  saveUserModelPresets: (presets) => rawRequest('/console/api/web/user-model-presets', { method: 'POST', body: { presets } }),
  updateProfile: (payload) => rawRequest('/console/api/web/profile', { method: 'POST', body: payload }),
  uploadAvatar: (image, filename = 'avatar.png') =>
    rawRequest('/console/api/web/profile/avatar', { method: 'POST', body: { image, filename } }),
  createApp: (payload) => rawRequest('/console/api/web/my-apps/create', { method: 'POST', body: payload }),
  updateApp: (appId, payload) => rawRequest(`/console/api/web/my-apps/${encodeURIComponent(appId)}/update`, { method: 'POST', body: payload }),
  deleteApp: (appId) => rawRequest(`/console/api/web/my-apps/${encodeURIComponent(appId)}/delete`, { method: 'POST', body: {} }),
  uploadCover: (image, filename = 'cover.png') =>
    rawRequest('/console/api/web/my-apps/upload-cover', { method: 'POST', body: { image, filename } }),
  // 会话
  conversations: () => rawRequest('/console/api/web/conversations'),
  messages: (convId, params = {}) => {
    const qs = new URLSearchParams(params);
    const suffix = qs.toString() ? `?${qs}` : '';
    return rawRequest(`/console/api/web/conversations/${encodeURIComponent(convId)}/messages${suffix}`);
  },
  conversationSummary: (convId) => rawRequest(`/console/api/web/conversations/${encodeURIComponent(convId)}/summary`),
  saveConversationSummary: (convId, payload) => rawRequest(`/console/api/web/conversations/${encodeURIComponent(convId)}/summary`, { method: 'POST', body: payload }),
  sendChat: (payload) => rawRequest('/console/api/web/chat', { method: 'POST', body: payload }),
  sendChatStream: (payload, handlers) => sseRequest('/console/api/web/chat/stream', payload, handlers),
  startConversation: (payload) => rawRequest('/console/api/web/conversations/start', { method: 'POST', body: payload }),
  copyConversation: (convId) => rawRequest(`/console/api/web/conversations/${encodeURIComponent(convId)}/copy`, { method: 'POST', body: {} }),
  deleteConversation: (convId) => rawRequest(`/console/api/web/conversations/${encodeURIComponent(convId)}/delete`, { method: 'POST', body: {} }),
  regenerate: (convId, modelId = '') => rawRequest('/console/api/web/regenerate', { method: 'POST', body: { conversation_id: convId, model_id: modelId || '' } }),
  swipeMessage: (messageId, dir, modelId = '') => rawRequest(`/console/api/web/messages/${encodeURIComponent(messageId)}/swipe`, { method: 'POST', body: { dir, model_id: modelId || '' } }),
  editMessage: (messageId, content) => rawRequest(`/console/api/web/messages/${encodeURIComponent(messageId)}/edit`, { method: 'POST', body: { content } }),
  rollbackMessage: (messageId) => rawRequest(`/console/api/web/messages/${encodeURIComponent(messageId)}/rollback`, { method: 'POST', body: {} }),
  deleteMessage: (messageId) => rawRequest(`/console/api/web/messages/${encodeURIComponent(messageId)}/delete`, { method: 'POST', body: {} }),
  // 群聊
  groupChats: () => rawRequest('/console/api/web/group-chats'),
  createGroupChat: (payload) => rawRequest('/console/api/web/group-chats', { method: 'POST', body: payload }),
  groupChat: (groupId) => rawRequest(`/console/api/web/group-chats/${encodeURIComponent(groupId)}`),
  deleteGroupChat: (groupId) => rawRequest(`/console/api/web/group-chats/${encodeURIComponent(groupId)}/delete`, { method: 'POST', body: {} }),
  sendGroupMessage: (groupId, payload) => rawRequest(`/console/api/web/group-chats/${encodeURIComponent(groupId)}/message`, { method: 'POST', body: payload }),
  groupReply: (groupId, payload = {}) => rawRequest(`/console/api/web/group-chats/${encodeURIComponent(groupId)}/reply`, { method: 'POST', body: payload }),
  // 人设 persona
  getPersona: () => rawRequest('/console/api/web/persona'),
  setPersona: (name, description) => rawRequest('/console/api/web/persona', { method: 'POST', body: { name, description } }),
  // 长期记忆
  memories: (params = {}) => {
    const qs = new URLSearchParams(params);
    return rawRequest(`/console/api/web/memories?${qs}`);
  },
  saveMemory: (payload) => rawRequest('/console/api/web/memories', { method: 'POST', body: payload }),
  deleteMemory: (memoryId) => rawRequest(`/console/api/web/memories/${encodeURIComponent(memoryId)}/delete`, { method: 'POST', body: {} }),
  // 角色卡导入/导出（SillyTavern V2）
  importCard: (card) => rawRequest('/console/api/web/cards/import', {
    method: 'POST',
    body: card && card.card_file ? card : { card },
  }),
  exportCard: (appId) => rawRequest(`/console/api/web/my-apps/${encodeURIComponent(appId)}/export`),
  exportCardPng: (appId) => rawRequest(`/console/api/web/my-apps/${encodeURIComponent(appId)}/export-png`),
};

// 全局工具：要求登录否则跳转到 login
export function requireAuth() {
  if (!getToken()) {
    location.replace('/app/login.html?next=' + encodeURIComponent(location.pathname));
    return false;
  }
  return true;
}

export { getToken, setToken, clearAuth, getCachedUser, setCachedUser, formatDateTime, ApiError };

window.aiXingyueApp = { api, getToken, setToken, clearAuth, getCachedUser, setCachedUser, requireAuth, ApiError };
