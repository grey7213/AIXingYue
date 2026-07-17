import {
  normalizeCardExperience,
  normalizeMediaAssets,
  normalizeMediaBindings,
  parseGalgameDirectives,
  safeRegExp,
  stripExperienceDirectives,
} from './card-experience-schema.mjs?v=20260717-handoff-merge';

const BLOCKED_ELEMENTS = new Set(['SCRIPT', 'STYLE', 'IFRAME', 'OBJECT', 'EMBED', 'BASE', 'FORM', 'META', 'LINK']);
const URL_ATTRIBUTES = new Set(['href', 'src', 'poster']);
const REGEX_WORKER_URL = new URL('./card-experience-regex-worker.mjs?v=20260717-handoff-merge', import.meta.url);

function timedRegexMatches(patterns, input, timeoutMs = 120) {
  const safePatterns = Array.isArray(patterns) ? patterns.slice(0, 60) : [];
  if (!safePatterns.length) return Promise.resolve([]);
  if (typeof Worker === 'undefined') {
    return Promise.resolve(safePatterns.map((item) => {
      const regex = safeRegExp(item?.pattern, item?.flags);
      return !!(regex && regex.test(String(input || '').slice(-4096)));
    }));
  }
  return new Promise((resolve) => {
    let worker;
    try {
      worker = new Worker(REGEX_WORKER_URL, { type: 'module', name: 'homer-card-experience-regex' });
    } catch {
      resolve(safePatterns.map((item) => {
        const regex = safeRegExp(item?.pattern, item?.flags);
        return !!(regex && regex.test(String(input || '').slice(-4096)));
      }));
      return;
    }
    let finished = false;
    const finish = (matches) => {
      if (finished) return;
      finished = true;
      clearTimeout(timer);
      worker.terminate();
      resolve(Array.isArray(matches) ? matches : safePatterns.map(() => false));
    };
    const timer = setTimeout(() => finish([]), timeoutMs);
    worker.onmessage = (event) => finish(event?.data?.matches);
    worker.onerror = () => finish([]);
    worker.postMessage({ patterns: safePatterns, input: String(input || '').slice(-8192) });
  });
}

function safeUrl(value) {
  const input = String(value || '').trim();
  if (!input) return '';
  if (input.startsWith('/') && !input.startsWith('//')) return input;
  if (/^https:\/\//i.test(input)) return input;
  if (/^data:image\/(?:png|jpe?g|webp|gif);base64,/i.test(input)) return input;
  return '';
}

function normalizeLegacyRpHub(value) {
  if (!value || typeof value !== 'object') return { bgm_playlist: [] };
  const seen = new Set();
  const bgmPlaylist = (Array.isArray(value.bgm_playlist) ? value.bgm_playlist : []).slice(0, 20).map((item, index) => {
    if (!item || typeof item !== 'object') return null;
    const url = String(item.url || '').trim();
    let parsed;
    try { parsed = new URL(url); } catch { return null; }
    if (parsed.protocol !== 'https:' || parsed.hostname !== 'raw.githubusercontent.com' || !/\.(?:mp3|ogg|wav|m4a)$/i.test(parsed.pathname)) return null;
    if (seen.has(url)) return null;
    seen.add(url);
    return {
      id: `legacy-rp-bgm-${index + 1}`,
      kind: 'bgm',
      name: String(item.title || item.name || `BGM ${index + 1}`).trim().slice(0, 120),
      url,
      mime_type: parsed.pathname.toLowerCase().endsWith('.mp3') ? 'audio/mpeg' : 'audio/*',
      status: 'ready',
      metadata: { source: 'legacy-rp-hub' },
    };
  }).filter(Boolean);
  return { bgm_playlist: bgmPlaylist };
}

export function sanitizeCardHtml(html) {
  if (typeof DOMParser === 'undefined') return '';
  const doc = new DOMParser().parseFromString(`<div id="card-root">${String(html || '').slice(0, 50000)}</div>`, 'text/html');
  const root = doc.getElementById('card-root');
  if (!root) return '';
  for (const element of [...root.querySelectorAll('*')]) {
    if (BLOCKED_ELEMENTS.has(element.tagName)) {
      element.remove();
      continue;
    }
    for (const attr of [...element.attributes]) {
      const name = attr.name.toLowerCase();
      if (name.startsWith('on') || name === 'srcdoc' || name === 'style') {
        element.removeAttribute(attr.name);
      } else if (URL_ATTRIBUTES.has(name)) {
        const url = safeUrl(attr.value);
        if (url) element.setAttribute(attr.name, url);
        else element.removeAttribute(attr.name);
      }
    }
    if (element.tagName === 'A') {
      element.setAttribute('rel', 'noopener noreferrer');
      element.setAttribute('target', '_blank');
    }
  }
  return root.innerHTML;
}

export function sanitizeScopedCss(css) {
  let output = String(css || '').slice(0, 30000);
  output = output.replace(/@(?:import|charset|namespace)[^;]*;/gi, '');
  output = output.replace(/@font-face\s*\{[\s\S]*?\}/gi, '');
  output = output.replace(/url\s*\([^)]*\)/gi, 'none');
  output = output.replace(/(?:expression|behavior|-moz-binding)\s*:[^;}]*/gi, '');
  output = output.replace(/<\/style/gi, '<\\/style');
  return output;
}

