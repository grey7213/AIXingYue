import { createHash } from 'node:crypto';

const SHA256 = /^[a-f0-9]{64}$/i;
const isObject = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const hasIdentifier = value => (typeof value === 'string' && value.trim() !== '')
    || (typeof value === 'number' && Number.isFinite(value) && value > 0);

export const isCardCacheRequested = value => value === 1 || value === '1';

/** Hash the complete JSON representation, not its path or a mutable card marker. */
export function jsonContentSha256(value) {
    return createHash('sha256').update(JSON.stringify(value), 'utf8').digest('hex');
}

function matchesRevision(value, revision) {
    return typeof value === 'string' && SHA256.test(value) && value.toLowerCase() === revision;
}

/**
 * Called only after the normal authenticated upstream session has been fully read.
 * This changes transport size, never authentication, freshness or session state.
 * Invalid, admin-preview and legacy responses are deliberately left untouched.
 */
export function withSessionCardTransport(payload, { enabled, clientSha, status } = {}) {
    if (!isCardCacheRequested(enabled) || !(status >= 200 && status < 300) || !isObject(payload)) return payload;
    const wrapped = isObject(payload.data);
    const session = wrapped ? payload.data : payload;
    const launch = session.launch;
    if (payload.error || payload.success === false || session.error || session.success === false
        || !isObject(session.user) || !hasIdentifier(session.user.id ?? session.user.user_id)
        || !isObject(launch) || launch.admin_preview || session.admin_preview
        || !hasIdentifier(launch.app_id) || !hasIdentifier(launch.conversation_id)
        || typeof launch.bridge_token !== 'string' || !launch.bridge_token.trim()
        || !isObject(launch.card) || !Object.keys(launch.card).length) return payload;

    try {
        const sha256 = jsonContentSha256(launch.card);
        const nextLaunch = { ...launch, card_transport: { version: 1, sha256 } };
        if (matchesRevision(clientSha, sha256)) delete nextLaunch.card;
        const nextSession = { ...session, launch: nextLaunch };
        return wrapped ? { ...payload, data: nextSession } : nextSession;
    } catch {
        // A transport optimization cannot replace a valid legacy response with an error.
        return payload;
    }
}

/** Called only after path validation and the complete processCharacter read. */
export function withCharacterCardTransport(character, { enabled, clientSha } = {}) {
    const version = enabled === 2 || enabled === '2' ? 2 : isCardCacheRequested(enabled) ? 1 : 0;
    if (!version || !isObject(character) || character.shallow
        || typeof character.avatar !== 'string' || !character.avatar.trim()
        || !isObject(character.data) || !Object.keys(character.data).length) return character;

    try {
        if (version === 2) {
            // Only these two known computed statistics are volatile. Keep chat,
            // json_data, author fields and every unknown field in the content.
            const fields = ['chat_size', 'date_last_chat'];
            if (!fields.every(key => Object.hasOwn(character, key)
                && typeof character[key] === 'number' && Number.isFinite(character[key])
                && character[key] >= 0)) return character;
            const content = { ...character };
            const fresh_stats = { chat_size: character.chat_size, date_last_chat: character.date_last_chat };
            fields.forEach(key => delete content[key]);
            const marker = { version: 2, sha256: jsonContentSha256(content) };
            return matchesRevision(clientSha, marker.sha256)
                ? { homer_character_transport: { ...marker, not_modified: true }, fresh_stats }
                : { homer_character_transport: marker, character: content, fresh_stats };
        }
        const sha256 = jsonContentSha256(character);
        const marker = { version, sha256 };
        return matchesRevision(clientSha, sha256)
            ? { homer_character_transport: { ...marker, not_modified: true } }
            : { homer_character_transport: marker, character };
    } catch {
        return character;
    }
}
