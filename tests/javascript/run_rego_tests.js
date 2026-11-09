'use strict';

// Native runner for the scenarios and assertions from the original Python suite.
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { isDeepStrictEqual } = require('node:util');
const root = path.resolve(__dirname, '../..');
const suite = JSON.parse(fs.readFileSync(path.join(root, 'tests/fixtures/scenarios.json'), 'utf8'));

function at(value, location) {
  for (const part of location ? location.split('.') : []) {
    if (value === null || !Object.hasOwn(value, part)) throw new Error(`Missing path: ${location}`);
    value = value[part];
  }
  return value;
}

function check(value, spec) {
  switch (spec.op) {
    case 'equals': return isDeepStrictEqual(value, spec.expected);
    case 'at': return isDeepStrictEqual(at(value, spec.path), spec.expected);
    case 'contains':
      if (typeof value === 'string') return value.includes(spec.expected);
      if (Array.isArray(value)) return value.some(item => isDeepStrictEqual(item, spec.expected));
      return Object.hasOwn(value, spec.expected);
    case 'count': {
      const current = at(value, spec.path);
      const length = typeof current === 'string' || Array.isArray(current) ? current.length : Object.keys(current).length;
      return length === spec.expected;
    }
    case 'any': return at(value, spec.path).some(item => check(item, spec.check));
    case 'all': return spec.checks.every(item => check(value, item));
    default: throw new Error(`Unknown assertion: ${spec.op}`);
  }
}

let passed = 0;
const passing = [];
for (const scenario of suite.cases) {
  const label = `${scenario.article} / ${scenario.name}`;
  try {
    const input = JSON.parse(JSON.stringify(suite.base_input));
    for (const patch of scenario.patches) {
      let current = input;
      for (const part of patch.path.slice(0, -1)) current = current[part];
      const key = patch.path[patch.path.length - 1];
      if (patch.remove) delete current[key];
      else current[key] = patch.value;
    }
    const result = spawnSync('opa', ['eval', '--format', 'json', '--data', path.join(root, 'gdpr'),
      '--stdin-input', scenario.expr], { input: JSON.stringify(input), encoding: 'utf8', cwd: root,
      timeout: 30000, maxBuffer: 16 * 1024 * 1024, windowsHide: true });
    if (result.error) throw result.error;
    if (result.status !== 0) throw new Error(result.stderr || result.stdout);
    const payload = JSON.parse(result.stdout);
    const value = payload.result?.[0]?.expressions?.[0]?.value ?? null;
    if (!check(value, scenario.expect)) throw new Error(`expr=${scenario.expr}; value=${JSON.stringify(value)}`);
    console.log(`PASS ${label}`);
    passed++;
    passing.push(scenario);
  } catch (error) {
    console.error(`FAIL ${label}: ${error.message}`);
  }
}
console.log(`\nResult: ${passed}/${suite.cases.length} passed`);
console.log('\nScenario coverage checklist:');
let covered = 0;
for (const item of suite.coverage) {
  const ok = passing.some(scenario => scenario.article === item.article &&
    item.terms.every(term => `${scenario.name} ${scenario.expr}`.toLowerCase().includes(term.toLowerCase())));
  console.log(`${ok ? 'PASS' : 'MISS'} ${item.article} / ${item.kind} / ${item.label}`);
  if (ok) covered++;
}
console.log(`\nScenario coverage result: ${covered}/${suite.coverage.length} expected items covered`);
process.exitCode = passed === suite.cases.length && covered === suite.coverage.length ? 0 : 1;
