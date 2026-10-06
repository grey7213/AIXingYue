// Mirrors the server's SHA-256 of its exact JSON encoding. HTTPS uses the
// browser's native digest; HTTP/older WebViews may use the pure Android helper
// before the offline licensed fallback. Capture JSON exactly once in all paths.
export async function jsonContentSha256(value, { subtle = globalThis.crypto?.subtle, nativeBridge } = {}) {
    const body = JSON.stringify(value);
    if (typeof body !== 'string') throw new TypeError('Expected a JSON value');
    let bytes;
    if (subtle) {
        bytes = new TextEncoder().encode(body);
        try {
            return digestHex(await subtle.digest('SHA-256', bytes));
        } catch { /* Some older WebViews expose but cannot use SubtleCrypto. */ }
    }
    try {
        const bridge = nativeBridge === undefined ? globalThis.HomerNative : nativeBridge;
        if (typeof bridge?.sha256Utf8 === 'function') {
            // JavaScriptInterface methods must retain their injected receiver.
            const digest = bridge.sha256Utf8(body);
            if (typeof digest === 'string' && /^[a-f0-9]{64}$/.test(digest)) return digest;
        }
    } catch { /* Missing/old/refusing native clients keep the full web fallback. */ }
    bytes ??= new TextEncoder().encode(body);
    return encodedBytesSha256(bytes, { subtle: null });
}

function digestHex(digest) {
    return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('');
}

// The caller owns these exact bytes and must keep them unchanged until this
// promise settles. Cache writers can reuse their private UTF-8 capture for the
// budget and complete digest without serializing/encoding it a second time.
export async function encodedBytesSha256(bytes, { subtle = globalThis.crypto?.subtle } = {}) {
    if (!(bytes instanceof Uint8Array)) throw new TypeError('Expected encoded Uint8Array bytes');
    if (subtle) {
        try {
            const digest = await subtle.digest('SHA-256', bytes);
            return digestHex(digest);
        } catch { /* Some older WebViews expose but cannot use SubtleCrypto. */ }
    }
    const { sha256 } = await import('../lib/sha256.browser.mjs');
    return sha256(bytes);
}
