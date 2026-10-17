'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const script = fs.readFileSync(path.join(__dirname, '../admin/admin.js'), 'utf8');
const start = script.indexOf('function parseCsv(text){');
const end = script.indexOf('function selectedImageMap(', start);
assert.ok(start >= 0 && end > start, 'bulk import parser must exist');
const context = {};
vm.runInNewContext(script.slice(start, end), context);
const plan = context.csvImageRequirements;
const header = 'name,description,department,category,price,variants,colourName,imageFile,imageUrls';
function csv(local, external = '') {
  return header + '\n' + 'Watch,Watch description,unisex,Accessories,100,One Size:5,Black,"' + local + '","' + external + '"\n';
}

test('single and multiple local filenames are collected in order', () => {
  const single = plan(csv('front.jpg'));
  assert.equal(single.productRows, 1);
  assert.equal(single.requirements.length, 1);
  const multiple = plan(csv('front.jpg|side.jpg|back.jpg'));
  assert.deepEqual(Array.from(multiple.requirements, item => item.fileName), ['front.jpg', 'side.jpg', 'back.jpg']);
});

test('external images count toward the eight image limit', () => {
  assert.equal(plan(csv('front.jpg|side.jpg', 'https://example.com/back.jpg')).requirements.length, 2);
  assert.throws(() => plan(csv(Array(9).fill(0).map((_,i) => 'img'+i+'.jpg').join('|'))), /at most 8 images/);
  assert.throws(() => plan(csv(Array(8).fill(0).map((_,i) => 'img'+i+'.jpg').join('|'), 'https://example.com/back.jpg')), /at most 8 images/);
});

test('rejects empty, duplicate and path traversal filenames', () => {
  assert.throws(() => plan(csv('front.jpg||side.jpg')), /must not be empty/);
  assert.throws(() => plan(csv('front.jpg|front.jpg')), /more than once/);
  assert.throws(() => plan(csv('../front.jpg')), /invalid/);
  assert.throws(() => plan(csv('folder\\front.jpg')), /invalid/);
});

test('URL only products remain supported', () => {
  assert.equal(plan(csv('', 'https://example.com/front.jpg')).requirements.length, 0);
});