function template(value, context) {
  const data = {
    message: context.message || '',
    character: context.card?.name || '',
    'world.name': context.world?.name || '',
    'world.content': context.world?.content || '',
  };
  return String(value || '').replace(/\{\{\s*([\w.]+)\s*\}\}/g, (_, key) => escapeText(data[key] ?? ''));
}

const BASE_STYLE = `
  :host { --ce-z: 70; font-family: inherit; color-scheme: dark; }
  *, *::before, *::after { box-sizing: border-box; }
  .ce-stage { position: fixed; inset: 0; z-index: var(--ce-z); pointer-events: none; }
  .ce-background { position: absolute; inset: 0; z-index: -2; background-position: center; background-size: cover; opacity: 0; transition: opacity .45s ease, background-image .45s ease; }
  .ce-background.is-visible { opacity: 1; }
  .ce-background::after { content: ''; position: absolute; inset: 0; background: linear-gradient(180deg, rgba(13,9,20,.08), rgba(13,9,20,.3)); }
  .ce-portrait { position: absolute; bottom: 0; left: 50%; z-index: -1; width: min(52vw, 620px); height: min(82vh, 940px); object-fit: contain; object-position: bottom center; transform: translateX(-50%); opacity: 0; transition: opacity .35s ease, transform .35s ease; }
  .ce-portrait.is-visible { opacity: 1; transform: translateX(-50%) translateY(0); }
  .ce-edge { position: absolute; top: 26%; display: grid; gap: 8px; pointer-events: auto; }
  .ce-edge.left { left: max(6px, env(safe-area-inset-left)); }
  .ce-edge.right { right: max(6px, env(safe-area-inset-right)); }
  .ce-edge button, .ce-player { border: 1px solid rgba(255,255,255,.25); color: #fff; background: rgba(24,17,38,.8); box-shadow: 0 10px 28px rgba(0,0,0,.24); backdrop-filter: blur(14px); }
  .ce-edge button { max-width: 38px; min-height: 76px; border-radius: 12px; padding: 10px 8px; writing-mode: vertical-rl; letter-spacing: 2px; cursor: pointer; }
  .ce-sidebar { position: absolute; top: 0; bottom: 0; z-index: 4; overflow: auto; pointer-events: auto; background: rgba(20,14,31,.94); box-shadow: 0 0 44px rgba(0,0,0,.38); backdrop-filter: blur(20px); transition: transform .24s ease; }
  .ce-sidebar.left { left: 0; transform: translateX(-105%); }
  .ce-sidebar.right { right: 0; transform: translateX(105%); }
  .ce-sidebar.is-open { transform: translateX(0); }
  .ce-sidebar__bar { position: sticky; top: 0; z-index: 1; display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 14px 16px; background: rgba(20,14,31,.96); border-bottom: 1px solid rgba(255,255,255,.12); }
  .ce-sidebar__close, .ce-popup__close { border: 0; color: #fff; background: transparent; font-size: 25px; line-height: 1; cursor: pointer; }
  .ce-sidebar__content { min-height: calc(100% - 56px); }
  .ce-backdrop { position: absolute; inset: 0; z-index: 5; display: grid; place-items: center; padding: 18px; pointer-events: auto; background: rgba(8,5,14,.58); opacity: 0; visibility: hidden; transition: .2s; }
  .ce-backdrop.is-open { opacity: 1; visibility: visible; }
  .ce-popup { position: relative; width: min(640px, 94vw); max-height: min(82vh, 820px); overflow: auto; }
  .ce-popup__close { position: absolute; top: 10px; right: 12px; z-index: 2; width: 34px; height: 34px; border-radius: 50%; background: rgba(0,0,0,.35); }
  .ce-floats { position: absolute; top: max(74px, env(safe-area-inset-top)); left: 50%; z-index: 6; width: min(460px, calc(100vw - 32px)); transform: translateX(-50%); display: grid; gap: 10px; pointer-events: auto; }
  .ce-float { border: 1px solid rgba(255,255,255,.2); border-radius: 16px; background: rgba(24,17,38,.92); box-shadow: 0 16px 42px rgba(0,0,0,.34); overflow: hidden; animation: ce-in .22s ease both; }
  .ce-player { position: absolute; right: max(14px, env(safe-area-inset-right)); bottom: max(82px, env(safe-area-inset-bottom)); z-index: 3; display: flex; align-items: center; gap: 8px; min-height: 42px; max-width: min(360px, calc(100vw - 28px)); padding: 8px 12px; border-radius: 999px; pointer-events: auto; }
  .ce-player button { flex: 0 0 auto; width: 28px; height: 28px; border: 0; border-radius: 50%; color: #21162f; background: #fff; cursor: pointer; }
  .ce-player span { overflow: hidden; font-size: 12px; white-space: nowrap; text-overflow: ellipsis; }
  .ce-player select { max-width: 130px; min-width: 72px; border: 0; border-radius: 8px; padding: 3px 6px; font-size: 12px; color: #21162f; background: #fff; cursor: pointer; }
  .ce-player input[type=range] { flex: 0 0 auto; width: 62px; accent-color: #b984ff; cursor: pointer; }
  .ce-player__vol-btn { position: relative; }

  @keyframes ce-in { from { opacity: 0; transform: translateY(-10px); } }
  /* galgame 横板模式 */
  :host(.ce-galgame-on) { --ce-z: 60; }
  .ce-stage.is-galgame { background: #05030a; pointer-events: auto; }
  .ce-stage.is-galgame .ce-background { z-index: 0; opacity: 1; }
  .ce-stage.is-galgame .ce-portrait { z-index: 1; }
  .ce-stage.is-galgame.layout-left .ce-portrait { left: 26%; }
  .ce-stage.is-galgame.layout-right .ce-portrait { left: 74%; }
  .ce-galgame { position: absolute; left: 50%; z-index: 8; width: min(1080px, calc(100vw - 32px)); transform: translateX(-50%); pointer-events: auto; }
  .ce-galgame.pos-bottom { bottom: max(18px, env(safe-area-inset-bottom)); }
  .ce-galgame.pos-top { top: max(18px, env(safe-area-inset-top)); }
  .ce-galgame__box { position: relative; padding: 18px 22px 20px; border: 1px solid rgba(255,255,255,.18); border-radius: 18px; color: #f6f1ff; background: linear-gradient(160deg, rgba(24,16,40,.92), rgba(12,8,22,.94)); box-shadow: 0 20px 54px rgba(0,0,0,.46); backdrop-filter: blur(16px); }
  .ce-galgame__name { position: absolute; top: -16px; left: 20px; padding: 4px 16px; font-size: 14px; font-weight: 700; letter-spacing: 1px; color: #fff; background: linear-gradient(135deg, #7c5cff, #b984ff); border-radius: 999px; box-shadow: 0 8px 20px rgba(124,92,255,.42); }
  .ce-galgame__text { margin: 6px 0 0; max-height: 34vh; overflow: auto; font-size: 16px; line-height: 1.7; white-space: pre-wrap; word-break: break-word; }
  .ce-galgame__hint { position: absolute; right: 16px; bottom: 10px; font-size: 12px; opacity: .55; animation: ce-blink 1.4s ease infinite; }
  @keyframes ce-blink { 50% { opacity: .1; } }
  @media (max-width: 640px) {
    .ce-edge { top: 22%; }
    .ce-edge button { min-height: 62px; max-width: 34px; font-size: 12px; }
    .ce-sidebar { max-width: calc(100vw - 34px); }
    .ce-portrait { width: min(92vw, 620px); height: 68vh; }
    .ce-stage.is-galgame.layout-left .ce-portrait,
    .ce-stage.is-galgame.layout-right .ce-portrait { left: 50%; }
    .ce-galgame__text { font-size: 15px; max-height: 40vh; }
  }
`;


