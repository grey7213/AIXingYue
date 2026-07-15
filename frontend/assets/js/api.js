// 惑梦（Homer） 共享 API 工具
// 同源请求，由 Nginx 反向代理到后端 Python 服务
const API_BASE = '';
const TOKEN_KEY = 'ai_xingyue_token';
const USER_KEY = 'ai_xingyue_user';

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || '';
}

export function setToken(token) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

export function getCachedUser() {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function setCachedUser(user) {
  if (user) {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  } else {
    localStorage.removeItem(USER_KEY);
  }
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function isLoggedIn() {
  return !!getToken();
}

function handleUnauthorized() {
  clearAuth();
  if (location.pathname.startsWith('/app/') && !location.pathname.endsWith('/login.html')) {
    const next = location.pathname + location.search + location.hash;
    location.replace('/app/login.html?next=' + encodeURIComponent(next));
  }
}

async function request(path, { method = 'GET', body, headers = {}, auth = true } = {}) {
  const finalHeaders = { 'Accept': 'application/json', ...headers };
  if (body !== undefined && body !== null && !(body instanceof FormData)) {
    finalHeaders['Content-Type'] = 'application/json';
  }
  if (auth) {
    const token = getToken();
    if (token) finalHeaders['Authorization'] = `Bearer ${token}`;
  }
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers: finalHeaders,
      body: body instanceof FormData ? body : (body !== undefined && body !== null ? JSON.stringify(body) : undefined),
    });
  } catch (err) {
    throw new ApiError('网络请求失败，请检查网络连接', 0, null);
  }
  const text = await response.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { raw: text };
  }
  if (response.status === 401 && auth) handleUnauthorized();
  if (!response.ok) {
    const message = (data && (data.message || data.msg)) || `HTTP ${response.status}`;
    throw new ApiError(message, response.status, data);
  }
  if (data && data.result === 'failure') {
    throw new ApiError(data.message || data.msg || '请求失败', data.code || response.status, data);
  }
  if (data && typeof data.code === 'number' && data.code !== 0 && data.msg) {
    throw new ApiError(data.msg, data.code, data);
  }
  return data;
}

export class ApiError extends Error {
  constructor(message, code, payload) {
    super(message);
    this.code = code;
    this.payload = payload;
  }
}

