const fs = require('node:fs');
const vm = require('node:vm');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const key = 'x'.repeat(64);
const mime = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
let name = 'Tipo_de_Cambio_BNA.xlsx', bytes = [80,75,1,2], uploads = 0, duplicate = false;
const file = {getName:()=>name, setName:n=>{name=n;}, getId:()=>'id-existente',
  getLastUpdated:()=>new Date(1000), getMimeType:()=>mime, getBlob:()=>({getBytes:()=>bytes})};
const box = {
  PropertiesService:{getScriptProperties:()=>({getProperty:()=>key})},
  Utilities:{Charset:{UTF_8:'utf8'},
    computeHmacSha256Signature:(p,k)=>Array.from(crypto.createHmac('sha256',k).update(p).digest()),
    base64Encode:b=>Buffer.from(b).toString('base64'),base64Decode:s=>Array.from(Buffer.from(s,'base64')),
    newBlob:b=>({getBytes:()=>b})},
  DriveApp:{getFolderById:()=>({getFilesByName:n=>{let remaining=(n===name || duplicate)?1:0;
    return {hasNext:()=>remaining>0,next:()=>{remaining--;return file;}};}})},
  LockService:{getScriptLock:()=>({waitLock:()=>{},releaseLock:()=>{}})},
  CacheService:{getScriptCache:()=>({get:()=>null,put:()=>{}})},
  ScriptApp:{getOAuthToken:()=>'token-prueba'},
  UrlFetchApp:{fetch:(url,opts)=>{assert.match(url,/uploadType=media$/); assert.equal(opts.method,'patch');
    uploads++;bytes=opts.payload;return {getResponseCode:()=>200};}},
  ContentService:{MimeType:{JSON:'json'},createTextOutput:text=>({text,setMimeType(){return this;}})}
};
vm.createContext(box);vm.runInContext(fs.readFileSync(__dirname+'/Codigo.gs','utf8'),box);
function call(action,extra={}) {
 const payload=JSON.stringify({action,timestamp:Date.now()/1000,nonce:crypto.randomBytes(16).toString('hex'),...extra});
 const signature=crypto.createHmac('sha256',key).update(payload).digest('hex');
 return JSON.parse(box.doPost({postData:{contents:JSON.stringify({payload,signature})}}).text);
}
assert.equal(call('read').fileName,'Tipo_de_Cambio_BNA.xlsx');
assert.equal(call('write',{version:'incorrecta',content:'UEsBAg=='}).ok,false);
assert.equal(uploads,0);assert.equal(name,'Tipo_de_Cambio_BNA.xlsx');
const result=call('write',{version:'1000',content:'UEsDBA=='});
assert.equal(result.ok,true);assert.equal(result.fileId,'id-existente');
assert.equal(result.fileName,'Datos Financieros.xlsx');assert.equal(uploads,1);
assert.equal(call('read').fileName,'Datos Financieros.xlsx');
assert.equal(call('read').content,'UEsDBA==');
duplicate=true;
assert.equal(call('read').ok,false);
console.log('Puente: migración de nombre conserva ID, lectura verifica contenido, cambio concurrente y nombres duplicados bloqueados.');
