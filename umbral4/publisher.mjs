function civilKey(iso) {
  const d=new Date(iso);
  if(!Number.isFinite(d.getTime())) throw Error("Invalid timestamp");
  const p=Object.fromEntries(new Intl.DateTimeFormat("en-GB",{timeZone:"Europe/Madrid",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hourCycle:"h23"}).formatToParts(d).map(x=>[x.type,x.value]));
  return `${p.year}-${p.month}-${p.day}/${p.hour}:${p.minute}`;
}

function validEpisode(e) {
  return !!e && /^\d{4}-\d{2}-\d{2}\/(09|21):00$/.test(e.key) && civilKey(e.dueAt)===e.key &&
    typeof e.id==="string" && e.id.length>0 && Number.isSafeInteger(e.number) && e.number>0 &&
    /^[a-f0-9]{64}$/.test(e.videoSha) && /^[a-f0-9]{64}$/.test(e.coverSha) &&
    e.qaPassed===true && typeof e.caption==="string" && e.caption.includes(`[UMBRAL4:${e.key}]`);
}

function validReceipt(e,r,expectedId) {
  return !!r && /^\d+$/.test(r.mediaId) && (!expectedId||r.mediaId===expectedId) &&
    r.ownerVerified===true && r.productType==="REELS" && r.caption===e.caption &&
    /^https:\/\/www\.instagram\.com\/reel\/[A-Za-z0-9_-]+\/?$/.test(r.permalink) &&
    Number.isFinite(Date.parse(r.publishedAt)) && Date.parse(r.publishedAt)>=Date.parse(e.dueAt);
}

async function tick(store,meta,nowIso) {
  const now=Date.parse(nowIso);
  if(!Number.isFinite(now)) throw Error("Invalid clock");
  // Every durable mutation is a compare-and-swap of the same account ledger.
  // Adapters must never retry a publish POST, even on 429 or 500.
  const snap=await store.read();
  const ledger=snap.value;
  if(!Array.isArray(ledger.episodes)||!Number.isSafeInteger(ledger.lastNumber)) throw Error("Invalid ledger");
  const rows=[...ledger.episodes].sort((a,b)=>a.key.localeCompare(b.key));
  if(new Set(rows.map(e=>e.key)).size!==rows.length || new Set(rows.map(e=>e.id)).size!==rows.length) throw Error("Duplicate ledger entry");
  const active=rows.filter(e=>["PUBLISHING","AMBIGUOUS"].includes(e.state));
  if(active.length>1) throw Error("Multiple unresolved intents");
  async function replace(s,e,patch) {
    return store.cas(s.version,{...s.value,episodes:s.value.episodes.map(x=>x.key===e.key?{...x,...patch}:x),...(patch.state==="PUBLISHED"?{lastNumber:e.number}:{})});
  }
  async function confirm(key,expectedId) {
    const s=await store.read(), e=s.value.episodes.find(x=>x.key===key);
    if(!e) throw Error("Missing intent");
    if(e.state==="PUBLISHED") return "PUBLISHED";
    if(!["PUBLISHING","AMBIGUOUS"].includes(e.state)||e.number!==s.value.lastNumber+1) throw Error("Invalid intent");
    let receipt;
    try {receipt=await meta.findReceipt(e,expectedId);} catch {return "UNCONFIRMED";}
    if(!validReceipt(e,receipt,expectedId)) return "UNCONFIRMED";
    if(s.value.episodes.some(x=>x.state==="PUBLISHED"&&x.receipt?.mediaId===receipt.mediaId)) throw Error("Duplicate media ID");
    return await replace(s,e,{state:"PUBLISHED",receipt})?"PUBLISHED":"CONFLICT";
  }
  if(active.length) {
    const e=active[0], result=await confirm(e.key,e.expectedMediaId);
    if(result==="PUBLISHED"||result==="CONFLICT") return result;
    if(e.state==="PUBLISHING" && now-Date.parse(e.intentAt)>=120000) await replace(snap,e,{state:"AMBIGUOUS"});
    return "BLOCKED_UNCONFIRMED";
  }
  const e=rows.find(x=>x.state!=="PUBLISHED");
  if(!e) return "EMPTY";
  if(!validEpisode(e)||e.number!==ledger.lastNumber+1) return "INVALID_EPISODE";
  if(now<Date.parse(e.dueAt)) return "NOT_DUE";
  if(!["READY","SCHEDULED","RETRYABLE_ERROR"].includes(e.state)) return "BLOCKED_NOT_READY";
  // Reconcile before checking expiry: a published container is not FINISHED.
  const found=await meta.findReceipt(e);
  if(found) {
    if(!validReceipt(e,found)||rows.some(x=>x.state==="PUBLISHED"&&x.receipt?.mediaId===found.mediaId)) return "BLOCKED_UNCONFIRMED";
    return await replace(snap,e,{state:"PUBLISHED",receipt:found})?"PUBLISHED":"CONFLICT";
  }
  if(!e.containerId||!Number.isFinite(Date.parse(e.containerExpiresAt))||Date.parse(e.containerExpiresAt)<=now) return "CONTAINER_NOT_READY";
  // No generation, no model download, no audio repair, no waiting for render.
  if(!await meta.checkReady(e)) return "CONTAINER_NOT_READY";
  // Persist irreversible intent before touching Meta; only the CAS winner may POST.
  if(!await replace(snap,e,{state:"PUBLISHING",intentAt:new Date(now).toISOString()})) return "CONFLICT";
  let mediaId;
  try {mediaId=await meta.publishOnce(e);} catch {return "BLOCKED_UNCONFIRMED";}
  if(typeof mediaId!=="string"||!/^\d+$/.test(mediaId)) return "BLOCKED_UNCONFIRMED";
  const s=await store.read(), pending=s.value.episodes.find(x=>x.key===e.key);
  if(pending?.state==="PUBLISHED") return "PUBLISHED";
  if(!pending||!["PUBLISHING","AMBIGUOUS"].includes(pending.state)) throw Error("Lost durable intent");
  if(!await replace(s,pending,{expectedMediaId:mediaId})) return "CONFLICT";
  return confirm(e.key,mediaId);
}

function reserveLevel(n){if(!Number.isInteger(n)||n<0)throw Error("Invalid reserve");return n<2?"EMERGENCY":n<4?"CRITICAL":n<10?"WARNING":n<14?"REFILL":"OPTIMAL";}
export {civilKey,validEpisode,validReceipt,tick,reserveLevel};
