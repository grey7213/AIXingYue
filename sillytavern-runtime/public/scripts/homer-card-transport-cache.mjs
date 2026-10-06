// Account-scoped transport bytes only, never an offline authorization or chat store.
import { encodedBytesSha256, jsonContentSha256 } from './homer-content-digest.mjs';
export const CARD_TRANSPORT_TTL_MS = 4 * 60 * 60 * 1000;
export const CARD_TRANSPORT_MAX_ROWS = 8;
export const CARD_TRANSPORT_MAX_BYTES = 32 * 1024 * 1024;
const ENTRIES = 'entries';
const METADATA = 'metadata';
const encoder = new TextEncoder();
// One private, bounded layer per module, not eight sources per cache instance.
const memory = new Map();
let memoryBytes = 0, memoryEpoch = {};
const factoryIds = new WeakMap();
let factorySequence = 0;
const activeGenerations = new Map();
// Confirmed-use metadata only: at most eight queued/in-flight items with one
// serialized flush. No source bytes, credentials or session state enter here.
const pendingTouches = new Map();
let touchTimer = null, activeTouch = null;
const TOUCH_DELAY_MS = 100;
const revisionPattern = /^[a-f0-9]{64}$/;
const forbiddenFields = new Set(['token', 'user', 'session', 'launch', 'runtime', 'messages',
    'bridge_token', 'access_token', 'refresh_token', 'authorization', 'password', 'api_key', 'headers', 'cookies']);
const owns = (value, key) => Object.prototype.hasOwnProperty.call(value, key);
const diagnosticKinds = new Set(['session-card', 'character-mirror', 'character-content-v2']);
const diagnosticReasons = new Set(['read-start', 'metadata-missing', 'metadata-expired', 'metadata-invalid',
    'metadata-valid', 'hint-emitted', 'row-missing', 'row-invalid', 'digest-start', 'digest-mismatch',
    'digest-error', 'post-digest-expired', 'post-digest-invalid', 'read-verified', 'idb-error',
    'metadata-expired-candidate', 'row-expired-candidate', 'post-digest-expired-candidate', 'expired-retained',
    'memory-hit', 'memory-stored', 'memory-evicted']);

function diagnostic(kind, reason) {
    // Opt-in local diagnostics only. Never put identities, revisions or source
    // bytes in a mark, and an unavailable/throwing observer cannot affect IO.
    try {
        if (globalThis.__HOMER_CARD_CACHE_DIAGNOSTICS__ === true
            && diagnosticKinds.has(kind) && diagnosticReasons.has(reason)) {
            globalThis.performance?.mark(`homer-card-cache:${kind}:${reason}`);
        }
    } catch { /* Observation is optional, never a read/write authority. */ }
}

function diagnosticMetadata(identity, meta, clock, allowExpiredCandidate) {
    try {
        if (globalThis.__HOMER_CARD_CACHE_DIAGNOSTICS__ !== true) return;
        const now = clock();
        const reason = !meta ? 'metadata-missing'
            : !validMetadata(identity, meta, now, true) ? 'metadata-invalid'
                : meta.expiresAt <= now ? allowExpiredCandidate ? 'metadata-expired-candidate' : 'metadata-expired'
                    : 'metadata-valid';
        diagnostic(identity.kind, reason);
    } catch { /* Even a diagnostic clock/flag getter must not affect a read. */ }
}

function diagnosticAfterDigest(kind, expiresAt, clock) {
    try {
        if (globalThis.__HOMER_CARD_CACHE_DIAGNOSTICS__ !== true) return;
        diagnostic(kind, expiresAt <= clock() ? 'post-digest-expired' : 'post-digest-invalid');
    } catch { /* Diagnostic classification cannot change the rejection branch. */ }
}

function object(value) {
    return Boolean(value && typeof value === 'object' && !Array.isArray(value)
        && (Object.getPrototypeOf(value) === Object.prototype || Object.getPrototypeOf(value) === null));
}

function scope(owner, kind, id) {
    if (typeof owner !== 'string' || !owner.trim() || owner.length > 200
        || typeof id !== 'string' || !id.trim() || id.length > 200
        || !['session-card', 'character-mirror', 'character-content-v2'].includes(kind)) throw new TypeError('Invalid card transport scope');
    return { owner, kind, id, key: [owner, kind, id] };
}

