// This is a one-initialization handoff, not a settings cache. It holds only
// quick-reply preset JSON already returned by the current authenticated read.
const activeHandoffs = new Set();

function cloneQuickReplyPresets(response) {
    if (!response || !Object.hasOwn(response, 'quickReplyPresets')
        || !Array.isArray(response.quickReplyPresets)) return null;
    try {
        // loadSets migrates old presets in place. Never mutate the shared
        // settings response or retain aliases to another subscriber's data.
        return JSON.parse(JSON.stringify(response.quickReplyPresets));
    } catch {
        return null;
    }
}

/**
 * Reuse preset data only while this particular settings initialization runs.
 * An overlapping initialization is deliberately ambiguous and uses the
 * original authenticated fetch instead of consuming a different scope.
 * @param {object} response Successful, parsed settings response
 * @param {() => any} initialize Existing initialization, in its original order
 * @param {() => boolean} [isCurrent] Optional owner/epoch validity guard
 * @returns {Promise<any>}
 */
export async function withQuickReplySettingsHandoff(response, initialize, isCurrent = () => true) {
    const handoff = { presets: cloneQuickReplyPresets(response), isCurrent };
    activeHandoffs.add(handoff);
    try {
        return await initialize();
    } finally {
        handoff.presets = null;
        activeHandoffs.delete(handoff);
    }
}

/**
 * Consume the current initialization's private clone exactly once. null means
 * no safe handoff; an empty array is a valid result and must not trigger fetch.
 * @returns {object[]|null}
 */
export function takeQuickReplySettingsPresets() {
    if (activeHandoffs.size !== 1) return null;
    const handoff = activeHandoffs.values().next().value;
    try {
        if (!handoff.isCurrent()) {
            handoff.presets = null;
            return null;
        }
    } catch {
        handoff.presets = null;
        return null;
    }
    const presets = handoff.presets;
    handoff.presets = null;
    return presets;
}
