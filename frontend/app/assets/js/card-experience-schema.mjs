export const CARD_EXPERIENCE_VERSION = 1;

export const MEDIA_KINDS = Object.freeze(['bgm', 'portrait', 'background']);
export const UI_ACTIONS = Object.freeze(['open_popup', 'show_floating', 'switch_bgm', 'open_sidebar', 'set_scene']);

const clamp = (value, min, max, fallback) => {
  const number = Number(value);
  return Number.isFinite(number) ? Math.max(min, Math.min(max, number)) : fallback;
};

const text = (value, max = 200) => String(value == null ? '' : value).trim().slice(0, max);
const idText = (value, fallback = '') => text(value, 96).replace(/[^\w:.-]/g, '-') || fallback;

export function newStableId(prefix = 'item') {
  if (globalThis.crypto?.randomUUID) return `${prefix}-${globalThis.crypto.randomUUID()}`;
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

export function defaultCardExperience() {
  return {
    version: CARD_EXPERIENCE_VERSION,
    bgm: {
      enabled: false,
      default_asset_id: '',
      autoplay: 'after-interaction',
      volume: 0.45,
      loop: true,
      show_floating_player: true,
    },
    ui_rules: [],
    sidebars: [],
  };
}

export function normalizeMediaAsset(raw, index = 0) {
  if (!raw || typeof raw !== 'object') return null;
  const kind = MEDIA_KINDS.includes(raw.kind) ? raw.kind : '';
  const id = idText(raw.id || raw.asset_id, `asset-${index + 1}`);
  const url = text(raw.url || raw.public_url, 2048);
  if (!kind || !id || !url) return null;
  return {
    id,
    kind,
    name: text(raw.name || raw.filename || `${kind}-${index + 1}`, 120),
    url,
    mime_type: text(raw.mime_type || raw.content_type, 100),
    size_bytes: Math.round(clamp(raw.size_bytes, 0, 80 * 1024 * 1024, 0)),
    sha256: text(raw.sha256, 64).toLowerCase(),
    status: raw.status === 'pending' ? 'pending' : 'ready',
    metadata: raw.metadata && typeof raw.metadata === 'object' ? { ...raw.metadata } : {},
  };
}

export function normalizeMediaAssets(value) {
  if (!Array.isArray(value)) return [];
  const seen = new Set();
  return value.slice(0, 200).map(normalizeMediaAsset).filter((asset) => {
    if (!asset || seen.has(asset.id)) return false;
    seen.add(asset.id);
    return true;
  });
}

export function normalizeMediaBinding(raw, index = 0) {
  if (!raw || typeof raw !== 'object') return null;
  const kind = MEDIA_KINDS.includes(raw.kind) ? raw.kind : '';
  const assetId = idText(raw.asset_id);
  if (!kind || !assetId) return null;
  return {
    id: idText(raw.id, `binding-${index + 1}`),
    kind,
    asset_id: assetId,
    label: text(raw.label, 80),
    activation: ['entry', 'regex', 'manual'].includes(raw.activation) ? raw.activation : 'entry',
  };
}

export function normalizeMediaBindings(value) {
  if (!Array.isArray(value)) return [];
  return value.slice(0, 30).map(normalizeMediaBinding).filter(Boolean);
}

export function normalizeUiRule(raw, index = 0) {
  if (!raw || typeof raw !== 'object') return null;
  const action = UI_ACTIONS.includes(raw.action) ? raw.action : 'open_popup';
  const pattern = text(raw.pattern || raw.find, 500);
  if (!pattern) return null;
  return {
    id: idText(raw.id, `ui-rule-${index + 1}`),
    name: text(raw.name || `界面规则 ${index + 1}`, 80),
    enabled: raw.enabled !== false,
    pattern,
    flags: text(raw.flags || 'i', 8).replace(/[^gimsuy]/g, ''),
    action,
    target_id: idText(raw.target_id),
    template_html: String(raw.template_html || raw.html || '').slice(0, 30000),
    scoped_css: String(raw.scoped_css || raw.css || '').slice(0, 30000),
    duration_ms: Math.round(clamp(raw.duration_ms, 0, 120000, action === 'show_floating' ? 5000 : 0)),
    order: Math.round(clamp(raw.order, -10000, 10000, index + 1)),
    remove_match: raw.remove_match !== false,
  };
}

export function normalizeSidebar(raw, index = 0) {
  if (!raw || typeof raw !== 'object') return null;
  return {
    id: idText(raw.id, `sidebar-${index + 1}`),
    name: text(raw.name || `侧栏 ${index + 1}`, 80),
    enabled: raw.enabled !== false,
    position: raw.position === 'left' ? 'left' : 'right',
    width: Math.round(clamp(raw.width, 240, 720, 340)),
    order: Math.round(clamp(raw.order, -10000, 10000, index + 1)),
    trigger_label: text(raw.trigger_label || raw.name || `侧栏 ${index + 1}`, 24),
    open_pattern: text(raw.open_pattern, 500),
    flags: text(raw.flags || 'i', 8).replace(/[^gimsuy]/g, ''),
    content_mode: raw.content_mode === 'worldbook' ? 'worldbook' : 'static',
    world_entry_id: idText(raw.world_entry_id),
    content_html: String(raw.content_html || '').slice(0, 50000),
    scoped_css: String(raw.scoped_css || '').slice(0, 30000),
  };
}

export function normalizeCardExperience(raw) {
  const fallback = defaultCardExperience();
  if (!raw || typeof raw !== 'object') return fallback;
  const bgm = raw.bgm && typeof raw.bgm === 'object' ? raw.bgm : {};
  return {
    version: CARD_EXPERIENCE_VERSION,
    bgm: {
      enabled: !!bgm.enabled,
      default_asset_id: idText(bgm.default_asset_id),
      autoplay: 'after-interaction',
      volume: clamp(bgm.volume, 0, 1, 0.45),
      loop: bgm.loop !== false,
      show_floating_player: bgm.show_floating_player !== false,
    },
    ui_rules: (Array.isArray(raw.ui_rules) ? raw.ui_rules : []).slice(0, 40).map(normalizeUiRule).filter(Boolean).sort((a, b) => a.order - b.order),
    sidebars: (Array.isArray(raw.sidebars) ? raw.sidebars : []).slice(0, 20).map(normalizeSidebar).filter(Boolean).sort((a, b) => a.order - b.order),
  };
}

export function normalizeWorldEntryMedia(entry) {
  return { ...entry, media_bindings: normalizeMediaBindings(entry?.media_bindings) };
}

export function createUiRuleTemplate(action = 'open_popup', index = 0) {
  const examples = {
    open_popup: ['弹窗', '\\[POPUP:notice\\]', '<section class="notice"><h3>提示</h3><p>{{message}}</p><button data-card-action="close-popup">知道了</button></section>'],
    show_floating: ['悬浮提示', '\\[FLOAT:notice\\]', '<div class="toast-card">剧情提示</div>'],
    switch_bgm: ['切换 BGM', '\\[BGM:main\\]', ''],
    open_sidebar: ['打开侧栏', '\\[SIDEBAR:info\\]', ''],
    set_scene: ['切换场景', '\\[SCENE:room\\]', ''],
  };
  const sample = examples[action] || examples.open_popup;
  return normalizeUiRule({
    id: newStableId('ui-rule'),
    name: `${sample[0]} ${index + 1}`,
    pattern: sample[1],
    flags: 'i',
    action,
    template_html: sample[2],
    scoped_css: action === 'open_popup' ? '.notice { padding: 24px; color: #fff; background: #241b35; border-radius: 18px; }' : '',
    duration_ms: action === 'show_floating' ? 5000 : 0,
    order: index + 1,
    enabled: true,
  }, index);
}

export function createSidebarTemplate(index = 0) {
  return normalizeSidebar({
    id: newStableId('sidebar'),
    name: `资料栏 ${index + 1}`,
    trigger_label: `资料 ${index + 1}`,
    position: index % 2 ? 'left' : 'right',
    width: 340,
    order: index + 1,
    open_pattern: `\\[SIDEBAR:info${index + 1}\\]`,
    flags: 'i',
    content_html: '<article class="info-panel"><h3>资料栏</h3><p>在这里填写图鉴、图片库、助手或其他内容。</p></article>',
    scoped_css: '.info-panel { padding: 20px; color: #f8f4ff; }',
  }, index);
}

export function safeRegExp(pattern, flags = 'i') {
  const source = text(pattern, 240);
  if (!source) return null;
  // Keep the author regex subset deliberately conservative; runtime matching also runs in a timed Worker.
  if (/\((?:[^()]|\\.)*[+*](?:[^()]|\\.)*\)[+*{]/.test(source)) return null;
  if (/\((?:[^()]|\\.)*\|(?:[^()]|\\.)*\)\s*(?:[+*]|\{\d*,?\d*\})/.test(source)) return null;
  if (/\\[1-9]|\(\?[=!<]/.test(source)) return null;
  if ((source.match(/(?<!\\)\|/g) || []).length > 8) return null;
  try {
    const uniqueFlags = [...new Set(String(flags).replace(/[^gimsuy]/g, ''))].join('');
    return new RegExp(source, uniqueFlags);
  } catch {
    return null;
  }
}

export function stripExperienceDirectives(input, experience) {
  let output = String(input == null ? '' : input);
  const config = normalizeCardExperience(experience);
  for (const rule of config.ui_rules) {
    if (!rule.enabled || !rule.remove_match) continue;
    const regex = safeRegExp(rule.pattern, rule.flags.includes('g') ? rule.flags : `${rule.flags}g`);
    if (regex) output = output.replace(regex, '');
  }
  for (const sidebar of config.sidebars) {
    if (!sidebar.enabled || !sidebar.open_pattern) continue;
    const regex = safeRegExp(sidebar.open_pattern, sidebar.flags.includes('g') ? sidebar.flags : `${sidebar.flags}g`);
    if (regex) output = output.replace(regex, '');
  }
  return output.replace(/\n{3,}/g, '\n\n').trim();
}