function validPayload(kind, payload) {
    if (!object(payload) || Object.keys(payload).some(key => forbiddenFields.has(key.toLowerCase()))) return false;
    if (owns(payload, 'data') && !object(payload.data)) return false;
    if (![payload.name, payload.data?.name].some(name => typeof name === 'string' && name.trim())) return false;
    if (owns(payload, 'spec') && !['chara_card_v2', 'chara_card_v3'].includes(payload.spec)) return false;
    return kind === 'session-card' || typeof payload.avatar === 'string' && Boolean(payload.avatar.trim());
}

function marker(row) {
    // Corrupt fields reduce to null; every valid replacement has a fresh entryId.
    return JSON.stringify([typeof row?.entryId === 'string' && row.entryId.length <= 200 ? row.entryId : null,
        typeof row?.revision === 'string' && revisionPattern.test(row.revision) ? row.revision : null,
        Number.isFinite(row?.expiresAt) ? row.expiresAt : null]);
}

function jsonShape(payload) {
    // Walk objects/arrays, not the contents of multi-MiB source strings. JSON
    // capture cannot contain cycles, aliases or non-JSON object instances.
    const pending = [payload], seen = new WeakSet();
    while (pending.length) {
        const value = pending.pop();
        if (value === null || ['string', 'boolean'].includes(typeof value)) continue;
        if (typeof value === 'number') { if (!Number.isFinite(value)) return false; continue; }
        if (!object(value) && !Array.isArray(value) || seen.has(value)) return false;
        seen.add(value);
        for (const key of Object.keys(value)) pending.push(value[key]);
    }
    return true;
}

function validMetadata(identity, meta, timestamp, allowExpiredCandidate = false) {
    const sameKey = value => Array.isArray(value) && value.length === 3 && value.every((part, index) => part === identity.key[index]);
    return Boolean(meta && sameKey(meta.key)
        && meta.owner === identity.owner && meta.kind === identity.kind && meta.id === identity.id
        && typeof meta.entryId === 'string' && meta.entryId.length > 0 && meta.entryId.length <= 200
        && typeof meta.revision === 'string' && revisionPattern.test(meta.revision)
        && Number.isFinite(meta.expiresAt) && (allowExpiredCandidate || meta.expiresAt > timestamp)
        && meta.expiresAt <= timestamp + CARD_TRANSPORT_TTL_MS
        && Number.isSafeInteger(meta.bytes) && meta.bytes > 0 && meta.bytes <= CARD_TRANSPORT_MAX_BYTES
        && Number.isFinite(meta.lastStoredAt) && meta.expiresAt === meta.lastStoredAt + CARD_TRANSPORT_TTL_MS);
}

function validRow(identity, row, meta, timestamp, allowExpiredCandidate = false) {
    const sameKey = value => Array.isArray(value) && value.length === 3 && value.every((part, index) => part === identity.key[index]);
    return Boolean(validMetadata(identity, meta, timestamp, allowExpiredCandidate) && row && sameKey(row.key)
        && row.owner === identity.owner && row.kind === identity.kind && row.id === identity.id
        && typeof row.entryId === 'string' && row.entryId.length > 0 && row.entryId.length <= 200
        && marker(row) === marker(meta) && validPayload(identity.kind, row.payload) && jsonShape(row.payload));
}

function cloneJson(value) {
    try { if (typeof globalThis.structuredClone === 'function') return globalThis.structuredClone(value); }
    catch { /* Older WebViews retain the complete JSON fallback. */ }
    return JSON.parse(JSON.stringify(value));
}

function memoryEligible(kind, payload) {
    // Legacy mirrors contain changing statistics; only stable source payloads
    // enter this layer. Never retain the surrounding token/session response.
    return ['session-card', 'character-content-v2'].includes(kind)
        && !owns(payload, 'chat_size') && !owns(payload, 'date_last_chat');
}

function memoryKey(key, cacheScope) {
    return Array.isArray(key) && key.length === 3 && key.every(part => typeof part === 'string')
        && typeof cacheScope === 'string'
        ? `${cacheScope.length}:${cacheScope}` + key.map(part => `${part.length}:${part}`).join('') : '';
}

