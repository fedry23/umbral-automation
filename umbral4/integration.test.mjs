import assert from "node:assert/strict";
import {readdirSync,readFileSync} from "node:fs";
import {civilDue,nextKey,calendar,importHistory,archiveStore,manifestFor} from "./ledger.mjs";
import {hostProof,prepare} from "./prepare.mjs";
import {tick} from "./publisher.mjs";
import {metaAdapter} from "./adapters.mjs";

function memory(){
 let rows=new Map(),tail=Promise.resolve();
 return {get:async k=>structuredClone(rows.get(k)),transaction(fn){
  const run=tail.then(async()=>{const copy=structuredClone(rows);
   const ret=await fn({get:async k=>structuredClone(copy.get(k)),put:async(k,v)=>copy.set(k,structuredClone(v))});
   rows=copy;return ret;});
  tail=run.catch(()=>{});return run;
 }};
}
const history=readdirSync("docs/published").filter(n=>n.endsWith(".json")).map(name=>({name,row:JSON.parse(readFileSync("docs/published/"+name,"utf8"))}));
const pending=readdirSync("docs/pending").filter(n=>n.endsWith(".json"));
const first="2026-11-24/09:00"; // fixed base snapshot; not deployment authorization.
const imported=importHistory(history,pending,first);
assert.equal(imported.ledger.lastNumber,21);
assert.equal(imported.ledger.episodes.length,14);
assert.equal(imported.records.length,17);
assert.throws(()=>importHistory(history,[...pending,"2026-11-24_09.json"],first),/Unresolved/);
assert.throws(()=>importHistory(history, pending,"2026-11-24/21:00"),/contiguous/);
assert.throws(()=>importHistory([...history,history[0]],pending,first),/Invalid historical/);
assert.equal(civilDue("2026-03-29/09:00"),"2026-03-29T07:00:00.000Z");
assert.equal(civilDue("2026-10-25/21:00"),"2026-10-25T20:00:00.000Z");
assert.equal(nextKey("2028-02-28/21:00"),"2028-02-29/09:00");
assert.throws(()=>civilDue("2026-02-30/09:00"));
const storage=memory();let store=archiveStore(storage);
await store.initialize(history,pending,first);
await assert.rejects(()=>store.initialize(history,pending,first),/Already/);
const sha="a".repeat(64),cover="b".repeat(64);
function manifest(e){return {key:e.key,id:e.id,number:e.number,qaPassed:true,storyboard:Array(6).fill("scene"),caption:"EPISODIO "+e.number+" [UMBRAL4:"+e.key+"]",video:{sha256:sha,bytes:10,privateKey:"umbral4/video"},cover:{sha256:cover,bytes:5,privateKey:"umbral4/cover"}};}
function proof(e,now){return {key:e.key,videoSha:sha,coverSha:cover,videoBytes:10,coverBytes:5,videoUrl:"https://media.example/reel.mp4",coverUrl:"https://media.example/cover.jpg",verifiedAt:now};}
async function ready(){
 const s=await store.read(),e=s.value.episodes[0],now=new Date(Date.parse(e.dueAt)-3600000).toISOString();
 const m=manifestFor(e,manifest(e));
 assert.throws(()=>hostProof(m,{...proof(m,now),videoSha:cover},"media.example",Date.parse(now)));
 const hosted=hostProof(m,proof(m,now),"media.example",Date.parse(now));
 assert.equal(await store.cas(s.version,{...s.value,episodes:[hosted,...s.value.episodes.slice(1)]}),true);
 return {e:hosted,now};
}
let creates=0,posts=0,remote=null;
const meta={createContainer:async()=>String(++creates),containerStatus:async()=>"FINISHED",checkReady:async()=>true,findReceipt:async e=>remote?.caption===e.caption?remote:null,publishOnce:async e=>{posts++;remote={mediaId:String(700000+posts),ownerVerified:true,productType:"REELS",caption:e.caption,permalink:"https://www.instagram.com/reel/test"+posts+"/",publishedAt:e.dueAt};return remote.mediaId;}};
let {e,now}=await ready();
assert.equal(await prepare(store,meta,new Date(Date.parse(e.dueAt)-10800000).toISOString()),"NOT_PREPARATION_TIME");
await Promise.all([prepare(store,meta,now),prepare(store,meta,now)]);
assert.equal(creates,1);
assert.equal(await prepare(store,meta,now),"PREPARED");
assert.equal(await tick(store,meta,now),"NOT_DUE");
await Promise.all([tick(store,meta,e.dueAt),tick(store,meta,e.dueAt)]);
assert.equal(posts,1);
assert.equal((await store.archived(e.key)).receipt.mediaId,"700001");
assert.equal((await store.read()).value.lastNumber,22);
store=archiveStore(storage);
assert.equal((await store.read()).value.episodes.length,14);
assert.equal((await store.read()).value.nextKey,"2026-11-24/21:00");
// 28 distinct slots, including restart, archival and automatic calendar extension.
for(let i=1;i<28;i++){
 ({e,now}=await ready());
 assert.equal(await prepare(store,meta,now),"PROCESSING");
 assert.equal(await prepare(store,meta,now),"PREPARED");
 assert.equal(await tick(store,meta,e.dueAt),"PUBLISHED");
 assert.equal((await store.archived(e.key)).number,22+i);
 assert.equal((await store.read()).value.episodes.length,14);
}
assert.equal(posts,28);assert.equal((await store.read()).value.lastNumber,49);
({e,now}=await ready());
await prepare(store,{...meta,createContainer:async()=>{throw Error("timeout");}},now);
assert.equal(await prepare(store,meta,now),"PREPARATION_UNCERTAIN");
assert.equal(creates,28);
assert.equal(await tick(store,meta,e.dueAt),"BLOCKED_NOT_READY");
const s=await store.read();
await assert.rejects(()=>store.cas(s.version,{...s.value,episodes:s.value.episodes.slice(1)}),/reorder/);
await assert.rejects(()=>store.cas(s.version,{...s.value,lastNumber:99}),/Number/);
const calls=[];
const transport=metaAdapter({token:"fake",account:"123",fetcher:async(url,opt)=>{calls.push({url,opt});return new Response(JSON.stringify({id:"321"}));}});
assert.equal(await transport.createContainer({hostingVerified:true,videoUrl:"https://example.com/reel.mp4",coverUrl:"https://example.com/cover.jpg",caption:"test"}),"321");
assert.equal(await transport.publishOnce({containerId:"321"}),"321");
assert.equal(calls.length,2);
assert.ok(calls.every(c=>!c.url.includes("fake")&&c.opt.method==="POST"&&c.opt.redirect==="error"));
console.log("History import, calendar, preparation concurrency, 28 consecutive simulated receipts, archival, restart, failure guards and fake Meta transport passed.");
