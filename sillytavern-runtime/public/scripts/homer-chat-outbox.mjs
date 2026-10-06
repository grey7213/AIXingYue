// Durable chat-storage snapshots only. No model requests or login credentials.
export const OUTBOX_ACK_MAX_ROWS = 24;
export const OUTBOX_ACK_MAX_BYTES = 32 * 1024 * 1024;
const STORE = 'snapshots';
const encoder = new TextEncoder();

function identity(scope, kind = 'chat') {
    let parts;
    try { parts = JSON.parse(scope); } catch { throw new TypeError('Invalid outbox scope'); }
    if (!Array.isArray(parts) || parts.length !== 3
        || parts.some(value => typeof value !== 'string' || !value.trim() || value.length > 160)
        || !['chat', 'extension-settings'].includes(kind)) throw new TypeError('Invalid outbox scope or kind');
    const [owner, app_id, conversation_id] = parts;
    return { scope: JSON.stringify(parts), owner, app_id, conversation_id, kind, key: [...parts, kind] };
}

function capture(snapshot, kind) {
    const id = identity(snapshot?.scope, kind);
    if (typeof snapshot?.body !== 'string') throw new TypeError('Outbox body must be captured JSON');
    let payload;
    try { payload = JSON.parse(snapshot.body); } catch { throw new TypeError('Invalid outbox body'); }
    if (!payload || Array.isArray(payload) || typeof payload !== 'object'
        || payload.app_id !== id.app_id || payload.conversation_id !== id.conversation_id) {
        throw new TypeError('Outbox body does not match its scope');
    }
    const allowed = kind === 'chat' ? ['app_id', 'conversation_id', 'title', 'messages']
        : ['app_id', 'conversation_id', 'extension_settings'];
    if (Object.keys(payload).some(key => !allowed.includes(key))) throw new TypeError('Unsupported outbox fields');
    if (kind === 'chat' && !Array.isArray(payload.messages)) throw new TypeError('Outbox messages are required');
    if (kind === 'extension-settings' && (!payload.extension_settings
        || typeof payload.extension_settings !== 'object' || Array.isArray(payload.extension_settings))) {
        throw new TypeError('Outbox extension settings are required');
    }
    return { ...id, body: snapshot.body, bytes: encoder.encode(snapshot.body).byteLength };
}

function handle(row) {
    return { scope: row.scope, owner: row.owner, app_id: row.app_id, conversation_id: row.conversation_id,
        kind: row.kind, revision: row.revision, ackRevision: row.ackRevision || 0,
        commitId: row.commitId, body: row.body, bytes: row.bytes, pending: row.pending === 1 };
}

function safeAcknowledgement(kind, response) {
    if (kind !== 'chat') return {};
    if (!Array.isArray(response?.messages)) throw new TypeError('Cloud did not acknowledge chat messages');
    // Do not persist arbitrary response/config/header/token fields.
    const fields = ['id', 'role', 'content', 'created_at', 'swipes', 'swipe_index'];
    return { messages: response.messages.map(message => {
        const item = {};
        if (!message || typeof message !== 'object' || Array.isArray(message)) throw new TypeError('Invalid cloud message');
        for (const field of fields) if (Object.prototype.hasOwnProperty.call(message, field)) item[field] = message[field];
        return JSON.parse(JSON.stringify(item));
    }) };
}

