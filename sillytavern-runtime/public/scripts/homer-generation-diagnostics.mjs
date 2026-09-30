import { currentModelScope, recordModelFailure } from './homer-model-gate.mjs';
const guidance = {
    'HM-G400': '请求参数无效，请调整后重试',
    'HM-G401': '登录或会话已过期，请重新进入会话',
    'HM-G402': '积分不足，请补充积分或选择消耗更低的模型',
    'HM-G403': '没有权限进行此操作',
    'HM-G404': '角色或会话不可用，请重新选择',
    'HM-G409': '会话与角色不匹配，请重新进入会话',
    'HM-G429': '请求过于频繁，请稍后重试或更换模型',
    'HM-G503': '当前模型暂不可用，请更换模型后重试',
    'HM-G504': '当前模型响应超时，请更换模型后重试',
    'HM-G502': '当前模型生成失败，请更换模型后重试',
    'HM-G204': '当前模型未返回有效内容，请更换模型后重试',
    'HM-GNET': '网络连接中断，请检查网络后重试；仍失败可尝试更换模型',
    'HM-R422': '预设正则执行失败，请联系管理员检查规则',
};
export function generationFailure(payload, status = 502) {
    const value = payload?.error || {};
    const code = Object.hasOwn(guidance, value.code) ? value.code
        : Object.hasOwn(guidance, `HM-G${status}`) ? `HM-G${status}` : 'HM-G502';
    const error = new Error(`[${code}] ${guidance[code]}`);
    error.code = code;
    error.request_id = /^[a-zA-Z0-9_-]{1,80}$/.test(value.request_id || '') ? value.request_id : '';
    return error;
}
export function beginDiagnostic(model, type = 'normal') {
    return { schema: 'homer-generation-v1', scope: currentModelScope(), local_id: crypto.randomUUID(), model: String(model).slice(0, 160), generation_type: type,
        started_at: new Date().toISOString(), start: performance.now(), first_token_ms: null,
        output_chars: 0, status: 'generating', error_code: '' };
}
export function observeDiagnostic(trace, data, text = '') {
    const d = data?.homer_diagnostic;
    if (d) for (const key of ['request_id', 'prompt_id', 'prompt_revision', 'regex_id', 'regex_revision', 'worldbook_revision']) {
        if (/^[a-zA-Z0-9_-]{0,160}$/.test(String(d[key] || ''))) trace[key] = String(d[key] || '');
    }
    if (Number.isInteger(d?.regex_count)) trace.regex_count = d.regex_count;
    if (text && trace.first_token_ms == null) trace.first_token_ms = Math.round(performance.now() - trace.start);
    trace.output_chars = text.length;
}
export function finishDiagnostic(trace, error = null) {
    if (trace.status !== 'generating') return;
    trace.status = error ? (error.name === 'AbortError' ? 'cancelled' : 'failed') : 'complete';
    trace.error_code = error?.code || '';
    if (error?.request_id) trace.request_id = error.request_id;
    trace.total_ms = Math.round(performance.now() - trace.start);
    delete trace.start;
    recordModelFailure(trace);
    window.dispatchEvent(new CustomEvent('homer-generation-diagnostic', { detail: { ...trace } }));
}

export function safeDiagnostic(value) {
    const result = {};
    for (const key of ['schema', 'local_id', 'model', 'generation_type', 'started_at', 'status', 'error_code', 'request_id', 'prompt_id', 'prompt_revision', 'regex_id', 'regex_revision', 'worldbook_revision']) {
        if (typeof value?.[key] === 'string') result[key] = value[key].slice(0, 160);
    }
    for (const key of ['first_token_ms', 'total_ms', 'output_chars', 'regex_count', 'display_regex_count']) {
        if (value?.[key] === null || Number.isFinite(value?.[key])) result[key] = value[key];
    }
    result.display_regex_error_count = Array.isArray(value?.display_regex_errors) ? value.display_regex_errors.length : 0;
    return result;
}