export const api = {
  // 公共接口
  health: () => request('/health', { auth: false }),
  siteSettings: () => request('/console/api/public/site-settings', { auth: false }),
  sendEmailCode: (email, lang = 'zh-Hans') =>
    request('/console/api/register/email', { method: 'POST', body: { email, lang }, auth: false }),
  sendPasswordResetCode: (email, lang = 'zh-Hans') =>
    request('/console/api/password-reset/email', { method: 'POST', body: { email, lang }, auth: false }),
  register: (email, password, code, name) =>
    request('/console/api/register', { method: 'POST', body: { email, password, code, name }, auth: false }),
  login: (email, password) =>
    request('/console/api/login', { method: 'POST', body: { email, password }, auth: false }),
  resetPassword: (email, password, code) =>
    request('/console/api/password-reset', { method: 'POST', body: { email, password, code }, auth: false }),

  // 用户接口
  profile: () => request('/console/api/account/profile'),
  points: () => request('/console/api/user/point'),
  credits: () => request('/console/api/user/credits'),
  redeemCode: (code) => request('/console/api/web/redeem-code', { method: 'POST', body: { code } }),
  depositMeta: () => request('/console/api/web/deposit-meta'),
  createPaymentOrder: (planId, payType) =>
    request('/console/api/web/payments/orders', { method: 'POST', body: { plan_id: planId, pay_type: payType } }),
  paymentOrder: (orderNo) => request(`/console/api/web/payments/orders/${encodeURIComponent(orderNo)}`),
  recharge: (amount, productId = 'ctf_internal_recharge_100') =>
    request('/console/api/ctf/recharge', { method: 'POST', body: { points: amount, product_id: productId } }),
  claimDaily: () => request('/console/api/ctf/dailyapppoints', { method: 'POST', body: {} }),
  myApps: (params = {}) => {
    const qs = new URLSearchParams(params);
    return request(`/console/api/web/my-apps?${qs}`);
  },
  myAppsCount: () => request('/console/api/web/my-apps-count'),
  createApp: (payload) => request('/console/api/web/my-apps/create', { method: 'POST', body: payload }),
  updateApp: (appId, payload) => request(`/console/api/web/my-apps/${encodeURIComponent(appId)}/update`, { method: 'POST', body: payload }),
  deleteApp: (appId) => request(`/console/api/web/my-apps/${encodeURIComponent(appId)}/delete`, { method: 'POST', body: {} }),
  uploadCover: (image, filename = 'cover.png') =>
    request('/console/api/web/my-apps/upload-cover', { method: 'POST', body: { image, filename } }),

  // 管理员接口
  admin: {
    whoami: () => request('/admin/api/whoami'),
    stats: () => request('/admin/api/stats'),
    users: (page = 1, limit = 20, search = '') => {
      const qs = new URLSearchParams({ page, limit, ...(search ? { search } : {}) });
      return request(`/admin/api/users?${qs}`);
    },
    adjustPoints: (userId, delta) =>
      request(`/admin/api/users/${encodeURIComponent(userId)}/points`, { method: 'POST', body: { delta } }),
    setUserAdmin: (userId, isAdmin) =>
      request(`/admin/api/users/${encodeURIComponent(userId)}/admin`, { method: 'POST', body: { is_admin: !!isAdmin } }),
    setAdvancedCreation: (userId, enabled) =>
      request(`/admin/api/users/${encodeURIComponent(userId)}/advanced-creation`, { method: 'POST', body: { enabled: !!enabled } }),
    requestLog: (page = 1, limit = 50, filters = {}) => {
      const qs = new URLSearchParams({ page, limit });
      if (filters.method) qs.set('method', filters.method);
      if (filters.path) qs.set('path', filters.path);
      return request(`/admin/api/request-log?${qs}`);
    },
    requestLogDetail: (id) => request(`/admin/api/request-log/${id}`),
    rechargeOrders: (page = 1, limit = 50) => {
      const qs = new URLSearchParams({ page, limit });
      return request(`/admin/api/recharge-orders?${qs}`);
    },
    redeemCodes: (page = 1, limit = 50, status = '') => {
      const qs = new URLSearchParams({ page, limit });
      if (status) qs.set('status', status);
      return request(`/admin/api/redeem-codes?${qs}`);
    },
    createRedeemCodes: (payload) =>
      request('/admin/api/redeem-codes/create', { method: 'POST', body: payload }),
    disableRedeemCode: (code) =>
      request(`/admin/api/redeem-codes/${encodeURIComponent(code)}/disable`, { method: 'POST', body: {} }),
    siteSettings: () => request('/admin/api/site-settings'),
    saveSiteSettings: (payload) =>
      request('/admin/api/site-settings', { method: 'POST', body: payload }),
    llmSettings: () => request('/admin/api/llm-settings'),
    saveLlmSettings: (payload) =>
      request('/admin/api/llm-settings', { method: 'POST', body: payload }),
    globalPresets: () => request('/admin/api/global-presets'),
    importGlobalPromptPreset: (payload) =>
      request('/admin/api/global-presets/import-prompt', { method: 'POST', body: payload }),
    importGlobalRegexPreset: (payload) =>
      request('/admin/api/global-presets/import-regex', { method: 'POST', body: payload }),
    saveGlobalPreset: (kind, presetId, payload) =>
      request(`/admin/api/global-presets/${encodeURIComponent(kind)}/${encodeURIComponent(presetId)}`, { method: 'POST', body: { preset: payload } }),
    activateGlobalPreset: (kind, presetId) =>
      request(`/admin/api/global-presets/${encodeURIComponent(kind)}/${encodeURIComponent(presetId)}/activate`, { method: 'POST', body: {} }),
    tavoPlugins: () => request('/admin/api/tavo-plugins'),
    importTavoPlugin: (payload) =>
      request('/admin/api/tavo-plugins/import', { method: 'POST', body: payload }),
    toggleTavoPlugin: (pluginId, enabled) =>
      request(`/admin/api/tavo-plugins/${encodeURIComponent(pluginId)}/toggle`, { method: 'POST', body: { enabled: !!enabled } }),
    deleteTavoPlugin: (pluginId) =>
      request(`/admin/api/tavo-plugins/${encodeURIComponent(pluginId)}/delete`, { method: 'POST', body: {} }),
    apps: (params = {}) => {
      const qs = new URLSearchParams(params);
      return request(`/admin/api/apps?${qs}`);
    },
    appDetail: (appId) => request(`/admin/api/apps/${encodeURIComponent(appId)}`),
    createApp: (payload) => request('/admin/api/apps/create', { method: 'POST', body: payload }),
    importApps: (payload) => request('/admin/api/apps/import', { method: 'POST', body: payload }),
    bulkUpdateApps: (payload) => request('/admin/api/apps/bulk-update', { method: 'POST', body: payload }),
    updateApp: (appId, payload) =>
      request(`/admin/api/apps/${encodeURIComponent(appId)}/update`, { method: 'POST', body: payload }),
    deleteApp: (appId) =>
      request(`/admin/api/apps/${encodeURIComponent(appId)}/delete`, { method: 'POST', body: {} }),
  },
};

export function formatDateTime(ts) {
  if (!ts) return '';
  // 支持秒和毫秒
  const ms = ts > 1e12 ? ts : ts * 1000;
  const d = new Date(ms);
  if (isNaN(d.getTime())) return '';
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

export function shortId(id, len = 8) {
  if (!id) return '';
  return String(id).length > len ? String(id).slice(0, len) + '…' : String(id);
}

window.aiXingyueApi = api;
window.aiXingyueAuth = { getToken, setToken, clearAuth, isLoggedIn, getCachedUser, setCachedUser, formatDateTime, shortId, ApiError };
