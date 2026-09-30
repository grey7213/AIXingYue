// Public metadata only; never pass a provider's secret settings to the chat UI.
export function publicModel(model) {
    return {
        id: String(model?.id || ''), name: String(model?.display_name || model?.name || model?.model || model?.id || '未命名模型'),
        model: String(model?.model || ''), price_label: String(model?.price_label || ''),
        group_id: String(model?.group_id || model?.preset_id || 'site'),
        group_name: String(model?.group_name || model?.preset_name || ''),
        enabled: model?.enabled !== false,
    };
}

export function fillModelSelect(select, models, selectedId = '') {
    select.replaceChildren();
    select.dataset.pickerTitle = '选择模型';
    const groups = new Map();
    for (const raw of models || []) {
        const model = publicModel(raw);
        if (!model.enabled || !model.id) continue;
        if (!groups.has(model.group_id)) {
            const group = document.createElement('optgroup');
            group.label = model.group_name || (model.group_id === 'site' ? '站点模型' : `模型分组 ${groups.size + 1}`);
            groups.set(model.group_id, group); select.append(group);
        }
        const option = document.createElement('option');
        option.value = model.id;
        option.textContent = model.name + (model.price_label ? ` · ${model.price_label}` : '');
        groups.get(model.group_id).append(option);
    }
    if (Array.from(select.options).some(option => option.value === selectedId)) select.value = selectedId;
}
