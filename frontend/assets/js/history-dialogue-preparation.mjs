// IDs from a freshly authorized list only. This module neither fetches nor
// binds a character; the retained runtime owns authorization and save fences.
export const HISTORY_PREPARATION_TTL_MS = 30_000;

export function historyPreparationOwner(user) {
  return String(user?.id || user?.user_id || '').trim();
}

export function selectFreshHistoryTargets(list) {
  const targets = [], seen = new Set();
  for (const item of Array.isArray(list) ? list : []) {
    const appId = String(item?.app_id || '').trim();
    const conversationId = String(item?.id || item?.conversation_id || '').trim();
    if (!appId || !conversationId || appId.length > 160 || conversationId.length > 160) continue;
    const key = JSON.stringify([appId, conversationId]);
    if (seen.has(key)) continue;
    seen.add(key);
    targets.push(Object.freeze({ app_id: appId, conversation_id: conversationId }));
    if (targets.length === 2) break;
  }
  return Object.freeze(targets);
}

export function normalizeHistoryPreparation(value, owner, now = Date.now()) {
  if (!owner || value?.owner !== owner || !Array.isArray(value.targets)
      || value.targets.length < 1 || value.targets.length > 2
      || !Number.isFinite(value.expires_at) || value.expires_at <= now
      || value.expires_at > now + HISTORY_PREPARATION_TTL_MS) return null;
  const targets = [], seen = new Set();
  for (const item of value.targets) {
    if (typeof item?.app_id !== 'string' || typeof item?.conversation_id !== 'string') return null;
    const appId = item.app_id.trim(), conversationId = item.conversation_id.trim();
    if (!appId || !conversationId || appId.length > 160 || conversationId.length > 160) return null;
    const key = JSON.stringify([appId, conversationId]);
    if (seen.has(key)) continue;
    seen.add(key);
    targets.push(Object.freeze({ app_id: appId, conversation_id: conversationId }));
  }
  return Object.freeze({ owner, expires_at: value.expires_at, targets: Object.freeze(targets) });
}

// One latest batch, no timers, no expiry extension. A real selection, document
// reset or account change clears it; a late empty-host handshake can only flush
// the same owner/expiry-checked batch once.
export function createHistoryPreparationMailbox({ getOwner, eligible, send, now = Date.now }) {
  let pending = null;
  const clear = () => { pending = null; };
  const flush = () => {
    if (!pending) return false;
    if (!eligible()) { clear(); return false; }
    const batch = normalizeHistoryPreparation(pending, getOwner(), now());
    if (!batch) { clear(); return false; }
    if (send(batch) !== true) return false;
    clear();
    return true;
  };
  return Object.freeze({
    offer(value) {
      if (!eligible()) { clear(); return false; }
      pending = normalizeHistoryPreparation(value, getOwner(), now());
      return flush();
    },
    flush, clear,
  });
}
