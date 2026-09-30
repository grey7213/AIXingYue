import { api } from './api.js?v=20260917-r8';

// Dedicated persistence: saving images never overwrites chat models or presets.
export function adminImages() {
  return {
    imageModels: [], imageBusy: false, imageError: '', imageLoaded: false, imageSelected: '',
    imageCurrent() { return this.imageModels.find(m => m.id === this.imageSelected); },
    async loadImageModels() {
      this.imageBusy = true; this.imageError = '';
      try {
        const r = await api.imageModels();
        this.imageModels = (r.data || r).list || [];
        if (!this.imageCurrent()) this.imageSelected = this.imageModels[0]?.id || '';
        this.imageLoaded = true;
      } catch (e) { this.imageError = e.message || '读取失败，请重试'; }
      finally { this.imageBusy = false; }
    },
    addImageModel() {
      const id = crypto.randomUUID();
      this.imageModels.push({id, name: '新生图模型', model: '', base_url: '', api_key: '', enabled: false, cost_points: 0, size: '1024x1024', quality: '', memo: ''});
      this.imageSelected = id;
    },
    async removeImageModel() {
      const {confirmAction} = await import('./dialogs.js?v=20260917-r8');
      if (!await confirmAction('保存后用户将不能再选择此模型，已生成的图片会保留。', {title:'移除生图模型',confirmText:'移除'})) return;
      this.imageModels = this.imageModels.filter(m => m.id !== this.imageSelected);
      this.imageSelected = this.imageModels[0]?.id || '';
    },
    async saveImageModels() {
      this.imageBusy = true; this.imageError = '';
      try {
        const r = await api.saveImageModels(this.imageModels);
        this.imageModels = (r.data || r).list || [];
        this.showToast('生图配置已保存', 'success');
      } catch (e) { this.imageError = e.message || '保存失败，请重试'; }
      finally { this.imageBusy = false; }
    },
  };
}
