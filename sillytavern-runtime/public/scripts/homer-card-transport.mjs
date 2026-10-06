import { createCardTransportCache, CARD_TRANSPORT_TTL_MS } from './homer-card-transport-cache.mjs';

const cache = createCardTransportCache();
const SHA256 = /^[a-f0-9]{64}$/;
const object = value => value && typeof value === 'object' && !Array.isArray(value);
const clone = value => {
    // Cache reads already verify a complete JSON snapshot. Preserve isolation
    // without another multi-MB JSON encode/parse when the WebView can clone it.
    try { if (typeof globalThis.structuredClone === 'function') return globalThis.structuredClone(value); }
    catch { /* Older WebViews may expose an unusable implementation. */ }
    return JSON.parse(JSON.stringify(value));
};
const owns = (value, key) => Object.prototype.hasOwnProperty.call(value, key);
const MIRROR_CONTENT_KIND = 'character-content-v2';
const diagnosticKinds = new Set(['session-card', MIRROR_CONTENT_KIND]);
const diagnosticReasons = new Set(['read-start', 'owner-missing', 'id-missing', 'startup-deadline',
    'network-with-revision', 'network-without-revision', 'hint-accepted', 'verified-row', 'unusable-row',
    'storage-rejected', 'storage-threw', 'account-guard-rejected', 'body-wait-start', 'body-wait-deadline',
    'restore-accepted', 'restore-retry', 'online-or-auth-rejected', 'expired-candidate-hint', 'expired-candidate-verified']);
function diagnostic(kind, reason) {
    try {
        if (globalThis.__HOMER_CARD_CACHE_DIAGNOSTICS__ === true
            && diagnosticKinds.has(kind) && diagnosticReasons.has(reason)) {
            globalThis.performance?.mark(`homer-card-transport:${kind}:${reason}`);
        }
    } catch { /* Observability must never change request or authorization. */ }
}
function freshCharacterStats(value) {
    const fields = ['chat_size', 'date_last_chat'];
    if (!object(value) || Object.keys(value).length !== fields.length
        || !fields.every(key => owns(value, key) && Number.isFinite(value[key]) && value[key] >= 0)) {
        throw new Error('角色统计资料无效，请重新打开');
    }
    return { chat_size: value.chat_size, date_last_chat: value.date_last_chat };
}

