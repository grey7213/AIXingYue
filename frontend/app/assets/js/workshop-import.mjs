export const RESOURCE_LABELS = { preset: '预设', mod: 'Mod', regex: '界面模板', ui_template: '界面模板' };
export const canonicalResourceType = type => type === 'regex' ? 'ui_template' : type;
export const isTemplateResource = type => canonicalResourceType(type) === 'ui_template';

export function normalizeResource(type, source) {
    if (!RESOURCE_LABELS[type]) throw Error('不支持的资源类型');
    if (isTemplateResource(type)) {
        const root = source?.data || source;
        if (Array.isArray(source) || root?.regex_scripts || root?.extensions?.regex_scripts || root?.scripts || root?.findRegex !== undefined || root?.find !== undefined) {
            return normalizeRules(source);
        }
        if (typeof source === 'string' && source.trim()) return source;
        if (source && typeof source === 'object') return source;
        throw Error('请选择非空的 HTML、文本或 JSON 模板');
    }
    if (!source || typeof source !== 'object') throw Error('文件内容需要是 JSON 对象或数组');
    const root = source.data && typeof source.data === 'object' ? source.data : source;
    let entries;
    const candidates = type === 'mod'
        ? [Array.isArray(source) ? source : null, root.entries, root.character_book?.entries, root.world_info, root.items]
        : [Array.isArray(source) ? source : null, root.prompts, root.blocks, root.entries, root.preset?.prompts, root.items];
    entries = candidates.find(value => Array.isArray(value) || (value && typeof value === 'object'));
    if (entries && !Array.isArray(entries)) entries = Object.values(entries);
    if (!entries?.length || entries.some(item => !item || typeof item !== 'object' || Array.isArray(item))) {
        throw Error(`文件中没有可导入的${RESOURCE_LABELS[type]}条目`);
    }
    // Keep native flags, ordering and unknown extension fields intact.
    if (type === 'preset' && (Array.isArray(root.prompts) || Array.isArray(root.blocks))) return { ...root };
    return { ...(Array.isArray(root) ? {} : root), entries };
}

function normalizeRules(source) {
    const root = source.data && typeof source.data === 'object' ? source.data : source;
    let entries = Array.isArray(source) ? source : root.regex_scripts || root.extensions?.regex_scripts || root.scripts;
    if (!entries && (root.findRegex !== undefined || root.find !== undefined)) entries = [root];
    if (!Array.isArray(entries) || !entries.length) throw Error('文件中没有可导入的正则规则');
    return { regex_scripts: entries.map((item, index) => {
        if (!item || typeof item !== 'object') throw Error(`第 ${index + 1} 条规则不是有效对象`);
        const find = item.findRegex ?? item.find ?? item.pattern;
        if (typeof find !== 'string' || !find.trim()) throw Error(`第 ${index + 1} 条规则缺少查找表达式`);
        return { ...item, scriptName: item.scriptName || item.name || `规则 ${index + 1}`, findRegex: find,
            replaceString: String(item.replaceString ?? item.replace ?? item.replacement ?? ''),
            disabled: item.disabled === true || item.enabled === false,
            placement: Array.isArray(item.placement) ? item.placement : [2] };
    }) };
}

export async function readResourceFile(type, file) {
    if (!file || file.size > 8 * 1024 * 1024) throw Error('请选择 8 MB 以内的资源文件');
    const text = (await file.text()).replace(/^\uFEFF/, '');
    let source;
    try { source = JSON.parse(text); }
    catch {
        if (!isTemplateResource(type) || /\.json$/i.test(file.name)) throw Error('文件不是有效的 JSON，请选择导出的资源文件');
        source = text;
    }
    return normalizeResource(type, source);
}
