'use strict';
const fs=require('fs'), vm=require('vm'), assert=require('assert'), crypto=require('crypto');
const path=require('path');
const code=fs.readFileSync(path.join(__dirname,'../apps_script/Code.gs'),'utf8');
const html=fs.readFileSync(path.join(__dirname,'../apps_script/Index.html'),'utf8');
assert(html.includes('EINMAL BERNE IMMER BERNE'));
assert(html.includes('tus-berne-logo.svg'));
assert(html.includes('data-mode="locked"'));
assert(html.includes('google.script.run'));
const js=html.split('<script>')[1].split('</script>')[0];
new vm.Script(js, {filename:'Index-embedded.js'});

const schema={
 Wochen:['wochenbeginn','modus','revision','geaendert_am','quell_hash','anzahl_zeilen'],
 Einzelkorrekturen:['wochenbeginn','revision','spiel_id','feld','wert','geaendert_am'],
 Fixierte_Spiele:['wochenbeginn','revision','position','datum','uhrzeit','art','staffel','heim','gast','heimkabine','gastkabine','srkabine','turnier'],
 Protokoll:['zeitpunkt','wochenbeginn','aktion','details','revision']
};
const rows=Object.fromEntries(Object.entries(schema).map(([k,v])=>[k,[v]]));
const source={schema_version:1,generated_at:'2026-11-10T14:20:55+01:00',period:{weeks:[{start:'2026-11-09',end:'2026-11-15'}]},games:[
 {date:'2026-11-14',time:'09:30',kind:'Meisterschaft',league:'Bezirksliga',home:'tus BERNE 1.C',away:'GW Eimsbüttel 1.C',home_cabin:'1',guest_cabin:'3',sr_cabin:'SR1',festival:false},
 {date:'2026-11-15',time:'09:00',kind:'Meisterschaft',league:'Bezirksliga',home:'tus BERNE 2.C',away:'Gast 2.C',home_cabin:'2',guest_cabin:'4',sr_cabin:'SR2',festival:false}
]};
function sheet(name){
  return {getLastRow:()=>rows[name].length,
    getRange:(r,c,n=1,w=1)=>({
      getDisplayValues:()=>Array.from({length:n},(_,i)=>Array.from({length:w},(_,j)=>String(rows[name][r-1+i]?.[c-1+j]??''))),
      setValues:xs=>{xs.forEach((v,i)=>{rows[name][r-1+i]=v;});}
    })};
}
const context={
  SpreadsheetApp:{openById:()=>({getSheetByName:sheet})},
  LockService:{getScriptLock:()=>({waitLock:()=>{},releaseLock:()=>{}})},
  UrlFetchApp:{fetch:u=>({getResponseCode:()=>200,getContentText:()=>JSON.stringify(u.includes('kabinen_auto_data')?source:{...source,manual_weeks:{'2026-11-09':{revision:0}}})})},
  Utilities:{Charset:{UTF_8:'UTF-8'},DigestAlgorithm:{SHA_256:'SHA_256'},
    computeDigest:(_,v)=>[...crypto.createHash('sha256').update(v,'utf8').digest()].map(n=>n>127?n-256:n),
    formatDate:(d,tz,pattern)=>{if(pattern==='yyyy-MM-dd'){return tz==='GMT'?d.toISOString().slice(0,10):'2026-11-11';}
      if(pattern==="yyyy-MM-dd'T'HH:mm:ssXXX")return '2026-11-11T10:30:00+01:00';
      return d.toISOString().slice(0,10);}},
  console,HtmlService:{createHtmlOutputFromFile:()=>({setTitle(){return this},addMetaTag(){return this}})},
};
vm.createContext(context);vm.runInContext(code,context);
let state=context.apiLoad();assert.strictEqual(state.revision,0);assert.strictEqual(state.games.length,2);assert.strictEqual(state.published.state,'published');
const id=state.gameIds[0];
let saved=context.apiSave({week:state.week,revision:state.revision,sourceHash:state.sourceHash,mode:'partial',changes:{[id]:{guest_cabin:'4'}}});
assert.strictEqual(saved.revision,1);state=context.apiLoad();assert.strictEqual(state.mode,'partial');
assert.strictEqual(state.effectiveGames[0].guest_cabin,'4');assert.strictEqual(state.effectiveGames[0].home_cabin,'1');
assert.strictEqual(rows.Wochen.length,2);assert.strictEqual(rows.Wochen[1][5],'1');
assert.throws(()=>context.apiSave({week:state.week,revision:0,sourceHash:state.sourceHash,mode:'automatic'}),/inzwischen geändert/);
saved=context.apiSave({week:state.week,revision:1,sourceHash:state.sourceHash,mode:'locked',games:[source.games[1]]});
assert.strictEqual(saved.revision,2);state=context.apiLoad();assert.strictEqual(state.mode,'locked');assert.strictEqual(state.effectiveGames.length,1);
saved=context.apiSave({week:state.week,revision:2,sourceHash:state.sourceHash,mode:'locked',games:[]});
state=context.apiLoad();assert.strictEqual(state.effectiveGames.length,0);assert.strictEqual(state.revision,3);
saved=context.apiSave({week:state.week,revision:3,sourceHash:state.sourceHash,mode:'automatic'});
state=context.apiLoad();assert.strictEqual(state.mode,'automatic');assert.strictEqual(state.effectiveGames.length,2);
assert.strictEqual(rows.Protokoll.length,5);
assert.throws(()=>context.apiSave({week:'2026-11-09',revision:4,sourceHash:'wrong',mode:'automatic'}),/automatische Belegung/);
assert.throws(()=>context.apiSave({week:'2026-11-09',revision:4,sourceHash:state.sourceHash,mode:'partial',changes:{[id]:{guest_cabin:'SR1'}}}),/nicht erlaubt/);
console.log('Apps Script: Google-Back-end + Wochenmodus + Revisionsschutz + Vollsperre + Rücksetzung OK');