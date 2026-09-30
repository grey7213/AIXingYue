import { api, requireAuth, getCachedUser } from './app-core.js?v=20260917-r8';
import { readPageCache, writePageCache } from './page-cache.js';
import { RESOURCE_LABELS, normalizeResource, readResourceFile, canonicalResourceType } from './workshop-import.mjs';
import { confirmAction } from '/assets/js/dialogs.js';

const $ = selector => document.querySelector(selector);
const params = new URLSearchParams(location.search);
const type = RESOURCE_LABELS[params.get('type')] ? canonicalResourceType(params.get('type')) : 'preset';
const label = RESOURCE_LABELS[type], id = params.get('id') || '';
const listUrl = `/app/workshop-resource.html?type=${type}`;
const editUrl = workId => `/app/workshop-resource-editor.html?type=${type}${workId ? `&id=${encodeURIComponent(workId)}` : ''}`;
const dataOf = value => value?.data ?? value ?? {};
const owner = getCachedUser();
const sameOwner = () => String(getCachedUser()?.id || '') === String(owner?.id || '');
const status = (text = '', error = false) => { $('#resource-status').textContent = text; $('#resource-status').classList.toggle('error', error); };
document.title = `${label} · 惑梦`;

if (requireAuth()) {
    if ($('#resource-list')) initList();
    else initEditor();
}

function initList() {
    let scope = 'mine', query = '', epoch = 0;
    $('#resource-title').textContent = label;
    $('#resource-new').href = editUrl();
    $('#resource-intro').textContent = ({ preset: '管理对话预设，支持导入原生预设文件。', mod: '管理世界书与对话 Mod，支持导入条目文件。', ui_template: '界面模板通过正则替换展示内容。导入规则后，可以测试文本与页面效果。' })[type];
    function render(list) {
        const root = $('#resource-list'); root.replaceChildren();
        for (const work of list) {
            const link = document.createElement('a'); link.className = 'resource-item'; link.href = editUrl(work.id);
            const body = document.createElement('span'), title = document.createElement('strong'), summary = document.createElement('small');
            title.textContent = work.name || '未命名资源'; summary.textContent = work.summary || (work.is_public ? '公开资源' : '仅自己可见');
            body.append(title, summary); const arrow = document.createElement('span'); arrow.textContent = '›'; arrow.style.flex = '0'; arrow.setAttribute('aria-hidden', 'true');
            link.append(body, arrow); root.append(link);
        }
    }
    async function refresh() {
        const version = ++epoch, cacheKey = `resources.${type}.${scope}`;
        const cached = !query && readPageCache(cacheKey, owner);
        if (cached?.list) render(cached.list);
        status($('#resource-list').childElementCount ? '' : '正在读取资源…'); $('#resource-retry').hidden = true;
        try {
            const result = dataOf(await api.communityWorks({ type, scope, q: query }));
            if (version !== epoch || !sameOwner()) return;
            const list = (result.list || []).filter(work => canonicalResourceType(work.work_type) === type);
            render(list); status(list.length ? '' : query ? '没有找到相关资源，试试其他关键词。' : '这里还没有资源。点击右上角新建，可直接从文件导入。');
            if (!query) writePageCache(cacheKey, owner, { list });
        } catch (error) {
            if (version !== epoch) return;
            status(error.message || '读取失败，请重试。', true); $('#resource-retry').hidden = false;
        }
    }
    $('#resource-search').onsubmit = event => { event.preventDefault(); query = new FormData(event.target).get('q').trim(); void refresh(); };
    for (const button of document.querySelectorAll('[data-scope]')) button.onclick = () => {
        scope = button.dataset.scope;
        for (const other of document.querySelectorAll('[data-scope]')) other.setAttribute('aria-pressed', String(other === button));
        $('#resource-list').replaceChildren(); void refresh();
    };
    $('#resource-retry').onclick = refresh;
    window.addEventListener('pageshow', event => { if (event.persisted) void refresh(); });
    void refresh();
}