// The factory is injectable for tests; the real application uses browser IndexedDB.
export function createChatOutbox({ indexedDB = globalThis.indexedDB, databaseName = 'homer-chat-outbox-v1' } = {}) {
    let opening = null;
    let sequence = 0;
    // This is a storage identity, not an authentication secret. It also fences
    // a delayed ACK when an old acknowledged row was evicted then recreated.
    const instanceId = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
    function open() {
        if (opening) return opening;
        opening = new Promise((resolve, reject) => {
            if (!indexedDB?.open) { reject(new Error('Local conversation storage is unavailable')); return; }
            let abandoned = false;
            const request = indexedDB.open(databaseName, 1);
            request.onupgradeneeded = () => {
                const db = request.result;
                if (!db.objectStoreNames.contains(STORE)) {
                    const store = db.createObjectStore(STORE, { keyPath: 'key' });
                    store.createIndex('owner', 'owner');
                    store.createIndex('pending', 'pending');
                }
            };
            request.onerror = () => reject(request.error || new Error('Local storage could not open'));
            request.onblocked = () => { abandoned = true; reject(new Error('Local storage upgrade is blocked')); };
            request.onsuccess = () => {
                if (abandoned) { request.result.close(); return; }
                request.result.onversionchange = () => { request.result.close(); opening = null; };
                resolve(request.result);
            };
        }).catch(error => { opening = null; throw error; });
        return opening;
    }

    async function transaction(mode, execute) {
        const db = await open();
        return new Promise((resolve, reject) => {
            let tx, result, failure;
            try {
                // Prefer strict durability when supported; old WebViews still
                // require transaction completion, never a request-success ACK.
                try { tx = db.transaction(STORE, mode, mode === 'readwrite' ? { durability: 'strict' } : undefined); }
                catch (error) { if (!(error instanceof TypeError)) throw error; tx = db.transaction(STORE, mode); }
                tx.oncomplete = () => resolve(result);
                tx.onabort = () => reject(failure || tx.error || new Error('Local storage transaction aborted'));
                tx.onerror = event => { failure ||= event.target?.error || tx.error; };
                const guarded = callback => (...args) => {
                    try { callback(...args); } catch (error) { failure = error; tx.abort(); }
                };
                execute(tx.objectStore(STORE), value => { result = value; }, guarded);
            } catch (error) {
                failure = error;
                if (tx) { try { tx.abort(); } catch { reject(error); } } else reject(error);
            }
        });
    }

    function pruneAcknowledged(store, guarded) {
        const rows = [];
        let bytes = 0;
        const request = store.index('pending').openCursor(0);
        request.onsuccess = guarded(() => {
            const cursor = request.result;
            if (cursor) {
                const row = cursor.value;
                const size = Number(row.bytes || 0) + Number(row.ackBytes || 0);
                rows.push({ key: row.key, size, updatedAt: row.updatedAt || 0 }); bytes += size;
                cursor.continue(); return;
            }
            rows.sort((a, b) => a.updatedAt - b.updatedAt);
            while (rows.length > OUTBOX_ACK_MAX_ROWS || bytes > OUTBOX_ACK_MAX_BYTES) {
                const oldest = rows.shift(); if (!oldest) break;
                bytes -= oldest.size; store.delete(oldest.key);
            }
        });
    }

    function readStored(id) {
        return transaction('readonly', (store, done, guarded) => {
            const request = store.get(id.key);
            request.onsuccess = guarded(() => done(request.result));
        });
    }

    function sameCommittedRow(row, expected) {
        return Boolean(row && row.revision === expected.revision
            && row.body === expected.body && row.commitId === expected.commitId);
    }

    function sameAcknowledgement(row, ackBody) {
        return row.pending === 0 && row.ackRevision === row.revision
            && JSON.stringify(row.ackPayload) === ackBody;
    }

    return {
        async prepare(snapshot, kind = 'chat') {
            const captured = capture(snapshot, kind);
            // A read-only, completed transaction can confirm an unchanged
            // durable body without taking another exclusive write lock. A
            // changed/missing row is rechecked below inside its strict write
            // transaction, so concurrent prepares cannot lose a revision.
            const stored = await readStored(captured);
            if (stored?.body === captured.body) return handle(stored);
            return transaction('readwrite', (store, done, guarded) => {
                const request = store.get(captured.key);
                request.onsuccess = guarded(() => {
                    const previous = request.result;
                    if (previous?.body === captured.body) { done(handle(previous)); return; }
                    const row = { ...captured, revision: (previous?.revision || 0) + 1,
                        commitId: `${instanceId}-${++sequence}`,
                        ackRevision: previous?.ackRevision || 0, pending: 1, ackPayload: null, ackBytes: 0, updatedAt: Date.now() };
                    store.put(row); done(handle(row));
                });
            });
        },
        async cloudACK(committed, response) {
            const id = identity(committed?.scope, committed?.kind);
            const expected = { revision: committed?.revision, body: committed?.body, commitId: committed?.commitId };
            const ackPayload = safeAcknowledgement(id.kind, response);
            const ackBody = JSON.stringify(ackPayload);
            const stored = await readStored(id);
            if (!sameCommittedRow(stored, expected)) return { applied: false, revision: stored?.revision || 0 };
            // An identical cached cloud response is not a new storage ACK.
            // Do not rewrite a large row, refresh its eviction age, or scan
            // every acknowledged body again. The caller's version fence must
            // likewise not advance for this no-op. Different message IDs or
            // any other allowed ACK fields still require the real write.
            if (sameAcknowledgement(stored, ackBody)) {
                return { applied: false, revision: stored.revision, unchanged: true };
            }
            return transaction('readwrite', (store, done, guarded) => {
                const request = store.get(id.key);
                request.onsuccess = guarded(() => {
                    const row = request.result;
                    if (!sameCommittedRow(row, expected)) {
                        done({ applied: false, revision: row?.revision || 0 }); return;
                    }
                    // Another ACK/prepare may have won between the read-only
                    // check and this write transaction. Recheck identity and
                    // exact payload; never clear that newer pending snapshot.
                    if (sameAcknowledgement(row, ackBody)) {
                        done({ applied: false, revision: row.revision, unchanged: true }); return;
                    }
                    row.pending = 0; row.ackRevision = row.revision;
                    row.ackPayload = ackPayload; row.ackBytes = encoder.encode(ackBody).byteLength;
                    row.updatedAt = Date.now(); store.put(row);
                    pruneAcknowledged(store, guarded);
                    done({ applied: true, revision: row.revision });
                });
            });
        },
        async fence(scope, kind = 'chat') {
            const id = identity(scope, kind);
            return transaction('readonly', (store, done, guarded) => {
                const request = store.get(id.key);
                request.onsuccess = guarded(() => done({ revision: request.result?.revision || 0, ackRevision: request.result?.ackRevision || 0,
                    commitId: request.result?.commitId || null }));
            });
        },
        async read(scope, kind = 'chat', fence) {
            const id = identity(scope, kind);
            return transaction('readonly', (store, done, guarded) => {
                const request = store.get(id.key);
                request.onsuccess = guarded(() => {
                    const row = request.result;
                    if (!row) { done(null); return; }
                    const current = handle(row);
                    done({ ...current, payload: JSON.parse(row.body), ackPayload: row.ackPayload,
                        preferred: current.pending || Boolean(fence && (current.revision > fence.revision || current.ackRevision > fence.ackRevision
                            || current.commitId !== fence.commitId)) });
                });
            });
        },
        async pending(owner) {
            if (typeof owner !== 'string' || !owner.trim()) return [];
            return transaction('readonly', (store, done, guarded) => {
                const rows = [], request = store.index('owner').openCursor(owner);
                request.onsuccess = guarded(() => {
                    const cursor = request.result;
                    if (!cursor) { done(rows); return; }
                    if (cursor.value.pending === 1) rows.push(handle(cursor.value));
                    cursor.continue();
                });
            });
        },
        async close() { const db = opening ? await opening : null; db?.close(); opening = null; },
    };
}
