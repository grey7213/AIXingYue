import { api, requireAuth, getCachedUser, setCachedUser, ApiError } from '/app/assets/js/app-core.js';
import { injectLayout, loadPublicSiteSettings } from '/app/assets/js/layout.js?v=20260703-channels-closed';

function normalizeCard(raw) {
  const data = raw?.data || raw || {};
  return {
    id: String(data.id || data.app_id || ''),
    name: data.name || data.app_name || data.title || '',
    summary: data.summary || data.intro || '',
    description: data.description || data.prompt || '',
    opening_statement: data.opening_statement || data.opening || '',
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
  };
}

window.characterPage = characterPage;
document.addEventListener('alpine:init', () => {
  if (window.Alpine?.data) window.Alpine.data('characterPage', characterPage);
});
