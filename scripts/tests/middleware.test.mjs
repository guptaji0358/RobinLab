import test from 'node:test';
import assert from 'node:assert/strict';
import { onRequest } from '../functions/_middleware.js';

const run = (u) => onRequest({ request: new Request(u), next: async () => new Response('ok', { status: 200 }) });

const redirects = [
  ['https://robinlab.pages.dev/', 'https://roveuth.com/'],
  ['https://robinlab.pages.dev/skills', 'https://roveuth.com/skills'],
  ['https://robinlab.pages.dev/skills?a=1&b=x%20y', 'https://roveuth.com/skills?a=1&b=x%20y'],
  ['https://robinlab.pages.dev/projects/Contact%20Book/', 'https://roveuth.com/projects/Contact%20Book/'],
  ['http://robinlab.pages.dev/collection?share=t', 'https://roveuth.com/collection?share=t'],
  ['https://www.roveuth.com/skills?x=1', 'https://roveuth.com/skills?x=1'],
];
for (const [from, to] of redirects) {
  test(`301 ${from}`, async () => {
    const r = await run(from);
    assert.equal(r.status, 301);
    assert.equal(r.headers.get('location'), to);
  });
}
for (const u of ['https://roveuth.com/', 'https://roveuth.com/skills?x=1', 'https://44c1666a.robinlab.pages.dev/', 'https://master.robinlab.pages.dev/', 'http://localhost:8788/']) {
  test(`pass-through ${u}`, async () => {
    const r = await run(u);
    assert.equal(r.status, 200);
  });
}
