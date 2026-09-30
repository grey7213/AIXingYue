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
    const values = [content, ...existing];
    if (!values.some(isDocument)) return unchanged;
    const data = card?.data || card || {};
    const primary = String(data.first_mes || card?.first_mes || '').trim();
    const alternates = data.alternate_greetings || card?.alternate_greetings || [];
    const candidates = [...new Set([primary, ...(Array.isArray(alternates) ? alternates : [])]
        .filter(value => typeof value === 'string' && value.trim()).map(value => value.trim()))];
    const outputs = new Map();
    for (const raw of candidates) {
        try {
            const displayed = String(render(raw)).trim();
            if (displayed === raw || !isDocument(displayed)) continue;
            const sources = outputs.get(displayed) || new Set();
            sources.add(raw); outputs.set(displayed, sources);
        } catch { /* Unknown legacy pipelines must not overwrite user messages. */ }
    }
    const restore = value => {
        const sources = outputs.get(String(value).trim());
        return sources?.size === 1 ? sources.values().next().value : value;
    };
    return { content: restore(content), swipes: existing.map(restore) };
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
