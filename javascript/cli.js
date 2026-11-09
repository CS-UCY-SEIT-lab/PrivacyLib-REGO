'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { GdprRouter } = require('./src/gdpr-router');

async function main() {
  const [policy, file = path.join(__dirname, '../gdpr/input.json'), userId] = process.argv.slice(2);
  if (!policy) throw new Error('Usage: node javascript/cli.js <policy> [input.json] [userId]');
  const input = JSON.parse(fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, ''));
  console.log(JSON.stringify(await new GdprRouter().route(policy, input, userId), null, 2));
}

main().catch(error => { console.error(error.message); process.exitCode = 1; });