class CardExperienceRuntime {
  constructor() {
    this.host = null;
    this.shadow = null;
    this.card = {};
    this.config = normalizeCardExperience({});
    this.assets = [];
    this.world = [];
    this.audio = null;
    this.currentAssetId = '';
    this.lastMessageSignature = '';
    this.lastRawMessage = '';
    this.lastCleanMessage = '';
    this.userGestureHandler = () => this.tryAutoplay();
  }

  mount(card, host = document.getElementById('card-experience-root')) {
    if (!host) return;
    this.destroy();
    this.card = card && typeof card === 'object' ? card : {};
    this.config = normalizeCardExperience(this.card.card_experience);
    this.assets = normalizeMediaAssets(this.card.media_assets).filter((asset) => asset.status === 'ready');
    const legacyRpHub = normalizeLegacyRpHub(this.card.legacy_rp_hub);
    if (!this.config.bgm.enabled && legacyRpHub.bgm_playlist.length) {
      this.assets = [...this.assets, ...legacyRpHub.bgm_playlist];
      this.config.bgm = {
        ...this.config.bgm,
        enabled: true,
        default_asset_id: legacyRpHub.bgm_playlist[0].id,
        autoplay: 'after-interaction',
        volume: 0.45,
        loop: true,
        show_floating_player: true,
      };
    }
    this.world = Array.isArray(this.card.world_info) ? this.card.world_info : [];
    this.host = host;
    this.shadow = host.shadowRoot || host.attachShadow({ mode: 'open' });
    this.shadow.innerHTML = `<style>${BASE_STYLE}</style><div class="ce-stage">
      <div class="ce-background"></div><img class="ce-portrait" alt="" referrerpolicy="no-referrer">
      <div class="ce-edge left"></div><div class="ce-edge right"></div>
      <div class="ce-sidebar-slot"></div>
      <div class="ce-backdrop"><div class="ce-popup"><button class="ce-popup__close" type="button" aria-label="关闭">×</button><div class="ce-popup__content"></div></div></div>
      <div class="ce-floats" aria-live="polite"></div>
      <div class="ce-player" hidden><button class="ce-player__toggle" type="button" aria-label="播放或暂停">▶</button><span class="ce-player__title">BGM</span><select class="ce-player__list" aria-label="切换曲目" hidden></select><input class="ce-player__vol" type="range" min="0" max="1" step="0.01" aria-label="音量"></div>
      <div class="ce-galgame" hidden><div class="ce-galgame__box"><span class="ce-galgame__name"></span><div class="ce-galgame__text"></div><span class="ce-galgame__hint">▼</span></div></div>
    </div>`;
    this.audio = new Audio();
    this.audio.preload = 'metadata';
    this.audio.loop = this.config.bgm.loop;
    this.audio.volume = this.config.bgm.volume;
    this.bindBaseEvents();
    this.renderSidebarTriggers();
    this.setupGalgame();
    if (this.config.bgm.enabled && this.config.bgm.default_asset_id) this.switchBgm(this.config.bgm.default_asset_id, false);
  }

