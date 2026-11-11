/**
 * tus BERNE – Mobile Kabinenverwaltung über private Google-Tabelle.
 * Web-App als Eigentümer ausführen; Zugriff NUR ICH.
 * WICHTIG: Die Web-App ist eine Verwaltungsoberfläche, kein öffentlicher JSON-Endpunkt.
 */
const CAB_SHEET_ID = '1U8PoGl6_vGeLxFBryIL0JVBZPw9RAtFnHbQeoov_spc';
const CAB_SOURCE_URL = 'https://kuhfi.github.io/tusberne-infoboard/data/kabinen_auto_data.json';
const CAB_PUBLISHED_URL = 'https://kuhfi.github.io/tusberne-infoboard/data/kabinen_live_data.json';
const CAB_TZ = 'Europe/Berlin';
const CAB_FIELDS = ['date','time','kind','league','home','away','home_cabin','guest_cabin','sr_cabin','festival'];
const CAB_ID_FIELDS = ['date','time','kind','league','home','away'];
const CAB_ALLOWED = {home_cabin:['','1','2','3','4'],guest_cabin:['','1','2','3','4'],sr_cabin:['','SR1','SR2']};
const CAB_WEEK_HEADERS = ['wochenbeginn','modus','revision','geaendert_am','quell_hash','anzahl_zeilen'];
const CAB_PARTIAL_HEADERS = ['wochenbeginn','revision','spiel_id','feld','wert','geaendert_am'];
const CAB_LOCKED_HEADERS = ['wochenbeginn','revision','position','datum','uhrzeit','art','staffel','heim','gast','heimkabine','gastkabine','srkabine','turnier'];
const CAB_LOG_HEADERS = ['zeitpunkt','wochenbeginn','aktion','details','revision'];

function doGet() {
  return HtmlService.createHtmlOutputFromFile('Index')
    .setTitle('tus BERNE – Kabinenverwaltung')
    .addMetaTag('viewport','width=device-width, initial-scale=1');
}

