import { MacrosParser } from './macros.js';
import { power_user } from './power-user.js';
import { macros as macroSystem } from './macros/macro-system.js';
import { isBuiltinNameMacro } from './macros/definitions/env-macros.js';
import { ELSE_MARKER } from './macros/definitions/core-macros.js';

// Read at invocation time: startup has cyclic imports and extensions can change
// registrations after startup. This guard never evaluates a macro or processor.
export function assertDeterministicMacroReplayEligible(value) {
    const text = String(value ?? '');
    const experimental = Boolean(power_user.experimental_macro_engine);
    if (experimental && (!macroSystem.engine.hasOnlyCoreProcessors() || macroSystem.envBuilder.hasProviders()
        || /\\[{}]|{{trim}}/i.test(text) || text.includes(ELSE_MARKER))) {
        throw new Error('Unsafe deterministic regex replay');
    }
    // Legacy registrations retain key casing, but evaluation matches them with
    // case-insensitive regexes. Its public iterator only reads keys/descriptions.
    const isRegistered = name => experimental ? macroSystem.registry.hasMacro(name)
        : MacrosParser.has(name) || [...MacrosParser].some(({ key }) => key.toLowerCase() === name);
    if (/{{match}}/i.test(text) && isRegistered('match')) {
        throw new Error('Unsafe deterministic regex replay');
    }
    for (const match of text.matchAll(/{{(user|char)}}/gi)) {
        const name = match[1].toLowerCase();
        if (experimental ? !isBuiltinNameMacro(name) : isRegistered(name)) {
            throw new Error('Unsafe deterministic regex replay');
        }
    }
}
