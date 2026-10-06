// Prompt Template's canonical per-swipe state, never rendered HTML or an iframe.
// A versioned presence descriptor distinguishes a legitimate absent variable
// field from an older/incomplete snapshot containing only a processed flag.
const FIELDS = ['is_ejs_processed', 'variables', 'variables_initialized'];
const DESCRIPTOR = 'homer_prompt_state';
const own = (value, key) => Object.prototype.hasOwnProperty.call(value, key);
const record = value => value !== null && typeof value === 'object' && !Array.isArray(value)
    && Object.prototype.toString.call(value) === '[object Object]';

function cloneJson(value, parents = new Set()) {
    if (value === null || typeof value === 'string' || typeof value === 'boolean') return value;
    if (typeof value === 'number' && Number.isFinite(value)) return value;
    if ((!Array.isArray(value) && !record(value)) || parents.has(value)) throw new TypeError('Invalid prompt state');
    const next = new Set(parents); next.add(value);
    if (Array.isArray(value)) {
        const result = [];
        for (let index = 0; index < value.length; index++) {
            const property = Object.getOwnPropertyDescriptor(value, index);
            if (property && !own(property, 'value')) throw new TypeError('Invalid prompt state');
            result.push(!property || property.value === undefined ? null : cloneJson(property.value, next));
        }
        return result;
    }
    const result = {};
    for (const [key, property] of Object.entries(Object.getOwnPropertyDescriptors(value))) {
        if (!property.enumerable) continue;
        if (!own(property, 'value') || property.value === undefined) throw new TypeError('Invalid prompt state');
        Object.defineProperty(result, key, { value: cloneJson(property.value, next), enumerable: true, writable: true, configurable: true });
    }
    return result;
}

function validIndex(message) {
    const swipes = message?.swipes;
    const index = message?.swipe_id;
    return Array.isArray(swipes) && swipes.every(item => typeof item === 'string')
        && Number.isSafeInteger(index) && index >= 0 && index < Math.max(1, swipes.length);
}

function stateFields(message, present, swipeSource = message) {
    if (!validIndex(swipeSource)) return null;
    const count = Math.max(1, swipeSource.swipes.length), values = {};
    try {
        for (const key of FIELDS) {
            if (present[key] !== own(message, key)) return null;
            if (!present[key]) continue;
            const property = Object.getOwnPropertyDescriptor(message, key);
            if (!property || !own(property, 'value')) return null;
            const items = property.value;
            if (!Array.isArray(items) || items.length > count) return null;
            const cloned = cloneJson(items);
            if (key === 'variables' ? cloned.some(item => item !== null && !record(item))
                : cloned.some(item => item !== null && typeof item !== 'boolean')) return null;
            values[key] = cloned;
        }
        for (let index = 0; index < count; index++) {
            // Explicitly absent variables are a legal no-variable snapshot.
            // Present-but-missing variables cannot accompany initialized state.
            if (values.variables_initialized?.[index] === true && !record(values.variables?.[index])) return null;
            if (values.is_ejs_processed?.[index] === true && present.variables && !record(values.variables?.[index])) return null;
        }
        return values;
    } catch { return null; }
}

export function capturePromptMessageState(message, swipeSource = message) {
    const present = Object.fromEntries(FIELDS.map(key => [key, own(message || {}, key)]));
    if (!FIELDS.some(key => present[key])) return null;
    const values = stateFields(message, present, swipeSource);
    return values ? { values, descriptor: { version: 1, present } } : null;
}

function restoredState(message) {
    const descriptor = message?.extra?.[DESCRIPTOR];
    if (!record(descriptor) || descriptor.version !== 1 || !record(descriptor.present)
        || Object.keys(descriptor).some(key => !['version', 'present'].includes(key))
        || Object.keys(descriptor.present).length !== FIELDS.length
        || FIELDS.some(key => typeof descriptor.present[key] !== 'boolean')) return null;
    return stateFields(message, descriptor.present);
}

function role(message) {
    return message.is_system && !message.extra?.homer_hidden ? 'system' : message.is_user ? 'user' : 'assistant';
}

function source(message) {
    if (!message || typeof message.mes !== 'string' || typeof message.is_user !== 'boolean'
        || typeof message.is_system !== 'boolean' || !validIndex(message)) return null;
    // A permanent evaluation may change mes without changing the swipe source.
    // Such a snapshot cannot safely claim that the selected swipe was processed.
    if (message.swipes.length && message.mes !== message.swipes[message.swipe_id]) return null;
    return { role: role(message), mes: message.mes, swipes: [...message.swipes], swipe_id: message.swipe_id };
}

function sameSwipes(left, right) {
    return Array.isArray(left) && Array.isArray(right) && left.length === right.length
        && left.every((item, index) => typeof item === 'string' && item === right[index]);
}

function matchesCloud(cloud, id, canonical) {
    return cloud && typeof cloud.id === 'string' && cloud.id === id && id !== ''
        && cloud.role === canonical.role && cloud.content === canonical.mes
        && cloud.swipe_index === canonical.swipe_id && sameSwipes(cloud.swipes, canonical.swipes);
}

export function samePromptMessageSource(left, right) {
    const a = source(left), b = source(right);
    return Boolean(a && b && a.role === b.role && a.mes === b.mes && a.swipe_id === b.swipe_id && sameSwipes(a.swipes, b.swipes));
}

export function clearPromptMessageState(message) {
    for (const key of FIELDS) delete message[key];
    if (record(message.extra)) delete message.extra[DESCRIPTOR];
}

export function prepareAcknowledgedPromptStates(fresh, local, acknowledged) {
    if (!Array.isArray(fresh) || !Array.isArray(local) || !Array.isArray(acknowledged)) return [];
    const localId = item => item?.extra?.homer_message_id || item?.extra?.homer_sync_id || '';
    const unique = (items, getId) => {
        const counts = new Map();
        for (const item of items) { const id = getId(item); counts.set(id, (counts.get(id) || 0) + 1); }
        return id => typeof id === 'string' && id !== '' && counts.get(id) === 1;
    };
    const freshUnique = unique(fresh, item => item?.id), ackUnique = unique(acknowledged, item => item?.id), localUnique = unique(local, localId);
    return fresh.map((message, index) => {
        const previous = local[index], id = localId(previous), canonical = source(previous), values = restoredState(previous);
        if (!canonical || !values || !freshUnique(id) || !ackUnique(id) || !localUnique(id)
            || !matchesCloud(message, id, canonical) || !matchesCloud(acknowledged[index], id, canonical)) return null;
        return { source: canonical, values };
    });
}

export function restoreAcknowledgedPromptStates(messages, states) {
    let restored = 0;
    messages.forEach((message, index) => {
        const state = states?.[index];
        if (!state || !samePromptMessageSource(message, { ...state.source, is_user: state.source.role === 'user',
            is_system: state.source.role === 'system', extra: {} })) return;
        const captured = capturePromptMessageState({ swipes: message.swipes, swipe_id: message.swipe_id, ...state.values });
        if (!captured) return;
        clearPromptMessageState(message);
        Object.assign(message, captured.values);
        message.extra ||= {};
        message.extra[DESCRIPTOR] = captured.descriptor;
        restored++;
    });
    return restored;
}
