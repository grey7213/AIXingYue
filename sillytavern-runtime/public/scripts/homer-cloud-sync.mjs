// Serializes chat-storage writes only. This never retries a model generation.
export const CHAT_KEEPALIVE_MAX_BYTES = 24 * 1024;
// Completed deduplication state is optional: never retain twelve entire large
// histories (plus provider/server response fields) just to skip another save.
export const CHAT_SAVED_CACHE_MAX_BYTES = 4 * 1024 * 1024;

function safeSavedResponse(response) {
    const fields = ['id', 'role', 'content', 'created_at', 'swipes', 'swipe_index'];
    if (!Array.isArray(response?.messages)) return {};
    return { messages: response.messages.map(message => {
        const item = {};
        for (const key of fields) if (message && Object.prototype.hasOwnProperty.call(message, key)) item[key] = message[key];
        return item;
    }) };
}

export function captureCloudSync(scope, payload) {
    const body = JSON.stringify(payload);
    return { scope, body, payload: JSON.parse(body), bytes: new TextEncoder().encode(body).byteLength };
}

export function canApplyCloudSync(snapshot, currentScope, currentMessages) {
    return snapshot.scope === currentScope
        && JSON.stringify(snapshot.payload.messages) === JSON.stringify(currentMessages);
}

export function createCloudSyncQueue(send) {
    const scopes = new Map();
    let tail = Promise.resolve();
    function stateFor(scope) {
        if (!scopes.has(scope)) scopes.set(scope, { saved: '', savedResponse: null, savedBytes: 0, latest: null, pending: null });
        return scopes.get(scope);
    }
    function pruneSavedScopes() {
        let bytes = [...scopes.values()].reduce((sum, value) => sum + value.savedBytes, 0);
        if (scopes.size <= 12 && bytes <= CHAT_SAVED_CACHE_MAX_BYTES) return;
        for (const [key, value] of scopes) {
            if (!value.pending && (!value.latest || value.latest.settled)) {
                scopes.delete(key); bytes -= value.savedBytes;
            }
            if (scopes.size <= 12 && bytes <= CHAT_SAVED_CACHE_MAX_BYTES) break;
        }
    }
    return {
        enqueue(snapshot, { keepaliveOnly = false } = {}) {
            const state = stateFor(snapshot.scope);
            if (state.latest?.snapshot.body === snapshot.body && !state.latest.settled) return state.latest.promise;
            if (state.saved === snapshot.body && !state.pending) return Promise.resolve({ snapshot, skipped: true,
                response: JSON.parse(JSON.stringify(state.savedResponse)) });
            const entry = { snapshot, settled: false, promise: null };
            state.latest = entry;
            state.pending = snapshot;
            if (keepaliveOnly && snapshot.bytes > CHAT_KEEPALIVE_MAX_BYTES) {
                entry.settled = true;
                entry.promise = Promise.resolve({ snapshot, deferred: true });
                return entry.promise;
            }
            entry.promise = tail.then(async () => {
                const response = await send(snapshot, { keepalive: snapshot.bytes <= CHAT_KEEPALIVE_MAX_BYTES });
                const savedResponse = JSON.parse(JSON.stringify(safeSavedResponse(response)));
                const savedBytes = snapshot.bytes + new TextEncoder().encode(JSON.stringify(savedResponse)).byteLength;
                // A very large completed history is already durable in the
                // outbox/server. Saving it again is safe; retaining it forever
                // for in-memory deduplication is not needed.
                state.saved = savedBytes <= CHAT_SAVED_CACHE_MAX_BYTES ? snapshot.body : '';
                state.savedResponse = state.saved ? savedResponse : null;
                state.savedBytes = state.saved ? savedBytes : 0;
                if (state.pending === snapshot) state.pending = null;
                return { snapshot, response };
            }).finally(() => {
                entry.settled = true;
                if (state.latest === entry) state.latest = null;
                pruneSavedScopes();
            });
            // Retain the latest failed snapshot, without poisoning future
            // storage writes. A retry is explicit, not a provider replay.
            tail = entry.promise.catch(() => {});
            return entry.promise;
        },
        pending(scope) { return scopes.get(scope)?.pending || null; },
    };
}