  get galgameEnabled() {
    return !!this.config.galgame?.enabled;
  }

  setupGalgame() {
    const stage = this.shadow.querySelector('.ce-stage');
    const box = this.shadow.querySelector('.ce-galgame');
    if (!stage || !box) return;
    if (!this.galgameEnabled) {
      box.hidden = true;
      this.host?.classList.remove('ce-galgame-on');
      return;
    }
    const galgame = this.config.galgame;
    this.host?.classList.add('ce-galgame-on');
    stage.classList.add('is-galgame', `layout-${galgame.portrait_layout}`);
    box.hidden = false;
    box.classList.remove('pos-top', 'pos-bottom');
    box.classList.add(galgame.dialogue_position === 'top' ? 'pos-top' : 'pos-bottom');
    const nameEl = box.querySelector('.ce-galgame__name');
    if (nameEl) nameEl.textContent = this.card.name || '';
    // 默认背景 / 立绘
    const bg = this.findAsset(galgame.default_background_id, 'background');
    if (bg) this.applyBackground(bg);
    const portrait = this.findAsset(galgame.default_portrait_id, 'portrait') || this.assets.find((a) => a.kind === 'portrait');
    if (portrait) this.applyPortrait(portrait);
  }

  applyBackground(asset) {
    if (!asset) return;
    const el = this.shadow.querySelector('.ce-background');
    if (!el) return;
    el.style.backgroundImage = `url("${String(asset.url).replace(/["\\\n\r]/g, '')}")`;
    el.classList.add('is-visible');
  }

  applyPortrait(asset) {
    if (!asset) return;
    const el = this.shadow.querySelector('.ce-portrait');
    if (!el) return;
    el.src = asset.url;
    el.alt = asset.name || this.card.name || '';
    el.classList.add('is-visible');
  }

  // 按情绪标签切换立绘：匹配 metadata.emotion（大小写不敏感）。
  switchPortraitByEmotion(emotion) {
    const tag = String(emotion || '').trim().toLowerCase();
    if (!tag) return false;
    const asset = this.assets.find((a) => a.kind === 'portrait' && String(a.metadata?.emotion || '').trim().toLowerCase() === tag)
      || this.assets.find((a) => a.kind === 'portrait' && String(a.name || '').trim().toLowerCase().includes(tag));
    if (!asset) return false;
    this.applyPortrait(asset);
    return true;
  }

