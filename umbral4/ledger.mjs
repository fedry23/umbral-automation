function civilDue(key){
 const m=/^(\d{4}-\d{2}-\d{2})\/(09|21):00$/.exec(key);
 if(!m)throw Error("Invalid civil slot");
 const [day,h]=m.slice(1);
 const base=Date.parse(day+"T"+h+":00:00Z");
 if(!Number.isFinite(base)||new Date(base).toISOString().slice(0,10)!==day)throw Error("Invalid civil date");
 const fmt=new Intl.DateTimeFormat("en-GB",{timeZone:"Europe/Madrid",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hourCycle:"h23"});
 for(const offset of [1,2]){
  const t=new Date(base-offset*3600000),p=Object.fromEntries(fmt.formatToParts(t).map(x=>[x.type,x.value]));
  if(`${p.year}-${p.month}-${p.day}/${p.hour}:${p.minute}`===key)return t.toISOString();
 }
 throw Error("Unresolvable civil slot");
}

function nextKey(key){
 civilDue(key);
 if(key.endsWith("/09:00"))return key.slice(0,10)+"/21:00";
 const d=new Date(key.slice(0,10)+"T00:00:00Z");
 d.setUTCDate(d.getUTCDate()+1);
 return d.toISOString().slice(0,10)+"/09:00";
}

function calendar(first,lastNumber,count=14){
 if(!Number.isSafeInteger(lastNumber)||lastNumber<0||!Number.isInteger(count)||count<1||count>14)throw Error("Invalid calendar");
 const rows=[];let key=first;
 for(let i=0;i<count;i++){rows.push({key,dueAt:civilDue(key),id:"slot:"+key,number:lastNumber+i+1,state:"PENDING"});key=nextKey(key);}
 return rows;
}

function importHistory(files,pending,first){
 civilDue(first);
 if(!Array.isArray(files)||!files.length||!Array.isArray(pending))throw Error("Missing history");
 const names=new Set(),media=new Set(),numbers=new Set(),keys=new Set(),records=[];
 for(const item of files){
  const {name,row}=item;
  if(!/^(?:\d{4}-\d{2}-\d{2}(?:_09)?|test-[\w-]+)\.json$/.test(name)||names.has(name)||!row||typeof row.instagram_media_id!=="string"||!/^\d+$/.test(row.instagram_media_id)||!Number.isFinite(Date.parse(row.published_at)))throw Error("Invalid historical receipt");
  names.add(name);if(media.has(row.instagram_media_id))throw Error("Duplicate historical media");media.add(row.instagram_media_id);
  if(row.episode_number!==undefined){if(!Number.isSafeInteger(row.episode_number)||row.episode_number<1||numbers.has(row.episode_number))throw Error("Duplicate or invalid historical number");numbers.add(row.episode_number);}
  if(!name.startsWith("test-")){
   const day=name.slice(0,10),slot=name.includes("_09")?"09":"21",key=day+"/"+slot+":00";
   civilDue(key);
   if(day!==row.date||(row.slot!==undefined&&row.slot!==slot)||key>=first||keys.has(key))throw Error("Historical slot mismatch");
   keys.add(key);
   if(row.verification==="published_media_read_back"&&(!/^https:\/\/www\.instagram\.com\/reel\/[\w-]+\/?$/.test(row.permalink||"")||!Number.isSafeInteger(row.episode_number)))throw Error("Invalid verified receipt");
   records.push({key,name,row,verified:row.verification==="published_media_read_back"});
  }else records.push({key:null,name,row,verified:row.verification==="published_media_read_back"});
 }
 for(const name of pending){if(!names.has(name))throw Error("Unresolved historical intent: "+name);}
 const official=records.filter(x=>x.key).sort((a,b)=>a.key.localeCompare(b.key));
 const latest=official.at(-1),lastNumber=Math.max(...numbers);
 if(!latest?.verified||latest.row.episode_number!==lastNumber||nextKey(latest.key)!==first)throw Error("Cutover not contiguous with latest verified official receipt");
 // Check the continuous numbered official series, retaining older unverified and test receipts separately.
 const verified=official.filter(x=>x.verified);
 for(let i=1;i<verified.length;i++){
  if(verified[i].row.episode_number!==verified[i-1].row.episode_number+1||nextKey(verified[i-1].key)!==verified[i].key)throw Error("Historical official gap");
 }
 return {records,ledger:{lastNumber,nextKey:first,episodes:calendar(first,lastNumber)}};
}

