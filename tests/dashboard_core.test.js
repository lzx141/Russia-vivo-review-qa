const test = require('node:test');
const assert = require('node:assert/strict');
const core = require('../src/dashboard/dashboard_core.js');

test('normalizeRoute restores valid hashes and rejects unknown routes', () => {
  const routes = ['overview', 'governance'];
  assert.equal(core.normalizeRoute('#governance', routes), 'governance');
  assert.equal(core.normalizeRoute('#unknown', routes), 'overview');
  assert.equal(core.normalizeRoute('', routes), 'overview');
});

test('formatMetric renders numbers and refuses invalid values', () => {
  assert.equal(core.formatMetric(12345), '12,345');
  assert.equal(core.formatMetric(92.54, {suffix: '%', digits: 1}), '92.5%');
  assert.equal(core.formatMetric(null), '—');
  assert.equal(core.formatMetric('not-a-number'), '—');
});

test('buildGovernanceView never fabricates missing metrics', () => {
  const view = core.buildGovernanceView({status: 'unavailable'});
  assert.equal(view.available, false);
  assert.equal(view.status, 'unavailable');
  assert.deepEqual(view.metrics, []);
  assert.equal(view.comparison, null);
});

test('buildGovernanceView preserves manifest and comparison evidence', () => {
  const comparison = {status: 'available', matched_product_count: 3};
  const view = core.buildGovernanceView({
    status: 'available',
    run_manifest: {
      run_id: 'run-1', input_rows: 100, accepted_rows: 82,
      quarantined_rows: 12, duplicate_rows: 6, quality_pass_rate: 82,
      quality_gate_status: 'passed'
    },
    source_comparison: comparison,
  });
  assert.equal(view.available, true);
  assert.equal(view.metrics[0].value, 100);
  assert.equal(view.metrics[3].value, 6);
  assert.equal(view.comparison, comparison);
});

test('buildGovernanceView exposes dataset audit evidence and source coverage', () => {
  const sourceCoverage = [
    {platform: 'Wildberries', total: 20, latest_record_at: '2026-09-30 07:11:00'},
    {platform: 'OZON', total: 5, latest_record_at: '2026-09-29 00:00:00'},
  ];
  const view = core.buildGovernanceView({
    status: 'available',
    evidence_source: 'published_dataset_audit',
    run_manifest: {
      input_rows: 25, accepted_rows: 25, quarantined_rows: 0,
      duplicate_rows: 0, quality_pass_rate: 100,
      quality_gate_status: 'passed',
    },
    source_coverage: sourceCoverage,
    freshness: {latest_record_at: '2026-09-30 07:11:00', status: 'current'},
    audit_scope: {version: 'abc1234', generated_at: '2026-10-04 12:00:00'},
  });

  assert.equal(view.available, true);
  assert.equal(view.evidenceSource, 'published_dataset_audit');
  assert.equal(view.sourceCoverage, sourceCoverage);
  assert.equal(view.freshness.status, 'current');
  assert.equal(view.auditScope.version, 'abc1234');
});