  switchBackgroundByTag(tag) {
    const key = String(tag || '').trim().toLowerCase();
    if (!key) return false;
    const asset = this.assets.find((a) => a.kind === 'background' && String(a.metadata?.emotion || a.name || '').trim().toLowerCase().includes(key));
    if (!asset) return false;
    this.applyBackground(asset);
    return true;
  }

  // 把最新一条 AI 文本呈现到对话栏，同时依据指令切换立绘/背景。
  showGalgameDialogue(rawText) {
    if (!this.galgameEnabled) return;
    const box = this.shadow.querySelector('.ce-galgame');
    const textEl = this.shadow.querySelector('.ce-galgame__text');
    if (!box || !textEl) return;
    const directives = parseGalgameDirectives(String(rawText || ''), this.config.galgame);
    if (directives.portrait) this.switchPortraitByEmotion(directives.portrait);
    if (directives.background) this.switchBackgroundByTag(directives.background);
    const clean = stripExperienceDirectives(rawText, this.config);
    box.hidden = false;
    if (this.config.galgame.typewriter) this.typewrite(textEl, clean);
    else textEl.textContent = clean;
  }

  typewrite(el, text) {
    if (this._typeTimer) { clearInterval(this._typeTimer); this._typeTimer = null; }
    const full = String(text || '');
    el.textContent = '';
    let index = 0;
    const step = Math.max(1, Math.round(full.length / 240));
    this._typeTimer = setInterval(() => {
      index += step;
      el.textContent = full.slice(0, index);
      if (index >= full.length) {
        clearInterval(this._typeTimer);
        this._typeTimer = null;
      }
    }, 16);
  }


  bindBaseEvents() {
    this.shadow.querySelector('.ce-popup__close')?.addEventListener('click', () => this.closePopup());
    this.shadow.querySelector('.ce-backdrop')?.addEventListener('click', (event) => {
      if (event.target.classList.contains('ce-backdrop')) this.closePopup();
    });
    this.shadow.querySelector('.ce-player__toggle')?.addEventListener('click', () => this.toggleAudio());
    const list = this.shadow.querySelector('.ce-player__list');
    if (list) list.addEventListener('change', () => { if (list.value) this.switchBgm(list.value, true); });
    const vol = this.shadow.querySelector('.ce-player__vol');
    if (vol) {
      vol.value = String(this.config.bgm.volume);
      vol.addEventListener('input', () => {
        const level = Math.min(1, Math.max(0, Number(vol.value) || 0));
        this.config.bgm.volume = level;
        if (this.audio) this.audio.volume = level;
      });
    }
    this.renderBgmPlayer();
    document.removeEventListener('pointerdown', this.userGestureHandler);
    document.addEventListener('pointerdown', this.userGestureHandler, { once: true, passive: true });
  }

  // 用媒体库里的全部 bgm 资源填充悬浮播放器的曲目下拉框。单曲时隐藏下拉。
  renderBgmPlayer() {
    const list = this.shadow.querySelector('.ce-player__list');
    if (!list) return;
    const tracks = this.assets.filter((asset) => asset.kind === 'bgm');
    list.replaceChildren();
    for (const track of tracks) {
      const option = document.createElement('option');
      option.value = track.id;
      option.textContent = track.name || 'BGM';
      list.append(option);
    }
    list.hidden = tracks.length < 2;
    if (this.currentAssetId) list.value = this.currentAssetId;
  }


  renderSidebarTriggers() {
    for (const position of ['left', 'right']) {
      const dock = this.shadow.querySelector(`.ce-edge.${position}`);
      dock.replaceChildren();
      for (const sidebar of this.config.sidebars.filter((item) => item.enabled && item.position === position)) {
        const button = document.createElement('button');
        button.type = 'button';
        button.textContent = sidebar.trigger_label || sidebar.name;
        button.addEventListener('click', () => this.openSidebar(sidebar.id));
        dock.append(button);
      }
    }
  }

  findAsset(id, kind = '') {
    return this.assets.find((asset) => asset.id === id && (!kind || asset.kind === kind));
  }

  async switchBgm(assetId, play = true) {
    const asset = this.findAsset(assetId, 'bgm');
    if (!asset || !this.audio) return false;
    if (this.currentAssetId !== asset.id) {
      this.currentAssetId = asset.id;
      this.audio.src = asset.url;
      this.audio.loop = this.config.bgm.loop;
      this.audio.volume = this.config.bgm.volume;
      const player = this.shadow.querySelector('.ce-player');
      player.hidden = !this.config.bgm.show_floating_player;
      player.querySelector('.ce-player__title').textContent = asset.name || 'BGM';
      const list = player.querySelector('.ce-player__list');
      if (list && list.value !== asset.id) list.value = asset.id;
    }
    if (play) return this.tryAutoplay();

    return true;
  }