function checkCalendar(ledger){
 if(!ledger||!Number.isSafeInteger(ledger.lastNumber)||!Array.isArray(ledger.episodes)||ledger.episodes.length<1||ledger.episodes.length>14)throw Error("Invalid active calendar");
 let key=ledger.nextKey;
 for(let i=0;i<ledger.episodes.length;i++){
  const e=ledger.episodes[i];
  if(e.key!==key||e.dueAt!==civilDue(key)||e.number!==ledger.lastNumber+i+1||e.id!=="slot:"+key||e.state==="PUBLISHED")throw Error("Calendar gap or numbering mismatch");
  key=nextKey(key);
 }
 return true;
}

function archiveStore(storage){
 const MAX=100000;
 return {
  async read(){const s=await storage.get("ledger4");if(!s)throw Error("Not initialized");checkCalendar(s.value);return s;},
  async cas(version,value){
   return storage.transaction(async tx=>{
    const s=await tx.get("ledger4");if(!s||s.version!==version)return false;
    checkCalendar(s.value);
    if(value.nextKey!==s.value.nextKey||value.episodes.length!==s.value.episodes.length||value.episodes.some((e,i)=>e.key!==s.value.episodes[i].key||e.id!==s.value.episodes[i].id||e.number!==s.value.episodes[i].number||e.dueAt!==s.value.episodes[i].dueAt))throw Error("Cannot reorder active calendar");
    const done=value.episodes.filter(e=>e.state==="PUBLISHED");
    let next=value;
    if(done.length){
     const e=done[0],prior=s.value.episodes[0],r=e.receipt;
     if(done.length!==1||e.key!==prior.key||e.number!==s.value.lastNumber+1||value.lastNumber!==e.number||!r||typeof r.mediaId!=="string"||!/^\d+$/.test(r.mediaId)||r.ownerVerified!==true||r.productType!=="REELS"||r.caption!==e.caption||!/^https:\/\/www\.instagram\.com\/reel\/[\w-]+\/?$/.test(r.permalink||"")||!(Date.parse(r.publishedAt)>=Date.parse(e.dueAt)))throw Error("Invalid archive transition");
     if(await tx.get("media:"+r.mediaId)||await tx.get("receipt:"+e.key)||await tx.get("number:"+e.number))throw Error("Duplicate archived publication");
     await tx.put("media:"+r.mediaId,e.key);await tx.put("receipt:"+e.key,e);await tx.put("number:"+e.number,e.key);
     const remaining=value.episodes.slice(1),tail=nextKey(value.episodes.at(-1).key);
     next={...value,nextKey:nextKey(e.key),episodes:[...remaining,...calendar(tail,e.number+remaining.length,1)]};
    }else if(value.lastNumber!==s.value.lastNumber)throw Error("Number may advance only after receipt");
    checkCalendar(next);
    const result={version:version+1,value:next};
    if(encodeURIComponent(JSON.stringify(result)).length>MAX)throw Error("Active ledger too large");
    await tx.put("ledger4",result);return true;
   });
  }
 };
}

function manifestFor(e,m){
 if(!e||e.state!=="PENDING"||!m||m.key!==e.key||m.number!==e.number||m.id!==e.id||m.qaPassed!==true||!Array.isArray(m.storyboard)||m.storyboard.length<6||m.storyboard.some(x=>typeof x!=="string"||!x.trim())||typeof m.caption!=="string"||!m.caption.includes(`[UMBRAL4:${e.key}]`)||!m.caption.includes("EPISODIO "+e.number)||m.caption.length>2200)throw Error("Invalid episode manifest");
 for(const kind of ["video","cover"]){
  const a=m[kind];if(!a||!/^[a-f0-9]{64}$/.test(a.sha256)||!Number.isSafeInteger(a.bytes)||a.bytes<=0||typeof a.privateKey!=="string"||!a.privateKey.startsWith("umbral4/")||a.privateKey.includes(".."))throw Error("Invalid "+kind);
 }
 return {...e,state:"READY",caption:m.caption,storyboard:m.storyboard,qaPassed:true,videoSha:m.video.sha256,coverSha:m.cover.sha256,video:m.video,cover:m.cover};
}
export {civilDue,nextKey,calendar,importHistory,checkCalendar,archiveStore,manifestFor};