function storageMemoryScope(factory, databaseName) {
    if (!factory || !['object', 'function'].includes(typeof factory)
        || typeof databaseName !== 'string' || databaseName.length > 512) return null;
    if (!factoryIds.has(factory)) factoryIds.set(factory, ++factorySequence);
    return `${factoryIds.get(factory)}:${databaseName}`;
}

function forgetMemory(key, cacheScope) {
    const encodedKey = memoryKey(key, cacheScope), entry = memory.get(encodedKey);
    if (!entry) return;
    memory.delete(encodedKey); memoryBytes -= entry.bytes;
    diagnostic(entry.meta.kind, 'memory-evicted');
}

function beginMutation() {
    // A late completed read/write must not repopulate memory after an explicit
    // account invalidation or global clear. Ordinary mutations fence only
    // their key, so simultaneous session/mirror writes can both be admitted.
    memoryEpoch = {};
    for (const item of [...pendingTouches.values()]) cancelTouch(item.key, item.cacheScope);
    if (activeTouch) cancelTouch(activeTouch.key, activeTouch.cacheScope);
    return memoryEpoch;
}

function releaseTouch(item) {
    if (!item.released) { item.released = true; item.epoch.release(); }
}

function cancelTouch(key, cacheScope) {
    const encoded = memoryKey(key, cacheScope), item = pendingTouches.get(encoded);
    if (item) { pendingTouches.delete(encoded); item.cancelled = true; releaseTouch(item); }
    if (activeTouch?.encoded === encoded) {
        activeTouch.cancelled = true;
        try { activeTouch.transaction?.abort(); } catch { /* Already settled. */ }
        releaseTouch(activeTouch);
    }
    if (!pendingTouches.size && touchTimer !== null) { clearTimeout(touchTimer); touchTimer = null; }
}

function touchCurrent(item) {
    return !item.cancelled && isEpochCurrent(item.epoch)
        && (!item.isCurrent || item.isCurrent());
}

function scheduleTouchFlush() {
    if (touchTimer !== null || activeTouch || !pendingTouches.size) return;
    touchTimer = setTimeout(() => {
        touchTimer = null;
        const item = pendingTouches.values().next().value;
        if (!item) return;
        pendingTouches.delete(item.encoded); activeTouch = item;
        void item.flush(item).catch(() => {}).finally(() => {
            releaseTouch(item);
            if (activeTouch === item) activeTouch = null;
            scheduleTouchFlush();
        });
    }, TOUCH_DELAY_MS);
}

function lastUsedAt(meta, clock) {
    return Number.isFinite(meta.lastUsedAt) && meta.lastUsedAt >= meta.lastStoredAt && meta.lastUsedAt <= clock
        ? meta.lastUsedAt : meta.lastStoredAt;
}

function evictionRecency(meta, cacheScope, clock) {
    let used = lastUsedAt(meta, clock);
    const encoded = memoryKey(meta.key, cacheScope);
    const item = pendingTouches.get(encoded) || (activeTouch?.encoded === encoded ? activeTouch : null);
    if (item && !item.cancelled && isEpochCurrent(item.epoch)
        && item.entryId === meta.entryId && item.revision === meta.revision && item.usedAt <= clock) used = Math.max(used, item.usedAt);
    return used;
}

function acquireGeneration(key, cacheScope, mutation = false) {
    const encodedKey = memoryKey(key, cacheScope);
    let state = activeGenerations.get(encodedKey);
    if (!state) {
        state = { token: {}, pending: 0 };
        activeGenerations.set(encodedKey, state);
    }
    if (mutation) state.token = {};
    state.pending++;
    return { global: memoryEpoch, state, token: state.token, release() {
        if (--state.pending === 0 && activeGenerations.get(encodedKey) === state) activeGenerations.delete(encodedKey);
    } };
}

function invalidateGeneration(key, cacheScope) {
    const state = activeGenerations.get(memoryKey(key, cacheScope));
    if (state) state.token = {};
}

function isEpochCurrent(epoch) {
    return epoch.global === memoryEpoch && epoch.state.token === epoch.token;
}

/**
 * Clear only private verified source bytes, never IndexedDB, login or history.
 * The host must call this on logout/account invalidation. Source bytes are not
 * credentials or authorization, including when reused without reading IDB.
 * @param {string} [owner] Omit to release all accounts' in-memory source bytes.
 */
