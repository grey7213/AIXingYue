// Cache source preparation only. Captures, trimming and stateful macro
// substitution are evaluated on every use; no final HTML/script state is cached.
export function fingerprintCardJson(text) {
    let hash = 2166136261;
    for (let index = 0; index < text.length; index++) {
        hash ^= text.charCodeAt(index);
        hash = Math.imul(hash, 16777619);
    }
    return `v2-${(hash >>> 0).toString(16).padStart(8, '0')}-${text.length}`;
}

export function createCardPreparationCache({ maxEntries = 8, maxChars = 8_000_000, fingerprint = fingerprintCardJson } = {}) {
    const entries = new Map();
    let chars = 0;
    return {
        prepare(scope, card) {
            // Compare the complete serialized source, not timestamps, names,
            // object identity or a hash alone. Runtime overlays may change a
            // card even while its published version stays the same.
            const json = JSON.stringify(card || {});
            const previous = entries.get(scope);
            if (previous?.json === json) {
                entries.delete(scope);
                entries.set(scope, previous);
                return { ...previous, reused: true };
            }
            if (previous) { chars -= previous.json.length; entries.delete(scope); }
            const prepared = { json, signature: fingerprint(json) };
            if (maxEntries > 0 && json.length <= maxChars) {
                entries.set(scope, prepared);
                chars += json.length;
                while (entries.size > maxEntries || chars > maxChars) {
                    const key = entries.keys().next().value;
                    chars -= entries.get(key).json.length;
                    entries.delete(key);
                }
            }
            return { ...prepared, reused: false };
        },
        clear() { entries.clear(); chars = 0; },
    };
}

export function createRegexTemplateCache({ maxEntries = 32, maxChars = 8_000_000 } = {}) {
    const entries = new Map();
    let chars = 0;
    return {
        get(script) {
            const source = script.replaceString;
            const previous = entries.get(script);
            if (previous?.source === source) {
                entries.delete(script); entries.set(script, previous);
                return previous.parts;
            }
            if (previous) { entries.delete(script); chars -= previous.source.length; }
            // Keep exactly the canonical two-pass token semantics, including
            // $0/{{match}}, leading-zero group numbers and named groups.
            const normalized = source.replace(/{{match}}/gi, '$0');
            const parts = [];
            let offset = 0;
            for (const match of normalized.matchAll(/\$(\d+)|\$<([^>]+)>/g)) {
                if (match.index > offset) parts.push(normalized.slice(offset, match.index));
                parts.push(match[1] ? { number: Number(match[1]) } : { name: match[2] });
                offset = match.index + match[0].length;
            }
            if (offset < normalized.length || !parts.length) parts.push(normalized.slice(offset));
            if (maxEntries > 0 && source.length <= maxChars) {
                entries.set(script, { source, parts }); chars += source.length;
                while (entries.size > maxEntries || chars > maxChars) {
                    const key = entries.keys().next().value;
                    chars -= entries.get(key).source.length; entries.delete(key);
                }
            }
            return parts;
        },
    };
}

export function fillRegexTemplate(parts, args, filter) {
    if (parts.length === 1 && typeof parts[0] === 'string') return parts[0];
    return parts.map(part => {
        if (typeof part === 'string') return part;
        const groups = args[args.length - 1];
        const value = Object.hasOwn(part, 'number') ? args[part.number]
            : groups && typeof groups === 'object' ? groups[part.name] : undefined;
        return value ? filter(value) : '';
    }).join('');
}
