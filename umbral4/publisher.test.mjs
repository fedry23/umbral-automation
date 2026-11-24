import {tick,civilKey,reserveLevel} from "./publisher.mjs";
async function runTests(tick,civilKey,reserveLevel){
 const ok=(x,m)=>{if(!x)throw Error(m);};
 let count=0;
 const check=async(name,fn)=>{await fn();count++;};
 function fixture(){
  const dueAt="2026-11-24T08:00:00Z", key="2026-11-24/09:00";
  const e={key,dueAt,id:"a",number:22,videoSha:"a".repeat(64),coverSha:"b".repeat(64),qaPassed:true,caption:`Terror [UMBRAL4:${key}]`,state:"READY",containerId:"999",containerExpiresAt:"2026-11-25T02:00:00Z"};
  let value={lastNumber:21,episodes:[e]},v=0,posts=0,remote=null;
  const clone=x=>JSON.parse(JSON.stringify(x));
  const store={read:async()=>({version:v,value:clone(value)}),cas:async(ver,val)=>{if(ver!==v)return false;value=clone(val);v++;return true;}};
  const meta={checkReady:async()=>true,findReceipt:async()=>remote,publishOnce:async()=>{posts++;remote={mediaId:"123",ownerVerified:true,productType:"REELS",caption:e.caption,permalink:"https://www.instagram.com/reel/abc/",publishedAt:"2026-11-24T08:00:03Z"};return "123";}};
  return {store,meta,e,dueAt,get posts(){return posts},get value(){return value}};
 }
 await check("normal",async()=>{const f=fixture();ok(await tick(f.store,f.meta,f.dueAt)==="PUBLISHED","normal");ok(f.posts===1&&f.value.lastNumber===22,"receipt");});
 await check("early",async()=>{const f=fixture();ok(await tick(f.store,f.meta,"2026-11-24T07:59:59Z")==="NOT_DUE"&&f.posts===0,"early");});
 await check("late",async()=>{const f=fixture();ok(await tick(f.store,f.meta,"2026-11-24T11:00:00Z")==="PUBLISHED","late");});
 await check("concurrent",async()=>{const f=fixture();await Promise.all([tick(f.store,f.meta,f.dueAt),tick(f.store,f.meta,f.dueAt)]);ok(f.posts===1,"duplicate");});
 await check("timeout after POST",async()=>{const f=fixture(),post=f.meta.publishOnce;f.meta.publishOnce=async()=>{await post();throw Error("timeout");};ok(await tick(f.store,f.meta,f.dueAt)==="BLOCKED_UNCONFIRMED","ambiguous");ok(await tick(f.store,f.meta,f.dueAt)==="PUBLISHED"&&f.posts===1,"reconcile");});
 for(const err of ["timeout before POST","429","500","expired token"]){await check(err,async()=>{const f=fixture();let n=0;f.meta.publishOnce=async()=>{n++;throw Error(err)};await tick(f.store,f.meta,f.dueAt);await tick(f.store,f.meta,"2026-11-24T08:03:00Z");await tick(f.store,f.meta,"2026-11-24T08:05:00Z");ok(n===1&&f.value.episodes[0].state==="AMBIGUOUS","no blind retry");});}
 await check("expired container",async()=>{const f=fixture();ok(await tick(f.store,f.meta,"2026-11-25T08:00:00Z")==="CONTAINER_NOT_READY"&&f.posts===0,"expired");});
 await check("generator failure",async()=>{const f=fixture();ok(await tick(f.store,f.meta,f.dueAt)==="PUBLISHED","ready independent");});
 await check("integrity",async()=>{const f=fixture();const s=await f.store.read();s.value.episodes[0].videoSha="bad";await f.store.cas(s.version,s.value);ok(await tick(f.store,f.meta,f.dueAt)==="INVALID_EPISODE"&&f.posts===0,"hash");});
 await check("cover invalid",async()=>{const f=fixture();const s=await f.store.read();s.value.episodes[0].coverSha="bad";await f.store.cas(s.version,s.value);ok(await tick(f.store,f.meta,f.dueAt)==="INVALID_EPISODE","cover");});
 await check("storage unavailable",async()=>{const f=fixture();f.meta.checkReady=async()=>false;ok(await tick(f.store,f.meta,f.dueAt)==="CONTAINER_NOT_READY"&&f.posts===0,"storage");});
 await check("receipt false",async()=>{const f=fixture();f.meta.findReceipt=async()=>({mediaId:"123"});ok(await tick(f.store,f.meta,f.dueAt)==="BLOCKED_UNCONFIRMED"&&f.posts===0,"false receipt");});
 await check("restart after intent",async()=>{const f=fixture();const s=await f.store.read();s.value.episodes[0].state="PUBLISHING";s.value.episodes[0].intentAt=f.dueAt;await f.store.cas(s.version,s.value);await tick(f.store,f.meta,"2026-11-24T08:03:00Z");ok(f.posts===0&&f.value.episodes[0].state==="AMBIGUOUS","restart");});
 await check("numbering",async()=>{const f=fixture();const s=await f.store.read();s.value.episodes[0].number=23;await f.store.cas(s.version,s.value);ok(await tick(f.store,f.meta,f.dueAt)==="INVALID_EPISODE","number");});
 await check("DST",async()=>{ok(civilKey("2026-03-29T07:00:00Z")==="2026-03-29/09:00"&&civilKey("2026-10-25T08:00:00Z")==="2026-10-25/09:00","DST");});
 await check("reserve",async()=>{ok([0,2,4,10,14].map(reserveLevel).join(",")==="EMERGENCY,CRITICAL,WARNING,REFILL,OPTIMAL","reserve");});
 await check("ledger CAS failure",async()=>{const f=fixture();f.store.cas=async()=>false;ok(await tick(f.store,f.meta,f.dueAt)==="CONFLICT"&&f.posts===0,"CAS");});
 return count;
}
console.log("Passed",await runTests(tick,civilKey,reserveLevel),"offline scenarios");
