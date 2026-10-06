// Optional display-cache writes, not the canonical chat/outbox save barrier.
// Keep Java/SQLite and duplicate page-cache work off the ready-frame path.
export function createSettledPreviewQueue({ scope, write, schedule, cancel, limit = 8 }) {
    const pending = new Map();
    let scheduled = null;
    const flush = () => {
        if (scheduled !== null) cancel(scheduled);
        scheduled = null;
        const items = [...pending.values()];
        pending.clear();
        for (const item of items) {
            if (item.scope !== scope()) continue;
            try { write(item.snapshot); } catch { /* Optional cache cannot block the live chat. */ }
        }
    };
    return {
        // The caller supplies an owned normalized display snapshot, never a
        // live canonical chat array, credentials, or a mutable runtime object.
        enqueue(snapshot) {
            const ownerScope = scope();
            if (!ownerScope || !snapshot?.app_id || !snapshot?.conversation_id) return;
            const key = JSON.stringify([ownerScope, snapshot.app_id, snapshot.conversation_id]);
            pending.delete(key);
            pending.set(key, { scope: ownerScope, snapshot });
            while (pending.size > limit) pending.delete(pending.keys().next().value);
            if (scheduled === null) scheduled = schedule(flush);
        },
        flush,
        clear() {
            if (scheduled !== null) cancel(scheduled);
            scheduled = null;
            pending.clear();
        },
    };
}
