export const CARD_EXPERIENCE_VERSION = 1;

export const MEDIA_KINDS = Object.freeze(['bgm', 'portrait', 'background', 'spine']);
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
    galgame: defaultGalgame(),
  };
}

export function defaultGalgame() {
  return {
    enabled: false,
    dialogue_position: 'bottom', // bottom | top
    portrait_layout: 'center', // center | left | right | dual
    default_portrait_id: '',
    default_background_id: '',
    // 情绪切换：AI 回复里出现 pattern（默认 [立绘:xxx]）时，按标签匹配立绘素材的 metadata.emotion。
    portrait_directive: '\\[(?:立绘|portrait|图)[:：]\\s*([^\\]]+)\\]',
    background_directive: '\\[(?:背景|bg|scene)[:：]\\s*([^\\]]+)\\]',
    hide_bubble_avatar: true,
    typewriter: true,
  };
}

export function normalizeGalgame(raw) {
  const fallback = defaultGalgame();
  if (!raw || typeof raw !== 'object') return fallback;
  const dialoguePosition = raw.dialogue_position === 'top' ? 'top' : 'bottom';
  const layouts = ['center', 'left', 'right', 'dual'];
  const portraitLayout = layouts.includes(raw.portrait_layout) ? raw.portrait_layout : 'center';
  return {
    enabled: !!raw.enabled,
    dialogue_position: dialoguePosition,
    portrait_layout: portraitLayout,
    default_portrait_id: idText(raw.default_portrait_id),
    default_background_id: idText(raw.default_background_id),
    portrait_directive: text(raw.portrait_directive || fallback.portrait_directive, 500),
    background_directive: text(raw.background_directive || fallback.background_directive, 500),
    hide_bubble_avatar: raw.hide_bubble_avatar !== false,
    typewriter: raw.typewriter !== false,
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
    metadata: normalizeAssetMetadata(raw.metadata, raw),
  };
}

// 立绘情绪/姿态标签：既可写在 metadata.emotion，也兼容顶层 emotion 字段。
export function normalizeAssetMetadata(metadata, raw = {}) {
  const meta = metadata && typeof metadata === 'object' ? { ...metadata } : {};
  const emotion = text(meta.emotion || raw.emotion, 40);
  if (emotion) meta.emotion = emotion;
  else delete meta.emotion;
  return meta;
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
    galgame: normalizeGalgame(raw.galgame),
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
  // galgame 立绘/背景指令标记不应显示在正文里。
  if (config.galgame?.enabled) {
    for (const directive of [config.galgame.portrait_directive, config.galgame.background_directive]) {
      const regex = safeRegExp(directive, 'ig');
      if (regex) output = output.replace(regex, '');
    }
  }
  return output.replace(/\n{3,}/g, '\n\n').trim();
}

// 从一段文本里解析 galgame 指令（立绘/背景标签），返回捕获到的标签文本。
export function parseGalgameDirectives(input, galgame) {
  const result = { portrait: '', background: '' };
  if (!galgame || !galgame.enabled) return result;
  const grab = (pattern) => {
    const regex = safeRegExp(pattern, 'ig');
    if (!regex) return '';
    let last = '';
    let match;
    let guard = 0;
    while ((match = regex.exec(input)) && guard < 40) {
      guard += 1;
      if (match[1] != null) last = String(match[1]).trim();
      if (match.index === regex.lastIndex) regex.lastIndex += 1;
    }
    return last;
  };
  result.portrait = grab(galgame.portrait_directive);
  result.background = grab(galgame.background_directive);
  return result;
}