function sheet_(name, header) {
  const s = SpreadsheetApp.openById(CAB_SHEET_ID).getSheetByName(name);
  if (!s) throw Error('Fehlendes Tabellenblatt: ' + name);
  const got = s.getRange(1,1,1,header.length).getDisplayValues()[0];
  if (JSON.stringify(got)!==JSON.stringify(header)) {
    throw Error('Die Spalten von '+name+' wurden geändert. Bitte nicht direkt in der Google-Tabelle bearbeiten.');
  }
  return s;
}
function rows_(name, header) {
  const s = sheet_(name, header), count = s.getLastRow();
  return count > 1 ? s.getRange(2,1,count-1,header.length).getDisplayValues() : [];
}
function appendRows_(sheet, data) {
  if (data.length) sheet.getRange(sheet.getLastRow()+1,1,data.length,data[0].length).setValues(data);
}
function isoNow_() {return Utilities.formatDate(new Date(),CAB_TZ,"yyyy-MM-dd'T'HH:mm:ssXXX");}
function monday_() {
  const date=Utilities.formatDate(new Date(),CAB_TZ,'yyyy-MM-dd');
  const d=new Date(date+'T12:00:00Z');
  const offset=(d.getUTCDay()+6)%7;
  d.setUTCDate(d.getUTCDate()-offset);
  return Utilities.formatDate(d,'GMT','yyyy-MM-dd');
}
function sha_(value) {
  const dig=Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256,value,Utilities.Charset.UTF_8);
  return dig.map(b=>('0'+((b+256)%256).toString(16)).slice(-2)).join('');
}
function gameId_(g) {return sha_(JSON.stringify(CAB_ID_FIELDS.map(f=>g[f]||''))).slice(0,20);}
function normalizeGame_(game) {
  const g={};
  CAB_FIELDS.forEach(field=>{g[field]=field==='festival'?game[field]===true:String(game[field]??'').trim();});
  return g;
}
function getJson_(url) {
  const resp=UrlFetchApp.fetch(url,{muteHttpExceptions:true,followRedirects:true,headers:{'Cache-Control':'no-cache'}});
  if(resp.getResponseCode()!==200)throw Error('Datenquelle antwortet mit HTTP '+resp.getResponseCode());
  const obj=JSON.parse(resp.getContentText('UTF-8'));
  if(obj.schema_version!==1 || !Array.isArray(obj.games) || !Array.isArray(obj.period?.weeks))throw Error('Ungültiger Kabinendatensatz');
  return obj;
}
function source_() {
  const raw=getJson_(CAB_SOURCE_URL);
  const week=monday_(), period=raw.period.weeks.find(w=>w.start===week);
  if(!period)return {week:week,period:null,games:[],hash:'',generated_at:raw.generated_at||''};
  const games=raw.games.filter(g=>g.date>=period.start&&g.date<=period.end).map(normalizeGame_);
  return {week:week,period:period,games:games,hash:sha_(JSON.stringify(games)),generated_at:raw.generated_at||''};
}
function latest_(week) {
  let winner={week:week,mode:'automatic',revision:0,updated_at:'',source_hash:''};
  rows_('Wochen',CAB_WEEK_HEADERS).forEach(r=>{
    if(r[0]===week && Number.isSafeInteger(Number(r[2])) && Number(r[2])>winner.revision) {
      winner={week:week,mode:r[1],revision:Number(r[2]),updated_at:r[3],source_hash:r[4],row_count:Number(r[5])};
    }
  });
  if(!['automatic','partial','locked'].includes(winner.mode))throw Error('Ungültiger Wochenmodus in Google Sheets');
  return winner;
}
function record_(latest) {
  const changes={}, games=[];
  if(latest.mode==='partial'){
    const matching=rows_('Einzelkorrekturen',CAB_PARTIAL_HEADERS).filter(r=>r[0]===latest.week && Number(r[1])===latest.revision);
    if(matching.length!==latest.row_count)throw Error('Unvollständige Einzelkorrekturen: Google-Tabelle prüfen');
    matching.forEach(r=>{
      if(!(r[2] in changes))changes[r[2]]={};
      changes[r[2]][r[3]]=r[4];
    });
  }
  if(latest.mode==='locked'){
    const matching=rows_('Fixierte_Spiele',CAB_LOCKED_HEADERS).filter(r=>r[0]===latest.week&&Number(r[1])===latest.revision);
    if(matching.length!==latest.row_count)throw Error('Unvollständiger Wochenplan: Google-Tabelle prüfen');
    matching.sort((a,b)=>Number(a[2])-Number(b[2])).forEach(r=>games.push(normalizeGame_({
      date:r[3],time:r[4],kind:r[5],league:r[6],home:r[7],away:r[8],
      home_cabin:r[9],guest_cabin:r[10],sr_cabin:r[11],festival:r[12]==='TRUE'||r[12]==='true'
    })));
  }
  return {changes:changes,games:games};
}
function safeChanges_(raw, games) {
  if(!raw||typeof raw!=='object'||Array.isArray(raw)||Object.keys(raw).length>200)throw Error('Ungültige Einzelkorrekturen');
  const keys=games.map(gameId_), result={};
  Object.keys(raw).forEach(key=>{
    if(keys.filter(k=>k===key).length!==1 || !/^[0-9a-f]{20}$/.test(key))throw Error('Spielzuordnung ist nicht mehr eindeutig. Bitte neu laden.');
    const fields=raw[key];
    if(!fields||typeof fields!=='object'||Array.isArray(fields)||!Object.keys(fields).length)throw Error('Ungültige Kabinenkorrektur');
    Object.keys(fields).forEach(field=>{
      if(!CAB_ALLOWED[field]||typeof fields[field]!=='string'||!CAB_ALLOWED[field].includes(fields[field]))throw Error('Kabinenwert nicht erlaubt: '+field);
    });
    result[key]=fields;
  });
  return result;
}
function safeGame_(raw, start, end) {
  if(!raw || typeof raw!=='object'||Array.isArray(raw)||Object.keys(raw).some(k=>!CAB_FIELDS.includes(k)))throw Error('Ungültige Spielfelder');
  const g=normalizeGame_(raw);
  if(!/^\d{4}-\d{2}-\d{2}$/.test(g.date) || g.date<start || g.date>end)throw Error('Spieldatum liegt außerhalb der laufenden Woche');
  if(!/^(?:[01]?\d|2[0-3]):[0-5]\d$/.test(g.time))throw Error('Ungültige Anstoßzeit');
  ['home','away','kind','league'].forEach(f=>{
    if(g[f].length>160 || /[\x00-\x1F]/.test(g[f]))throw Error('Ungültiger Spieltext');
  });
  if(!g.home || !g.away)throw Error('Heim- und Gastmannschaft sind erforderlich');
  Object.keys(CAB_ALLOWED).forEach(f=>{if(!CAB_ALLOWED[f].includes(g[f]))throw Error('Ungültige Kabine');});
  if(typeof raw.festival!=='boolean')throw Error('Turnier muss ja/nein sein');
  return g;
}
function effective_(games,mode,record) {
  if(mode==='locked') return record.games.map(g=>Object.assign({manual_override:true},g));
  if(mode!=='partial')return games;
  const keys=games.map(gameId_);
  return games.map((game,i)=>{
    if(keys.filter(k=>k===keys[i]).length!==1 || !record.changes[keys[i]])return game;
    return Object.assign({},game,record.changes[keys[i]],{manual_override:true});
  });
}
function publishedState_(week,revision) {
  try {
    const raw=getJson_(CAB_PUBLISHED_URL), info=raw.manual_weeks?.[week];
    if(!info)return {state:revision===0?'published':'pending',revision:0};
    const publishedRev=Number(info.revision||0);
    return {state:publishedRev>=revision?'published':'pending',revision:publishedRev};
  } catch(e) {return {state:'unavailable',revision:0};}
}

