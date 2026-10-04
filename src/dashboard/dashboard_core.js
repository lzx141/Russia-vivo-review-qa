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
      evidenceSource: governance.evidence_source || 'external_artifact',
      metrics: manifest ? [
        {label: '输入记录', value: manifest.input_rows},
        {label: '接受记录', value: manifest.accepted_rows},
        {label: '隔离记录', value: manifest.quarantined_rows},
        {label: '重复记录', value: manifest.duplicate_rows},
        {label: '日期完整率', value: manifest.date_completeness, suffix: '%', digits: 2},
        {label: '核心字段完整率', value: manifest.content_completeness, suffix: '%', digits: 2},
        {label: '翻译覆盖率', value: manifest.translation_coverage, suffix: '%', digits: 2},
      ] : [],
      manifest,
      comparison,
      sourceCoverage: Array.isArray(governance.source_coverage) ? governance.source_coverage : [],
      freshness: governance.freshness || {},
      auditScope: governance.audit_scope || {},
    };
  }

  return {normalizeRoute, formatMetric, buildGovernanceView};
});
