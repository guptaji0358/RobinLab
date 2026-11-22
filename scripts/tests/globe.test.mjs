// Globe geography guard rails. Run: node --test scripts/tests/globe.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', 'root', 'js');
const sandbox = { window: {} };
vm.runInNewContext(readFileSync(join(ROOT, 'globe-data.js'), 'utf8'), sandbox);
const D = sandbox.window.RLGlobeData;
const hm = (d) => d.toISOString().slice(11, 16);
const within = (d, utc, mins = 4) => {
  const [h, m] = utc.split(':').map(Number);
  const want = h * 60 + m, got = d.getUTCHours() * 60 + d.getUTCMinutes();
  assert.ok(Math.abs(((got - want + 720 + 1440) % 1440) - 720) <= mins, `${hm(d)} vs ${utc}`);
};

test('every timezone entry has valid, hemisphere-consistent coordinates', () => {
  const src = readFileSync(join(ROOT, 'globe-data.js'), 'utf8');
  const rows = [...src.matchAll(/'([A-Za-z_\/]+)': \['[^']*', '[^']*', '[^']*', (-?[\d.]+), (-?[\d.]+)\]/g)];
  assert.ok(rows.length > 50);
  for (const [, tz, la, lo] of rows) {
    assert.ok(Math.abs(la) <= 90 && Math.abs(lo) <= 180, tz);
    const l = D.fromTimezone(tz);
    assert.equal(l.lat, +la); assert.equal(l.lon, +lo); assert.equal(l.precise, false);
  }
  const south = ['America/Sao_Paulo', 'Australia/Sydney', 'Africa/Johannesburg', 'Asia/Jakarta'];
  for (const z of south) assert.ok(D.fromTimezone(z).lat < 0, z);
  for (const z of ['America/New_York', 'America/Los_Angeles', 'Europe/London', 'America/Sao_Paulo'])
    assert.ok(D.fromTimezone(z).lon < 1, z);
  assert.equal(D.fromTimezone('Mars/Olympus'), null);
});

// Marker anchor (globe-scene.js place()) must land on the texel three.js's SphereGeometry
// assigns to the same lat/lon in an equirectangular map (u = (lon+180)/360, v = (lat+90)/180).
test('marker anchor matches SphereGeometry/equirectangular texture mapping', () => {
  const rad = Math.PI / 180;
  const anchor = (la, lo) => [Math.cos(la * rad) * Math.cos(lo * rad), Math.sin(la * rad), -Math.cos(la * rad) * Math.sin(lo * rad)];
  const vertex = (u, v) => { // three.js SphereGeometry
    const phi = u * 2 * Math.PI, theta = (1 - v) * Math.PI;
    return [-Math.cos(phi) * Math.sin(theta), Math.cos(theta), Math.sin(phi) * Math.sin(theta)];
  };
  for (const [la, lo] of [[28.61, 77.21], [40.71, -74.01], [-33.87, 151.21], [51.51, -0.13], [0, 0], [-23.55, -46.63]]) {
    const a = anchor(la, lo), b = vertex((lo + 180) / 360, (la + 90) / 180);
    a.forEach((x, i) => assert.ok(Math.abs(x - b[i]) < 1e-9, `${la},${lo} axis ${i}`));
  }
});

test('initial spin brings the visitor longitude to face the camera (+z)', () => {
  for (const lo of [77.21, -74.01, 151.21, -0.13, 179, -179]) {
    const rad = Math.PI / 180, a = -(lo * rad) - 1.57;
    const x = Math.cos(lo * rad), z = -Math.sin(lo * rad);
    const zr = -x * Math.sin(a) + z * Math.cos(a); // Y-rotation by a
    assert.ok(zr > 0.999, `lon ${lo}: z=${zr}`);
  }
});

test('sunrise/sunset match NOAA reference values within 4 minutes', () => {
  // Reference (UTC): Greenwich 2026-06-21 03:43 / 20:21; New Delhi 2026-11-22 01:18 / 11:55
  // (06:48 / 17:25 IST); Sydney 2026-12-21 18:41(prev day) / 09:05 (05:41 / 20:05 AEDT)
  let s = D.sun(51.4769, 0, new Date(2026, 5, 21, 12));
  within(s.rise, '03:43'); within(s.set, '20:21');
  s = D.sun(28.61, 77.21, new Date(2026, 10, 22, 12));
  within(s.rise, '01:18'); within(s.set, '11:55');
  s = D.sun(-33.87, 151.21, new Date(2026, 11, 21, 12));
  within(s.rise, '18:41'); within(s.set, '09:05');
});

test('polar day/night returns null; hemispheres flip day length seasonally', () => {
  assert.equal(D.sun(78.2, 15.6, new Date(2026, 5, 21, 12)), null); // Svalbard, midnight sun
  assert.equal(D.sun(78.2, 15.6, new Date(2026, 11, 21, 12)), null); // polar night
  const len = (la, m, day) => { const s = D.sun(la, 0, new Date(2026, m, day, 12)); return (s.set - s.rise) / 36e5; };
  assert.ok(len(51.5, 5, 21) > len(51.5, 11, 21) + 6);
  assert.ok(len(-33.9, 11, 21) > len(-33.9, 5, 21) + 3);
});

test('UTC offset label handles DST (Intl) for fixed dates', () => {
  const off = (tz, iso) => {
    const p = new Intl.DateTimeFormat('en-US', { timeZone: tz, timeZoneName: 'longOffset' }).formatToParts(new Date(iso)).find((x) => x.type === 'timeZoneName').value;
    return p;
  };
  assert.equal(off('America/New_York', '2026-01-15T12:00:00Z'), 'GMT-05:00');
  assert.equal(off('America/New_York', '2026-07-15T12:00:00Z'), 'GMT-04:00');
  assert.equal(off('Asia/Kolkata', '2026-07-15T12:00:00Z'), 'GMT+05:30');
});
