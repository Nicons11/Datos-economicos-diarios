const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(__dirname + '/Programador.gs', 'utf8');

function environment() {
  const values = {TOKEN_GITHUB: 'token-de-prueba'};
  const calls = [];
  let status = 204;
  let releases = 0;
  let created = 0;
  const deleted = [];
  const old = {getHandlerFunction: () => 'revisarActualizacionGitHub'};
  const unrelated = {getHandlerFunction: () => 'otraFuncion'};
  const box = {
    console: {log: () => {}},
    PropertiesService: {getScriptProperties: () => ({getProperty: k => values[k], setProperty: (k, v) => {values[k] = v;}})},
    Utilities: {formatDate: (date, zone, pattern) => {
      assert.equal(zone, 'America/Argentina/Buenos_Aires');
      const shifted = new Date(date.getTime() - 3 * 3600000).toISOString();
      return pattern === 'HH' ? shifted.slice(11, 13) : shifted.slice(0, 10);
    }},
    LockService: {getScriptLock: () => ({tryLock: () => true, releaseLock: () => {releases++;}})},
    UrlFetchApp: {fetch: (url, options) => {calls.push({url, options}); return {getResponseCode: () => status};}},
    ScriptApp: {
      getProjectTriggers: () => [old, unrelated],
      newTrigger: name => ({timeBased: () => ({everyMinutes: n => ({create: () => {
        assert.equal(name, 'revisarActualizacionGitHub'); assert.equal(n, 5); created++;
      }})})}),
      deleteTrigger: t => deleted.push(t)
    }
  };
  vm.createContext(box); vm.runInContext(source, box);
  return {box, values, calls, setStatus: s => {status = s;}, releases: () => releases,
    created: () => created, deleted, old};
}

let e = environment();
e.box.revisarActualizacionGitHubEn_(new Date('2026-10-28T22:59:00Z'));
assert.equal(e.calls.length, 0);
e.box.revisarActualizacionGitHubEn_(new Date('2026-10-28T23:00:00Z'));
e.box.revisarActualizacionGitHubEn_(new Date('2026-10-28T23:05:00Z'));
assert.equal(e.calls.length, 1);
assert.equal(e.values.ULTIMO_PEDIDO_GITHUB_20H, '2026-10-28');
assert.equal(e.calls[0].options.method, 'post');
assert.equal(JSON.parse(e.calls[0].options.payload).inputs.comprobar_fuente, false);
e.box.revisarActualizacionGitHubEn_(new Date('2026-10-30T00:00:00Z'));
assert.equal(e.calls.length, 1);
e.box.revisarActualizacionGitHubEn_(new Date('2026-10-29T23:05:00Z'));
assert.equal(e.calls.length, 2);

e = environment(); e.setStatus(403);
assert.throws(() => e.box.revisarActualizacionGitHubEn_(new Date('2026-10-28T23:05:00Z')), /HTTP 403/);
assert.equal(e.values.ULTIMO_PEDIDO_GITHUB_20H, undefined);
assert.equal(e.releases(), 1);
e.setStatus(204);
e.box.revisarActualizacionGitHubEn_(new Date('2026-10-28T23:10:00Z'));
assert.equal(e.calls.length, 2);

e = environment(); e.box.probarActualizacionGitHub();
assert.equal(e.values.ULTIMO_PEDIDO_GITHUB_20H, undefined);
e.box.instalarProgramadorGitHub();
assert.equal(e.created(), 1); assert.deepEqual(e.deleted, [e.old]);
delete e.values.TOKEN_GITHUB;
assert.throws(() => e.box.instalarProgramadorGitHub(), /TOKEN_GITHUB/);
assert.equal(e.created(), 1);
console.log('Programador: horario argentino, deduplicación diaria, día siguiente, reintento tras fallo, prueba manual y conservación de otros disparadores OK.');
