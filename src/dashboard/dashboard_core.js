(function(root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.DashboardCore = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function() {
  function normalizeRoute(hash, routes) {
    const route = String(hash || '').replace(/^#/, '').trim();
    return Array.isArray(routes) && routes.includes(route) ? route : 'overview';
  }

  function formatMetric(value, {suffix = '', digits = 0} = {}) {
    if (value === null || value === undefined || value === '') return '—';
    const number = Number(value);
    if (!Number.isFinite(number)) return '—';
    return `${number.toLocaleString('zh-CN', {
      minimumFractionDigits: 0,
      maximumFractionDigits: digits,
    })}${suffix}`;
  }

  function buildGovernanceView(governance) {
    if (!governance || governance.status !== 'available') {
      return {
        available: false,
        status: 'unavailable',
        metrics: [],
        manifest: null,
        comparison: null,
      };
    }
    const manifest = governance.run_manifest || null;
    const comparison = governance.source_comparison || null;
    return {
      available: Boolean(manifest || comparison),
      status: governance.status,
      metrics: manifest ? [
        {label: '输入记录', value: manifest.input_rows},
        {label: '接受记录', value: manifest.accepted_rows},
        {label: '隔离记录', value: manifest.quarantined_rows},
        {label: '重复记录', value: manifest.duplicate_rows},
      ] : [],
      manifest,
      comparison,
    };
  }

  return {normalizeRoute, formatMetric, buildGovernanceView};
});
