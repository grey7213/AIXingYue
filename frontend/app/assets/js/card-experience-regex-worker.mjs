import { safeRegExp } from './card-experience-schema.mjs?v=20260716';

self.onmessage = (event) => {
  const data = event?.data || {};
  const input = String(data.input || '').slice(-8192);
  const patterns = Array.isArray(data.patterns) ? data.patterns.slice(0, 60) : [];
  const matches = patterns.map((item) => {
    const regex = safeRegExp(item?.pattern, item?.flags);
    return !!(regex && regex.test(input));
  });
  self.postMessage({ matches });
};
