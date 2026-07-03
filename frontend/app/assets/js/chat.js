import { api, requireAuth, getCachedUser, setCachedUser, ApiError } from '/app/assets/js/app-core.js';
import { injectLayout, loadPublicSiteSettings } from '/app/assets/js/layout.js?v=20260703-channels-closed';

const STATUS_LABELS = {
  name: '姓名',
  Name: '姓名',
  hp: '生命',
  HP: '生命',
  mp: '魔力',
  MP: '魔力',
  status: '状态',
  Status: '状态',
  姓名: '姓名',
  名称: '名称',
  屬性: '属性',
  属性: '属性',
  学段: '学段',
  學段: '学段',
  时间: '时间',
  時間: '时间',
  地点: '地点',
  地點: '地点',
  H对象: '对象',
  H對象: '对象',
  对象: '对象',
  對象: '对象',
  未来事件: '未来事件',
  未來事件: '未来事件',
  目标: '目标',
  目標: '目标',
  目标进度: '目标进度',
  目標進度: '目标进度',
};

const PANEL_TITLES = {
  battle_status_panel: '战斗状态',
  status_panel: '状态',
  character_status_panel: '角色状态',
  relationship_status_panel: '关系状态',
  protagonist: '我方',
  player: '我方',
  hero: '我方',
  opponent: '对手',
  enemy: '对手',
  affection: '好感',
  relationship: '关系',
};

const LONG_TEXT_PREVIEW_CHARS = 3600;
const ADVANCED_SOURCE_PREVIEW_CHARS = 2600;
const ADVANCED_RENDER_MAX_CHARS = 450000;
const MESSAGE_LOAD_LIMIT = 80;
const ADVANCED_RENDER_SETTINGS_KEY = 'ai_xingyue_tavo_render_settings';
const ADVANCED_JS_MODES = new Set(['disabled', 'auto', 'script', 'code-block']);
const DEFAULT_ADVANCED_RENDER_SETTINGS = Object.freeze({
  enabled: true,
  javascript: 'auto',
  confirmTavoJs: true,
  formula: 'disabled',
});

