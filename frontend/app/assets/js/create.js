import { api, requireAuth, getCachedUser, setCachedUser, ApiError } from '/app/assets/js/app-core.js';
import { injectLayout, loadPublicSiteSettings } from '/app/assets/js/layout.js?v=20260703-channels-closed';

const emptyForm = () => ({
  name: '',
  summary: '',
  description: '',
  opening_statement: '',
  pre_prompt: '',
  personality: '',
  scenario: '',
  mes_example: '',
  post_history_instructions: '',
  prompt_blocks: [],
  quick_replies: [],
  regex_scripts: [],
  alternate_greetings: [],
  world_info: [],
  tagsText: '',
  llm_model: '',
  is_public: true,
  cover_url: '',
  bg_url: '',
  nsfw: false,
  protected_prompt: false,
  anonymous: false,
  sampling: {
    temperature: 1,
    top_p: 1,
    presence_penalty: 0,
    frequency_penalty: 0,
    history_length: 12,
  },
});

function createPage() {
  return {
    user: null,
    points: 0,
    sidebarOpen: false,
    loading: false,
    uploading: false,
    uploadingBg: false,
    toast: null,
    toastTimer: null,
    modelPresets: [],
    defaultModelPresetId: '',
    form: emptyForm(),
    editingId: '',  // empty = create, set = edit existing app
    expand: { persona: false, advanced: false, promptManager: false, greetings: false, worldinfo: false, sampling: false, voice: false, share: false },
    importing: false,
    siteSettings: null,
    previewOpen: false,
    activeSection: 'creator-basic',

    async init() {
      injectLayout('workshop');
      this.siteSettings = await loadPublicSiteSettings().catch(() => null);
      if (!requireAuth()) return;
      // Edit mode? read ?id=
      const params = new URLSearchParams(location.search);
      this.editingId = params.get('id') || '';
      const cached = getCachedUser();
      if (cached) this.user = cached;
      try {
        const profile = await api.profile();
        this.user = profile;
        setCachedUser(profile);
        const p = await api.points();
        this.points = parseInt(p.points || p.data?.points || 0, 10);
        await this.loadModelPresets();
        if (this.editingId) await this.loadExisting();
      } catch (err) {
        if (err instanceof ApiError && err.code === 401) {
          location.replace('/app/login.html?next=' + encodeURIComponent(location.pathname + location.search));
        }
      }
    },

    creatorText(key, fallback = '') {
      const legacyByokKeys = new Set(['tip_text', 'model_hint', 'bottom_note', 'user_model_prefix', 'user_model_group_label']);
      const value = this.siteSettings?.creator?.[key] || fallback;
      if (!legacyByokKeys.has(key)) return value;
      return String(value || fallback)
        .replace(/可使用站点模型，也可在“我的”页配置[^。]+。/g, '模型由平台统一接入。')
        .replace(/可以使用站点模型，也可以选择你在“我的”页保存的[^。]+。/g, '只能选择站点模型，API Key 由后台统一管理。')
        .replace(/如选择[^。]+。/g, 'API Key 由后台统一管理。')
        .replace('我的：', '')
        .replace('我的模型', '站点模型');
    },

    previewTags() {
      return String(this.form.tagsText || '')
        .split(/[，,\n]/)
        .map(tag => tag.trim())
        .filter(Boolean)
        .slice(0, 6);
    },

    scrollToSection(id) {
      const target = document.getElementById(id);
      if (!target) return;
      this.activeSection = id;
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    },

    async loadExisting() {
      try {
        const r = await api.appDetails(this.editingId);
        const app = r?.data || r;
        if (!app || !app.id) return;
        this.form.name = app.name || '';
        this.form.summary = app.summary || '';
        this.form.description = app.description || '';
        this.form.opening_statement = app.opening_statement || '';
        this.form.pre_prompt = app.pre_prompt || '';
        this.form.personality = app.personality || '';
        this.form.scenario = app.scenario || '';
        this.form.mes_example = app.mes_example || '';
        this.form.post_history_instructions = app.post_history_instructions || '';
        this.form.prompt_blocks = Array.isArray(app.prompt_blocks)
          ? app.prompt_blocks.map((b, idx) => ({
              id: b.id || ('prompt-' + (idx + 1)),
              name: b.name || `${this.creatorText('prompt_block_name_prefix', '提示词块')} ${idx + 1}`,
              position: b.position || 'system_after',
              order: typeof b.order === 'number' ? b.order : idx + 1,
              enabled: b.enabled !== false,
              content: b.content || '',
            }))
          : [];
        this.form.quick_replies = Array.isArray(app.quick_replies)
          ? app.quick_replies.map((q, idx) => ({
              id: q.id || ('quick-' + (idx + 1)),
              label: q.label || q.name || `${this.creatorText('quick_reply_name_prefix', '快捷回复')} ${idx + 1}`,
              message: q.message || q.content || '',
              enabled: q.enabled !== false,
              order: typeof q.order === 'number' ? q.order : idx + 1,
            }))
          : [];
        this.form.regex_scripts = Array.isArray(app.regex_scripts)
          ? app.regex_scripts.map((s, idx) => ({
              id: s.id || ('regex-' + (idx + 1)),
              name: s.name || `${this.creatorText('regex_name_prefix', 'Regex')} ${idx + 1}`,
              find: s.find || s.pattern || '',
              replace: s.replace || s.replacement || '',
              flags: s.flags || '',
              enabled: s.enabled !== false,
              order: typeof s.order === 'number' ? s.order : idx + 1,
            }))
          : [];
        this.form.alternate_greetings = Array.isArray(app.alternate_greetings) ? [...app.alternate_greetings] : [];
        this.form.world_info = Array.isArray(app.world_info)
          ? app.world_info.map(e => ({
              id: e.id || '',
              name: e.name || '',
              keysText: Array.isArray(e.keys) ? e.keys.join('，') : (e.keys || ''),
              secondaryKeysText: Array.isArray(e.secondary_keys) ? e.secondary_keys.join('，') : (e.secondary_keys || ''),
              content: e.content || '',
              enabled: e.enabled !== false,
              constant: !!e.constant,
              selective: !!e.selective,
              position: e.position || 'system',
              depth: typeof e.depth === 'number' ? e.depth : 4,
              priority: typeof e.priority === 'number' ? e.priority : 100,
              order: typeof e.order === 'number' ? e.order : 100,
              probability: typeof e.probability === 'number' ? e.probability : 100,
              recursive: !!e.recursive,
              case_sensitive: !!e.case_sensitive,
            }))
          : [];
        this.form.tagsText = Array.isArray(app.tags) ? app.tags.join('，') : (app.tags || '');
        this.form.llm_model = String(app.llm_model || '').startsWith('user:')
          ? (this.defaultModelPresetId || '')
          : (app.llm_model || this.defaultModelPresetId || '');
        this.form.is_public = app.is_public !== false;
        this.form.cover_url = app.cover || app.cover_url || '';
        this.form.bg_url = app.bg_url || '';
        this.form.nsfw = !!app.nsfw;
        this.form.protected_prompt = !!app.protected_prompt;
        this.form.anonymous = !!app.anonymous;
        const s = app.sampling || {};
        this.form.sampling = {
          temperature: typeof s.temperature === 'number' ? s.temperature : 1,
          top_p: typeof s.top_p === 'number' ? s.top_p : 1,
          presence_penalty: typeof s.presence_penalty === 'number' ? s.presence_penalty : 0,
          frequency_penalty: typeof s.frequency_penalty === 'number' ? s.frequency_penalty : 0,
          history_length: typeof s.history_length === 'number' ? s.history_length : 12,
        };
      } catch (err) {
        this.showToast(this.creatorText('load_existing_failed', err.message || '读取角色失败'), 'error');
      }
    },

    async loadModelPresets() {
      try {
        const siteResult = await api.modelPresets();
        const siteData = siteResult?.data || siteResult || {};
        const sitePresets = (siteData.list || []).map(p => ({ ...p, label: p.name || p.model || p.id, group: this.creatorText('site_model_group_label', '站点模型') }));
        this.modelPresets = sitePresets;
        this.defaultModelPresetId = siteData.default_id || this.modelPresets[0]?.id || '';
        if (String(this.form.llm_model || '').startsWith('user:')) {
          this.form.llm_model = this.defaultModelPresetId || '';
        }
        if (!this.form.llm_model && this.defaultModelPresetId) {
          this.form.llm_model = this.defaultModelPresetId;
        }
      } catch (err) {
        this.modelPresets = [];
      }
    },

    showToast(message, type = 'info', duration = 2800) {
      if (this.toastTimer) clearTimeout(this.toastTimer);
      this.toast = { message, type };
      this.toastTimer = setTimeout(() => { this.toast = null; }, duration);
    },

    async onCoverChange(event) {
      const file = event.target.files?.[0];
      if (!file) return;
      this.uploading = true;
      try {
        const dataUrl = await fileToDataUrl(file);
        const r = await api.uploadCover(dataUrl, file.name);
        const data = r?.data || r;
        this.form.cover_url = data.url || data.path || '';
        this.showToast(this.creatorText('cover_uploaded', '封面已上传'), 'success');
      } catch (err) {
        this.showToast(err.message || this.creatorText('cover_upload_failed', '封面上传失败'), 'error');
      } finally {
        this.uploading = false;
      }
    },

    async onBgChange(event) {
      const file = event.target.files?.[0];
      if (!file) return;
      this.uploadingBg = true;
      try {
        const dataUrl = await fileToDataUrl(file);
        const r = await api.uploadCover(dataUrl, file.name);
        const data = r?.data || r;
        this.form.bg_url = data.url || data.path || '';
        this.showToast(this.creatorText('bg_uploaded', '背景已上传'), 'success');
      } catch (err) {
        this.showToast(err.message || this.creatorText('bg_upload_failed', '背景上传失败'), 'error');
      } finally {
        this.uploadingBg = false;
      }
    },

    toggleVisibility() {
      this.form.is_public = !this.form.is_public;
    },

    bumpSampling(key, delta, lo, hi, decimals = 1) {
      let v = Number(this.form.sampling[key]) || 0;
      v = Math.round((v + delta) * 100) / 100;
      if (lo !== null && v < lo) v = lo;
      if (hi !== null && v > hi) v = hi;
      this.form.sampling[key] = v;
    },

    payload() {
      return {
        name: this.form.name.trim(),
        summary: this.form.summary.trim(),
        description: this.form.description.trim(),
        opening_statement: this.form.opening_statement.trim(),
        pre_prompt: this.form.pre_prompt.trim(),
        personality: this.form.personality.trim(),
        scenario: this.form.scenario.trim(),
        mes_example: this.form.mes_example.trim(),
        post_history_instructions: this.form.post_history_instructions.trim(),
        prompt_blocks: this.form.prompt_blocks
          .map((b, idx) => ({
            id: b.id || ('prompt-' + (idx + 1)),
            name: (b.name || `${this.creatorText('prompt_block_name_prefix', '提示词块')} ${idx + 1}`).trim(),
            position: b.position || 'system_after',
            order: Number.isFinite(Number(b.order)) ? Number(b.order) : idx + 1,
            enabled: b.enabled !== false,
            content: (b.content || '').trim(),
          }))
          .filter(b => b.content),
        quick_replies: this.form.quick_replies
          .map((q, idx) => ({
            id: q.id || ('quick-' + (idx + 1)),
            label: (q.label || `${this.creatorText('quick_reply_name_prefix', '快捷回复')} ${idx + 1}`).trim(),
            message: (q.message || '').trim(),
            enabled: q.enabled !== false,
            order: Number.isFinite(Number(q.order)) ? Number(q.order) : idx + 1,
          }))
          .filter(q => q.message),
        regex_scripts: this.form.regex_scripts
          .map((s, idx) => ({
            id: s.id || ('regex-' + (idx + 1)),
            name: (s.name || `${this.creatorText('regex_name_prefix', 'Regex')} ${idx + 1}`).trim(),
            find: (s.find || '').trim(),
            replace: s.replace || '',
            flags: (s.flags || '').trim(),
            enabled: s.enabled !== false,
            order: Number.isFinite(Number(s.order)) ? Number(s.order) : idx + 1,
          }))
          .filter(s => s.find),
        alternate_greetings: this.form.alternate_greetings.map(s => (s || '').trim()).filter(Boolean),
        world_info: this.form.world_info
          .map((e, idx) => ({
            id: e.id || ('world-' + (idx + 1)),
            name: (e.name || `${this.creatorText('world_entry_name_prefix', '世界书条目')} ${idx + 1}`).trim(),
            keys: (e.keysText || '').split(/[，,\n]/).map(s => s.trim()).filter(Boolean),
            secondary_keys: (e.secondaryKeysText || '').split(/[，,\n]/).map(s => s.trim()).filter(Boolean),
            content: (e.content || '').trim(),
            enabled: e.enabled !== false,
            constant: !!e.constant,
            selective: !!e.selective,
            position: e.position || 'system',
            depth: Number.isFinite(Number(e.depth)) ? Number(e.depth) : 4,
            priority: Number.isFinite(Number(e.priority)) ? Number(e.priority) : 100,
            order: Number.isFinite(Number(e.order)) ? Number(e.order) : idx + 1,
            probability: Number.isFinite(Number(e.probability)) ? Number(e.probability) : 100,
            recursive: !!e.recursive,
            case_sensitive: !!e.case_sensitive,
          }))
          .filter(e => e.content),
        tags: this.form.tagsText.split(/[，,\n]/).map(s => s.trim()).filter(Boolean),
        llm_model: this.form.llm_model.trim(),
        cover_url: this.form.cover_url.trim(),
        bg_url: this.form.bg_url.trim(),
        nsfw: !!this.form.nsfw,
        protected: !!this.form.protected_prompt,
        protected_prompt: !!this.form.protected_prompt,
        anonymous: !!this.form.anonymous,
        is_public: !!this.form.is_public,
        status: 'published',
        sampling: { ...this.form.sampling },
      };
    },

    // ---- 备用开场白 ----
    addGreeting() { this.form.alternate_greetings.push(''); this.expand.greetings = true; },
    removeGreeting(i) { this.form.alternate_greetings.splice(i, 1); },

    // ---- 世界书 ----
    addWorldEntry() {
      const next = this.form.world_info.length + 1;
      this.form.world_info.push({
        id: 'world-' + Date.now() + '-' + next,
        name: `${this.creatorText('world_entry_name_prefix', '世界书条目')} ${next}`,
        keysText: '',
        secondaryKeysText: '',
        content: '',
        enabled: true,
        constant: false,
        selective: false,
        position: 'system',
        depth: 4,
        priority: 100,
        order: next,
        probability: 100,
        recursive: false,
        case_sensitive: false,
      });
      this.expand.worldinfo = true;
    },
    removeWorldEntry(i) { this.form.world_info.splice(i, 1); },

    // ---- Prompt Manager ----
    addPromptBlock(position = 'system_after') {
      const next = this.form.prompt_blocks.length + 1;
      this.form.prompt_blocks.push({
        id: 'prompt-' + Date.now().toString(36) + '-' + next,
        name: `${this.creatorText('prompt_block_name_prefix', '提示词块')} ${next}`,
        position,
        order: next,
        enabled: true,
        content: '',
      });
      this.expand.promptManager = true;
    },
    removePromptBlock(i) { this.form.prompt_blocks.splice(i, 1); },

    // ---- 扩展：快捷回复 / Regex ----
    addQuickReply() {
      const next = this.form.quick_replies.length + 1;
      this.form.quick_replies.push({
        id: 'quick-' + Date.now().toString(36) + '-' + next,
        label: `${this.creatorText('quick_reply_name_prefix', '快捷回复')} ${next}`,
        message: '',
        enabled: true,
        order: next,
      });
      this.expand.advanced = true;
    },
    removeQuickReply(i) { this.form.quick_replies.splice(i, 1); },
    addRegexScript() {
      const next = this.form.regex_scripts.length + 1;
      this.form.regex_scripts.push({
        id: 'regex-' + Date.now().toString(36) + '-' + next,
        name: `${this.creatorText('regex_name_prefix', 'Regex')} ${next}`,
        find: '',
        replace: '',
        flags: '',
        enabled: true,
        order: next,
      });
      this.expand.advanced = true;
    },
    removeRegexScript(i) { this.form.regex_scripts.splice(i, 1); },

    // ---- 导入 SillyTavern 角色卡 ----
    triggerImport() {
      if (this.$refs.importInput) this.$refs.importInput.click();
    },
    async onImportFile(event) {
      const file = event.target.files?.[0];
      event.target.value = '';
      if (!file) return;
      this.importing = true;
      try {
        let r;
        if (file.type === 'image/png' || file.name.toLowerCase().endsWith('.png')) {
          const cardFile = await fileToDataUrl(file);
          r = await api.importCard({ card_file: cardFile, filename: file.name });
        } else {
          const text = await file.text();
          let card;
          try { card = JSON.parse(text); }
          catch { throw new Error(this.creatorText('import_invalid_file', '文件不是有效的 JSON/PNG 角色卡')); }
          r = await api.importCard(card);
        }
        const app = r?.data || r;
        this.showToast(this.creatorText('import_success', '导入成功，正在打开…'), 'success', 1200);
        setTimeout(() => { location.href = `/app/create.html?id=${encodeURIComponent(app.id)}`; }, 500);
      } catch (err) {
        this.showToast(err.message || this.creatorText('import_failed', '导入失败'), 'error');
      } finally {
        this.importing = false;
      }
    },

    // ---- 导出当前角色卡为 SillyTavern V2 JSON ----
    async exportCard() {
      if (!this.editingId) return;
      try {
        const r = await api.exportCard(this.editingId);
        const card = r?.data || r;
        const blob = new Blob([JSON.stringify(card, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${(this.form.name || 'character').replace(/[^\w一-龥-]+/g, '_')}.json`;
        document.body.appendChild(a); a.click(); a.remove();
        URL.revokeObjectURL(url);
        this.showToast(this.creatorText('export_success', '已导出'), 'success', 1200);
      } catch (err) {
        this.showToast(err.message || this.creatorText('export_failed', '导出失败'), 'error');
      }
    },

    async exportCardPng() {
      if (!this.editingId) return;
      try {
        const r = await api.exportCardPng(this.editingId);
        const data = r?.data || r;
        const a = document.createElement('a');
        a.href = data.data_url;
        a.download = data.filename || `${(this.form.name || 'character').replace(/[^\w一-龥-]+/g, '_')}.png`;
        document.body.appendChild(a); a.click(); a.remove();
        this.showToast(this.creatorText('png_export_success', 'PNG 角色卡已导出'), 'success', 1200);
      } catch (err) {
        this.showToast(err.message || this.creatorText('png_export_failed', 'PNG 导出失败'), 'error');
      }
    },

    async submit() {
      const payload = this.payload();
      if (!payload.name) {
        this.showToast(this.creatorText('validate_name', '请填写角色名称'), 'error');
        return;
      }
      if (!payload.summary && !payload.description) {
        this.showToast(this.creatorText('validate_summary', '请填写一句简介或角色设定'), 'error');
        return;
      }
      this.loading = true;
      try {
        let app;
        if (this.editingId) {
          const r = await api.updateApp(this.editingId, payload);
          app = r?.data || r;
          this.showToast(this.creatorText('saved_success', '角色已保存'), 'success', 1200);
          setTimeout(() => { location.href = '/app/my-apps.html'; }, 450);
        } else {
          const r = await api.createApp(payload);
          app = r?.data || r;
          this.showToast(this.creatorText('created_success', '角色已创建'), 'success', 1200);
          setTimeout(() => {
            location.href = `/app/chat.html?app_id=${encodeURIComponent(app.id)}`;
          }, 450);
        }
      } catch (err) {
        this.showToast(err.message || this.creatorText('save_failed', '保存失败'), 'error');
      } finally {
        this.loading = false;
      }
    },

    async remove() {
      if (!this.editingId) return;
      if (!confirm(this.creatorText('delete_confirm', '确定删除这个角色？此操作无法撤销。'))) return;
      this.loading = true;
      try {
        await api.deleteApp(this.editingId);
        this.showToast(this.creatorText('delete_success', '已删除'), 'success', 1000);
        setTimeout(() => { location.href = '/app/my-apps.html'; }, 350);
      } catch (err) {
        this.showToast(err.message || this.creatorText('delete_failed', '删除失败'), 'error');
      } finally {
        this.loading = false;
      }
    },
  };
}

function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ''));
    reader.onerror = () => reject(reader.error || new Error('read file failed'));
    reader.readAsDataURL(file);
  });
}

window.createPage = createPage;
document.addEventListener('alpine:init', () => {
  if (window.Alpine?.data) window.Alpine.data('createPage', createPage);
});
