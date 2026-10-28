// Agregar como archivo NUEVO en el proyecto existente de Apps Script.
// No reemplazar Codigo.gs, no cambiar CLAVE_GITHUB ni la implementación web.

function solicitarActualizacionGitHub_() {
  const token = PropertiesService.getScriptProperties().getProperty('TOKEN_GITHUB');
  if (!token || !token.trim()) throw new Error('Falta TOKEN_GITHUB en las propiedades del proyecto');
  const respuesta = UrlFetchApp.fetch(
    'https://api.github.com/repos/Nicons11/Datos-economicos-diarios/actions/workflows/actualizar.yml/dispatches',
    {
      method: 'post',
      contentType: 'application/json',
      headers: {
        Authorization: 'Bearer ' + token.trim(),
        Accept: 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28'
      },
      payload: JSON.stringify({ref: 'main', inputs: {comprobar_fuente: false}}),
      muteHttpExceptions: true
    });
  const estado = respuesta.getResponseCode();
  if (estado !== 204) {
    // No imprimir cuerpos de respuesta ni credenciales.
    throw new Error('GitHub no aceptó la solicitud: HTTP ' + estado + '. Revisar permisos o vencimiento de TOKEN_GITHUB.');
  }
}

// Prueba manual: solicita una ejecución, pero NO sustituye el pedido de las 20 h.
function probarActualizacionGitHub() {
  solicitarActualizacionGitHub_();
  console.log('GitHub aceptó la solicitud. Revisar Actions hasta que termine; aceptar no significa que el Excel ya se haya guardado.');
}

// Google comprueba cada cinco minutos; solo solicita una vez entre 20 y 21 h.
function revisarActualizacionGitHub() {
  revisarActualizacionGitHubEn_(new Date());
}

function revisarActualizacionGitHubEn_(ahora) {
  const zona = 'America/Argentina/Buenos_Aires';
  if (Utilities.formatDate(ahora, zona, 'HH') !== '20') return;
  const bloqueo = LockService.getScriptLock();
  if (!bloqueo.tryLock(1000)) return;
  try {
    const dia = Utilities.formatDate(ahora, zona, 'yyyy-MM-dd');
    const propiedades = PropertiesService.getScriptProperties();
    if (propiedades.getProperty('ULTIMO_PEDIDO_GITHUB_20H') === dia) return;
    solicitarActualizacionGitHub_();
    propiedades.setProperty('ULTIMO_PEDIDO_GITHUB_20H', dia);
    console.log('Pedido diario de las 20 h aceptado por GitHub para ' + dia + '. Revisar resultado en Actions.');
  } finally {
    bloqueo.releaseLock();
  }
}

function instalarProgramadorGitHub() {
  const token = PropertiesService.getScriptProperties().getProperty('TOKEN_GITHUB');
  if (!token || !token.trim()) throw new Error('Primero guardar TOKEN_GITHUB y ejecutar probarActualizacionGitHub');
  const anteriores = ScriptApp.getProjectTriggers().filter(
    t => t.getHandlerFunction() === 'revisarActualizacionGitHub');
  ScriptApp.newTrigger('revisarActualizacionGitHub').timeBased().everyMinutes(5).create();
  anteriores.forEach(t => ScriptApp.deleteTrigger(t));
  console.log('Programador instalado: pide una ejecución entre las 20:00 y las 21:00 de Argentina, habitualmente cerca de las 20:00. Google puede demorar el disparador.');
}

function desactivarProgramadorGitHub() {
  ScriptApp.getProjectTriggers().filter(t => t.getHandlerFunction() === 'revisarActualizacionGitHub')
    .forEach(t => ScriptApp.deleteTrigger(t));
  console.log('Programador externo desactivado. La actualización de GitHub y el puente de Drive se conservan.');
}