  async tryAutoplay() {
    if (!this.audio?.src || !this.config.bgm.enabled) return false;
    try {
      await this.audio.play();
      const button = this.shadow.querySelector('.ce-player button');
      if (button) button.textContent = 'Ⅱ';
      return true;
    } catch {
      const player = this.shadow.querySelector('.ce-player');
      if (player) player.hidden = false;
      return false;
    }
  }

  toggleAudio() {
    if (!this.audio?.src) return;
    if (this.audio.paused) this.tryAutoplay();
    else {
      this.audio.pause();
      const button = this.shadow.querySelector('.ce-player button');
      if (button) button.textContent = '▶';
    }
  }

  openPopup(rule, context) {
    const backdrop = this.shadow.querySelector('.ce-backdrop');
    const popup = this.shadow.querySelector('.ce-popup');
    const content = this.shadow.querySelector('.ce-popup__content');
    popup.querySelectorAll('style[data-author]').forEach((node) => node.remove());
    const style = document.createElement('style');
    style.dataset.author = '1';
    style.textContent = sanitizeScopedCss(rule.scoped_css);
    popup.prepend(style);
    content.innerHTML = sanitizeCardHtml(template(rule.template_html, context));
    this.bindDeclarativeActions(content);
    this.syncLiveElements(content);
    backdrop.classList.add('is-open');
  }


  closePopup() {
    this.shadow?.querySelector('.ce-backdrop')?.classList.remove('is-open');
  }

  showFloating(rule, context) {
    const card = document.createElement('div');
    card.className = 'ce-float';
    const style = document.createElement('style');
    style.textContent = sanitizeScopedCss(rule.scoped_css);
    card.append(style);
    const content = document.createElement('div');
    content.innerHTML = sanitizeCardHtml(template(rule.template_html, context));
    card.append(content);
    this.bindDeclarativeActions(card);
    this.shadow.querySelector('.ce-floats').append(card);
    setTimeout(() => card.remove(), rule.duration_ms || 5000);
  }

  insertComposerText(text, mode = 'append') {
    const clean = String(text || '').slice(0, 2000);
    if (!clean) return;
    document.dispatchEvent(new CustomEvent('card-experience-insert-text', {
      detail: { text: clean, mode: mode === 'replace' ? 'replace' : 'append' },
    }));
  }

  openSidebar(sidebarId, context = {}) {
    const sidebar = this.config.sidebars.find((item) => item.enabled && item.id === sidebarId);

    if (!sidebar) return;
    const slot = this.shadow.querySelector('.ce-sidebar-slot');
    slot.replaceChildren();
    const panel = document.createElement('aside');
    panel.className = `ce-sidebar ${sidebar.position}`;
    panel.style.width = `${sidebar.width}px`;
    const world = this.world.find((entry) => entry.id === sidebar.world_entry_id);
    const rawContent = sidebar.content_mode === 'worldbook' && world
      ? `<article class="worldbook-content"><h3>${escapeText(world.name || sidebar.name)}</h3><p>${escapeText(world.content || '').replace(/\n/g, '<br>')}</p></article>`
      : template(sidebar.content_html, { ...context, card: this.card, world });
    panel.innerHTML = `<style>${sanitizeScopedCss(sidebar.scoped_css)}</style><div class="ce-sidebar__bar"><strong>${escapeText(sidebar.name)}</strong><button class="ce-sidebar__close" type="button" aria-label="关闭">×</button></div><div class="ce-sidebar__content">${sanitizeCardHtml(rawContent)}</div>`;
    panel.querySelector('.ce-sidebar__close').addEventListener('click', () => panel.classList.remove('is-open'));
    this.bindDeclarativeActions(panel, { panel });
    this.syncLiveElements(panel);
    slot.append(panel);
    requestAnimationFrame(() => panel.classList.add('is-open'));
  }

