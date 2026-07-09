// Shared localStorage config load/save, used by page.js, provision/page.js,
// and credit-note/page.js. All three read/write the same 'rechnungsbot_config'
// key and merge with their own page-specific DEFAULT_CONFIG.
export const CONFIG_KEY = 'rechnungsbot_config';

export function loadConfig(defaults) {
  try {
    const stored = localStorage.getItem(CONFIG_KEY);
    if (stored) {
      return { ...defaults, ...JSON.parse(stored) };
    }
  } catch { /* ignore */ }
  return { ...defaults };
}

export function saveConfig(cfg) {
  try {
    localStorage.setItem(CONFIG_KEY, JSON.stringify(cfg));
  } catch { /* ignore */ }
}
