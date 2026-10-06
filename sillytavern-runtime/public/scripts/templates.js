import { DOMPurify, Handlebars } from '../lib.js';
import { applyLocale } from './i18n.js';

/**
 * @type {Map<string, function>}
 * @description Cache for Handlebars templates.
 */
const TEMPLATE_CACHE = new Map();
const TEMPLATE_PENDING = new Map();

// Only static templates used by the built-in startup hooks. Preloading does
// not render template data, run helpers, mount controls, or activate extensions.
// Keep paths identical to renderTemplate[Async]/renderExtensionTemplateAsync.
const STARTUP_TEMPLATE_PATHS = Object.freeze([
    '/scripts/templates/wandButton.html',
    '/scripts/templates/wandMenu.html',
    'scripts/extensions/attachments/manage-button.html',
    'scripts/extensions/attachments/attach-button.html',
    'scripts/extensions/caption/settings.html',
    'scripts/extensions/connection-manager/settings.html',
    'scripts/extensions/expressions/settings.html',
    'scripts/extensions/memory/settings.html',
    'scripts/extensions/regex/dropdown.html',
    'scripts/extensions/stable-diffusion/button.html',
    'scripts/extensions/stable-diffusion/dropdown.html',
    'scripts/extensions/stable-diffusion/settings.html',
    'scripts/extensions/translate/index.html',
    'scripts/extensions/translate/buttons.html',
    'scripts/extensions/tts/settings.html',
    'scripts/extensions/vectors/settings.html',
]);

function templatePath(templateId, fullPath = false) {
    return fullPath ? templateId : `/scripts/templates/${templateId}.html`;
}

/**
 * Loads a URL content using XMLHttpRequest synchronously.
 * @param {string} url URL to load synchronously
 * @returns {string} Response text
 */
function getUrlSync(url) {
    console.debug('Loading URL synchronously', url);
    const request = new XMLHttpRequest();
    request.open('GET', url, false); // `false` makes the request synchronous
    request.send();

    if (request.status >= 200 && request.status < 300) {
        return request.responseText;
    }

    throw new Error(`Error loading ${url}: ${request.status} ${request.statusText}`);
}

/**
 * Loads a URL content using XMLHttpRequest asynchronously.
 * @param {string} url URL to load asynchronously
 * @returns {Promise<string>} Response text
 */
function getUrlAsync(url) {
    return new Promise((resolve, reject) => {
        const request = new XMLHttpRequest();
        request.open('GET', url, true);
        request.onload = () => {
            if (request.status >= 200 && request.status < 300) {
                resolve(request.responseText);
            } else {
                reject(new Error(`Error loading ${url}: ${request.status} ${request.statusText}`));
            }
        };
        request.onerror = () => {
            reject(new Error(`Error loading ${url}: ${request.status} ${request.statusText}`));
        };
        request.send();
    });
}

function loadTemplateAsync(pathToTemplate) {
    const cached = TEMPLATE_CACHE.get(pathToTemplate);
    if (cached) return Promise.resolve(cached);
    const inFlight = TEMPLATE_PENDING.get(pathToTemplate);
    if (inFlight) return inFlight;

    const load = getUrlAsync(pathToTemplate).then(templateContent => {
        // A deprecated synchronous renderer may have filled the cache while
        // this read was in flight. Do not replace its already-working template.
        const template = TEMPLATE_CACHE.get(pathToTemplate) || Handlebars.compile(templateContent);
        TEMPLATE_CACHE.set(pathToTemplate, template);
        return template;
    });
    const pending = load.finally(() => {
        if (TEMPLATE_PENDING.get(pathToTemplate) === pending) TEMPLATE_PENDING.delete(pathToTemplate);
    });
    TEMPLATE_PENDING.set(pathToTemplate, pending);
    return pending;
}

/**
 * Warm only the built-in startup templates, with bounded transfer concurrency.
 * Failures are not cached or toasted: a normal render can retry and report them.
 * Handlebars.compile creates a lazy factory; this warms reads/factories, not
 * rendered HTML or a promise that template execution has already completed.
 * @returns {Promise<void>}
 */
export async function prefetchStartupTemplates() {
    let cursor = 0;
    async function worker() {
        while (cursor < STARTUP_TEMPLATE_PATHS.length) {
            const path = STARTUP_TEMPLATE_PATHS[cursor++];
            try { await loadTemplateAsync(path); } catch { /* The real render retries. */ }
        }
    }
    await Promise.all(Array.from({ length: 3 }, () => worker()));
}

/**
 * Renders a Handlebars template asynchronously.
 * @param {string} templateId ID of the template to render
 * @param {Record<string, any>} templateData The data to pass to the template
 * @param {boolean} sanitize Should the template be sanitized with DOMPurify
 * @param {boolean} localize Should the template be localized
 * @param {boolean} fullPath Should the template ID be treated as a full path or a relative path
 * @returns {Promise<string>} Rendered template
 */
export async function renderTemplateAsync(templateId, templateData = {}, sanitize = true, localize = true, fullPath = false) {
    try {
        const pathToTemplate = templatePath(templateId, fullPath);
        const template = await loadTemplateAsync(pathToTemplate);
        let result = template(templateData);

        if (sanitize) {
            result = DOMPurify.sanitize(result);
        }

        if (localize) {
            result = applyLocale(result);
        }

        return result;
    } catch (err) {
        console.error('Error rendering template', templateId, templateData, err);
        toastr.error('Check the DevTools console for more information.', 'Error rendering template');
    }
}

/**
 * Renders a Handlebars template synchronously.
 * @param {string} templateId ID of the template to render
 * @param {Record<string, any>} templateData The data to pass to the template
 * @param {boolean} sanitize Should the template be sanitized with DOMPurify
 * @param {boolean} localize Should the template be localized
 * @param {boolean} fullPath Should the template ID be treated as a full path or a relative path
 * @returns {string} Rendered template
 *
 * @deprecated Use renderTemplateAsync instead.
 */
export function renderTemplate(templateId, templateData = {}, sanitize = true, localize = true, fullPath = false) {
    function fetchTemplateSync(pathToTemplate) {
        let template = TEMPLATE_CACHE.get(pathToTemplate);
        if (!template) {
            const templateContent = getUrlSync(pathToTemplate);
            template = Handlebars.compile(templateContent);
            TEMPLATE_CACHE.set(pathToTemplate, template);
        }
        return template;
    }

    try {
        const pathToTemplate = templatePath(templateId, fullPath);
        const template = fetchTemplateSync(pathToTemplate);
        let result = template(templateData);

        if (sanitize) {
            result = DOMPurify.sanitize(result);
        }

        if (localize) {
            result = applyLocale(result);
        }

        return result;
    } catch (err) {
        console.error('Error rendering template', templateId, templateData, err);
        toastr.error('Check the DevTools console for more information.', 'Error rendering template');
    }
}