  // 声明式「实时数据同步」（mmd 架构思路）：把最新一条 AI 回复同步到独立界面
  // （侧边栏 / 弹窗 / 图鉴等）里带 data-card-live 的元素，让这些界面始终反映最新回复。
  // - <span data-card-live>：填入清洗后的最新回复全文（默认）。
  // - <span data-card-live="raw">：填入未清洗的原始回复。
  // - <span data-card-live data-live-pattern="HP[:：]\s*(\d+)" data-live-group="1">：
  //   用正则从回复中提取字段（取捕获组，默认第 1 组），提取失败则保留原内容。
  syncLiveElements(scope) {
    const root = scope || this.shadow;
    if (!root) return;
    const nodes = [...root.querySelectorAll('[data-card-live]')];
    if (!nodes.length) return;
    const raw = this.lastRawMessage || '';
    const clean = this.lastCleanMessage || '';
    for (const node of nodes) {
      const mode = String(node.dataset.cardLive || '').trim().toLowerCase();
      const source = mode === 'raw' ? raw : clean;
      const patternText = node.dataset.livePattern;
      if (patternText) {
        const regex = safeRegExp(patternText, node.dataset.liveFlags || '');
        if (!regex) continue;
        const match = regex.exec(source);
        if (match) {
          const groupIndex = Number(node.dataset.liveGroup || 1);
          const value = match[Number.isFinite(groupIndex) ? groupIndex : 1] ?? match[0];
          node.textContent = String(value ?? '').slice(0, 2000);
        }
        continue;
      }
      node.textContent = source.slice(0, 8000);
    }
  }


  setScene(worldEntryId) {
    const world = this.world.find((entry) => entry.id === worldEntryId);
    if (!world) return;
    const bindings = normalizeMediaBindings(world.media_bindings);
    const background = this.findAsset(bindings.find((item) => item.kind === 'background')?.asset_id, 'background');
    const portrait = this.findAsset(bindings.find((item) => item.kind === 'portrait')?.asset_id, 'portrait');
    const bgm = this.findAsset(bindings.find((item) => item.kind === 'bgm')?.asset_id, 'bgm');
    const backgroundEl = this.shadow.querySelector('.ce-background');
    const portraitEl = this.shadow.querySelector('.ce-portrait');
    if (background) {
      backgroundEl.style.backgroundImage = `url("${background.url.replace(/["\\\n\r]/g, '')}")`;
      backgroundEl.classList.add('is-visible');
    }
    if (portrait) {
      portraitEl.src = portrait.url;
      portraitEl.alt = world.name || this.card.name || '';
      portraitEl.classList.add('is-visible');
    }
    if (bgm) this.switchBgm(bgm.id, true);
  }

  bindDeclarativeActions(container, options = {}) {
    container.addEventListener('click', (event) => {
      const control = event.target.closest?.('[data-card-action]');
      if (!control || !container.contains(control)) return;
      const action = String(control.dataset.cardAction || '');
      const targetId = String(control.dataset.assetId || control.dataset.targetId || '');
      if (action === 'play-bgm') {
        if (targetId) this.switchBgm(targetId, true);
        else this.tryAutoplay();
      } else if (action === 'pause-bgm') {
        this.audio?.pause();
        const button = this.shadow.querySelector('.ce-player button');
        if (button) button.textContent = '▶';
      } else if (action === 'toggle-bgm') {
        this.toggleAudio();
      } else if (action === 'switch-bgm' && targetId) {
        this.switchBgm(targetId, true);
      } else if (action === 'insert-text') {
        const text = String(control.dataset.text || control.textContent || '').trim();
        if (text) this.insertComposerText(text, control.dataset.insertMode === 'replace' ? 'replace' : 'append');
      } else if (action === 'open-sidebar' && targetId) {

        this.openSidebar(targetId);
      } else if (action === 'set-scene' && targetId) {
        this.setScene(targetId);
      } else if (action === 'close-popup') {
        this.closePopup();
      } else if (action === 'close-sidebar') {
        options.panel?.classList.remove('is-open');
      }
    });
    this.bindCardSearchFilter(container);
  }