/** API for the HTML client, not an unauthenticated public endpoint. */
function apiLoad() {
  const source=source_(), latest=latest_(source.week), record=record_(latest);
  return {week:source.week, period:source.period, editable:Boolean(source.period),
    sourceGeneratedAt:source.generated_at, sourceHash:source.hash, revision:latest.revision,
    gameIds:source.games.map(gameId_),
    mode:latest.mode, updatedAt:latest.updated_at, games:source.games,
    changes:record.changes, lockedGames:record.games,
    effectiveGames:effective_(source.games,latest.mode,record),
    published:publishedState_(source.week,latest.revision)};
}

/** Private server action. Lock guards concurrent editors. Commit metadata LAST. */
function apiSave(request) {
  if(!request || typeof request!=='object')throw Error('Ungültige Anfrage');
  const lock=LockService.getScriptLock();
  lock.waitLock(15000);
  try {
    const source=source_();
    if(!source.period)throw Error('Für die laufende Woche sind keine gültigen Quelldaten verfügbar');
    const latest=latest_(source.week);
    if(request.week!==source.week)throw Error('Kalenderwoche geändert. Bitte neu laden.');
    if(!Number.isInteger(request.revision)||request.revision!==latest.revision)throw Error('Der Plan wurde inzwischen geändert. Bitte neu laden.');
    if(request.sourceHash!==source.hash)throw Error('Die automatische Belegung hat sich geändert. Bitte neu laden.');
    if(!['automatic','partial','locked'].includes(request.mode))throw Error('Ungültiger Modus');
    const now=isoNow_(), rev=latest.revision+1;
    let count=0;
    if(request.mode==='partial'){
      const changes=safeChanges_(request.changes,source.games);
      const data=[];
      Object.keys(changes).sort().forEach(key=>Object.keys(changes[key]).sort().forEach(field=>{
        data.push([source.week,String(rev),key,field,changes[key][field],now]);
      }));
      if(!data.length)request.mode='automatic';
      else {appendRows_(sheet_('Einzelkorrekturen',CAB_PARTIAL_HEADERS),data);count=data.length;}
    }
    if(request.mode==='locked'){
      if(!Array.isArray(request.games)||request.games.length>200)throw Error('Zu viele Spiele');
      const games=request.games.map(g=>safeGame_(g,source.period.start,source.period.end));
      const rows=games.map((g,i)=>[source.week,String(rev),String(i+1),g.date,g.time,g.kind,g.league,g.home,g.away,g.home_cabin,g.guest_cabin,g.sr_cabin,String(g.festival)]);
      appendRows_(sheet_('Fixierte_Spiele',CAB_LOCKED_HEADERS),rows);count=rows.length;
    }
    appendRows_(sheet_('Wochen',CAB_WEEK_HEADERS),[[source.week,request.mode,String(rev),now,source.hash,String(count)]]);
    try {appendRows_(sheet_('Protokoll',CAB_LOG_HEADERS),[[now,source.week,request.mode,'Über Web-App gespeichert',String(rev)]]);}catch(logError){console.warn('Protokoll konnte nicht geschrieben werden');}
    return {saved:true,revision:rev,mode:request.mode,updatedAt:now,published:{state:'pending'}};
  } finally {lock.releaseLock();}
}