export function clearCardTransportMemory(owner) {
    if (owner !== undefined) scope(owner, 'session-card', 'memory-clear-validation');
    beginMutation();
    for (const entry of [...memory.values()]) {
        if (owner === undefined || entry.meta.owner === owner) forgetMemory(entry.meta.key, entry.cacheScope);
    }
}

function remember(row, meta, bytes, epoch, privatePayload, cacheScope) {
    if (!isEpochCurrent(epoch) || cacheScope === null || !memoryEligible(row.kind, row.payload)
        || bytes !== meta.bytes || !Number.isSafeInteger(bytes) || bytes <= 0
        || bytes > CARD_TRANSPORT_MAX_BYTES) return;
    const payload = privatePayload ? row.payload : cloneJson(row.payload);
    if (!isEpochCurrent(epoch)) return;
    forgetMemory(row.key, cacheScope);
    memory.set(memoryKey(row.key, cacheScope), { meta: { ...meta, key: meta.key.slice() }, payload, bytes, cacheScope });
    memoryBytes += bytes;
    while (memory.size > CARD_TRANSPORT_MAX_ROWS || memoryBytes > CARD_TRANSPORT_MAX_BYTES) {
        const oldest = memory.values().next().value;
        forgetMemory(oldest.meta.key, oldest.cacheScope);
    }
    diagnostic(row.kind, 'memory-stored');
}

function verifiedMemory(identity, clock, candidateMode, epoch, cacheScope) {
    const key = memoryKey(identity.key, cacheScope), entry = memory.get(key);
    if (!entry || !isEpochCurrent(epoch) || !validMetadata(identity, entry.meta, clock(), candidateMode)) return null;
    // Private lookup only. Emit the valid revision before copying the body so
    // its fresh authenticated request can overlap the complete source clone.
    return entry;
}

