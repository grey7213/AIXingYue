/* Read the shell appearance before its first paint, without waiting for APIs. */
(() => {
  if (window.HomerApplyTheme) {
    window.HomerApplyTheme();
    return;
  }
  window.HomerApplyTheme = () => {
    let saved = null;
    try { saved = localStorage.getItem('ai_xingyue_shell_theme'); } catch {}
    const theme = saved === 'dark' ? 'dark' : saved !== null ? 'light'
      : typeof matchMedia === 'function' && matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    document.documentElement.dataset.theme = theme;
    // A missing/older native bridge must not prevent the document theme.
    try { window.HomerNative?.setAppTheme?.(theme); } catch {}
    return theme;
  };
  window.HomerApplyTheme();
})();
