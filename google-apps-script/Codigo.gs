// Puente privado entre GitHub Actions y el Excel de tu carpeta de Drive.
const CARPETA = '1o4O5rZIrIEjiwMHkRw1iYDTPHb2kBxmk';
const ARCHIVO = 'Tipo_de_Cambio_BNA.xlsx';
const MIME_EXCEL = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';

// Ejecutar una sola vez desde el editor. No imprime la clave privada.
function prepararConexion() {
  DriveApp.getFolderById(CARPETA).getName();
  const propiedades = PropertiesService.getScriptProperties();
  if (!propiedades.getProperty('CLAVE_GITHUB')) {
    propiedades.setProperty('CLAVE_GITHUB', Utilities.getUuid() + Utilities.getUuid());
  }
  console.log('Conexión preparada. La clave está en Configuración del proyecto > Propiedades de la secuencia de comandos. No la compartas en el chat.');
}

function respuesta_(objeto) {
  return ContentService.createTextOutput(JSON.stringify(objeto))
    .setMimeType(ContentService.MimeType.JSON);
}

function buscarArchivo_() {
  const archivos = DriveApp.getFolderById(CARPETA).getFilesByName(ARCHIVO);
  if (!archivos.hasNext()) return null;
  const archivo = archivos.next();
  if (archivos.hasNext()) throw new Error('Hay varios Excel con el mismo nombre en la carpeta');
  if (archivo.getMimeType() !== MIME_EXCEL) throw new Error('El archivo debe conservar formato Excel, sin convertirlo a Google Sheets');
  return archivo;
}

function comprobarFirma_(solicitud, clave) {
  if (!clave || typeof solicitud.payload !== 'string' || solicitud.payload.length > 15000000 ||
      typeof solicitud.signature !== 'string' || !/^[0-9a-f]{64}$/.test(solicitud.signature)) {
    throw new Error('Solicitud no autorizada');
  }
  const esperada = Utilities.computeHmacSha256Signature(solicitud.payload, clave, Utilities.Charset.UTF_8)
    .map(b => ('0' + ((b + 256) % 256).toString(16)).slice(-2)).join('');
  let diferencia = 0;
  for (let i = 0; i < 64; i++) diferencia |= esperada.charCodeAt(i) ^ solicitud.signature.charCodeAt(i);
  if (diferencia !== 0) throw new Error('Solicitud no autorizada');
  const datos = JSON.parse(solicitud.payload);
  if (!Number.isFinite(datos.timestamp) || Math.abs(Date.now() / 1000 - datos.timestamp) > 300 ||
      typeof datos.nonce !== 'string' || !/^[a-f0-9]{32}$/.test(datos.nonce)) {
    throw new Error('Solicitud vencida o inválida');
  }
  return datos;
}

function doPost(e) {
  const bloqueo = LockService.getScriptLock();
  let adquirido = false;
  try {
    const solicitud = JSON.parse(e.postData.contents);
    const datos = comprobarFirma_(solicitud, PropertiesService.getScriptProperties().getProperty('CLAVE_GITHUB'));
    bloqueo.waitLock(30000);
    adquirido = true;
    const cache = CacheService.getScriptCache();
    if (cache.get(datos.nonce)) throw new Error('Solicitud repetida');
    cache.put(datos.nonce, 'usada', 600);
    const archivo = buscarArchivo_();
    const version = archivo ? String(archivo.getLastUpdated().getTime()) : null;
    if (datos.action === 'read') {
      return respuesta_({ok: true, version: version,
        content: archivo ? Utilities.base64Encode(archivo.getBlob().getBytes()) : null});
    }
    if (datos.action !== 'write' || typeof datos.content !== 'string') throw new Error('Operación inválida');
    if (datos.version !== version) throw new Error('El Excel cambió durante la consulta; se conserva la versión de Drive');
    const bytes = Utilities.base64Decode(datos.content);
    if (bytes.length < 4 || bytes.length > 10000000 || bytes[0] !== 80 || bytes[1] !== 75) {
      throw new Error('Archivo Excel inválido o demasiado grande');
    }
    const blob = Utilities.newBlob(bytes, MIME_EXCEL, ARCHIVO);
    let guardado;
    if (archivo) {
      // Actualiza el binario sin borrar el archivo: se conserva su ID y enlace.
      const resultado = UrlFetchApp.fetch(
        'https://www.googleapis.com/upload/drive/v3/files/' + encodeURIComponent(archivo.getId()) + '?uploadType=media',
        {method: 'patch', contentType: MIME_EXCEL, payload: blob.getBytes(),
         headers: {Authorization: 'Bearer ' + ScriptApp.getOAuthToken()}, muteHttpExceptions: true});
      if (resultado.getResponseCode() < 200 || resultado.getResponseCode() >= 300) {
        throw new Error('Google Drive rechazó el guardado: HTTP ' + resultado.getResponseCode());
      }
      guardado = archivo;
    } else {
      guardado = DriveApp.getFolderById(CARPETA).createFile(blob);
    }
    return respuesta_({ok: true, fileId: guardado.getId()});
  } catch (error) {
    return respuesta_({ok: false, error: String(error.message || 'Error de la conexión')});
  } finally {
    if (adquirido) bloqueo.releaseLock();
  }
}

// Comprobación manual: no envía solicitudes ni modifica archivos.
function revisarPermisoActualizacion() {
  ScriptApp.requireScopes(ScriptApp.AuthMode.FULL, ['https://www.googleapis.com/auth/script.external_request']);
  UrlFetchApp.getRequest('https://www.googleapis.com/drive/v3/files');
  console.log('Permiso de actualización disponible. No se enviaron solicitudes ni se modificaron archivos.');
}

function mostrarAutorizacion() {
  console.log(ScriptApp.getAuthorizationInfo(ScriptApp.AuthMode.FULL).getAuthorizationUrl());
}

