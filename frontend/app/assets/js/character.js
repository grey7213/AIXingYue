import { api, requireAuth, getCachedUser, setCachedUser, ApiError } from '/app/assets/js/app-core.js';
import { injectLayout, loadPublicSiteSettings } from '/app/assets/js/layout.js?v=20260703-channels-closed';

const FIELD_LABELS = {
  name: '姓名',
  name_romaji: '罗马音',
  nickname: '昵称',
  age: '年龄',
  gender: '性别',
  school: '学校',
  grade: '年级',
  occupation: '身份',
  role: '身份',
  species: '种族',
  birthday: '生日',
  height: '身高',
  relationship: '关系',
  description: '角色介绍',
  personality: '性格',
  scenario: '场景',
  first_mes: '开场白',
  greeting: '开场白',
  mes_example: '对话示例',
};

const BASIC_FIELDS = ['name', 'name_romaji', 'nickname', 'age', 'gender', 'school', 'grade', 'occupation', 'role', 'species', 'birthday', 'height', 'relationship'];
const LONG_FIELDS = ['description', 'profile', 'summary', 'personality', 'scenario', 'background', 'setting', 'first_mes', 'greeting', 'mes_example'];

function stripJsonFence(text) {
  const value = String(text || '').trim();
  const match = value.match(/^```(?:json|jsonc)?\s*\n([\s\S]*?)\n?```$/i);
  return match ? match[1].trim() : value;
}

function tryParseJsonLike(text) {
  const value = stripJsonFence(text);
  if (!value || !/^[\[{]/.test(value)) return null;
  try { return JSON.parse(value); } catch { return null; }
}

function valueToText(value) {
  if (value == null || value === '') return '';
  if (Array.isArray(value)) {
    return value.map(valueToText).filter(Boolean).join('、');
  }
  if (typeof value === 'object') {
    const pairs = Object.entries(value)
      .filter(([, v]) => v != null && v !== '')
      .slice(0, 12)
      .map(([k, v]) => `${FIELD_LABELS[k] || k}：${valueToText(v)}`);
    return pairs.join('\n');
  }
  return String(value).trim();
}

function compactText(value, limit = 160) {
  const text = String(value || '').replace(/\s+/g, ' ').trim();
  return text.length > limit ? `${text.slice(0, limit)}...` : text;
}

function objectSource(parsed) {
  if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
    if (parsed.data && typeof parsed.data === 'object' && !Array.isArray(parsed.data)) return parsed.data;
    if (parsed.character && typeof parsed.character === 'object' && !Array.isArray(parsed.character)) return parsed.character;
    return parsed;
  }
  return null;
}

function structuredDetail(rawText) {
  const raw = String(rawText || '').trim();
  const parsed = tryParseJsonLike(raw);
  const source = objectSource(parsed);
  if (!source) {
    return { structured: false, raw, summary: compactText(raw), plain: raw, sections: [] };
  }

  const sections = [];
  const basics = BASIC_FIELDS
    .map(key => ({ key, label: FIELD_LABELS[key] || key, value: valueToText(source[key]) }))
    .filter(item => item.value);
  if (basics.length) sections.push({ title: '基础信息', items: basics });

  for (const key of LONG_FIELDS) {
    const text = valueToText(source[key]);
    if (!text) continue;
    const title = FIELD_LABELS[key] || key;
    sections.push({ title, body: text });
  }

  const used = new Set([...BASIC_FIELDS, ...LONG_FIELDS, 'creator_notes', 'extensions', 'character_book', 'alternate_greetings']);
  const extraItems = Object.entries(source)
    .filter(([key, value]) => !used.has(key) && value != null && value !== '' && typeof value !== 'object')
    .slice(0, 10)
    .map(([key, value]) => ({ key, label: FIELD_LABELS[key] || key, value: valueToText(value) }))
    .filter(item => item.value);
  if (extraItems.length) sections.push({ title: '其他信息', items: extraItems });

  const summarySource = valueToText(source.description || source.profile || source.summary)
    || basics.map(item => `${item.label}：${item.value}`).join('，')
    || raw;
  return {
    structured: sections.length > 0,
    raw,
    summary: compactText(summarySource),
    plain: sections.length ? '' : raw,
    sections,
  };
}

function normalizeCard(raw) {
  const data = raw?.data || raw || {};
  const description = data.description || data.prompt || '';
  const opening = data.opening_statement || data.opening || '';
  const descriptionDetail = structuredDetail(description);
  const openingDetail = structuredDetail(opening);
  return {
    id: String(data.id || data.app_id || ''),
    name: data.name || data.app_name || data.title || '',
    summary: data.summary || data.intro || '',
    description,
    description_detail: descriptionDetail,
    opening_statement: opening,
    opening_detail: openingDetail,
    cover: data.cover || data.cover_url || data.image || data.icon_url || '',
    icon: data.icon || data.icon_url || data.avatar || '',
    tags: Array.isArray(data.tags) ? data.tags : [],
    source: data.source || 'upstream',
  };
}

function characterPage() {
  return {
    user: null,
    points: 0,
    loading: false,
    card: null,
    siteSettings: null,

    async init() {
      injectLayout('home');
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
      } catch (err) {
        if (err instanceof ApiError && err.code === 401) {
          location.replace('/app/login.html?next=' + encodeURIComponent(location.pathname + location.search));
          return;
        }
      }
      const id = new URLSearchParams(location.search).get('id');
      if (!id) return;
      await this.loadCard(id);
    },

    async loadCard(id) {
      this.loading = true;
      try {
        const r = await api.appDetails(id);
        const card = normalizeCard(r);
        this.card = card.id ? card : null;
      } catch {
        this.card = null;
      } finally {
        this.loading = false;
      }
    },

    characterText(key, fallback = '') {
      return this.siteSettings?.character?.[key] || fallback;
    },

    cardSummary() {
      if (!this.card) return '';
      return this.card.summary || this.card.description_detail?.summary || this.card.opening_detail?.summary || this.characterText('summary_fallback', '点击开始对话。');
    },
  };
}

window.characterPage = characterPage;
document.addEventListener('alpine:init', () => {
  if (window.Alpine?.data) window.Alpine.data('characterPage', characterPage);
});