function initEditor() {
    const form = $('#resource-form');
    const field = name => form.elements.namedItem(name);
    let detail = null, writable = !id, busy = false, dirty = false, worker = null, timer = 0;
    const draftKey = `resource-draft.${type}.${id || 'new'}`;
    $('#resource-back').href = listUrl;
    $('#resource-title').textContent = id ? label : `新建${label}`;
    $('#resource-regex-preview').hidden = type !== 'ui_template';
    $('#resource-demo-field').hidden = true;
    $('#resource-file').accept = type === 'ui_template' ? '.json,.html,.txt' : '.json,application/json';
    const fileInput = $('#resource-file');
    const importButton = document.createElement('button');
    importButton.type = 'button'; importButton.className = 'resource-button';
    importButton.id = 'resource-import-button'; importButton.textContent = '选择文件';
    importButton.onclick = () => { if (writable && !busy) fileInput.click(); };
    const fileName = document.createElement('span'); fileName.className = 'resource-file-name';
    fileName.textContent = type === 'ui_template' ? '支持 HTML、TXT 或 JSON' : '支持 JSON 文件';
    fileInput.hidden = true; fileInput.before(importButton, fileName);
    function content() {
        const raw = field('content').value.trim();
        let parsed;
        try { parsed = JSON.parse(raw); }
        catch { if (type === 'ui_template') parsed = raw; else throw Error('内容不是有效的 JSON，请检查源内容或重新导入'); }
        return normalizeResource(type, parsed);
    }
    function updateCount(value) {
        const entries = value?.regex_scripts || value?.entries || value?.prompts || value?.blocks;
        $('#resource-count').textContent = entries ? `已读取 ${Array.isArray(entries) ? entries.length : Object.keys(entries).length} 条${label}内容` : '内容已读入';
    }
    function draft() {
        if (!writable || !sameOwner()) return;
        dirty = true;
        const values = Object.fromEntries(['name','summary','content','demo_html','version_name','version_description'].map(name => [name, field(name).value]));
        values.is_public = field('is_public').checked; values.is_open_source = field('is_open_source').checked;
        writePageCache(draftKey, owner, values);
    }
    let draftTimer;
    form.addEventListener('input', () => { dirty = true; clearTimeout(draftTimer); draftTimer = setTimeout(draft, 350); });
    function fill(values) {
        for (const name of ['name','summary','content','demo_html','version_name','version_description']) {
            if (values[name] !== undefined) field(name).value = typeof values[name] === 'string' ? values[name] : JSON.stringify(values[name], null, 2);
        }
        for (const name of ['is_public','is_open_source']) field(name).checked = !!values[name];
        try { updateCount(content()); } catch {}
    }
    $('#resource-file').onchange = async event => {
        const file = event.target.files?.[0]; event.target.value = '';
        if (!file || !writable || busy) return;
        try {
            const value = await readResourceFile(type, file);
            fileName.textContent = file.name;
            field('content').value = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
            if (!field('name').value.trim()) field('name').value = file.name.replace(/\.[^.]+$/, '').slice(0, 120);
            updateCount(value); draft(); status('已导入。点击保存后生效。');
        } catch (error) { status(error.message, true); }
    };
    form.onsubmit = async event => {
        event.preventDefault(); if (busy || !writable || !sameOwner()) return;
        try {
            const value = content();
            if (id && (!field('version_name').value.trim() || !field('version_description').value.trim())) throw Error('请填写版本名称与更新说明');
            const payload = { work_type: detail?.work_type || type, name: field('name').value.trim(), summary: field('summary').value.trim(), content: value,
                is_public: field('is_public').checked, is_open_source: field('is_open_source').checked,
                demo_html: type === 'ui_template' ? field('demo_html').value : '',
                version_name: field('version_name').value.trim(), version_description: field('version_description').value.trim() };
            busy = true; $('#resource-save').disabled = true; $('#resource-save').textContent = '保存中…'; status();
            if (id) await api.updateCommunityWork(id, payload); else await api.createCommunityWork(payload);
            dirty = false; clearTimeout(draftTimer); writePageCache(draftKey, owner, {});
            location.replace(listUrl);
        } catch (error) { status(error.message || '保存失败，内容已保留。', true); }
        finally { busy = false; $('#resource-save').disabled = false; $('#resource-save').textContent = '保存'; }
    };
    $('#resource-back').onclick = async event => {
        if (busy) { event.preventDefault(); return; }
        if (!dirty) return;
        event.preventDefault(); draft();
        if (await confirmAction('草稿已保留，返回资源列表？')) { dirty = false; location.assign(listUrl); }
    };
    window.addEventListener('beforeunload', event => { if (dirty && writable) { draft(); event.preventDefault(); event.returnValue = ''; } });
    $('#resource-export').onclick = () => {
        try {
            const value = content(), blob = new Blob([typeof value === 'string' ? value : JSON.stringify(value, null, 2)], { type: typeof value === 'string' ? 'text/html' : 'application/json' });
            const href = URL.createObjectURL(blob), link = document.createElement('a'); link.href = href;
            link.download = (field('name').value || label).replace(/[\\/:*?"<>|]/g, '_') + (typeof value === 'string' ? '.html' : '.json');
            link.click(); setTimeout(() => URL.revokeObjectURL(href), 1000);
        } catch (error) { status(error.message, true); }
    };
    $('#resource-delete').onclick = async () => {
        if (busy || !writable || !id || !await confirmAction('删除这份资源？已使用的角色卡不会被删除。')) return;
        busy = true;
        try { await api.deleteCommunityWork(id); dirty = false; location.replace(listUrl); }
        catch (error) { status(error.message, true); } finally { busy = false; }
    };
    $('#resource-favorite').onclick = async () => {
        if (busy) return; busy = true;
        try { const result = dataOf(await api.toggleCommunityWorkFavorite(id)); $('#resource-favorite').textContent = result.favorited ? '取消收藏' : '收藏'; }
        catch (error) { status(error.message, true); } finally { busy = false; }
    };
    $('#regex-run').onclick = () => {
        worker?.terminate(); clearTimeout(timer);
        try {
            const value = content();
            const rules = value?.regex_scripts;
            // Preserve legacy HTML resources without inventing a regex that
            // would replace every message. Preview them directly, script-free.
            const sample = typeof value === 'string' ? value : value?.html || value?.ui_template?.html || $('#regex-sample').value;
            if (!rules && typeof value !== 'string' && !value?.html && !value?.ui_template?.html) throw Error('这份旧模板包含界面配置，没有文本替换规则。可保留原配置，或导入正则 JSON 后预览。');
            $('#regex-status').textContent = '正在预览…';
            worker = new Worker('/app/assets/js/regex-preview-worker.mjs', { type: 'module' });
            const current = worker;
            const stop = message => { if (worker !== current) return; current.terminate(); worker = null; clearTimeout(timer); $('#regex-status').textContent = message; };
            worker.onmessage = ({ data }) => {
                if (worker !== current) return;
                if (data.error) { stop(data.error); return; }
                $('#regex-output').textContent = data.output;
                // An opaque, script-free iframe prevents imported HTML accessing
                // accounts, storage, the network or the editor document.
                const html = data.output.replace(/^```(?:html)?\s*\n?/, '').replace(/\n?```\s*$/, '');
                $('#regex-frame').srcdoc = '<!doctype html><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; img-src data: blob:; form-action \'none\'; base-uri \'none\'"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:12px;font:15px/1.5 system-ui;overflow-wrap:anywhere}img{max-width:100%}</style>' + html;
                stop(`已按顺序应用 ${data.applied} 条规则`);
            };
            worker.onerror = () => stop('预览无法运行，请检查规则');
            worker.postMessage({ rules: rules || [], sample });
            timer = setTimeout(() => stop('此规则执行时间过长，已停止预览。请缩短样本或检查嵌套量词。'), 700);
        } catch (error) { $('#regex-status').textContent = error.message; }
    };
    window.addEventListener('pagehide', () => { worker?.terminate(); clearTimeout(timer); });
    async function load() {
        if (id) {
            $('#resource-save').disabled = true; status('正在读取资源…');
            try {
                detail = dataOf(await api.communityWork(id)); if (!sameOwner()) return;
                if (canonicalResourceType(detail.work_type) !== type) throw Error('资源类型不匹配');
                writable = !!detail.is_owner; fill(detail);
                $('#resource-title').textContent = detail.name || label;
                $('#resource-version-fields').hidden = !writable;
                $('#resource-delete').hidden = !writable;
                $('#resource-favorite').hidden = writable;
                $('#resource-favorite').textContent = detail.is_favorited ? '取消收藏' : '收藏';
                $('#resource-save').hidden = !writable; $('#resource-save').disabled = !writable;
                if (!writable) {
                    importButton.hidden = true;
                    for (const input of form.querySelectorAll('input,textarea,select')) input.disabled = true;
                    $('#regex-sample').disabled = false;
                    $('#resource-content-section').hidden = detail.content == null;
                    $('#resource-regex-preview').hidden = type !== 'ui_template' || detail.content == null;
                    $('#resource-export').hidden = detail.content == null;
                }
                if (detail.versions?.length) {
                    $('#resource-versions').hidden = false;
                    for (const version of detail.versions) { const row = document.createElement('p'); row.className = 'resource-version'; row.textContent = version.version_name || version.name || '历史版本'; const note = document.createElement('small'); note.textContent = version.author_description || version.version_description || version.description || ''; row.append(note); $('#resource-versions div').append(row); }
                }
                status();
            } catch (error) { writable = false; status(error.message || '无法读取资源，请返回重试。', true); }
        }
        const saved = writable && readPageCache(draftKey, owner);
        if (saved?.content) { fill(saved); dirty = true; status('已恢复上次未保存的草稿。'); }
    }
    void load();
}
