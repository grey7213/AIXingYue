import {
  normalizeCardExperience,
  normalizeMediaAssets,
  normalizeMediaBindings,
  safeRegExp,
  stripExperienceDirectives,
} from './card-experience-schema.mjs';

const BLOCKED_ELEMENTS = new Set(['SCRIPT', 'STYLE', 'IFRAME', 'OBJECT', 'EMBED', 'BASE', 'FORM', 'META', 'LINK']);
const URL_ATTRIBUTES = new Set(['href', 'src', 'poster']);
const REGEX_WORKER_URL = new URL('./card-experience-regex-worker.mjs?v=20260716', import.meta.url);

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
  .ce-player { position: absolute; right: max(14px, env(safe-area-inset-right)); bottom: max(82px, env(safe-area-inset-bottom)); z-index: 3; display: flex; align-items: center; gap: 8px; min-height: 42px; max-width: min(300px, calc(100vw - 28px)); padding: 8px 12px; border-radius: 999px; pointer-events: auto; }
  .ce-player button { width: 28px; height: 28px; border: 0; border-radius: 50%; color: #21162f; background: #fff; cursor: pointer; }
  .ce-player span { overflow: hidden; font-size: 12px; white-space: nowrap; text-overflow: ellipsis; }
  @keyframes ce-in { from { opacity: 0; transform: translateY(-10px); } }
  @media (max-width: 640px) {
    .ce-edge { top: 22%; }
    .ce-edge button { min-height: 62px; max-width: 34px; font-size: 12px; }
    .ce-sidebar { max-width: calc(100vw - 34px); }
    .ce-portrait { width: min(92vw, 620px); height: 68vh; }
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
    this.userGestureHandler = () => this.tryAutoplay();
  }

  mount(card, host = document.getElementById('card-experience-root')) {
    if (!host) return;
    this.destroy();
    this.card = card && typeof card === 'object' ? card : {};
    this.config = normalizeCardExperience(this.card.card_experience);
    this.assets = normalizeMediaAssets(this.card.media_assets).filter((asset) => asset.status === 'ready');
    this.world = Array.isArray(this.card.world_info) ? this.card.world_info : [];
    this.host = host;
    this.shadow = host.shadowRoot || host.attachShadow({ mode: 'open' });
    this.shadow.innerHTML = `<style>${BASE_STYLE}</style><div class="ce-stage">
      <div class="ce-background"></div><img class="ce-portrait" alt="" referrerpolicy="no-referrer">
      <div class="ce-edge left"></div><div class="ce-edge right"></div>
      <div class="ce-sidebar-slot"></div>
      <div class="ce-backdrop"><div class="ce-popup"><button class="ce-popup__close" type="button" aria-label="关闭">×</button><div class="ce-popup__content"></div></div></div>
      <div class="ce-floats" aria-live="polite"></div>
      <div class="ce-player" hidden><button type="button" aria-label="播放或暂停">▶</button><span>BGM</span></div>
    </div>`;
    this.audio = new Audio();
    this.audio.preload = 'metadata';
    this.audio.loop = this.config.bgm.loop;
    this.audio.volume = this.config.bgm.volume;
    this.bindBaseEvents();
    this.renderSidebarTriggers();
    if (this.config.bgm.enabled && this.config.bgm.default_asset_id) this.switchBgm(this.config.bgm.default_asset_id, false);
  }

  bindBaseEvents() {
    this.shadow.querySelector('.ce-popup__close')?.addEventListener('click', () => this.closePopup());
    this.shadow.querySelector('.ce-backdrop')?.addEventListener('click', (event) => {
      if (event.target.classList.contains('ce-backdrop')) this.closePopup();
    });
    this.shadow.querySelector('.ce-player button')?.addEventListener('click', () => this.toggleAudio());
    document.removeEventListener('pointerdown', this.userGestureHandler);
    document.addEventListener('pointerdown', this.userGestureHandler, { once: true, passive: true });
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
      player.querySelector('span').textContent = asset.name || 'BGM';
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
    slot.append(panel);
    requestAnimationFrame(() => panel.classList.add('is-open'));
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
  }

  async consume(message, options = {}) {
    const input = String(message || '').slice(-8192);
    const signature = `${options.messageId || ''}:${input}`;
    if (!input || signature === this.lastMessageSignature) return;
    this.lastMessageSignature = signature;
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

export function destroyCardExperience() {
  cardExperienceRuntime.destroy();
}
