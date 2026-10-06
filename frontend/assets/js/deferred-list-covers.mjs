// Pure presentation resource scheduling. Never delays a row, its text or click.
// An explicit open predicate is required: transformed/hidden scroll roots can
// report internal intersections even when their drawer is closed.
export function createDeferredListCovers({ list, scrollRoot = list, isOpen, setCover, margin = 100 }) {
  if (!list || typeof isOpen !== 'function' || typeof setCover !== 'function') {
    throw new TypeError('A list, open predicate and cover setter are required');
  }
  const view = list.ownerDocument.defaultView;
  const nearby = Math.max(0, Math.min(300, Number(margin) || 0));
  const items = new Map();
  let observer = null;
  let generation = 0;
  let settleTimer = null;
  let disposed = false;

  const active = () => !disposed && list.isConnected && scrollRoot.isConnected && isOpen();
  const belongs = node => node.isConnected && list.contains(node);
  const pending = item => item.url && item.assigned !== item.url;
  const paint = (node, item) => {
    // Look up the current item/URL instead of capturing an old request's value.
    if (!active() || !belongs(node) || items.get(node) !== item || !pending(item)) return;
    setCover(node, item.url);
    item.assigned = item.url;
    if (item.observed) observer?.unobserve(node);
    item.observed = false;
  };

  function refresh() {
    if (!active()) return;
    if (typeof view.IntersectionObserver === 'function') {
      if (!observer) {
        const ticket = generation;
        observer = new view.IntersectionObserver(entries => {
          if (ticket !== generation || !active()) return;
          for (const entry of entries) {
            if (!entry.isIntersecting) continue;
            const item = items.get(entry.target);
            if (item) paint(entry.target, item);
          }
        }, { root: scrollRoot, rootMargin: `${nearby}px 0px`, threshold: 0 });
      }
      for (const [node, item] of items) {
        if (!item.observed && pending(item) && belongs(node)) {
          observer.observe(node);
          item.observed = true;
        }
      }
      return;
    }
    // Older engines get the same bounded geometry rule, not eager whole-list
    // loading. Include the actual viewport as well as the scroll-root clip.
    const box = scrollRoot.getBoundingClientRect();
    const left = Math.max(0, box.left), right = Math.min(view.innerWidth, box.right);
    const top = Math.max(0, box.top) - nearby;
    const bottom = Math.min(view.innerHeight, box.bottom) + nearby;
    if (right <= left || bottom <= top) return;
    for (const [node, item] of items) {
      if (!pending(item) || !belongs(node)) continue;
      const rect = node.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0 && rect.right > left && rect.left < right
          && rect.bottom > top && rect.top < bottom) paint(node, item);
    }
  }

  function set(node, url) {
    if (disposed || !node) return;
    const desired = String(url || '');
    let item = items.get(node);
    if (!item) {
      item = { url: desired, assigned: '', observed: false };
      items.set(node, item);
    } else if (item.url !== desired) {
      if (item.assigned) setCover(node, ''); // Never expose a previous role's cover.
      item.url = desired;
      item.assigned = '';
      if (item.observed) observer?.unobserve(node);
      item.observed = false;
    }
    if (!desired && item.observed) {
      observer?.unobserve(node);
      item.observed = false;
    }
    // set() may run before the row is appended. retain()/open() handles that.
  }

  function retain(nodes) {
    if (disposed) return;
    const retained = new Set(nodes);
    for (const [node, item] of items) {
      if (retained.has(node)) continue;
      if (item.observed) observer?.unobserve(node);
      items.delete(node);
    }
    refresh();
  }

  function open() {
    if (!active()) return;
    refresh();
    if (typeof view.IntersectionObserver !== 'function') {
      // One bounded revisit after the drawer's opening transition, not a poll.
      if (settleTimer !== null) view.clearTimeout(settleTimer);
      const ticket = generation;
      settleTimer = view.setTimeout(() => {
        settleTimer = null;
        if (ticket === generation) refresh();
      }, 220);
    }
  }

  function close() {
    generation++;
    observer?.disconnect();
    observer = null;
    for (const item of items.values()) item.observed = false;
    if (settleTimer !== null) view.clearTimeout(settleTimer);
    settleTimer = null;
    // Keep already assigned images, including in-flight ones. Closing a drawer
    // must not clear/cancel and re-request every visited cover on the next open.
  }

  function dispose() {
    if (disposed) return;
    close();
    disposed = true;
    items.clear();
    scrollRoot.removeEventListener('scroll', refresh);
    view.removeEventListener('resize', refresh);
  }

  scrollRoot.addEventListener('scroll', refresh, { passive: true });
  view.addEventListener('resize', refresh, { passive: true });
  return Object.freeze({ set, retain, open, close, dispose });
}
