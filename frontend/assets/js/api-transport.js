// JSON/text API transport, not the streaming generation transport.
// A dropped read may be repeated once; writes are never replayed automatically.
export async function apiText(url, init = {}, { timeoutMs = /^(GET|HEAD)$/i.test(init.method || 'GET') ? 12000 : 60000, fetchImpl = fetch } = {}) {
    const controller = new AbortController();
    const caller = init.signal;
    const cancel = () => controller.abort(caller.reason);
    if (caller?.aborted) cancel();
    else caller?.addEventListener('abort', cancel, { once: true });
    let timedOut = false;
    const timer = setTimeout(() => { timedOut = true; controller.abort(); }, timeoutMs);
    const attempts = /^(GET|HEAD)$/i.test(init.method || 'GET') ? 2 : 1;
    try {
        for (let attempt = 0; attempt < attempts; attempt++) {
            try {
                controller.signal.throwIfAborted();
                const response = await fetchImpl(url, { ...init, signal: controller.signal });
                // Keep the deadline active until the complete body has arrived.
                const text = await response.text();
                return { response, text };
            } catch (error) {
                if (caller?.aborted) throw caller.reason || error;
                if (!controller.signal.aborted && error instanceof TypeError && attempt + 1 < attempts) continue;
                if (controller.signal.aborted || error instanceof TypeError) {
                    const failure = new Error(timedOut
                        ? '服务器响应超时，请重试。'
                        : '未能连接服务器，请重试。未确认的操作不会自动重复提交。');
                    failure.name = 'ApiConnectionError';
                    failure.code = 0;
                    failure.reason = timedOut ? 'timeout' : 'network';
                    throw failure;
                }
                throw error;
            }
        }
    } finally {
        clearTimeout(timer);
        caller?.removeEventListener('abort', cancel);
    }
}
