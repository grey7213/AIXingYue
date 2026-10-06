// Restore card-authored alternate openings when the cloud stores only its
// initial greeting. Never replace an edited message or reorder saved swipes.
// Old /conversations/start stored display-regex output instead of source. A
// frontend template can itself contain its trigger, so applying regex again
// nests a whole document inside itself and splits Markdown fences. Recover only
// exact, unambiguous full-document outputs of this version's authored greetings.
// This is a runtime projection, not a destructive migration or a generic HTML
// regex bypass; unrelated/edited messages and ordinary code remain untouched.
export function canReplayGreetingRules(raw, scripts) {
    // Never execute variable, random, time, or other stateful macros merely to
    // identify old display output. Only deterministic name/match substitutions
    // are safe; unknown legacy content stays unchanged.
    const dynamicMacro = /{{(?!\s*(?:char|user|match)\s*}})/i;
    return !dynamicMacro.test(raw) && scripts.filter(rule => !rule.disabled)
        .every(rule => ![rule.findRegex, rule.replaceString, ...(rule.trimStrings || [])]
            .some(value => dynamicMacro.test(String(value || ''))));
}

export function restoreRenderedGreetings(card, existing, content, render) {
    const unchanged = { content, swipes: existing };
    const isDocument = text => /<body(?:\s[^>]*)?>[\s\S]*<\/body\s*>/i.test(text);
    // Historical Python display-regex projection capped replacement output at
    // precisely this boundary, then saved that incomplete document as a swipe.
    // Recovery is only an exact, unique prefix of a COMPLETE deterministic
    // authored output; this is not a general "partial HTML" repair heuristic.
    const legacyLimit = 240000;
    const isLegacyPrefix = text => typeof text === 'string'
        && (text.length === legacyLimit || text.replace(/\r\n/g, '\n').length === legacyLimit)
        && /^[ \t]*(?:`{3,}[ \t]*(?:html)?[ \t]*\r?\n)?[ \t]*<(?:!doctype\s+html|html[\s>]|body[\s>])/i.test(text)
        && /<body(?:\s[^>]*)?>/i.test(text) && !isDocument(text);
    const values = [content, ...existing];
    if (!values.some(value => isDocument(value) || isLegacyPrefix(value))) return unchanged;
    const data = card?.data || card || {};
    const primary = String(data.first_mes || card?.first_mes || '').trim();
    const alternates = data.alternate_greetings || card?.alternate_greetings || [];
    const candidates = [...new Set([primary, ...(Array.isArray(alternates) ? alternates : [])]
        .filter(value => typeof value === 'string' && value.trim()).map(value => value.trim()))];
    // Transport newline conversion is equivalent; body edits, entities and
    // author-version differences are not. Keep all sources under the same key
    // so normalization never guesses between ambiguous authored candidates.
    const outputKey = value => String(value).trim().replace(/\r\n/g, '\n');
    const authoredKeys = new Set(candidates.map(outputKey));
    const outputs = new Map();
    for (const raw of candidates) {
        try {
            const displayed = String(render(raw)).trim();
            if (displayed === raw || !isDocument(displayed)) continue;
            const key = outputKey(displayed);
            const sources = outputs.get(key) || new Set();
            sources.add(raw); outputs.set(key, sources);
            if (displayed.length > legacyLimit) {
                const prefixKey = outputKey(displayed.slice(0, legacyLimit));
                const prefixSources = outputs.get(prefixKey) || new Set();
                prefixSources.add(raw); outputs.set(prefixKey, prefixSources);
            }
        } catch { /* Unknown legacy pipelines must not overwrite user messages. */ }
    }
    const restore = value => {
        const key = outputKey(value);
        // A native authored HTML opening is source, even if another candidate
        // happens to render the same document with different transport endings.
        if (authoredKeys.has(key)) return value;
        if (!isDocument(value) && !isLegacyPrefix(value)) return value;
        const sources = outputs.get(key);
        return sources?.size === 1 ? sources.values().next().value : value;
    };
    return { content: restore(content), swipes: existing.map(restore) };
}

// Durable local rows contain canonical messages, not cloud-message DTOs. They
// need the same narrow legacy-opening projection without dropping swipe/author
// metadata or mutating the persisted row. Call only for the opening message.
export function restoreCanonicalGreeting(card, message, render, scripts = [], { guardedReplay = false } = {}) {
    if (!message || typeof message.mes !== 'string' || message.is_user
        || (message.is_system && !message.extra?.homer_hidden)) return message;
    const existing = Array.isArray(message.swipes) ? message.swipes : [];
    const swipeInfo = Array.isArray(message.swipe_info) ? message.swipe_info : [];
    const displays = [message.extra?.display_text, ...swipeInfo.map(item => item?.extra?.display_text)];
    // A durable row can already contain raw mes/swipes while its derived display
    // still contains the old authored document. Use one reverse-output map for
    // all fields: never render a multi-MB candidate once per cache entry.
    const combined = restoreRenderedGreetings(card, [...existing, ...displays], message.mes,
        // A guarded callback checks only rules that really execute and uses a
        // pure name/match replay, not the live stateful macro engine. Existing
        // callers without that contract retain the conservative all-rule guard.
        raw => canReplayGreetingRules(raw, guardedReplay ? [] : scripts) ? render(raw) : raw);
    const restored = { content: combined.content, swipes: combined.swipes.slice(0, existing.length) };
    const restoredDisplays = combined.swipes.slice(existing.length);
    const contentChanged = restored.content !== message.mes;
    const changedSwipes = restored.swipes.map((value, index) => value !== existing[index]);
    const matchesCanonical = (display, value, source) => typeof display === 'string'
        && value !== display && value === source;
    const activeDisplayChanged = matchesCanonical(displays[0], restoredDisplays[0], restored.content);
    const changedSwipeDisplays = swipeInfo.map((item, index) => index < existing.length
        && matchesCanonical(displays[index + 1], restoredDisplays[index + 1], restored.swipes[index]));
    if (!contentChanged && !changedSwipes.some(Boolean) && !activeDisplayChanged && !changedSwipeDisplays.some(Boolean)) return message;

    const projected = { ...message, mes: restored.content };
    if (changedSwipes.some(Boolean)) projected.swipes = restored.swipes;
    const withoutDisplay = extra => {
        const copy = { ...extra };
        delete copy.display_text;
        return copy;
    };
    // display_text wins over mes in the formatter. Invalidate only an exact,
    // uniquely recovered authored output of this canonical source. Unknown or
    // user-edited caches remain untouched, even when mes itself was recovered.
    if (activeDisplayChanged && message.extra && Object.hasOwn(message.extra, 'display_text')) {
        projected.extra = withoutDisplay(message.extra);
    }
    if (Array.isArray(message.swipe_info)) {
        let changedInfo = false;
        const info = message.swipe_info.map((item, index) => {
            if (!changedSwipeDisplays[index] || !item?.extra || !Object.hasOwn(item.extra, 'display_text')) return item;
            changedInfo = true;
            return { ...item, extra: withoutDisplay(item.extra) };
        });
        if (changedInfo) projected.swipe_info = info;
    }
    return projected;
}

export function greetingSwipes(card, existing, content = '') {
    const data = card?.data || card || {};
    const primary = String(data.first_mes || card?.first_mes || '').trim();
    const values = existing.length ? [...existing] : (content ? [content] : []);
    if (!primary || String(values[0] || '').trim() !== primary) return values;
    const alternates = data.alternate_greetings || card?.alternate_greetings;
    for (const text of Array.isArray(alternates) ? alternates : []) {
        if (typeof text === 'string' && text.trim() && !values.includes(text)) values.push(text);
    }
    return values;
}
