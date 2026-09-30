// Administrator-only editor. Drafts live in this runtime, not account settings.
import { confirmAction } from '/assets/js/dialogs.js';

const copy = value => JSON.parse(JSON.stringify(value));
const titles = { prompt: '预设', worldbook: '世界书', regex: '正则' };
function el(tag, text, cls = '') {
    const node = document.createElement(tag); node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
}
function button(text, action, cls = '') {
    const node = el('button', text, cls); node.type = 'button'; node.addEventListener('click', action); return node;
}

export function adminWorkspace({ getConfig, getDraft, apply, saveGlobal, busy, notice }) {
    if (!document.querySelector('#homer-admin-workspace-style')) {
        const link = el('link'); link.id = 'homer-admin-workspace-style'; link.rel = 'stylesheet';
        link.href = new URL('./admin-workspace.css', import.meta.url).href; document.head.append(link);
    }
    function open(root, kind) {
        if (busy()) { notice('生成期间不能修改配置，请先停止生成', 'warning'); return; }
        root.querySelector('.haw-editor')?.remove();
        let original = JSON.stringify(getConfig()[kind]);
        let value = copy(getConfig()[kind]);
        let pending = false;
        const page = el('section', undefined, 'haw-editor'); page.setAttribute('aria-label', titles[kind] + '会话设置');
        const header = el('header'); const heading = el('h2', titles[kind]);
        const changed = () => JSON.stringify(value) !== original;
        async function close() {
            if (pending) return;
            if (changed() && !await confirmAction('本次编辑尚未应用。离开将放弃这些修改。', { title: '放弃未应用的修改？', confirmText: '放弃修改' })) return;
            page.remove(); root.classList.remove('haw-editing'); root.querySelector(`[data-admin-kind="${kind}"]`)?.focus();
        }
        header.append(button('‹ 返回', close), heading, el('span', '本次会话', 'haw-badge'));
        const content = el('div', undefined, 'haw-content');
        const status = el('p', '应用后从下一轮生成生效；不会修改角色原件或全局配置。', 'haw-status'); status.setAttribute('role', 'status');
        const fields = el('div'); const search = el('input'); search.type = 'search'; search.placeholder = '搜索条目'; search.setAttribute('aria-label', '搜索条目');
        let filter = '';
        search.addEventListener('input', () => { filter = search.value.trim().toLocaleLowerCase(); renderEntries(); });
        const rows = () => kind === 'worldbook' ? value : kind === 'regex' ? (value.scripts ||= []) : (value.prompts?.length ? value.prompts : (value.blocks ||= []));
        function field(parent, label, item, key, type = 'text', choices = null) {
            const wrapper = el('label', undefined, 'haw-field'); wrapper.append(el('span', label));
            if (type === 'checkbox') wrapper.classList.add('haw-checkbox');
            let input;
            if (choices) { input = el('select'); for (const [v, name] of choices) { const o = el('option', name); o.value = v; input.append(o); } }
            else input = el(type === 'area' ? 'textarea' : 'input');
            if (!choices && type !== 'area') input.type = type;
            input.setAttribute('aria-label', label);
            if (type === 'checkbox') input.checked = Boolean(item[key]);
            else input.value = Array.isArray(item[key]) ? item[key].join(', ') : (item[key] ?? '');
            input.addEventListener('input', () => {
                if (type === 'checkbox') item[key] = input.checked;
                else if (type === 'number') item[key] = input.value === '' ? null : Number(input.value);
                else if (['keys', 'secondary_keys', 'trimStrings'].includes(key)) item[key] = input.value.split(/[,，\n]/).map(s => s.trim()).filter(Boolean);
                else item[key] = input.value;
                status.textContent = '有未应用的修改';
            });
            wrapper.append(input); parent.append(wrapper); return input;
        }
        function renderEntries() {
            fields.replaceChildren();
            if (kind !== 'worldbook') {
                enabledGroup.replaceChildren();
                field(enabledGroup, '启用整组' + titles[kind], value, 'enabled', 'checkbox');
                library.firstChild.textContent = '切换' + titles[kind] + ' · ' + (value.name || '未绑定');
            }
            const entries = rows();
            entries.forEach((item, index) => {
                const name = String(item.name || item.scriptName || item.comment || `条目 ${index + 1}`);
                if (filter && !name.toLocaleLowerCase().includes(filter)) return;
                const details = el('details', undefined, 'haw-entry'); const summary = el('summary');
                const enabled = kind === 'regex' ? !item.disabled : kind === 'prompt' && value.prompts?.length ? item.in_order && item.order_enabled : item.enabled !== false;
                summary.append(el('span', name), el('small', enabled ? '已启用' : '已关闭'));
                details.append(summary);
                const body = el('div', undefined, 'haw-entry-body'); details.append(body);
                field(body, '名称', item, kind === 'regex' ? 'scriptName' : 'name');
                if (kind === 'regex') {
                    field(body, '禁用此规则', item, 'disabled', 'checkbox');
                    field(body, '匹配表达式', item, 'findRegex', 'area'); field(body, '替换内容', item, 'replaceString', 'area');
                    const placements = el('fieldset'); placements.append(el('legend', '应用位置'));
                    for (const [id, label] of [[1, '用户输入'], [2, '模型回复']]) {
                        const row = el('label', label); const check = el('input'); check.type = 'checkbox'; check.checked = (item.placement || []).includes(id);
                        check.addEventListener('change', () => { item.placement = check.checked ? [...new Set([...(item.placement || []), id])] : (item.placement || []).filter(v => v !== id); status.textContent = '有未应用的修改'; });
                        row.prepend(check); placements.append(row);
                    }
                    body.append(placements);
                    field(body, '处理发送给模型的文本', item, 'promptOnly', 'checkbox'); field(body, '处理界面显示', item, 'markdownOnly', 'checkbox');
                    field(body, '最小深度', item, 'minDepth', 'number'); field(body, '最大深度（空表示不限）', item, 'maxDepth', 'number');
                } else {
                    if (kind === 'prompt' && value.prompts?.length) {
                        field(body, '加入发送顺序', item, 'in_order', 'checkbox'); field(body, '启用', item, 'order_enabled', 'checkbox');
                    } else field(body, '启用', item, 'enabled', 'checkbox');
                    if (item.marker) body.append(el('p', '此条目为原生结构标记，保留其系统含义。'));
                    else field(body, '内容', item, 'content', 'area');
                    field(body, '消息身份', item, 'role', 'text', [['system', '系统'], ['user', '用户'], ['assistant', '角色']]);
                    field(body, '顺序', item, 'order', 'number');
                    if (kind === 'worldbook') {
                        field(body, '始终生效', item, 'constant', 'checkbox'); field(body, '关键词（逗号分隔）', item, 'keys');
                        field(body, '二级关键词', item, 'secondary_keys'); field(body, '启用二级匹配', item, 'selective', 'checkbox');
                        field(body, '二级匹配方式', item, 'selective_logic', 'text', [['and_any', '任意匹配'], ['and_all', '全部匹配'], ['not_any', '均不匹配'], ['not_all', '不全部匹配']]);
                        field(body, '插入位置', item, 'position', 'text', [['system', '系统提示'], ['post_history', '历史之后'], ['depth', '指定深度']]);
                        field(body, '插入深度', item, 'depth', 'number'); field(body, '触发概率（0–100）', item, 'probability', 'number');
                    }
                }
                body.append(button('删除条目', async () => { if (await confirmAction('只从本次会话草稿中移除此条目。', { title: '删除条目？', confirmText: '删除' })) { entries.splice(index, 1); renderEntries(); status.textContent = '有未应用的修改'; } }, 'haw-danger'));
                fields.append(details);
            });
            if (!fields.children.length) fields.append(el('p', filter ? '没有匹配的条目' : '暂无条目，可在下方添加。', 'haw-empty'));
        }
        const library = el('details', undefined, 'haw-library');
        const enabledGroup = el('div');
        if (kind !== 'worldbook') {
            library.append(el('summary', '切换' + titles[kind] + ' · ' + (value.name || '未绑定')));
            for (const preset of getConfig().library?.[kind]?.items || []) {
                library.append(button(preset.name || preset.id, async () => {
                    if (changed() && !await confirmAction('切换将放弃当前未应用的编辑。', { title: '切换配置？', confirmText: '切换' })) return;
                    value = copy(preset); value.enabled = true; library.open = false; library.firstChild.textContent = '切换' + titles[kind] + ' · ' + value.name; renderEntries(); status.textContent = '已选择，点击应用后生效';
                }));
            }
            content.append(library);
            content.append(enabledGroup);
        }
        const add = button('＋ 添加条目', () => {
            const id = 'draft-' + crypto.randomUUID();
            rows().push(kind === 'regex' ? { id, scriptName: '新规则', findRegex: '', replaceString: '', placement: [2], markdownOnly: true, disabled: true } :
                { id, identifier: id, name: '新条目', content: '', enabled: true, in_order: true, order_enabled: true, order: rows().length, role: 'system', keys: [], constant: true, probability: 100, position: 'system' });
            filter = ''; search.value = ''; renderEntries(); fields.lastElementChild.open = true; fields.lastElementChild.scrollIntoView({ block: 'nearest' }); status.textContent = '有未应用的修改';
        });
        content.append(search, fields, add);
        const footer = el('footer', undefined, kind === 'worldbook' ? 'haw-footer-single' : '');
        async function commit(global) {
            if (pending || busy()) { status.textContent = '请等待当前操作结束'; return; }
            if (global && !await confirmAction('将覆盖全局库中的此配置，使用它的其他会话也会受到影响。不改变当前启用项或模型绑定。', { title: '保存到全局配置？', confirmText: '保存到全局' })) return;
            pending = true; page.classList.add('is-saving'); status.textContent = '正在校验并应用…';
            try {
                await apply({ ...getDraft(), [kind]: copy(value) });
                value = copy(getConfig()[kind]); original = JSON.stringify(value);
                if (global) await saveGlobal(kind, value);
                status.textContent = global ? '已保存到全局，并应用于本次会话' : '已应用于本次会话，下一轮生成生效'; renderEntries();
            } catch { status.textContent = '应用或保存失败，请检查配置、正则语法与网络后重试'; }
            finally { pending = false; page.classList.remove('is-saving'); }
        }
        footer.append(button('应用到本次会话', () => commit(false), 'haw-primary'));
        if (kind !== 'worldbook') footer.append(button('保存到全局…', () => commit(true), 'haw-global'));
        footer.append(button('恢复模型/角色默认', async () => {
            if (pending || busy()) return;
            if (!await confirmAction('放弃该项的本次会话调整，重新读取当前模型或角色的配置。', { title: '恢复默认？', confirmText: '恢复' })) return;
            pending = true;
            try { const draft = copy(getDraft()); delete draft[kind]; await apply(draft); value = copy(getConfig()[kind]); original = JSON.stringify(value); renderEntries(); status.textContent = '已恢复默认'; }
            catch { status.textContent = '恢复失败，请重试'; } finally { pending = false; }
        }));
        page.append(header, status, content, footer); root.append(page); root.classList.add('haw-editing'); renderEntries(); header.querySelector('button').focus();
    }
    return { open };
}
