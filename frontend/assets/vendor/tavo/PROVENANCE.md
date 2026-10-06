# TAVO H5 presentation asset provenance

Verified on 2026-10-01.

## Original assets

The `dist/` and `images/` directories contain the unchanged H5 assets extracted
from the locally supplied `tavo最新新新.apk` (TAVO 1.6.1 / 1061). They are the
message-presentation components, input component, images and supporting fonts;
they are **not the complete Flutter/Dart application source**.

Source APK SHA-256:

`16c12a871728ae06cee7025d77a005131f53bb5664e78616dcafbe8001919ef5`

APK entry prefix: `assets/flutter_assets/assets/`.

All 331 files were compared by relative path and SHA-256 against both that APK
and the preserved extracted assets under
`output/tavo-original-ui-20261001/flutter-ui-port/original/`. Results: 331
matching files, zero missing files, zero modified files. This provenance
document is additional project documentation, not an extracted APK asset.

The original `dist/js/bundle.min.js` is 810,129 bytes. SHA-256:

`83f45dd4a508d1914bb00ecf4366fc591785fe6e78996e422f801805c124760b`

## Homer integration code

The Homer-owned adapter is outside this vendor directory:

- `frontend/assets/js/tavo-chat-ui.js`
- `frontend/assets/css/tavo-chat-ui.css`
- the existing Homer chat host and SillyTavern bridge integration

These adapters are original integration code, not recovered TAVO native source.
Homer retains its actual conversation engine, authentication, persistence,
generation, regex processing and card-script runtime. No independent preview's
synthetic provider or synthetic account state is part of these vendor assets.

The adapter loads the original H5 bundle through an external script element,
not through an `eval`/`new Function` loading fallback. The original bundle
itself contains two dynamic `Function` sites for its original plugin runtime;
that is distinct from the adapter's loading mechanism.

## Packaged compatibility output

The existing Android build pipeline uses esbuild targeting Chromium 89, not
Babel. It may transform JavaScript and HTML in the generated APK staging tree.
Those derived packaged bytes can differ from the unchanged vendor source.

A read-only transform and syntax-parse probe passed for this bundle. This is
not proof of compatibility with every old WebView: DOM APIs, original CSS
selectors and device behavior still require runtime validation. In particular,
JavaScript lowering does not transform CSS `:has` selectors.

No account credentials, session data, signing material or private conversation
content is included in this provenance record.