// This cache is transport storage, never offline authorization. Every use must
// be confirmed by the current authenticated server response, including deletes
// and edits performed in another window. No token/user/session is persisted.
export function createCardTransport({ storage = cache, now = Date.now, readTimeoutMs = 800 } = {}) {
    const assertCurrent = current => { if (current && !current()) throw new Error('当前账号或会话已变化，请重新打开'); };
    const valid = row => object(row?.payload) && SHA256.test(row?.revision || '')
        && Number.isFinite(row.expiresAt) && row.expiresAt <= now() + CARD_TRANSPORT_TTL_MS
        && (row.expiresAt > now() || row.requiresOnlineConfirmation === true);
    function readAlongside(owner, kind, id, current, onlineRead) {
        diagnostic(kind, 'read-start');
        let startTimer, rowTimer, started = false, settled = false, disposed = false, resolveFirst, rejectFirst, resolveRow;
        const first = new Promise((resolve, reject) => { resolveFirst = resolve; rejectFirst = reject; });
        // A synchronous account guard can exit the caller before it awaits
        // this flight. Keep that rejection handled without changing its result.
        void first.catch(() => {});
        const completeRow = new Promise(resolve => { resolveRow = resolve; });
        const start = revision => {
            if (started || disposed) return;
            started = true;
            clearTimeout(startTimer);
            try {
                assertCurrent(current);
                diagnostic(kind, revision ? 'network-with-revision' : 'network-without-revision');
                resolveFirst(onlineRead(revision));
            } catch (error) { diagnostic(kind, 'account-guard-rejected'); rejectFirst(error); }
        };
        const finish = value => {
            if (settled || disposed) return;
            settled = true;
            clearTimeout(startTimer);
            clearTimeout(rowTimer);
            let row = null, error = null;
            try {
                assertCurrent(current);
                const candidateScope = value?.requiresOnlineConfirmation !== true
                    || value.owner === owner && value.kind === kind && value.id === id
                    && typeof value.entryId === 'string' && value.entryId && value.entryId.length <= 200;
                if (valid(value) && candidateScope) row = value;
            } catch (failure) { error = failure; }
            if (row && row.expiresAt <= now()) diagnostic(kind, 'expired-candidate-verified');
            diagnostic(kind, row ? 'verified-row' : 'unusable-row');
            resolveRow({ row, error });
            start(row?.revision || '');
        };
        const onRevision = hint => {
            // A small metadata hint only chooses the conditional request. It
            // is never a verified body, and cannot satisfy a not-modified reply.
            if (!object(hint) || hint.owner !== owner || hint.kind !== kind || hint.id !== id
                || typeof hint.entryId !== 'string' || !hint.entryId || hint.entryId.length > 200
                || typeof hint.revision !== 'string' || !SHA256.test(hint.revision) || !Number.isFinite(hint.expiresAt)
                || hint.expiresAt > now() + CARD_TRANSPORT_TTL_MS
                || hint.expiresAt <= now() && hint.requiresOnlineConfirmation !== true) return;
            if (hint.expiresAt <= now()) diagnostic(kind, 'expired-candidate-hint');
            diagnostic(kind, 'hint-accepted');
            start(hint.revision);
        };
        if (!owner || !id) {
            if (!owner) diagnostic(kind, 'owner-missing');
            if (!id) diagnostic(kind, 'id-missing');
            finish(null);
        }
        else {
            // Bound network startup, not the lifetime of body verification.
            // A slow authorized response can overlap the complete multi-MB
            // digest without discarding a valid row at this startup deadline.
            startTimer = setTimeout(() => { diagnostic(kind, 'startup-deadline'); start(''); }, readTimeoutMs);
            try { Promise.resolve(storage.read(owner, kind, id, {
                onRevision, allowExpiredCandidate: true, allowVerifiedMemory: true, allowOwnedPayload: true,
            })).then(finish, () => {
                diagnostic(kind, 'storage-rejected'); finish(null);
            }); }
            catch { diagnostic(kind, 'storage-threw'); finish(null); }
        }
        return {
            first,
            async cached() {
                assertCurrent(current);
                // Only a confirmed not-modified response needs these bytes.
                // Give an unfinished read its own bounded wait from here;
                // already verified rows are immediately reusable.
                if (!settled && !disposed && rowTimer === undefined) {
                    diagnostic(kind, 'body-wait-start');
                    rowTimer = setTimeout(() => { diagnostic(kind, 'body-wait-deadline'); finish(null); }, readTimeoutMs);
                }
                const outcome = await completeRow;
                assertCurrent(current);
                if (outcome.error) throw outcome.error;
                return valid(outcome.row) ? outcome.row : null;
            },
            dispose() {
                disposed = true;
                clearTimeout(startTimer);
                clearTimeout(rowTimer);
                if (!settled) { settled = true; resolveRow({ row: null, error: null }); }
                // Release unused flight observers without issuing a request
                // when an account guard exited before network startup.
                if (!started) { started = true; resolveFirst(undefined); }
            },
        };
    }
    function retain(owner, kind, id, revision, payload, current) {
        if (!owner || !id || !SHA256.test(revision || '') || !object(payload)) return;
        assertCurrent(current);
        // The storage contract captures JSON before its first await, before
        // the caller mutates/normalizes the live character. Do not duplicate
        // another multi-MB stringify/parse here on the rendering thread.
        // Failure of this disposable cache cannot fail a verified online read.
        try { void storage.write(owner, kind, id, revision, payload).catch(() => {}); } catch { /* optional */ }
    }
    function confirmUse(owner, kind, id, row, current) {
        assertCurrent(current);
        // Record recency only after the authenticated reply confirmed SHA,
        // never on metadata hints or speculative source reads. Optional,
        // coalesced metadata IO stays outside the ready critical path.
        try { storage.touch?.(owner, kind, id, row, { isCurrent: current }); } catch { /* optional */ }
    }
    function restoredPayload(owner, kind, id, row, revision, current) {
        assertCurrent(current);
        let payload;
        // Production cache can move the read's private isolated copy once.
        // Custom/older stores retain the defensive complete-clone fallback.
        try { payload = storage.consumePayload?.(owner, kind, id, row, { revision, isCurrent: current }); }
        catch { /* Optional ownership capability, not an authorization check. */ }
        assertCurrent(current);
        return object(payload) ? payload : clone(row.payload);
    }
    function query(path, revision) {
        const suffix = new URLSearchParams({ card_cache: '1' });
        if (revision) suffix.set('card_sha256', revision);
        return `${path}${path.includes('?') ? '&' : '?'}${suffix}`;
    }
    return {
        async session(path, { owner, appId, conversationId, request, validate, isCurrent }) {
            const flight = readAlongside(owner, 'session-card', appId, isCurrent,
                revision => request(query(path, revision)));
            try { for (let attempt = 0; attempt < 2; attempt++) {
                assertCurrent(isCurrent);
                const payload = await (attempt === 0 ? flight.first : request(query(path, '')));
                assertCurrent(isCurrent);
                // Incomplete legacy/error responses retain the existing site
                // fallback. Never restore a card into an unauthenticated body.
                const launch = payload?.launch;
                if (!object(launch) || !launch.bridge_token || launch.admin_preview) return payload;
                validate(payload);
                const actualOwner = String(payload?.user?.id || payload?.user?.user_id || '');
                if (!actualOwner || (owner && actualOwner !== owner)
                    || (appId && String(launch.app_id) !== String(appId))
                    || (conversationId && String(launch.conversation_id) !== String(conversationId))) {
                    throw new Error('会话资料与当前账号或角色不一致');
                }
                const marker = launch.card_transport;
                const negotiated = marker?.version === 1 && SHA256.test(marker.sha256 || '');
                if (!object(launch.card) && negotiated) {
                    const row = attempt === 0 ? await flight.cached() : null;
                    assertCurrent(isCurrent);
                    if (attempt === 0 && valid(row) && row.revision === marker.sha256 && actualOwner === owner) {
                        diagnostic('session-card', 'restore-accepted');
                        confirmUse(actualOwner, 'session-card', String(launch.app_id), row, isCurrent);
                        launch.card = restoredPayload(actualOwner, 'session-card', String(launch.app_id), row, marker.sha256, isCurrent);
                    } else {
                        // Missing, corrupt or mismatched local data cannot be
                        // substituted. Retry once without a known revision.
                        if (attempt === 0) { diagnostic('session-card', 'restore-retry'); continue; }
                        throw new Error('角色资料校验失败，请重新打开');
                    }
                } else if (object(launch.card) && negotiated) {
                    retain(actualOwner, 'session-card', String(launch.app_id), marker.sha256, launch.card, isCurrent);
                }
                return payload;
            } } catch (error) { diagnostic('session-card', 'online-or-auth-rejected'); throw error; }
            finally { flight.dispose(); }
        },
        async character(avatar, { owner, fetcher, headers, isCurrent }) {
            const onlineRead = revision => fetcher('/api/characters/get', {
                method: 'POST', headers,
                body: JSON.stringify({ avatar_url: avatar, card_cache: 2, ...(revision ? { card_sha256: revision } : {}) }),
            });
            const flight = readAlongside(owner, MIRROR_CONTENT_KIND, avatar, isCurrent, onlineRead);
            try { for (let attempt = 0; attempt < 2; attempt++) {
                assertCurrent(isCurrent);
                const response = await (attempt === 0 ? flight.first : onlineRead(''));
                assertCurrent(isCurrent);
                if (!response.ok) {
                    diagnostic(MIRROR_CONTENT_KIND, 'online-or-auth-rejected');
                    return response; // 401/403/404/5xx stay authoritative.
                }
                const body = await response.json();
                assertCurrent(isCurrent);
                const marker = body?.homer_character_transport;
                let character = body, usedRow = null;
                if (marker) {
                    if (marker.version !== 2 || !SHA256.test(marker.sha256 || '')) throw new Error('角色资料版本无效');
                    const stats = freshCharacterStats(body.fresh_stats);
                    if (marker.not_modified === true) {
                        const row = attempt === 0 ? await flight.cached() : null;
                        assertCurrent(isCurrent);
                        if (attempt === 0 && valid(row) && row.revision === marker.sha256 && row.payload.avatar === avatar) {
                            diagnostic(MIRROR_CONTENT_KIND, 'restore-accepted');
                            character = restoredPayload(owner, MIRROR_CONTENT_KIND, avatar, row, marker.sha256, isCurrent);
                            usedRow = row;
                        } else {
                            if (attempt === 0) { diagnostic(MIRROR_CONTENT_KIND, 'restore-retry'); continue; }
                            throw new Error('角色缓存校验失败，请重新打开');
                        }
                    } else {
                        character = body.character;
                        if (!object(character) || character.avatar !== avatar || !object(character.data)) throw new Error('角色资料与请求不一致');
                    }
                    // Statistics are always from this authenticated read. They
                    // are not part of stable card content or its persisted SHA;
                    // updating last-chat time must not retransmit MB of scripts.
                    if (owns(character, 'chat_size') || owns(character, 'date_last_chat')) {
                        throw new Error('角色资料版本格式无效');
                    }
                    if (marker.not_modified !== true) retain(owner, MIRROR_CONTENT_KIND, avatar, marker.sha256, character, isCurrent);
                    if (usedRow) confirmUse(owner, MIRROR_CONTENT_KIND, avatar, usedRow, isCurrent);
                    character = { ...character, ...stats };
                }
                return { ok: response.ok, status: response.status, json: async () => character };
            } } catch (error) { diagnostic(MIRROR_CONTENT_KIND, 'online-or-auth-rejected'); throw error; }
            finally { flight.dispose(); }
        },
    };
}

const transport = createCardTransport();
export const requestSessionCard = (path, options) => transport.session(path, options);
export const requestCachedCharacter = (avatar, options) => transport.character(avatar, options);