function escapeHtml(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function escapeAttr(value) {
  return escapeHtml(value).replace(/`/g, '&#96;');
}

function plainTextHtml(value) {
  return escapeHtml(value).replace(/\n/g, '<br>');
}

function normalizeAdvancedRenderSettings(settings = {}) {
  const source = settings && typeof settings === 'object' ? settings : {};
  const jsMode = ADVANCED_JS_MODES.has(source.javascript) ? source.javascript : DEFAULT_ADVANCED_RENDER_SETTINGS.javascript;
  return {
    enabled: source.enabled !== false,
    javascript: jsMode,
    confirmTavoJs: source.confirmTavoJs !== false,
    formula: source.formula === true || source.formula === 'enabled' ? 'enabled' : 'disabled',
  };
}

function normalizeRenderOptions(options = {}) {
  return {
    settings: normalizeAdvancedRenderSettings(options.advancedRenderSettings || options.settings || {}),
    confirmedTavoFrames: options.confirmedTavoFrames || {},
    fromFence: !!options.fromFence,
    fenceLang: normalizeFenceLang(options.fenceLang || ''),
  };
}

function hashString(value) {
  const source = String(value || '');
  let hash = 5381;
  for (let i = 0; i < source.length; i += 1) {
    hash = ((hash << 5) + hash) ^ source.charCodeAt(i);
  }
  return (hash >>> 0).toString(36);
}

const VISIBLE_REPLY_JSON_KEYS = [
  'final', 'final_reply', 'finalResponse', 'reply', 'response', 'answer',
  'dialogue', 'narration', 'message', 'content', 'text', 'output', 'body', 'html',
];
const INTERNAL_REPLY_JSON_KEYS = new Set(['thought', 'thoughts', 'reasoning', 'analysis', 'plan', 'planning', 'scratchpad', 'debug', 'metadata']);
const INTERNAL_SECTION_MARKERS = [
  'processing', 'initial input', 'initial inputs', 'continuing narrative',
  'narrative flow', 'guiding', 'reasoning', 'analysis', 'analyzing',
  'planning', 'response plan', 'drafting', 'thought', 'internal',
  'reflection', 'deliberation', 'strategy',
];
const METADATA_FENCE_LANGS = new Set(['yaml', 'yml', 'json', 'jsonc', 'toml', 'ini', 'properties', 'meta', 'metadata']);
const METADATA_FENCE_MARKERS = [
  '{{char}}', '{{user}}', 'persona', 'personality', 'scenario', 'worldbook', 'world_info',
  'relationships', 'residence', 'creator', 'version', 'updated_at', 'update_date',
];

function singleFencedBlock(text) {
  const match = String(text || '').trim().match(/^```([a-zA-Z0-9_-]*)[ \t]*\r?\n([\s\S]*?)\r?\n?```\s*$/);
  return match ? { lang: match[1].trim().toLowerCase(), body: match[2].trim() } : null;
}

function stringFromJsonValue(value) {
  if (typeof value === 'string') return value.trim() || null;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (Array.isArray(value)) {
    const parts = value.map(item => {
      if (typeof item === 'string') return item.trim();
      if (item && typeof item === 'object') return visibleReplyFromJson(item);
      return '';
    }).filter(Boolean);
    return parts.join('\n').trim() || null;
  }
  if (value && typeof value === 'object') return visibleReplyFromJson(value);
  return null;
}

function jsonObjectToPlainText(data) {
  const rows = [];
  Object.entries(data || {}).forEach(([key, value]) => {
    const label = String(key || '').trim();
    if (!label || INTERNAL_REPLY_JSON_KEYS.has(label.toLowerCase())) return;
    const piece = stringFromJsonValue(value);
    if (piece) rows.push(`${label}：${piece}`);
  });
  return rows.join('\n').trim() || null;
}

function visibleReplyFromJson(data) {
  if (Array.isArray(data)) return stringFromJsonValue(data);
  if (data && typeof data === 'object') {
    const lowerMap = Object.fromEntries(Object.keys(data).map(key => [key.toLowerCase(), key]));
    for (const key of VISIBLE_REPLY_JSON_KEYS) {
      const actualKey = Object.prototype.hasOwnProperty.call(data, key) ? key : lowerMap[key.toLowerCase()];
      if (!actualKey) continue;
      const piece = stringFromJsonValue(data[actualKey]);
      if (piece) return piece;
    }
    const nested = data.data;
    if (nested && (typeof nested === 'object' || typeof nested === 'string')) {
      const piece = stringFromJsonValue(nested);
      if (piece) return piece;
    }
    return jsonObjectToPlainText(data);
  }
  return typeof data === 'string' ? data.trim() || null : null;
}

function extractJsonVisibleReply(text) {
  let value = String(text || '').trim();
  if (!value) return null;
  const fenced = singleFencedBlock(value);
  if (fenced && ['json', 'jsonc'].includes(fenced.lang)) value = fenced.body;
  if (!/^[\[{]/.test(value)) return null;
  try {
    return visibleReplyFromJson(JSON.parse(value));
  } catch {
    return null;
  }
}

function cleanInternalHeading(line) {
  return String(line || '')
    .trim()
    .replace(/^\s{0,3}#{1,6}\s*/, '')
    .replace(/^[*_`#\s]+|[*_`#\s]+$/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function isInternalSectionHeading(line) {
  const heading = cleanInternalHeading(line);
  if (!heading || heading.length > 120 || /[\u4e00-\u9fff]/.test(heading)) return false;
  const lower = heading.toLowerCase();
  return INTERNAL_SECTION_MARKERS.some(marker => lower.includes(marker));
}

function stripInternalMarkdownSections(text) {
  const value = String(text || '').replace(/\r\n/g, '\n').replace(/\r/g, '\n');
  if (!value.trim()) return value;
  const blocks = value.split(/\n\s*\n/);
  let changed = false;
  const kept = [];
  blocks.forEach(block => {
    const first = block.split('\n').find(line => line.trim()) || '';
    if (isInternalSectionHeading(first)) {
      changed = true;
      return;
    }
    kept.push(block.trim());
  });
  return changed ? kept.filter(Boolean).join('\n\n').trim() : value.trim();
}

function stripInternalXmlTags(text) {
  return String(text || '').replace(/<(think|thinking|reasoning|analysis|scratchpad)\b[^>]*>[\s\S]*?<\/\1>/gi, '');
}

function stripLeadingReplyLabels(text) {
  let value = String(text || '').trim();
  for (let i = 0; i < 3; i += 1) {
    const next = value.replace(/^\s*(assistant|final answer|final response|response|reply|answer|角色回复|最终回复|回复|旁白|assistant reply)\s*[:：]\s*/i, '').trim();
    if (next === value) break;
    value = next;
  }
  return value;
}

function looksLikeLeadingMetadataFence(lang, body) {
  const normalizedLang = normalizeFenceLang(lang);
  const value = String(body || '').trim();
  const lower = value.toLowerCase();
  if (lower.includes('{{char}}') || lower.includes('{{user}}')) return true;
  if (METADATA_FENCE_MARKERS.some(marker => lower.includes(marker))) return true;
  if (METADATA_FENCE_LANGS.has(normalizedLang)) {
    const colonLines = value.match(/^\s*[-\w\u4e00-\u9fff{}.$[\]"']+\s*[:=]/gm) || [];
    return colonLines.length >= 2;
  }
  return false;
}

function stripLeadingMetadataFences(text) {
  let value = String(text || '').trim();
  let changed = false;
  for (let i = 0; i < 4; i += 1) {
    const match = value.match(/^\s*```([^\r\n`]*)\r?\n([\s\S]*?)\r?\n```\s*/);
    if (!match) break;
    const rest = value.slice(match[0].length).trimStart();
    if (!rest || !looksLikeLeadingMetadataFence(match[1], match[2])) break;
    value = rest;
    changed = true;
  }
  return changed ? value : text;
}

function extractLabeledFinalReply(text) {
  const value = String(text || '').trim();
  const patterns = [
    /(?:^|\n)\s*(final answer|final response|response|reply|answer)\s*[:：]\s*([\s\S]+)$/i,
    /(?:^|\n)\s*(最终回复|角色回复|回复正文|回复)\s*[:：]\s*([\s\S]+)$/i,
  ];
  for (const pattern of patterns) {
    const match = value.match(pattern);
    if (match?.[2]?.trim()) return match[2].trim();
  }
  return null;
}

function normalizeVisibleAssistantContent(content) {
  const original = String(content == null ? '' : content).trim();
  if (!original) return '';
  let value = original;
  for (let i = 0; i < 4; i += 1) {
    const before = value;
    value = stripInternalXmlTags(value).trim();
    const labeled = extractLabeledFinalReply(value);
    if (labeled) value = labeled;
    const extracted = extractJsonVisibleReply(value);
    if (extracted) value = extracted.trim();
    value = stripInternalMarkdownSections(value);
    value = stripLeadingReplyLabels(value);
    value = stripLeadingMetadataFences(value).trim();
    const fenced = singleFencedBlock(value);
    if (fenced && ['text', 'txt', 'markdown', 'md'].includes(fenced.lang)) value = fenced.body.trim();
    if (value === before) break;
  }
  value = value.replace(/\n{4,}/g, '\n\n\n').trim();
  return value || original;
}

function visibleMessageContent(content, role = '') {
  return role === 'assistant' ? normalizeVisibleAssistantContent(content) : String(content == null ? '' : content);
}

function normalizeStatusLabel(label) {
  const key = String(label || '').replace(/\s+/g, '').trim();
  return STATUS_LABELS[key] || key || '状态';
}

function normalizeFenceLang(lang) {
  return String(lang || '').trim().toLowerCase().split(/\s+/)[0] || '';
}

function isAdvancedRenderableBlock(code, lang = '') {
  const source = String(code || '').trim();
  if (!source) return false;
  const normalizedLang = normalizeFenceLang(lang);
  const hasAnyTag = /<\s*\/?[a-zA-Z][\w:-]*(?:\s|>|\/>)/.test(source);
  if (!hasAnyTag) return false;
  if (/^(html|htm|tavo|svg|xml|xhtml)$/.test(normalizedLang)) return true;
  return /<\s*(?:!doctype|html|head|body|style|script|template|canvas|svg|details|summary|dialog|main|section|article|div|span|p|br|hr|ruby|rt|rp|table|thead|tbody|tfoot|tr|td|th|ul|ol|li|dl|dt|dd|button|input|textarea|select|option|label|img|video|audio|source|picture|figure|figcaption)\b/i.test(source);
}

function getAdvancedFenceMatches(text) {
  const matches = [];
  const fenceRe = /```([^\r\n`]*)[ \t]*\r?\n([\s\S]*?)(?:```|$)/g;
  for (const match of String(text || '').matchAll(fenceRe)) {
    if (isAdvancedRenderableBlock(match[2], match[1])) {
      matches.push({ index: match.index, end: match.index + match[0].length, lang: match[1], code: match[2] });
    }
  }
  return matches;
}

function hasAdvancedRenderableContent(content, role = '', options = {}) {
  const renderOptions = normalizeRenderOptions(options);
  if (!renderOptions.settings.enabled) return false;
  const source = visibleMessageContent(content, role);
  if (!source) return false;
  if (getAdvancedFenceMatches(source).length) return true;
  return isAdvancedRenderableBlock(source);
}

function hasStructuredStatusPanel(content, role = '') {
  return getStructuredPanelMatches(visibleMessageContent(content, role)).length > 0;
}

function messageRenderKind(content, role = '', options = {}) {
  const source = visibleMessageContent(content, role);
  const classes = [];
  if (hasAdvancedRenderableContent(source, '', options)) classes.push('has-advanced-render');
  if (hasStructuredStatusPanel(source)) classes.push('has-status-panel');
  if (source.length > LONG_TEXT_PREVIEW_CHARS) classes.push('is-long-message');
  return classes.join(' ');
}

function sourceHasExecutableScript(source) {
  const value = String(source || '');
  return /<script\b/i.test(value)
    || /\son[a-z][\w:-]*\s*=/i.test(value)
    || /\b(?:href|src|xlink:href)\s*=\s*(['"]?)\s*javascript:/i.test(value);
}

function sourceHasScriptTag(source) {
  return /<script\b/i.test(String(source || ''));
}

function advancedSourceAllowsScripts(source, options = {}) {
  const renderOptions = normalizeRenderOptions(options);
  const mode = renderOptions.settings.javascript;
  if (!renderOptions.settings.enabled || mode === 'disabled') return false;
  if (!sourceHasExecutableScript(source)) return false;
  if (mode === 'code-block' && !renderOptions.fromFence) return false;
  return true;
}

function advancedFrameKey(source) {
  return `tavo-${hashString(source)}`;
}

function advancedSourceNeedsConfirmation(source, options = {}) {
  const renderOptions = normalizeRenderOptions(options);
  if (!advancedSourceAllowsScripts(source, renderOptions)) return false;
  if (!renderOptions.settings.confirmTavoJs) return false;
  return !renderOptions.confirmedTavoFrames?.[advancedFrameKey(source)];
}

function sanitizeUrlAttribute(el, attr) {
  const value = String(el.getAttribute(attr) || '').trim();
  if (!value) return;
  if (value.startsWith('#') || /^data:/i.test(value) || /^blob:/i.test(value)) return;
  el.removeAttribute(attr);
}

function rewriteTavernHelperScript(source) {
  return String(source || '')
    .replace(/\bwindow\.parent\.SillyTavern\b/g, 'window.__xySTTop.SillyTavern')
    .replace(/\bparent\.SillyTavern\b/g, 'window.__xySTTop.SillyTavern')
    .replace(/\bwindow\.top\b/g, 'window.__xySTTop')
    .replace(/\bwindow\.localStorage\b/g, 'window.__xyLocalStorage')
    .replace(/(^|[^\w$.])localStorage\b/g, '$1window.__xyLocalStorage')
    .replace(/\bwindow\.sessionStorage\b/g, 'window.__xySessionStorage')
    .replace(/(^|[^\w$.])sessionStorage\b/g, '$1window.__xySessionStorage');
}

function serializeSafeAttrs(el, allowed = ['class', 'style', 'dir']) {
  if (!el) return '';
  const parts = [];
  for (const attr of allowed) {
    const value = el.getAttribute(attr);
    if (value) parts.push(`${attr}="${escapeAttr(value)}"`);
  }
  return parts.length ? ' ' + parts.join(' ') : '';
}

function sanitizeAdvancedHtml(raw, options = {}) {
  const source = String(raw || '').trim();
  const allowScripts = options.allowScripts !== false;
  const hasExplicitHead = /<head\b/i.test(source);
  if (typeof DOMParser === 'undefined') {
    return { head: '', body: source, bodyAttrs: '' };
  }
  const doc = new DOMParser().parseFromString(source, 'text/html');
  doc.querySelectorAll('base, iframe, object, embed, link[rel], script[src], script[data-src]').forEach(el => el.remove());
  if (!allowScripts) doc.querySelectorAll('script').forEach(el => el.remove());
  if (allowScripts) {
    doc.querySelectorAll('script:not([src])').forEach(el => {
      el.textContent = rewriteTavernHelperScript(el.textContent || '');
      if (String(el.getAttribute('type') || '').trim().toLowerCase() === 'module') {
        el.removeAttribute('type');
      }
    });
  }
  doc.querySelectorAll('meta[http-equiv]').forEach(el => {
    const equiv = String(el.getAttribute('http-equiv') || '').toLowerCase();
    if (equiv.includes('refresh') || equiv.includes('content-security-policy')) el.remove();
  });
  doc.querySelectorAll('*').forEach(el => {
    ['src', 'href', 'xlink:href', 'poster', 'formaction', 'action'].forEach(attr => {
      if (el.hasAttribute(attr)) sanitizeUrlAttribute(el, attr);
    });
    ['srcset', 'ping', 'integrity'].forEach(attr => el.removeAttribute(attr));
    if (!allowScripts) {
      Array.from(el.attributes || []).forEach(attr => {
        if (/^on/i.test(attr.name)) el.removeAttribute(attr.name);
      });
    } else {
      Array.from(el.attributes || []).forEach(attr => {
        if (/^on/i.test(attr.name)) el.setAttribute(attr.name, rewriteTavernHelperScript(attr.value || ''));
      });
    }
  });
  const parsedHead = doc.head ? doc.head.innerHTML : '';
  const parsedBody = doc.body ? doc.body.innerHTML : source;
  return {
    head: hasExplicitHead ? parsedHead : '',
    body: hasExplicitHead ? parsedBody : `${parsedHead}${parsedBody}`,
    bodyAttrs: serializeSafeAttrs(doc.body),
  };
}

function buildTavoBridgeScript() {
  return `
    (() => {
      const listeners = Object.create(null);
      const state = Object.create(null);
      const storageBag = Object.create(null);
      const storage = {
        get length() { return Object.keys(storageBag).length; },
        key(index) { return Object.keys(storageBag)[Number(index)] || null; },
        getItem(name) {
          name = String(name);
          return Object.prototype.hasOwnProperty.call(storageBag, name) ? storageBag[name] : null;
        },
        setItem(name, value) { storageBag[String(name)] = String(value); },
        removeItem(name) { delete storageBag[String(name)]; },
        clear() { Object.keys(storageBag).forEach(key => delete storageBag[key]); },
      };
      window.addEventListener('error', event => {
        const message = String((event && (event.message || (event.error && event.error.message))) || '');
        if (message.includes('localStorage') && message.includes('sandboxed')) event.preventDefault();
        if (message.includes('sessionStorage') && message.includes('sandboxed')) event.preventDefault();
      }, true);
      const height = () => {
        const root = document.documentElement;
        const body = document.body;
        return Math.ceil(Math.max(root.scrollHeight, body ? body.scrollHeight : 0, 260));
      };
      const resize = () => {
        try { parent.postMessage({ type: 'xy-tavo-resize', height: height() }, '*'); } catch (e) {}
      };
      const clone = value => {
        try { return JSON.parse(JSON.stringify(value)); } catch (e) { return value; }
      };
      const rawText = () => {
        const raw = document.getElementById('raw-data-store');
        return raw ? raw.textContent || raw.innerText || '' : '';
      };
      const currentMessage = () => ({ mes: rawText(), name: 'assistant', is_system: false, is_user: false });
      const context = {
        get chat() { return [currentMessage()]; },
        saveChat() { return Promise.resolve(true); },
      };
      const topProxy = {};
      Object.defineProperties(topProxy, {
        document: { get() { return document; } },
        SillyTavern: { value: { getContext() { return context; } } },
        context: { get() { return context; } },
        localStorage: { get() { return storage; } },
        sessionStorage: { get() { return storage; } },
        pageXOffset: { get() { return window.pageXOffset || 0; } },
        pageYOffset: { get() { return window.pageYOffset || 0; } },
        innerWidth: { get() { return window.innerWidth; } },
        innerHeight: { get() { return window.innerHeight; } },
        visualViewport: { get() { return window.visualViewport || { width: window.innerWidth, height: window.innerHeight }; } },
        location: { value: { reload() { resize(); } } },
      });
      topProxy.getComputedStyle = el => window.getComputedStyle(el);
      topProxy.scrollTo = (...args) => { try { window.scrollTo(...args); } catch (e) {} };
      topProxy.updateMessageBlock = (idx, msg) => {
        try {
          const raw = document.getElementById('raw-data-store');
          if (raw && msg && typeof msg.mes === 'string') raw.textContent = msg.mes;
          resize();
        } catch (e) {}
      };
      const emptyWorldNames = () => [];
      const emptyWorld = () => Promise.resolve([]);
      window.__xyLocalStorage = storage;
      window.__xySessionStorage = storage;
      window.__xySTTop = topProxy;
      try { Object.defineProperty(window, 'localStorage', { value: storage, configurable: true }); } catch (e) {}
      try { Object.defineProperty(window, 'sessionStorage', { value: storage, configurable: true }); } catch (e) {}
      window.context = context;
      window.SillyTavern = topProxy.SillyTavern;
      window.getCharWorldbookNames = () => ({ primary: '', additional: [] });
      window.getChatWorldbookName = () => '';
      window.getGlobalWorldbookNames = emptyWorldNames;
      window.getWorldbook = emptyWorld;
      window.updateWorldbookWith = (name, updater) => emptyWorld().then(entries => {
        try { return typeof updater === 'function' ? updater(entries) : entries; } catch (e) { return entries; }
      });
      const api = {
        version: 'ai-xingyue-safe',
        notify(message) {
          try { parent.postMessage({ type: 'xy-tavo-notify', message: String(message || '').slice(0, 200) }, '*'); } catch (e) {}
          return true;
        },
        resize() { resize(); return true; },
        emit(name, detail) {
          (listeners[String(name)] || []).slice().forEach(fn => { try { fn(detail); } catch (e) {} });
          return true;
        },
        on(name, fn) {
          name = String(name);
          if (typeof fn !== 'function') return () => {};
          (listeners[name] || (listeners[name] = [])).push(fn);
          return () => { listeners[name] = (listeners[name] || []).filter(item => item !== fn); };
        },
        getState() { return clone(state); },
        setState(patch) {
          if (patch && typeof patch === 'object') Object.assign(state, patch);
          resize();
          return clone(state);
        },
        getVar(name) { return state[String(name)]; },
        setVar(name, value) {
          state[String(name)] = value;
          resize();
          return value;
        },
        confirm(action) {
          try { parent.postMessage({ type: 'xy-tavo-confirm-request', action: String(action || '').slice(0, 120) }, '*'); } catch (e) {}
          return false;
        },
        request() { return Promise.reject(new Error('Network access is disabled in AI星月 Tavo sandbox')); },
      };
      Object.defineProperty(window, 'TavoJS', { value: api, configurable: false, writable: false });
      window.tavo = api;
      window.Tavo = api;
      try { window.alert = message => api.notify(message); } catch (e) {}
    })();
  `;
}

function buildSandboxSrcdoc(raw, options = {}) {
  const allowScripts = options.allowScripts !== false;
  const sanitized = sanitizeAdvancedHtml(raw, { allowScripts });
  const tavoThemeVars = [
    '--SmartThemeBodyColor:#ffffff',
    '--SmartThemeEmColor:rgba(255,255,255,.92)',
    '--SmartThemeQuoteColor:#a1cdee',
    '--SmartThemeBlurTintColor:rgba(34,34,34,.88)',
    '--SmartThemeChatTintColor:#222222',
    '--SmartThemeBotMesBlurTintColor:rgba(43,81,110,.80)',
    '--SmartThemeUserMesBlurTintColor:rgba(86,86,87,.80)',
    '--SmartThemeBorderColor:rgba(255,255,255,.24)',
    '--SmartThemeShadowColor:rgba(0,0,0,.45)',
    '--SmartThemeFastUIBGColor:rgba(202,204,209,.40)',
    '--SmartThemeFastUITextColor:#ffffff',
    '--SmartThemeInputColor:rgba(202,204,209,.40)',
    '--SmartThemeButtonAccentColor:#a1cdee',
    '--xy-tavo-bg:#222222',
    '--xy-tavo-panel:rgba(43,81,110,.80)',
    '--xy-tavo-panel-alt:rgba(86,86,87,.80)',
    '--xy-tavo-text:#ffffff',
    '--xy-tavo-muted:rgba(255,255,255,.80)',
  ].join(';');
  const csp = [
    "default-src 'none'",
    "img-src data: blob:",
    "media-src data: blob:",
    "font-src data:",
    "style-src 'unsafe-inline'",
    allowScripts ? "script-src 'unsafe-inline'" : "script-src 'none'",
    "connect-src 'none'",
    "frame-src 'none'",
    "worker-src 'none'",
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'none'",
  ].join('; ');
  const baseStyle = `
    :root{${tavoThemeVars};color-scheme:dark;}
    html,body{margin:0;min-height:100%;background:var(--SmartThemeChatTintColor,#222222);color:var(--SmartThemeBodyColor,#ffffff);font-family:"Inter","PingFang SC","Microsoft YaHei",system-ui,sans-serif;}
    *{box-sizing:border-box;max-width:100%;}
    body{overflow:auto;accent-color:var(--SmartThemeQuoteColor,#a1cdee);}
    #chat,.chat,.chat-messages,.mes,.message,.mes_text,.mes-text,.message-content,.tavo-content{width:100%;min-height:100%;}
    .mes,.message,.mes_text,.mes-text,.message-content,.tavo-content{color:var(--SmartThemeBodyColor,#ffffff);}
    .mes_text:empty,.message-content:empty,.tavo-content:empty{min-height:260px;}
    button,input,textarea,select{font:inherit;color:inherit;background-color:rgba(255,255,255,.08);border:1px solid var(--SmartThemeBorderColor,rgba(255,255,255,.24));}
    button{cursor:pointer;}
    input::placeholder,textarea::placeholder{color:var(--xy-tavo-muted,rgba(255,255,255,.80));}
    img,video,canvas,svg{max-width:100%;}
    a{color:inherit;}
  `;
  const resizeScript = `
    (()=>{let last=0;const send=()=>{const root=document.documentElement;const body=document.body;const h=Math.ceil(Math.max(root.scrollHeight,body?body.scrollHeight:0,260));if(Math.abs(h-last)>4){last=h;parent.postMessage({type:'xy-tavo-resize',height:h},'*');}};addEventListener('load',send);try{new ResizeObserver(send).observe(document.documentElement);if(document.body)new ResizeObserver(send).observe(document.body);}catch(e){}setTimeout(send,80);setTimeout(send,600);})();
  `;
  const bridge = allowScripts ? `<script>${buildTavoBridgeScript()}<\/script>` : '';
  const resize = allowScripts ? `<script>${resizeScript}<\/script>` : '';
  const rawStore = /id=["']raw-data-store["']/i.test(sanitized.body)
    ? ''
    : `<textarea id="raw-data-store" hidden aria-hidden="true">${escapeHtml(sanitized.body)}</textarea>`;
  const compatBody = `<div id="chat" class="chat chat-messages"><div class="mes message assistant" data-role="assistant"><div id="message-content" class="mes_text mes-text message-content markdown-body tavo-content">${sanitized.body}</div></div></div>`;
  return `<!doctype html><html style="${escapeAttr(tavoThemeVars)}"><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="${escapeAttr(csp)}"><style>${baseStyle}</style>${bridge}${sanitized.head}</head><body${sanitized.bodyAttrs}>${rawStore}${compatBody}${resize}</body></html>`;
}

function renderAdvancedSourcePreview(code) {
  return '';
}

function renderAdvancedPausedCard(source, title, status, actionHtml = '') {
  return `<section class="tavo-frame-card is-paused"><div class="tavo-frame-card__bar"><span>${escapeHtml(title)}</span><span>${escapeHtml(status)}</span></div>${actionHtml}${renderAdvancedSourcePreview(source)}</section>`;
}

function renderAdvancedFrame(code, options = {}) {
  const source = String(code || '').trim();
  if (!source) return '';
  const renderOptions = normalizeRenderOptions(options);
  if (!renderOptions.settings.enabled) {
    return renderAdvancedPausedCard(source, '高级渲染', '已关闭');
  }
  if (source.length > ADVANCED_RENDER_MAX_CHARS) {
    return renderAdvancedPausedCard(source, '可视化', '内容过大');
  }
  const allowScripts = advancedSourceAllowsScripts(source, renderOptions);
  if (advancedSourceNeedsConfirmation(source, renderOptions)) {
    const key = advancedFrameKey(source);
    const action = `<div class="tavo-confirm"><button type="button" class="tavo-run-btn" data-tavo-key="${escapeAttr(key)}">启用 TavoJS</button><span>隔离执行</span></div>`;
    return renderAdvancedPausedCard(source, 'TavoJS', '等待确认', action);
  }
  const srcdoc = buildSandboxSrcdoc(source, { allowScripts });
  const sandbox = allowScripts ? 'allow-scripts' : '';
  const status = allowScripts ? '隔离 TavoJS' : '静态渲染';
  return `<section class="tavo-frame-card"><div class="tavo-frame-card__bar"><span>可视化</span><span>${status}</span></div><iframe class="tavo-frame" sandbox="${sandbox}" referrerpolicy="no-referrer" loading="lazy" srcdoc="${escapeAttr(srcdoc)}"></iframe>${renderAdvancedSourcePreview(source)}</section>`;
}

function formulasEnabled(options = {}) {
  return normalizeRenderOptions(options).settings.formula === 'enabled';
}

function renderInlineFormulaText(text) {
  const source = String(text || '');
  if (!source) return '';
  const inlineRe = /\\\(([\s\S]*?)\\\)/g;
  let html = '';
  let cursor = 0;
  for (const match of source.matchAll(inlineRe)) {
    html += plainTextHtml(source.slice(cursor, match.index));
    html += `<span class="math-inline">${escapeHtml(match[1].trim())}</span>`;
    cursor = match.index + match[0].length;
  }
  html += plainTextHtml(source.slice(cursor));
  return html;
}

function renderFormulaText(text) {
  const source = String(text || '');
  const displayRe = /\$\$([\s\S]*?)\$\$/g;
  let html = '';
  let cursor = 0;
  for (const match of source.matchAll(displayRe)) {
    html += renderInlineFormulaText(source.slice(cursor, match.index));
    html += `<div class="math-block">${escapeHtml(match[1].trim())}</div>`;
    cursor = match.index + match[0].length;
  }
  html += renderInlineFormulaText(source.slice(cursor));
  return html;
}

function renderTextWithFormulaFences(text) {
  const source = String(text || '');
  const fenceRe = /```(math|latex|tex|asciimath)[ \t]*\r?\n([\s\S]*?)```/gi;
  let html = '';
  let cursor = 0;
  for (const match of source.matchAll(fenceRe)) {
    html += renderFormulaText(source.slice(cursor, match.index));
    const lang = normalizeFenceLang(match[1]);
    const label = lang === 'asciimath' ? 'AsciiMath' : 'LaTeX';
    html += `<div class="math-block"><span class="math-block__label">${label}</span>${escapeHtml(match[2].trim())}</div>`;
    cursor = match.index + match[0].length;
  }
  html += renderFormulaText(source.slice(cursor));
  return html;
}

function renderPlainTextOnly(text, options = {}) {
  const value = String(text || '');
  if (!value) return '';
  const textHtml = (part) => formulasEnabled(options) ? renderTextWithFormulaFences(part) : plainTextHtml(part);
  if (value.length <= LONG_TEXT_PREVIEW_CHARS) {
    return `<div class="msg-text">${textHtml(value)}</div>`;
  }
  const head = value.slice(0, LONG_TEXT_PREVIEW_CHARS);
  const tail = value.slice(LONG_TEXT_PREVIEW_CHARS);
  return `<div class="msg-text">${textHtml(head)}</div><details class="msg-expand"><summary>展开完整内容</summary><div class="msg-text">${textHtml(tail)}</div></details>`;
}

function renderPlainTextSegment(text, options = {}) {
  const value = String(text || '');
  if (!value) return '';
  const trimmed = value.trim();
  const renderOptions = normalizeRenderOptions(options);
  if (renderOptions.settings.enabled && isAdvancedRenderableBlock(trimmed)) return renderAdvancedFrame(trimmed, options);
  return renderPlainTextOnly(value, options);
}

function renderTextWithAdvancedBlocks(text, options = {}) {
  const value = String(text || '');
  if (!value) return '';
  const renderOptions = normalizeRenderOptions(options);
  if (!renderOptions.settings.enabled) return renderPlainTextOnly(value, options);
  const matches = getAdvancedFenceMatches(value);
  if (!matches.length) return renderPlainTextSegment(value, options);
  let html = '';
  let cursor = 0;
  for (const item of matches) {
    html += renderPlainTextSegment(value.slice(cursor, item.index), options);
    html += renderAdvancedFrame(item.code, { ...options, fromFence: true, fenceLang: item.lang });
    cursor = item.end;
  }
  html += renderPlainTextSegment(value.slice(cursor), options);
  return html;
}

function parseStatusRows(raw) {
  const text = String(raw || '').trim();
  const matches = Array.from(text.matchAll(/\[([^\]\n]{1,24})\]/g));
  if (!matches.length) return [];
  const rows = [];
  for (let i = 0; i < matches.length; i += 1) {
    const match = matches[i];
    const next = matches[i + 1];
    const label = normalizeStatusLabel(match[1]);
    const start = match.index + match[0].length;
    const end = next ? next.index : text.length;
    const value = text.slice(start, end).trim();
    if (value) rows.push({ label, value });
  }
  return rows;
}

function normalizePanelTag(tag) {
  return String(tag || '').trim().replace(/-/g, '_').toLowerCase();
}

function panelTitle(tag) {
  const normalized = normalizePanelTag(tag);
  if (PANEL_TITLES[normalized]) return PANEL_TITLES[normalized];
  return normalized
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase())
    .replace(/\bStatus Panel\b/i, '状态');
}

function isStructuredPanelTag(tag) {
  const normalized = normalizePanelTag(tag);
  return normalized === 'status_panel'
    || normalized.endsWith('_status_panel')
    || normalized.endsWith('_status')
    || normalized === 'battle_status_panel';
}

function getStructuredPanelMatches(text) {
  const source = String(text || '');
  const matches = [];
  const re = /<([a-zA-Z][\w:-]*)>\s*([\s\S]*?)\s*<\/\1>/g;
  for (const match of source.matchAll(re)) {
    if (!isStructuredPanelTag(match[1])) continue;
    matches.push({ index: match.index, end: match.index + match[0].length, tag: match[1], body: match[2] });
  }
  return matches;
}

function stripWrappingBrackets(line) {
  const value = String(line || '').trim();
  const match = value.match(/^\[([\s\S]*)\]$/);
  return match ? match[1].trim() : value;
}

function parseLooseStatusRows(raw) {
  const rows = [];
  const lines = String(raw || '')
    .replace(/\r/g, '')
    .split('\n')
    .map(line => stripWrappingBrackets(line))
    .filter(Boolean);
  for (const line of lines) {
    const pipeParts = line.split('|').map(part => part.trim()).filter(Boolean);
    if (pipeParts.length >= 2) {
      rows.push({ label: normalizeStatusLabel(pipeParts[0]), value: pipeParts.slice(1).join(' / ') });
      continue;
    }
    const colon = line.match(/^([^:：]{1,24})[:：]\s*(.+)$/);
    if (colon) {
      rows.push({ label: normalizeStatusLabel(colon[1]), value: colon[2].trim() });
      continue;
    }
    rows.push({ label: '', value: line });
  }
  return rows;
}

function renderStatusRows(rows) {
  return rows.map(row => {
    if (!row.label) {
      return `<div class="status-card__line">${plainTextHtml(row.value)}</div>`;
    }
    return `<div class="status-card__row"><div class="status-card__label">${escapeHtml(row.label)}</div><div class="status-card__value">${plainTextHtml(row.value)}</div></div>`;
  }).join('');
}

function renderStatusBlock(raw) {
  const rows = parseStatusRows(raw);
  if (!rows.length) {
    return `<section class="status-card"><div class="status-card__title">状态</div><div class="msg-text">${plainTextHtml(raw)}</div></section>`;
  }
  const body = renderStatusRows(rows);
  return `<section class="status-card"><div class="status-card__title">状态</div>${body}</section>`;
}

function renderStructuredStatusPanel(tag, raw) {
  const source = String(raw || '').trim();
  const groups = [];
  const childRe = /<([a-zA-Z][\w:-]*)>\s*([\s\S]*?)\s*<\/\1>/g;
  for (const child of source.matchAll(childRe)) {
    const rows = parseLooseStatusRows(child[2]);
    if (rows.length) groups.push({ title: panelTitle(child[1]), rows });
  }
  if (!groups.length) {
    const rows = parseLooseStatusRows(source);
    const body = rows.length ? renderStatusRows(rows) : `<div class="msg-text">${plainTextHtml(source)}</div>`;
    return `<section class="status-card structured-status-card"><div class="status-card__title">${escapeHtml(panelTitle(tag))}</div>${body}</section>`;
  }
  const body = groups.map(group => (
    `<div class="status-card__group"><div class="status-card__group-title">${escapeHtml(group.title)}</div>${renderStatusRows(group.rows)}</div>`
  )).join('');
  return `<section class="status-card structured-status-card"><div class="status-card__title">${escapeHtml(panelTitle(tag))}</div>${body}</section>`;
}

function renderTextWithStatusPanels(text, options = {}) {
  const value = String(text || '');
  const matches = getStructuredPanelMatches(value);
  if (!matches.length) return renderTextWithAdvancedBlocks(value, options);
  let html = '';
  let cursor = 0;
  for (const item of matches) {
    html += renderTextWithAdvancedBlocks(value.slice(cursor, item.index), options);
    html += renderStructuredStatusPanel(item.tag, item.body);
    cursor = item.end;
  }
  html += renderTextWithAdvancedBlocks(value.slice(cursor), options);
  return html;
}

function renderMessageContent(content, role = '', options = {}) {
  const source = visibleMessageContent(content, role);
  if (!source) return '';
  const re = /<StatusBlock>([\s\S]*?)<\/StatusBlock>/gi;
  let html = '';
  let lastIndex = 0;
  for (const match of source.matchAll(re)) {
    html += renderTextWithStatusPanels(source.slice(lastIndex, match.index), options);
    html += renderStatusBlock(match[1]);
    lastIndex = match.index + match[0].length;
  }
  html += renderTextWithStatusPanels(source.slice(lastIndex), options);
  return html || renderPlainTextSegment(source, options);
}

function bindTavoFrameResizeListener() {
  if (typeof window === 'undefined' || window.__xyTavoResizeBound) return;
  window.__xyTavoResizeBound = true;
  window.addEventListener('message', (event) => {
    const data = event?.data || {};
    if (data.type !== 'xy-tavo-resize') return;
    const height = Math.max(260, Math.min(parseInt(data.height, 10) || 0, 860));
    if (!height) return;
    document.querySelectorAll('iframe.tavo-frame').forEach(frame => {
      if (frame.contentWindow === event.source) frame.style.height = `${height}px`;
    });
  });
  document.addEventListener('click', (event) => {
    const button = event.target?.closest?.('.tavo-run-btn');
    if (!button) return;
    const key = button.getAttribute('data-tavo-key') || '';
    if (key && typeof window.__xyConfirmTavoRender === 'function') {
      window.__xyConfirmTavoRender(key);
    }
  });
}

if (typeof window !== 'undefined') {
  window.__xyRenderMessageContent = renderMessageContent;
  window.__xyMessageRenderKind = messageRenderKind;
  window.__xyBuildSandboxSrcdoc = buildSandboxSrcdoc;
  window.__xyNormalizeVisibleAssistantContent = normalizeVisibleAssistantContent;
  window.__xyNormalizeAdvancedRenderSettings = normalizeAdvancedRenderSettings;
  bindTavoFrameResizeListener();
}

function chatPage() {
  return {
    user: null,
    points: 0,
    sidebarOpen: false,
    listOpen: false,
    conversations: [],
    conversation: null,
    messages: [],
    draft: '',
    replying: false,
    listening: false,
    busy: false,
    appId: '',
    appName: '',
    appDesc: '',
    appIcon: '',
    appHero: '',
    quickReplies: [],
    editingId: '',
    editingText: '',
    memoryOpen: false,
    advancedRenderOpen: false,
    advancedRenderSettings: { ...DEFAULT_ADVANCED_RENDER_SETTINGS },
    confirmedTavoFrames: {},
    confirmedTavoRenderVersion: 0,
    memories: [],
    summary: null,
    summaryDraft: '',
    memoryDraft: { title: '', content: '', keywords: '', pinned: true },
    savingMemory: false,
    savingSummary: false,
    modelPresets: [],
    currentModelId: '',
    messageLimit: MESSAGE_LOAD_LIMIT,
    messageTotal: 0,
    hasOlderMessages: false,
    loadingOlderMessages: false,
    _typeTimer: null,
    siteSettings: null,

    async init() {
      injectLayout('chat');
      this.loadAdvancedRenderSettings();
      this.bindAdvancedRenderConfirmHandler();
      this.siteSettings = await loadPublicSiteSettings().catch(() => null);
      if (!requireAuth()) return;
      const cached = getCachedUser();
      if (cached) this.user = cached;
      try {
        const profile = await api.profile();
        this.user = profile;
        setCachedUser(profile);
        const p = await api.points();
        this.points = parseInt(p.points || p.data?.points || 0, 10);
        await this.loadModelPresets();
      } catch (err) {
        if (err instanceof ApiError && err.code === 401) {
          location.replace('/app/login.html?next=' + encodeURIComponent(location.pathname + location.search));
          return;
        }
      }

      await this.loadConversations();

      const params = new URLSearchParams(location.search);
      const incomingAppId = params.get('app_id');
      const incomingConvId = params.get('conv_id');
      if (incomingConvId) {
        const c = this.conversations.find(x => x.id === incomingConvId);
        if (c) { await this.selectConversation(c); return; }
      }
      if (incomingAppId) {
        await this.startWithApp(incomingAppId);
      } else if (this.conversations.length > 0) {
        await this.selectConversation(this.conversations[0]);
      }
    },

    chatText(key, fallback = '') {
      return this.siteSettings?.chat?.[key] || fallback;
    },

    loadAdvancedRenderSettings() {
      try {
        const raw = localStorage.getItem(ADVANCED_RENDER_SETTINGS_KEY);
        this.advancedRenderSettings = normalizeAdvancedRenderSettings(raw ? JSON.parse(raw) : DEFAULT_ADVANCED_RENDER_SETTINGS);
      } catch {
        this.advancedRenderSettings = { ...DEFAULT_ADVANCED_RENDER_SETTINGS };
      }
    },

    saveAdvancedRenderSettings() {
      this.advancedRenderSettings = normalizeAdvancedRenderSettings(this.advancedRenderSettings);
      try {
        localStorage.setItem(ADVANCED_RENDER_SETTINGS_KEY, JSON.stringify(this.advancedRenderSettings));
      } catch { /* ignore private mode storage errors */ }
      this.confirmedTavoFrames = {};
      this.confirmedTavoRenderVersion += 1;
    },

    updateAdvancedRenderSettings(patch = {}) {
      this.advancedRenderSettings = normalizeAdvancedRenderSettings({
        ...this.advancedRenderSettings,
        ...patch,
      });
      this.saveAdvancedRenderSettings();
    },

    toggleAdvancedRenderPanel() {
      this.advancedRenderOpen = !this.advancedRenderOpen;
      if (this.advancedRenderOpen) this.memoryOpen = false;
    },

    toggleAdvancedRenderEnabled() {
      this.updateAdvancedRenderSettings({ enabled: !this.advancedRenderSettings.enabled });
    },

    setAdvancedJsMode(mode) {
      if (!ADVANCED_JS_MODES.has(mode)) return;
      this.updateAdvancedRenderSettings({ javascript: mode });
    },

    toggleTavoConfirmation() {
      this.updateAdvancedRenderSettings({ confirmTavoJs: !this.advancedRenderSettings.confirmTavoJs });
    },

    setFormulaMode(mode) {
      this.updateAdvancedRenderSettings({ formula: mode === 'enabled' ? 'enabled' : 'disabled' });
    },

    bindAdvancedRenderConfirmHandler() {
      window.__xyConfirmTavoRender = (key) => {
        if (!key) return;
        this.confirmedTavoFrames = { ...this.confirmedTavoFrames, [key]: true };
        this.confirmedTavoRenderVersion += 1;
        this.scrollToBottom();
      };
    },

    advancedRenderOptions() {
      this.confirmedTavoRenderVersion;
      return {
        advancedRenderSettings: this.advancedRenderSettings,
        confirmedTavoFrames: this.confirmedTavoFrames,
      };
    },

    renderMessageContent(content, role = '') {
      return renderMessageContent(content, role, this.advancedRenderOptions());
    },

    messageRenderKind(content, role = '') {
      return messageRenderKind(content, role, this.advancedRenderOptions());
    },

    rowClass(m) {
      return [
        m?.role === 'user' ? 'user' : 'assistant',
        messageRenderKind(m?.content, m?.role, this.advancedRenderOptions()),
      ].filter(Boolean).join(' ');
    },

    bubbleClass(m) {
      return [
        m?.role === 'user' ? 'user' : 'assistant',
        messageRenderKind(m?.content, m?.role, this.advancedRenderOptions()),
        m?.role === 'assistant' && m?._typing && !m?.content ? 'is-loading' : '',
      ].filter(Boolean).join(' ');
    },

    async loadModelPresets() {
      try {
        const r = await api.modelPresets();
        const data = r?.data || r || {};
        this.modelPresets = (data.list || []).filter(p => p.enabled !== false && p.id);
      } catch {
        this.modelPresets = [];
      }
    },

    modelStorageKey(appId = this.appId) {
      return `ai_xingyue_chat_model:${appId || 'global'}`;
    },

    restoreModelSelection() {
      const stored = localStorage.getItem(this.modelStorageKey()) || '';
      this.currentModelId = this.modelPresets.some(p => p.id === stored) ? stored : '';
    },

    persistModelSelection() {
      if (!this.appId) return;
      if (this.currentModelId) localStorage.setItem(this.modelStorageKey(), this.currentModelId);
      else localStorage.removeItem(this.modelStorageKey());
    },

    modelOptionLabel(preset) {
      const name = preset?.name || preset?.model || preset?.id || '';
      const model = preset?.model || '';
      return model && model !== name ? `${name} · ${model}` : name;
    },

    updatePointsFromPayload(payload) {
      const data = payload?.data || payload || {};
      const balance = data.balance || payload?.balance || {};
      const raw = data.points ?? balance.points ?? payload?.points;
      const next = parseInt(raw, 10);
      if (!Number.isNaN(next)) this.points = next;
    },

    async loadConversations() {
      try {
        const r = await api.conversations();
        this.conversations = (r?.data?.list || r?.list || []);
      } catch {
        this.conversations = [];
      }
    },

    async startWithApp(appId) {
      this.appId = appId;
      // 拉详情用于头图展示
      try {
        const r = await api.appDetails(appId);
        const data = r?.data || r;
        this.appName = data?.name || this.chatText('new_role_name', '新角色');
        this.appDesc = data?.description || data?.summary || '';
        this.appIcon = data?.icon || data?.icon_url || data?.cover || '';
        this.appHero = data?.bg_url || data?.cover || data?.cover_url || data?.banner || data?.background || '';
        this.quickReplies = Array.isArray(data?.quick_replies) ? data.quick_replies.filter(q => q.enabled !== false && q.message) : [];
        this.restoreModelSelection();
      } catch {
        this.appName = this.chatText('new_role_name', '新角色');
        this.quickReplies = [];
        this.restoreModelSelection();
      }
      // 已有该角色的会话 → 直接进入最近一个
      const existing = this.conversations.find(c => c.app_id === appId);
      if (existing) {
        await this.selectConversation(existing);
        return;
      }
      // 否则开新会话（后端会把开场白写成首条消息）
      await this.newChat();
    },

    async newChat() {
      if (!this.appId) return;
      this.busy = true;
      try {
        const r = await api.startConversation({ app_id: this.appId, app_name: this.appName, app_icon: this.appIcon });
        const data = r?.data || r;
        this.conversation = {
          id: data.conversation_id,
          app_id: this.appId,
          app_name: this.appName || data.app_name,
          app_icon: this.appIcon || data.app_icon,
          title: this.appName || this.chatText('new_chat_title', '新对话'),
        };
        this.messages = (data.messages || []).map(this.normMsg);
        this.messageTotal = this.messages.length;
        this.hasOlderMessages = false;
        await this.loadConversations();
        await this.loadMemoryContext();
        this.scrollToBottom();
      } catch (err) {
        this.messages = [];
        this.conversation = null;
      } finally {
        this.busy = false;
      }
    },

    normMsg(m) {
      return {
        id: m.id,
        role: m.role,
        content: m.content || '',
        created_at: m.created_at,
        swipes: Array.isArray(m.swipes) ? m.swipes : [],
        swipe_index: typeof m.swipe_index === 'number' ? m.swipe_index : 0,
        _typing: false,
      };
    },

    async selectConversation(c) {
      this.conversation = c;
      this.appId = c.app_id;
      this.appName = c.app_name || c.title || this.chatText('conversation_fallback_title', '对话');
      this.appIcon = c.app_icon || '';
      this.restoreModelSelection();
      this.listOpen = false;
      this.messages = [];
      this.messageTotal = 0;
      this.hasOlderMessages = false;
      // 补头图：拉一次角色详情（容错）
      try {
        const r = await api.appDetails(c.app_id);
        const data = r?.data || r;
        this.appHero = data?.bg_url || data?.cover || data?.cover_url || '';
        this.appDesc = data?.description || data?.summary || '';
        if (!this.appIcon) this.appIcon = data?.icon || data?.cover || '';
        this.quickReplies = Array.isArray(data?.quick_replies) ? data.quick_replies.filter(q => q.enabled !== false && q.message) : [];
      } catch { this.appHero = ''; this.quickReplies = []; }
      try {
        const r = await api.messages(c.id, { limit: this.messageLimit });
        const data = r?.data || r || {};
        const list = data.list || [];
        this.messages = list.map(this.normMsg);
        const total = parseInt(data.total ?? list.length, 10);
        this.messageTotal = Number.isNaN(total) ? list.length : total;
        this.hasOlderMessages = !!data.has_more || this.messages.length < this.messageTotal;
        await this.loadMemoryContext();
        this.scrollToBottom();
      } catch (err) {
        this.messages = [];
        this.messageTotal = 0;
        this.hasOlderMessages = false;
      }
    },

    async loadOlderMessages() {
      if (!this.conversation?.id || !this.messages.length || this.loadingOlderMessages || !this.hasOlderMessages) return;
      const first = this.messages[0];
      const before = parseInt(first?.created_at || 0, 10);
      if (!before) return;
      const area = this.$refs.messageArea;
      const previousHeight = area ? area.scrollHeight : 0;
      const previousTop = area ? area.scrollTop : 0;
      this.loadingOlderMessages = true;
      try {
        const r = await api.messages(this.conversation.id, { limit: this.messageLimit, before });
        const data = r?.data || r || {};
        const list = data.list || [];
        const existing = new Set(this.messages.map(m => m.id));
        const older = list.map(this.normMsg).filter(m => !existing.has(m.id));
        if (older.length) this.messages = older.concat(this.messages);
        const total = parseInt(data.total ?? this.messageTotal, 10);
        this.messageTotal = Number.isNaN(total) ? this.messageTotal : total;
        this.hasOlderMessages = !!data.has_more;
        this.$nextTick(() => {
          const el = this.$refs.messageArea;
          if (el) el.scrollTop = Math.max(0, el.scrollHeight - previousHeight + previousTop);
        });
      } catch {
        this.hasOlderMessages = false;
      } finally {
        this.loadingOlderMessages = false;
      }
    },

    async deleteConversation(c) {
      if (!confirm(this.chatText('delete_conversation_confirm', '删除这个对话？聊天记录将无法恢复。'))) return;
      try {
        await api.deleteConversation(c.id);
        if (this.conversation?.id === c.id) {
          this.conversation = null;
          this.messages = [];
          this.messageTotal = 0;
          this.hasOlderMessages = false;
        }
        await this.loadConversations();
      } catch (err) {
        alert(err.message || this.chatText('delete_failed_text', '删除失败'));
      }
    },

    async loadMemoryContext() {
      await Promise.all([this.loadMemories(), this.loadSummary()]);
    },

    async loadMemories() {
      if (!this.appId) {
        this.memories = [];
        return;
      }
      try {
        const r = await api.memories({ app_id: this.appId });
        this.memories = r?.data?.list || r?.list || [];
      } catch {
        this.memories = [];
      }
    },

    async loadSummary() {
      this.summary = null;
      this.summaryDraft = '';
      if (!this.conversation?.id) return;
      try {
        const r = await api.conversationSummary(this.conversation.id);
        const data = r?.data || r || {};
        this.summary = data?.conversation_id ? data : null;
        this.summaryDraft = data?.summary || '';
      } catch {
        this.summary = null;
      }
    },

    async toggleMemoryPanel() {
      this.memoryOpen = !this.memoryOpen;
      if (this.memoryOpen) this.advancedRenderOpen = false;
      if (this.memoryOpen) await this.loadMemoryContext();
    },

    async saveMemory() {
      const content = this.memoryDraft.content.trim();
      if (!content) return;
      this.savingMemory = true;
      try {
        const keywords = this.memoryDraft.keywords
          .split(/[,，\n]/)
          .map(x => x.trim())
          .filter(Boolean);
        await api.saveMemory({
          app_id: this.appId || '',
          title: this.memoryDraft.title.trim(),
          content,
          keywords,
          pinned: !!this.memoryDraft.pinned,
          enabled: true,
        });
        this.memoryDraft = { title: '', content: '', keywords: '', pinned: true };
        await this.loadMemories();
      } catch (err) {
        alert(err.message || this.chatText('save_memory_failed_text', '保存记忆失败'));
      } finally {
        this.savingMemory = false;
      }
    },

    async deleteMemory(m) {
      if (!m?.id || !confirm(this.chatText('delete_memory_confirm', '删除这条记忆？'))) return;
      try {
        await api.deleteMemory(m.id);
        await this.loadMemories();
      } catch (err) {
        alert(err.message || this.chatText('delete_memory_failed_text', '删除记忆失败'));
      }
    },

    speakMessage(m) {
      const text = (m?.content || '').trim();
      if (!text) return;
      if (!('speechSynthesis' in window)) {
        alert(this.chatText('unsupported_speak_text', '当前浏览器不支持朗读'));
        return;
      }
      window.speechSynthesis.cancel();
      const utter = new SpeechSynthesisUtterance(text);
      utter.lang = 'zh-CN';
      utter.rate = 1;
      window.speechSynthesis.speak(utter);
    },

    startSpeechInput() {
      if (this.listening) return;
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SpeechRecognition) {
        alert(this.chatText('unsupported_speech_input_text', '当前浏览器不支持语音输入'));
        return;
      }
      const rec = new SpeechRecognition();
      rec.lang = 'zh-CN';
      rec.interimResults = false;
      rec.maxAlternatives = 1;
      this.listening = true;
      rec.onresult = (event) => {
        const text = event?.results?.[0]?.[0]?.transcript || '';
        if (text) this.draft = (this.draft ? this.draft + ' ' : '') + text;
      };
      rec.onerror = () => { this.listening = false; };
      rec.onend = () => { this.listening = false; };
      rec.start();
    },

    async autoSummary() {
      if (!this.conversation?.id) return;
      this.savingSummary = true;
      try {
        const r = await api.saveConversationSummary(this.conversation.id, { auto: true });
        const data = r?.data || r || {};
        this.summary = data;
        this.summaryDraft = data?.summary || '';
      } catch (err) {
        alert(err.message || this.chatText('auto_summary_failed_text', '自动摘要失败'));
      } finally {
        this.savingSummary = false;
      }
    },

    async saveSummary() {
      if (!this.conversation?.id) return;
      const text = this.summaryDraft.trim();
      if (!text) return;
      this.savingSummary = true;
      try {
        const r = await api.saveConversationSummary(this.conversation.id, { summary: text });
        const data = r?.data || r || {};
        this.summary = data;
        this.summaryDraft = data?.summary || text;
      } catch (err) {
        alert(err.message || this.chatText('save_summary_failed_text', '保存摘要失败'));
      } finally {
        this.savingSummary = false;
      }
    },

    async sendQuickReply(q) {
      const text = (q?.message || q?.label || '').trim();
      if (text) await this.sendMessage(text);
    },

    async sendMessage(forcedText = '') {
      if (typeof forcedText !== 'string') forcedText = '';
      const text = (forcedText || this.draft).trim();
      if (!text || this.replying || !this.appId) return;
      if (!forcedText) this.draft = '';
      const tempUser = this.normMsg({ id: 'tmp-' + Date.now(), role: 'user', content: text, created_at: Date.now() });
      this.messages.push(tempUser);
      const replyMsg = this.normMsg({
        id: 'stream-' + Date.now(),
        role: 'assistant',
        content: '',
        created_at: Date.now(),
      });
      replyMsg._typing = true;
      this.messages.push(replyMsg);
      this.messageTotal = Math.max(this.messageTotal + 2, this.messages.length);
      this.replying = true;
      this.scrollToBottom();
      try {
        const payload = {
          app_id: this.appId,
          conversation_id: this.conversation?.id || '',
          content: text,
          app_name: this.appName,
          app_icon: this.appIcon,
          response_mode: 'streaming',
          model_id: this.currentModelId || '',
        };
        const data = await api.sendChatStream(payload, {
          onStart: (event) => {
            if (event?.conversation_id && !this.conversation) {
              this.conversation = {
                id: event.conversation_id,
                app_id: this.appId,
                app_name: this.appName,
                app_icon: this.appIcon,
                title: text.slice(0, 30),
              };
            }
          },
          onDelta: (chunk) => {
            replyMsg.content += chunk;
            this.scrollToBottom();
          },
          onEnd: (event) => {
            if (event?.message_id) replyMsg.id = event.message_id;
            if (event?.created_at) replyMsg.created_at = event.created_at;
            if (event?.reply && !replyMsg.content) replyMsg.content = event.reply;
            this.updatePointsFromPayload(event);
            replyMsg._typing = false;
          },
        });
        replyMsg._typing = false;
        if (data?.reply && !replyMsg.content) replyMsg.content = data.reply;
        this.updatePointsFromPayload(data);
        this.loadConversations();
      } catch (err) {
        replyMsg._typing = false;
        replyMsg.content = '⚠️ ' + this.chatText('error_prefix', '出错了：') + (err.message || this.chatText('retry_text', '请稍后重试'));
      } finally {
        this.replying = false;
        this.scrollToBottom();
      }
    },

    isLastAssistant(m) {
      if (m.role !== 'assistant') return false;
      return this.messages.length > 0 && this.messages[this.messages.length - 1].id === m.id;
    },

    showSwipe(m) {
      return m.role === 'assistant' && (this.isLastAssistant(m) || (m.swipes && m.swipes.length > 1));
    },

    swipeLabel(m) {
      const len = (m.swipes && m.swipes.length) || 1;
      const idx = (m.swipe_index || 0) + 1;
      return `${idx}/${Math.max(len, 1)}`;
    },

    applyUpdatedMessage(r, { animate = false } = {}) {
      const updated = r?.data?.message || r?.message || r?.data || r;
      if (!updated || !updated.id) return;
      const idx = this.messages.findIndex(x => x.id === updated.id);
      if (idx < 0) return;
      const normed = this.normMsg(updated);
      if (animate) {
        const full = normed.content;
        normed.content = '';
        this.messages.splice(idx, 1, normed);
        this.typewriter(this.messages[idx], full);
      } else {
        this.messages.splice(idx, 1, normed);
        this.scrollToBottom();
      }
    },

    async regenerate(m) {
      if (this.replying || !this.conversation) return;
      this.replying = true;
      this.scrollToBottom();
      try {
        const r = await api.regenerate(this.conversation.id, this.currentModelId || '');
        this.applyUpdatedMessage(r, { animate: true });
        this.updatePointsFromPayload(r);
        this.loadConversations();
      } catch (err) {
        alert(err.message || this.chatText('regenerate_failed_text', '重新生成失败'));
      } finally {
        this.replying = false;
      }
    },

    async swipePrev(m) {
      if ((m.swipe_index || 0) <= 0) return;
      try {
        const r = await api.swipeMessage(m.id, 'prev', this.currentModelId || '');
        this.applyUpdatedMessage(r);
      } catch (err) { /* noop */ }
    },

    async swipeNext(m) {
      const len = (m.swipes && m.swipes.length) || 1;
      const atEnd = (m.swipe_index || 0) >= len - 1;
      if (atEnd && !this.isLastAssistant(m)) return; // 不从对话中段生成
      if (atEnd) { this.replying = true; this.scrollToBottom(); }
      try {
        const r = await api.swipeMessage(m.id, 'next', this.currentModelId || '');
        this.applyUpdatedMessage(r, { animate: atEnd });
        this.updatePointsFromPayload(r);
      } catch (err) {
        if (atEnd) alert(err.message || this.chatText('generate_failed_text', '生成失败'));
      } finally {
        this.replying = false;
      }
    },

    startEdit(m) {
      this.editingId = m.id;
      this.editingText = m.content;
    },
    cancelEdit() {
      this.editingId = '';
      this.editingText = '';
    },
    async saveEdit(m) {
      const text = (this.editingText || '').trim();
      if (!text) { this.cancelEdit(); return; }
      try {
        const r = await api.editMessage(m.id, text);
        this.applyUpdatedMessage(r);
        this.cancelEdit();
      } catch (err) {
        alert(err.message || this.chatText('save_failed_text', '保存失败'));
      }
    },

    async deleteMessage(m) {
      if (!confirm(this.chatText('delete_message_confirm', '删除这条消息？'))) return;
      try {
        await api.deleteMessage(m.id);
        const idx = this.messages.findIndex(x => x.id === m.id);
        if (idx >= 0) this.messages.splice(idx, 1);
      } catch (err) {
        alert(err.message || this.chatText('delete_failed_text', '删除失败'));
      }
    },

    typewriter(msg, full) {
      if (this._typeTimer) clearTimeout(this._typeTimer);
      full = String(full == null ? '' : full);
      const chunk = Math.max(1, Math.ceil(full.length / 140));
      let i = 0;
      msg._typing = true;
      msg.content = '';
      const step = () => {
        if (i >= full.length) {
          msg.content = full;
          msg._typing = false;
          this.scrollToBottom();
          return;
        }
        i += chunk;
        msg.content = full.slice(0, i);
        this.scrollToBottom();
        this._typeTimer = setTimeout(step, 16);
      };
      step();
    },

    scrollToBottom() {
      this.$nextTick(() => {
        const el = this.$refs.messageArea;
        if (el) el.scrollTop = el.scrollHeight;
      });
    },
  };
}

window.chatPage = chatPage;
document.addEventListener('alpine:init', () => {
  if (window.Alpine?.data) window.Alpine.data('chatPage', chatPage);
});
