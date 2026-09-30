// Ephemeral display rules, deliberately separate from saved extension settings.
let scripts = [];
export function setOfficialDisplayRules(payload) {
    const errors = [];
    scripts = [];
    for (const rule of payload?.scripts || []) {
        try {
            const text = String(rule.findRegex || '');
            const match = text.match(/^\/([\s\S]*)\/([dgimsuvy]*)$/);
            new RegExp(match ? match[1] : text, match ? match[2] : '');
            if (!text) throw Error('empty');
            scripts.push({ ...rule, markdownOnly: true, promptOnly: false });
        } catch { errors.push(String(rule.id || 'unknown')); }
    }
    return { count: scripts.length, errors, revision: String(payload?.revision || '') };
}
export function officialDisplayRules() { return scripts; }