export function createCardTransportCache({ indexedDB = globalThis.indexedDB,
    databaseName = 'homer-card-transport-v1', now = Date.now } = {}) {
    let opening = null, sequence = 0;
    const verifiedReadTickets = new WeakMap();
    const ownedPayloadTickets = new WeakMap();
    const cacheScope = storageMemoryScope(indexedDB, databaseName);
    const forgetLocalMemory = key => forgetMemory(key, cacheScope);
    const instanceId = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;

    function timestamp() {
        const value = now();
        if (!Number.isFinite(value)) throw new TypeError('Invalid card transport clock');
        return value;
    }

    function open() {
        if (opening) return opening;
        opening = new Promise((resolve, reject) => {
            if (!indexedDB?.open) { reject(new Error('Card transport storage is unavailable')); return; }
            let abandoned = false;
            const request = indexedDB.open(databaseName, 1);
            request.onupgradeneeded = () => {
                const db = request.result;
                if (!db.objectStoreNames.contains(ENTRIES)) db.createObjectStore(ENTRIES, { keyPath: 'key' }).createIndex('owner', 'owner');
                if (!db.objectStoreNames.contains(METADATA)) {
                    const store = db.createObjectStore(METADATA, { keyPath: 'key' });
                    store.createIndex('owner', 'owner');
                }
            };
            request.onerror = () => reject(request.error || new Error('Card transport storage could not open'));
            request.onblocked = () => { abandoned = true; reject(new Error('Card transport storage is blocked')); };
            request.onsuccess = () => {
                if (abandoned) { request.result.close(); return; }
                request.result.onversionchange = () => {
                    request.result.close(); opening = null;
                    clearCardTransportMemory();
                };
                resolve(request.result);
            };
        }).catch(error => { opening = null; throw error; });
        return opening;
    }

    async function transaction(mode, execute, stores = [ENTRIES, METADATA]) {
        const db = await open();
        return new Promise((resolve, reject) => {
            let tx, result, failure;
            try {
                try { tx = db.transaction(stores, mode, mode === 'readwrite' ? { durability: 'strict' } : undefined); }
                catch (error) { if (!(error instanceof TypeError)) throw error; tx = db.transaction(stores, mode); }
                tx.oncomplete = () => resolve(result);
                tx.onabort = () => reject(failure || tx.error || new Error('Card transport transaction aborted'));
                tx.onerror = event => { failure ||= event.target?.error || tx.error; };
                const guarded = callback => (...args) => {
                    try { callback(...args); } catch (error) { failure = error; tx.abort(); }
                };
                execute(stores.includes(ENTRIES) ? tx.objectStore(ENTRIES) : null,
                    tx.objectStore(METADATA), value => { result = value; }, guarded, tx);
            } catch (error) {
                failure = error;
                if (tx) { try { tx.abort(); } catch { reject(error); } } else reject(error);
            }
        });
    }

    async function discardObserved(identity, observedRow, observedMeta) {
        const generation = acquireGeneration(identity.key, cacheScope, true);
        cancelTouch(identity.key, cacheScope);
        forgetLocalMemory(identity.key);
        try { return await transaction('readwrite', (entries, metadata, done, guarded) => {
            const rowRead = entries.get(identity.key), metaRead = metadata.get(identity.key);
            let received = 0;
            const remove = guarded(() => {
                if (++received !== 2) return;
                if (marker(rowRead.result) === marker(observedRow) && marker(metaRead.result) === marker(observedMeta)) {
                    entries.delete(identity.key); metadata.delete(identity.key); done(true);
                } else done(false);
            });
            rowRead.onsuccess = remove; metaRead.onsuccess = remove;
        }); } finally { generation.release(); }
    }

    function prune(entries, metadata, clock, guarded, removed = () => {}) {
        // Only the small metadata store is scanned, never cached card bodies.
        const rows = [], request = metadata.openCursor();
        request.onsuccess = guarded(() => {
            const cursor = request.result;
            if (cursor) {
                const row = cursor.value;
                let valid = false;
                try {
                    const identity = scope(row.owner, row.kind, row.id);
                    valid = validMetadata(identity, row, clock, true) && Array.isArray(cursor.primaryKey)
                        && cursor.primaryKey.length === 3 && cursor.primaryKey.every((part, index) => part === identity.key[index]);
                } catch { /* Only malformed disposable metadata is discarded. */ }
                // Age is not content invalidation: an unchanged source may be
                // confirmed by the next online read. Capacity remains bounded.
                if (!valid) {
                    invalidateGeneration(cursor.primaryKey, cacheScope);
                    cancelTouch(cursor.primaryKey, cacheScope);
                    forgetLocalMemory(cursor.primaryKey); removed(cursor.primaryKey);
                    entries.delete(cursor.primaryKey); metadata.delete(cursor.primaryKey);
                } else rows.push({ key: cursor.primaryKey, bytes: row.bytes, lastStoredAt: row.lastStoredAt,
                    lastUsedAt: evictionRecency(row, cacheScope, clock) });
                cursor.continue(); return;
            }
            rows.sort((left, right) => left.lastUsedAt - right.lastUsedAt || left.lastStoredAt - right.lastStoredAt);
            let bytes = rows.reduce((sum, row) => sum + row.bytes, 0);
            while (rows.length > CARD_TRANSPORT_MAX_ROWS || bytes > CARD_TRANSPORT_MAX_BYTES) {
                const row = rows.shift(); bytes -= row.bytes;
                invalidateGeneration(row.key, cacheScope);
                cancelTouch(row.key, cacheScope);
                forgetLocalMemory(row.key); removed(row.key);
                entries.delete(row.key); metadata.delete(row.key);
            }
        });
    }

    function verifiedResult(result, identity, meta, epoch, allowOwnedPayload = false, candidateMode = false) {
        verifiedReadTickets.set(result, { ...identity, revision: meta.revision, entryId: meta.entryId,
            global: epoch.global });
        if (allowOwnedPayload === true && isEpochCurrent(epoch)) {
            // The returned payload is already an isolated L1 clone or an IDB
            // structured-clone result. Never ticket the private memory object.
            ownedPayloadTickets.set(result, { ...identity, meta: { ...meta, key: meta.key.slice() },
                payload: result.payload, global: epoch.global, candidateMode });
        }
        return result;
    }

    async function flushTouch(item) {
        if (!touchCurrent(item)) return;
        await transaction('readwrite', (_entries, metadata, done, guarded, tx) => {
            item.transaction = tx;
            if (!touchCurrent(item)) { done(false); return; }
            const request = metadata.get(item.key);
            request.onsuccess = guarded(() => {
                const meta = request.result, clock = timestamp();
                if (!touchCurrent(item) || !validMetadata(item, meta, clock, true)
                    || meta.entryId !== item.entryId || meta.revision !== item.revision) { done(false); return; }
                // Never extend source TTL, create a missing entry or write a
                // payload. Revision/entryId protect replacements from a late use.
                metadata.put({ ...meta, lastUsedAt: Math.max(lastUsedAt(meta, clock), item.usedAt) });
                done(true);
            });
        }, [METADATA]);
    }

    return {
        async read(owner, kind, id, { onRevision, allowExpiredCandidate = false, allowVerifiedMemory = false,
            allowOwnedPayload = false } = {}) {
            const identity = scope(owner, kind, id);
            const epoch = acquireGeneration(identity.key, cacheScope);
            try {
            const candidateMode = allowExpiredCandidate === true;
            diagnostic(kind, 'read-start');
            // Explicit online-transport opt-in only. Default reads retain the
            // strict IDB/complete-SHA contract, including storage corruption.
            // A memory candidate is never usable until a fresh authenticated
            // response confirms its exact SHA and current owner/scope.
            const memo = allowVerifiedMemory === true ? verifiedMemory(identity, timestamp, candidateMode, epoch, cacheScope) : null;
            if (memo) {
                const { revision, expiresAt, entryId } = memo.meta;
                if (typeof onRevision === 'function') {
                    diagnostic(kind, 'hint-emitted');
                    try { onRevision(Object.freeze({ owner, kind, id, entryId, revision, expiresAt,
                        requiresOnlineConfirmation: true })); } catch { /* optional hint */ }
                }
                if (!isEpochCurrent(epoch) || !validMetadata(identity, memo.meta, timestamp(), candidateMode)) return null;
                let payload;
                try { payload = cloneJson(memo.payload); }
                catch { forgetLocalMemory(identity.key); return null; }
                if (!isEpochCurrent(epoch) || !validMetadata(identity, memo.meta, timestamp(), candidateMode)) return null;
                const key = memoryKey(identity.key, cacheScope);
                memory.delete(key); memory.set(key, memo);
                diagnostic(kind, 'memory-hit');
                diagnostic(kind, 'read-verified');
                return verifiedResult({ revision, payload, expiresAt, owner, kind, id, entryId,
                    requiresOnlineConfirmation: true }, identity, memo.meta, epoch, allowOwnedPayload, candidateMode);
            }
            let stored;
            try { stored = await transaction('readonly', (entries, metadata, done, guarded) => {
                // Submit the body read inside metadata success, after its hint.
                // This keeps the same active readonly snapshot while letting the
                // fresh authenticated request start before IDB clones the body.
                // The hint never makes that body usable or grants authorization.
                const meta = metadata.get(identity.key);
                meta.onsuccess = guarded(() => {
                    diagnosticMetadata(identity, meta.result, timestamp, candidateMode);
                    if (typeof onRevision === 'function' && validMetadata(identity, meta.result, timestamp(), candidateMode)) {
                        const value = meta.result;
                        diagnostic(kind, 'hint-emitted');
                        try { onRevision(Object.freeze({ owner, kind, id, entryId: value.entryId,
                            revision: value.revision, expiresAt: value.expiresAt,
                            ...(candidateMode ? { requiresOnlineConfirmation: true } : {}) })); } catch { /* optional hint */ }
                    }
                    // No await/microtask here: IndexedDB is active during this
                    // request event. Even invalid metadata retains the original
                    // complete-row validation and corrupt/orphan cleanup path.
                    const row = entries.get(identity.key);
                    row.onsuccess = guarded(() => done({ row: row.result, meta: meta.result }));
                });
            }); } catch (error) { diagnostic(kind, 'idb-error'); throw error; }
            if (!validRow(identity, stored.row, stored.meta, timestamp(), candidateMode)) {
                forgetLocalMemory(identity.key);
                if (validRow(identity, stored.row, stored.meta, timestamp(), true)) {
                    diagnostic(kind, 'expired-retained');
                    return null; // Default reads never return expired bytes, but do not destroy them.
                }
                diagnostic(kind, stored.row ? 'row-invalid' : 'row-missing');
                if (stored.row || stored.meta) void discardObserved(identity, stored.row, stored.meta).catch(() => {});
                return null;
            }
            const { revision, payload, expiresAt } = stored.row;
            if (expiresAt <= timestamp()) diagnostic(kind, 'row-expired-candidate');
            // A valid shape is not proof of intact bytes. Verify the complete
            // JSON against its revision, then recheck the full storage contract.
            diagnostic(kind, 'digest-start');
            let actualRevision;
            try { actualRevision = await jsonContentSha256(payload); }
            catch (error) { diagnostic(kind, 'digest-error'); throw error; }
            if (actualRevision !== revision) {
                diagnostic(kind, 'digest-mismatch');
                void discardObserved(identity, stored.row, stored.meta).catch(() => {});
                return null;
            }
            if (!validRow(identity, stored.row, stored.meta, timestamp(), candidateMode)) {
                if (validRow(identity, stored.row, stored.meta, timestamp(), true)) {
                    diagnostic(kind, 'expired-retained');
                    return null;
                }
                diagnosticAfterDigest(kind, expiresAt, timestamp);
                void discardObserved(identity, stored.row, stored.meta).catch(() => {});
                return null;
            }
            if (expiresAt <= timestamp()) diagnostic(kind, 'post-digest-expired-candidate');
            // IDB metadata may under-report bytes. Meter actual complete JSON
            // only on memory admission, never use that untrusted count for this
            // layer's budget. A mismatch keeps the original durable-read path.
            if (isEpochCurrent(epoch) && memoryEligible(kind, payload)) {
                try {
                    const bytes = encoder.encode(JSON.stringify(payload)).byteLength;
                    remember(stored.row, stored.meta, bytes, epoch, false, cacheScope);
                } catch { forgetLocalMemory(identity.key); /* Memory is optional; the complete SHA read remains usable. */ }
            }
            diagnostic(kind, 'read-verified');
            // Even a verified candidate is unusable as a session until the
            // current authenticated server response confirms this exact SHA.
            return verifiedResult({ revision, payload, expiresAt, ...(candidateMode ? {
                owner, kind, id, entryId: stored.row.entryId, requiresOnlineConfirmation: true,
            } : {}) }, identity, stored.meta, epoch, allowOwnedPayload, candidateMode);
            } finally { epoch.release(); }
        },
        /**
         * Move this read's isolated payload once, after fresh online SHA/scope
         * confirmation. This is not authorization and never exposes L1 bytes.
         * Legacy/custom consumers keep normal read() and cloning semantics.
         */
        consumePayload(owner, kind, id, row, { revision, isCurrent } = {}) {
            const identity = scope(owner, kind, id), ticket = row && ownedPayloadTickets.get(row);
            if (!ticket || ticket.global !== memoryEpoch || (isCurrent && !isCurrent())
                || ticket.key.some((part, index) => part !== identity.key[index])
                || revision !== ticket.meta.revision || row.revision !== ticket.meta.revision
                || row.expiresAt !== ticket.meta.expiresAt
                || ['owner', 'kind', 'id'].some(field => owns(row, field) && row[field] !== identity[field])
                || owns(row, 'entryId') && row.entryId !== ticket.meta.entryId
                || !validMetadata(identity, ticket.meta, timestamp(), ticket.candidateMode)
                || ticket.global !== memoryEpoch) return null;
            const descriptor = Object.getOwnPropertyDescriptor(row, 'payload');
            if (!descriptor?.configurable || descriptor.value !== ticket.payload) return null;
            const payload = ticket.payload;
            delete row.payload;
            ownedPayloadTickets.delete(row);
            return payload;
        },
        async write(owner, kind, id, revision, payload) {
            const identity = scope(owner, kind, id);
            if (typeof revision !== 'string' || !revisionPattern.test(revision) || !validPayload(kind, payload)) {
                throw new TypeError('Invalid card transport revision or payload');
            }
            // Capture immutable JSON before the first await. IDB structured
            // clone also prevents later reads from mutating persisted bytes.
            const body = JSON.stringify(payload), encoded = encoder.encode(body), bytes = encoded.byteLength;
            if (bytes > CARD_TRANSPORT_MAX_BYTES) return false;
            const captured = JSON.parse(body);
            if (!validPayload(kind, captured)) throw new TypeError('Invalid captured card payload');
            const epoch = acquireGeneration(identity.key, cacheScope, true);
            cancelTouch(identity.key, cacheScope);
            forgetLocalMemory(identity.key);
            try {
            if (await encodedBytesSha256(encoded) !== revision) throw new TypeError('Card transport content revision mismatch');
            const storedAt = timestamp(), expiresAt = storedAt + CARD_TRANSPORT_TTL_MS;
            const entryId = `${instanceId}-${++sequence}`;
            const row = { ...identity, entryId, revision, payload: captured, expiresAt };
            const meta = { ...identity, entryId, revision, expiresAt, bytes, lastStoredAt: storedAt, lastUsedAt: storedAt };
            let retained = true;
            const result = await transaction('readwrite', (entries, metadata, done, guarded) => {
                entries.put(row); metadata.put(meta);
                prune(entries, metadata, timestamp(), guarded, key => {
                    if (memoryKey(key, cacheScope) === memoryKey(identity.key, cacheScope)) retained = false;
                });
                done(true);
            });
            if (retained) remember(row, meta, bytes, epoch, true, cacheScope);
            return result;
            } finally { epoch.release(); }
        },
        async remove(owner, kind, id) {
            const identity = scope(owner, kind, id);
            const generation = acquireGeneration(identity.key, cacheScope, true);
            cancelTouch(identity.key, cacheScope);
            forgetLocalMemory(identity.key);
            try { return await transaction('readwrite', (entries, metadata, done) => {
                entries.delete(identity.key); metadata.delete(identity.key); done(true);
            }); } finally { generation.release(); }
        },
        async clearOwner(owner) {
            scope(owner, 'session-card', 'owner-clear-validation');
            beginMutation();
            for (const entry of [...memory.values()]) if (entry.meta.owner === owner && entry.cacheScope === cacheScope) forgetLocalMemory(entry.meta.key);
            return transaction('readwrite', (entries, metadata, done, guarded) => {
                const removed = new Set(); let completed = 0;
                // Key-only indexes also find an orphan in either store without
                // cloning large cached bodies or touching another account.
                for (const store of [entries, metadata]) {
                    const request = store.index('owner').openKeyCursor(owner);
                    request.onsuccess = guarded(() => {
                        const cursor = request.result;
                        if (!cursor) { if (++completed === 2) done(removed.size); return; }
                        entries.delete(cursor.primaryKey); metadata.delete(cursor.primaryKey);
                        removed.add(JSON.stringify(cursor.primaryKey)); cursor.continue();
                    });
                }
            });
        },
        /** Only call after fresh authenticated scope and exact server SHA confirmation. */
        touch(owner, kind, id, row, { isCurrent } = {}) {
            const identity = scope(owner, kind, id), ticket = row && verifiedReadTickets.get(row);
            if (!ticket || ticket.global !== memoryEpoch || cacheScope === null
                || !['session-card', 'character-content-v2'].includes(kind)
                || ticket.key.some((part, index) => part !== identity.key[index])
                || ticket.revision !== row.revision || (isCurrent && !isCurrent())) return false;
            const encoded = memoryKey(identity.key, cacheScope), usedAt = timestamp();
            const existing = pendingTouches.get(encoded);
            if (existing && existing.entryId === ticket.entryId && existing.revision === ticket.revision
                && touchCurrent(existing)) { existing.usedAt = Math.max(existing.usedAt, usedAt); return true; }
            cancelTouch(identity.key, cacheScope);
            while (pendingTouches.size + (activeTouch ? 1 : 0) >= CARD_TRANSPORT_MAX_ROWS && pendingTouches.size) {
                const oldest = pendingTouches.values().next().value;
                cancelTouch(oldest.key, oldest.cacheScope);
            }
            const item = { ...identity, encoded, cacheScope, revision: ticket.revision, entryId: ticket.entryId,
                usedAt, isCurrent, epoch: acquireGeneration(identity.key, cacheScope), flush: flushTouch };
            pendingTouches.set(encoded, item); scheduleTouchFlush();
            return true;
        },
        clearMemory(owner) { clearCardTransportMemory(owner); },
    };
}
