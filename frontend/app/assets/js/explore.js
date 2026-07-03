import { api, requireAuth, getCachedUser, setCachedUser, ApiError } from '/app/assets/js/app-core.js';
import { injectLayout, loadPublicSiteSettings } from '/app/assets/js/layout.js?v=20260703-fengyue-ui2';

const DEFAULT_PAGE_SIZE = 12;
const DEFAULT_FIRST_PAGE_PARAMS = Object.freeze({
  page: 1,
  page_size: DEFAULT_PAGE_SIZE,
  sort: 'random',
  rank: 'daily',
});

let defaultFirstPagePrefetch = api.exploreSearch(DEFAULT_FIRST_PAGE_PARAMS)
  .then(data => ({ ok: true, data }))
  .catch(error => ({ ok: false, error }));

function explorePage() {
  return {
    activeNav: 'home',
    user: null,
    points: 0,
    stats: null,
    sidebarOpen: false,
    loading: false,
    hasMore: true,
    page: 1,
    pageSize: DEFAULT_PAGE_SIZE,
    total: 0,
    searchKeyword: '',
    cards: [],
    activeCategory: 'all',
    activeSort: 'random',
    activeRank: 'daily',
    pictureless: false,
    siteSettings: null,
    categories: [
      { key: 'all', label: '全部' },
      { key: '恋爱', label: '恋爱' },
      { key: '二次元', label: '二次元' },
      { key: '游戏', label: '游戏' },
      { key: 'urban', label: '都市' },
      { key: 'history', label: '历史' },
      { key: 'fantasy', label: '玄幻' },
      { key: 'scifi', label: '科幻' },
      { key: 'mystery', label: '悬疑' },
    ],
    rankOptions: [
      { key: 'daily', label: '日榜' },
      { key: 'weekly', label: '周榜' },
      { key: 'monthly', label: '月榜' },
      { key: 'overall', label: '总榜' },
    ],
    sortOptions: [
      { key: 'random', label: '随机' },
      { key: 'popular', label: '热门' },
      { key: 'latest', label: '最新' },
      { key: 'updated', label: '更新' },
    ],

    async init() {
      injectLayout(this.activeNav);
      const settingsPromise = loadPublicSiteSettings()
        .then(settings => {
          this.siteSettings = settings;
          this.applyAppHomeLabels();
          return settings;
        })
        .catch(() => null);
      if (!requireAuth()) return;
      const cached = getCachedUser();
      if (cached) this.user = cached;

      const listPromise = this.loadList(true);
      const accountPromise = (async () => {
        try {
          const [profileResult, pointsResult, statsResult] = await Promise.allSettled([
            api.profile(),
            api.points(),
            api.homeStats(),
          ]);
          if (profileResult.status === 'fulfilled') {
            this.user = profileResult.value;
            setCachedUser(profileResult.value);
          } else if (profileResult.reason instanceof ApiError && profileResult.reason.code === 401) {
            location.replace('/app/login.html?next=' + encodeURIComponent(location.pathname));
            return;
          }
          if (pointsResult.status === 'fulfilled') {
            const p = pointsResult.value;
            this.points = parseInt(p.points || p.data?.points || 0, 10);
          }
          if (statsResult.status === 'fulfilled') this.stats = statsResult.value?.data || null;
        } catch (err) {
          if (err instanceof ApiError && err.code === 401) {
            location.replace('/app/login.html?next=' + encodeURIComponent(location.pathname));
          }
        }
      })();
      await Promise.allSettled([settingsPromise, listPromise, accountPromise]);
    },

    setCategory(k) { this.activeCategory = k; this.loadList(true); },
    setSort(k) { this.activeSort = k; this.loadList(true); },
    setRank(k) { this.activeRank = k; this.loadList(true); },
    togglePictureless() { this.pictureless = !this.pictureless; this.loadList(true); },

    appHomeText(key, fallback = '') {
      return this.siteSettings?.app_home?.[key] || fallback;
    },

    appHomeMapText(mapKey, key, fallback = '') {
      return this.siteSettings?.app_home?.[mapKey]?.[key] || fallback;
    },

    applyAppHomeLabels() {
      this.categories = this.categories.map(item => ({
        ...item,
        label: this.appHomeMapText('category_labels', item.key, item.label),
      }));
      this.rankOptions = this.rankOptions.map(item => ({
        ...item,
        label: this.appHomeMapText('rank_labels', item.key, item.label),
      }));
      this.sortOptions = this.sortOptions.map(item => ({
        ...item,
        label: this.appHomeMapText('sort_labels', item.key, item.label),
      }));
    },

    async loadList(reset = false) {
      if (reset) { this.page = 1; this.cards = []; this.hasMore = true; this.total = 0; }
      if (this.loading || !this.hasMore) return;
      this.loading = true;
      try {
        const params = {
          page: this.page,
          page_size: this.pageSize,
          sort: this.activeSort,
          rank: this.activeRank,
        };
        if (this.activeCategory !== 'all') params.tag = this.activeCategory;
        if (this.searchKeyword) params.q = this.searchKeyword;
        if (this.pictureless) params.pictureless = 'true';
        const canUsePrefetch = !!defaultFirstPagePrefetch
          && params.page === 1
          && params.page_size === DEFAULT_PAGE_SIZE
          && params.sort === DEFAULT_FIRST_PAGE_PARAMS.sort
          && params.rank === DEFAULT_FIRST_PAGE_PARAMS.rank
          && !params.tag
          && !params.q
          && !params.pictureless;
        let r;
        if (canUsePrefetch) {
          const prefetched = await defaultFirstPagePrefetch;
          defaultFirstPagePrefetch = null;
          if (!prefetched.ok) throw prefetched.error;
          r = prefetched.data;
        } else {
          r = await api.exploreSearch(params);
        }
        const data = r?.data || {};
        const list = data.apps || data.list || data.items || [];
        const normalized = list.map(raw => normalizeCard(raw, this.siteSettings?.app_home || {})).filter(Boolean);
        this.cards = [...this.cards, ...normalized];
        const total = parseInt(data.total ?? this.cards.length, 10);
        this.total = Number.isNaN(total) ? this.cards.length : total;
        this.hasMore = this.cards.length < this.total && normalized.length > 0;
        this.page += 1;
      } catch (err) {
        // 上游不可达时静默
        this.hasMore = false;
      } finally {
        this.loading = false;
      }
    },

    loadMore() { this.loadList(false); },

    emptyText(key, fallback = '') {
      return this.siteSettings?.empty_states?.[key] || fallback;
    },

    async toggleFavorite(card, event) {
      if (event) event.preventDefault();
      if (event) event.stopPropagation();
      try {
        const r = await api.toggleFavorite(card.id);
        card.favorited = !!r?.data?.favorited;
      } catch {}
    },
  };
}

function normalizeCard(raw, copy = {}) {
  if (!raw || typeof raw !== 'object') return null;
  const id = raw.id || raw.app_id || raw.appId || raw.installed_app_id;
  if (!id) return null;
  return {
    id: String(id),
    name: raw.name || raw.app_name || raw.title || copy.unnamed_role || '未命名角色',
    description: raw.description || raw.summary || raw.intro || raw.subtitle || copy.summary_fallback || '',
    author: raw.author || raw.creator || raw.publisher || raw.user_name || raw.created_by || copy.official_author || '',
    cover: raw.cover || raw.cover_url || raw.image || raw.icon_url || raw.banner || '',
    icon: raw.icon || raw.icon_url || raw.avatar || '',
    tags: Array.isArray(raw.tags) ? raw.tags : (Array.isArray(raw.category) ? raw.category : []),
    favorited: !!raw.favorited,
    pictureless: !!raw.pictureless,
  };
}

window.explorePage = explorePage;
document.addEventListener('alpine:init', () => {
  if (window.Alpine?.data) window.Alpine.data('explorePage', explorePage);
});
