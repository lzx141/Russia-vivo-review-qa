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
