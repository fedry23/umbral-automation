// Isolated Cloudflare probe. No network to Meta, no Instagram credentials, no public ingress.
import {archiveStore,manifestFor} from "./ledger.mjs";
import {tick} from "./publisher.mjs";
const first="2026-11-24/09:00";
const previous={name:"2026-11-23.json",row:{date:"2026-11-23",slot:"21",episode_number:1,instagram_media_id:"101",published_at:"2026-11-23T20:00:00Z",verification:"published_media_read_back",permalink:"https://www.instagram.com/reel/probe/"}};
function ensure(x){if(!x)throw Error("Probe assertion failed");}
export class Probe{
 constructor(state){this.storage=state.storage;}
 async fetch(req){
  const p=new URL(req.url).pathname;
  if(p==="/evidence"&&req.method==="POST"){
   await this.storage.put("proof","two independent cron events plus verified transaction and receipt");
   return new Response("ok");
  }
  if(p!=="/step"||req.method!=="POST")return new Response(null,{status:404});
  const scheduled=Number(await req.text());
  if(!Number.isSafeInteger(scheduled)||scheduled<=0)throw Error("Invalid schedule");
  const store=archiveStore(this.storage);
  let s=await this.storage.get("ledger4");
  if(!s){
   await store.initialize([previous],[],first);
   s=await store.read();
   const e=s.value.episodes[0],sha="a".repeat(64);
   const ready=manifestFor(e,{key:e.key,id:e.id,number:e.number,qaPassed:true,storyboard:Array(6).fill("Synthetic scene"),caption:"EPISODIO "+e.number+" [UMBRAL4:"+e.key+"]",video:{sha256:sha,bytes:1,privateKey:"umbral4/test.mp4"},cover:{sha256:sha,bytes:1,privateKey:"umbral4/test.jpg"}});
   const next={...ready,containerId:"999",containerExpiresAt:"2026-11-25T00:00:00Z"};
   ensure(await store.cas(s.version,{...s.value,episodes:[next,...s.value.episodes.slice(1)]}));
   ensure(!await store.cas(s.version,s.value));
   const receipt={mediaId:"102",ownerVerified:true,productType:"REELS",caption:next.caption,permalink:"https://www.instagram.com/reel/probe2/",publishedAt:next.dueAt};
   let posted=0,remote=false;
   const fake={checkReady:async()=>true,findReceipt:async()=>remote?receipt:null,publishOnce:async()=>{posted++;remote=true;return "102";}};
   ensure(await tick(store,fake,next.dueAt)==="PUBLISHED");
   ensure(posted===1);
  }
  const archived=await store.archived(first);
  ensure(archived?.receipt?.mediaId==="102");
  const current=await store.read();
  ensure(current.value.lastNumber===2&&current.value.episodes.length===14&&current.value.nextKey==="2026-11-24/21:00");
  const marker=await this.storage.transaction(async tx=>{
   const old=await tx.get("cron-proof");
   if(!old){await tx.put("cron-proof",{first:scheduled});return false;}
   if(scheduled<=old.first)return false;
   await tx.put("cron-proof",{first:old.first,second:scheduled});return true;
  });
  return new Response(marker?"verified":"first");
 }
}
export default {
 fetch(){return new Response(null,{status:404});},
 async scheduled(event,env){
  if(!Number.isFinite(Date.parse(env.PROBE_UNTIL))||Date.now()>Date.parse(env.PROBE_UNTIL))return;
  const probe=env.PROBE.get(env.PROBE.idFromName("transaction"));
  const result=await probe.fetch("https://internal/step",{method:"POST",body:String(event.scheduledTime)});
  if(!result.ok)throw Error("Probe failed");
  if(await result.text()==="verified"){
   const evidence=env.PROBE.get(env.PROBE.idFromName("independent-cron-proof"));
   if(!(await evidence.fetch("https://internal/evidence",{method:"POST"})).ok)throw Error("Evidence write failed");
  }
 }
};
