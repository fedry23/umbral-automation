function hostProof(e,proof,allowedHost,now){
 if(e.state!=="READY"||proof?.key!==e.key||proof.videoSha!==e.videoSha||proof.coverSha!==e.coverSha||proof.videoBytes!==e.video.bytes||proof.coverBytes!==e.cover.bytes||!Number.isFinite(Date.parse(proof.verifiedAt))||Date.parse(proof.verifiedAt)>now||now-Date.parse(proof.verifiedAt)>3600000)throw Error("Missing fresh byte verification");
 for(const u of [proof.videoUrl,proof.coverUrl]){
  const url=new URL(u);
  if(url.protocol!=="https:"||url.host!==allowedHost||url.username||url.password||url.hash||url.search)throw Error("Unapproved hosting");
 }
 if(proof.videoUrl===proof.coverUrl||!proof.videoUrl.endsWith(".mp4")||!/\.(jpg|jpeg)$/.test(proof.coverUrl))throw Error("Invalid hosted media");
 return {...e,hostingVerified:true,videoUrl:proof.videoUrl,coverUrl:proof.coverUrl,hostingVerifiedAt:proof.verifiedAt};
}

async function prepare(store,meta,nowIso){
 const now=Date.parse(nowIso);if(!Number.isFinite(now))throw Error("Invalid clock");
 const snap=await store.read(),rows=snap.value.episodes,e=rows[0];
 if(!e)return "EMPTY";
 const due=Date.parse(e.dueAt);
 // Preparation is allowed during the two hours before due or during recovery, not days ahead.
 if(now<due-7200000)return "NOT_PREPARATION_TIME";
 if(["PUBLISHING","AMBIGUOUS"].includes(e.state))return "BLOCKED_UNCONFIRMED";
 const replace=async patch=>store.cas(snap.version,{...snap.value,episodes:rows.map(x=>x.key===e.key?{...x,...patch}:x)});
 if(e.state==="SCHEDULED"&&Date.parse(e.containerExpiresAt)>now+60000)return "PREPARED";
 if(e.state==="PREPARING"&&e.containerId){
  if(Date.parse(e.containerExpiresAt)<=now){return await replace({state:"READY",containerId:null,containerExpiresAt:null})?"EXPIRED":"CONFLICT";}
  const status=await meta.containerStatus(e);
  if(status==="FINISHED")return await replace({state:"SCHEDULED"})?"PREPARED":"CONFLICT";
  if(status==="ERROR"||status==="EXPIRED")return await replace({state:"READY",containerId:null,containerExpiresAt:null})?"CONTAINER_FAILED":"CONFLICT";
  if(status==="PUBLISHED")return "BLOCKED_UNCONFIRMED";
  return "PROCESSING";
 }
 if(e.state==="PREPARING"){
  // A lost create response cannot publish a Reel, but can consume Meta capacity.
  // Do not create repeatedly; leave a visible state for a safe explicit reset.
  return "PREPARATION_UNCERTAIN";
 }
 if(e.state==="SCHEDULED"){
  return await replace({state:"READY",containerId:null,containerExpiresAt:null})?"EXPIRED":"CONFLICT";
 }
 if(e.state!=="READY"||e.hostingVerified!==true)return "NOT_READY";
 if(!await replace({state:"PREPARING",prepareStartedAt:new Date(now).toISOString()}))return "CONFLICT";
 let id;try{id=await meta.createContainer(e);}catch{return "PREPARATION_UNCERTAIN";}
 if(typeof id!=="string"||!/^\d+$/.test(id))return "PREPARATION_UNCERTAIN";
 const s=await store.read(),current=s.value.episodes.find(x=>x.key===e.key);
 if(!current||current.state!=="PREPARING"||current.containerId)return "CONFLICT";
 // Conservative application expiry (23 hours), not a guarantee from Meta.
 const ok=await store.cas(s.version,{...s.value,episodes:s.value.episodes.map(x=>x.key===e.key?{...x,containerId:id,containerExpiresAt:new Date(now+23*3600000).toISOString()}:x)});
 return ok?"PROCESSING":"CONFLICT";
}
export {hostProof,prepare};
