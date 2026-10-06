/**
 * Regex depth depends only on the non-system message positions, not on their
 * content. Keep this index scoped to one synchronous render batch: it must not
 * become a cache of macro, regex, Markdown or HTML output.
 */
export function getMessageDepth(messages, messageId) {
    const index = Number(messageId);
    // Keep the original live scan for single updates and unusual message
    // objects. In particular, do not alter stateful flag-getter evaluation.
    const usable = messages.map((message, i) => ({ message, i })).filter(item => !item.message.is_system);
    const position = usable.findIndex(item => item.i === index);
    return messageId >= 0 && position !== -1 ? usable.length - position - 1 : undefined;
}

/** Legacy macros are curly placeholders or these exact non-curly markers. */
export function containsLegacyMacroSyntax(content) {
    return typeof content !== 'string' || content.includes('{{') || /<(?:USER|BOT|CHAR|GROUP|CHARIFNOTGROUP)>/i.test(content);
}

/**
 * Build once for ordinary immutable-in-this-turn message positions. Macro
 * evaluation invalidates the batch before invoking arbitrary macro handlers;
 * the next lookup rebuilds it after those handlers have finished.
 */
export function createMessageDepthBatch(messages) {
    let depths = [];
    let references = [];
    let length = -1;
    let dirty = true;
    let hasDynamicFlags = false;

    function rebuild() {
        length = messages.length;
        depths = new Array(length);
        references = messages.slice();
        hasDynamicFlags = false;
        for (const message of references) {
            // A plugin may install a stateful getter. Do not change its live
            // evaluation semantics by caching that flag.
            const descriptor = Object.getOwnPropertyDescriptor(message, 'is_system');
            const prototype = Object.getPrototypeOf(message);
            if (descriptor?.get || descriptor?.set || (prototype !== Object.prototype && prototype !== null)) {
                hasDynamicFlags = true;
                break;
            }
        }
        if (!hasDynamicFlags) {
            let depth = 0;
            for (let i = length - 1; i >= 0; i--) {
                if (!messages[i].is_system) depths[i] = depth++;
            }
        }
        dirty = false;
    }

    return {
        invalidate() { dirty = true; },
        depth(messageId) {
            const index = Number(messageId);
            const validIndex = Number.isInteger(index) && index >= 0 && index < messages.length;
            if (dirty || length !== messages.length || (validIndex && references[index] !== messages[index])) rebuild();
            if (hasDynamicFlags) return getMessageDepth(messages, messageId);
            if (!validIndex) return undefined;
            return depths[index];
        },
    };
}