  // 声明式「卡内搜索 / 筛选」：作者只写带 data-* 的 HTML，运行时接管显隐逻辑。
  // - 搜索框：<input data-card-search>（可选 data-search-target 指定条目选择器，默认 [data-card-item]）
  // - 条目：<div data-card-item data-name data-desc data-type data-rank ...>
  // - 筛选按钮：<button data-card-filter data-filter-key="type" data-filter-value="god">
  //   同一 data-filter-key 视为一组，单选；data-filter-value="all" 表示不限。
  bindCardSearchFilter(container) {
    const searchInputs = [...container.querySelectorAll('[data-card-search]')];
    const filterButtons = [...container.querySelectorAll('[data-card-filter]')];
    if (!searchInputs.length && !filterButtons.length) return;
    const state = { query: '', filters: {} };
    const itemSelector = searchInputs[0]?.dataset.searchTarget || '[data-card-item]';
    let itemNodes;
    try {
      itemNodes = [...container.querySelectorAll(itemSelector)];
    } catch {
      itemNodes = [];
    }
    if (!itemNodes.length && itemSelector !== '[data-card-item]') {
      itemNodes = [...container.querySelectorAll('[data-card-item]')];
    }
    const items = () => itemNodes;
    const apply = () => {
      const q = state.query.trim().toLowerCase();
      for (const item of items()) {
        const haystack = [
          item.dataset.name, item.dataset.desc, item.dataset.searchText,
          item.getAttribute('aria-label'), item.textContent,
        ].filter(Boolean).join(' ').toLowerCase();
        const textOk = !q || haystack.includes(q);
        let filterOk = true;
        for (const [key, value] of Object.entries(state.filters)) {
          if (!value || value === 'all') continue;
          const raw = String(item.dataset[key] || '').toLowerCase();
          const set = raw.split(/[\s,]+/).filter(Boolean);
          if (!set.includes(value.toLowerCase())) { filterOk = false; break; }
        }
        const show = textOk && filterOk;
        item.style.display = show ? '' : 'none';
        item.toggleAttribute('hidden', !show);
      }
    };
    for (const input of searchInputs) {
      input.addEventListener('input', () => { state.query = input.value || ''; apply(); });
    }
    for (const btn of filterButtons) {
      btn.addEventListener('click', (event) => {
        event.preventDefault();
        const key = btn.dataset.filterKey || 'type';
        const value = btn.dataset.filterValue || 'all';
        state.filters[key] = value;
        for (const el of filterButtons) {
          if ((el.dataset.filterKey || 'type') === key) el.classList.toggle('is-active', el === btn);
        }
        apply();
      });
    }
    apply();
  }


  async consume(message, options = {}) {
    const input = String(message || '').slice(-8192);
    const signature = `${options.messageId || ''}:${input}`;
    if (!input || signature === this.lastMessageSignature) return;
    this.lastMessageSignature = signature;
    this.lastRawMessage = input;
    this.lastCleanMessage = this.clean(input);
    this.syncLiveElements();
    if (this.galgameEnabled) this.showGalgameDialogue(input);
    const context = { message: input, card: this.card, world: null };

    const rules = this.config.ui_rules.filter((rule) => rule.enabled);
    const sidebars = this.config.sidebars.filter((sidebar) => sidebar.enabled && sidebar.open_pattern);
    const matches = await timedRegexMatches(
      [
        ...rules.map((rule) => ({ pattern: rule.pattern, flags: rule.flags })),
        ...sidebars.map((sidebar) => ({ pattern: sidebar.open_pattern, flags: sidebar.flags })),
      ],
      input,
    );
    if (this.lastMessageSignature !== signature) return;
    for (let index = 0; index < rules.length; index += 1) {
      const rule = rules[index];
      if (!matches[index]) continue;
      if (rule.action === 'open_popup') this.openPopup(rule, context);
      if (rule.action === 'show_floating') this.showFloating(rule, context);
      if (rule.action === 'switch_bgm') this.switchBgm(rule.target_id, true);
      if (rule.action === 'open_sidebar') this.openSidebar(rule.target_id, context);
      if (rule.action === 'set_scene') this.setScene(rule.target_id);
    }
    for (let index = 0; index < sidebars.length; index += 1) {
      if (matches[rules.length + index]) this.openSidebar(sidebars[index].id, context);
    }
  }

  clean(message) {
    return stripExperienceDirectives(message, this.config);
  }

  destroy() {
    document.removeEventListener('pointerdown', this.userGestureHandler);
    if (this._typeTimer) { clearInterval(this._typeTimer); this._typeTimer = null; }
    this.host?.classList.remove('ce-galgame-on');
    this.audio?.pause();

    if (this.audio) {
      this.audio.removeAttribute('src');
      try { this.audio.load(); } catch { /* ignore */ }
    }
    this.audio = null;
    this.shadow?.replaceChildren();
    this.host = null;
    this.shadow = null;
    this.card = {};
    this.config = normalizeCardExperience({});
    this.assets = [];
    this.world = [];
    this.currentAssetId = '';
    this.lastMessageSignature = '';
    this.lastRawMessage = '';
    this.lastCleanMessage = '';
  }
}

function escapeText(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export const cardExperienceRuntime = new CardExperienceRuntime();

export function mountCardExperience(card, host) {
  cardExperienceRuntime.mount(card, host);
}

export function consumeCardExperienceText(text, options) {
  void cardExperienceRuntime.consume(text, options);
}

export function cleanCardExperienceText(text) {
  return cardExperienceRuntime.clean(text);
}

export function isCardGalgameEnabled() {
  return cardExperienceRuntime.galgameEnabled;
}

export function showGalgameDialogue(text) {
  cardExperienceRuntime.showGalgameDialogue(text);
}

export function destroyCardExperience() {
  cardExperienceRuntime.destroy();
}
