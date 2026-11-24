function durableStore(storage){
 return {
  async read(){const row=await storage.get("ledger");if(!row)throw Error("Ledger not provisioned");return row;},
  async cas(version,value){return storage.transaction(async tx=>{
   const row=await tx.get("ledger");if(!row||row.version!==version)return false;
   const next={version:version+1,value};
   if(encodeURIComponent(JSON.stringify(next)).length>100000)throw Error("Archive required before ledger size limit");
   await tx.put("ledger",next);return true;
  });}
 };
}

// Meta Graph API transport: no token in query, no POST retries.
// Inject fetcher for tests. Not wired to live credentials or scheduling.
function metaAdapter({token,account,version="v25.0",fetcher=fetch}){
 if(!token||!/^\d+$/.test(account)||!/^v\d+\.\d+$/.test(version))throw Error("Invalid Meta configuration");
 const root="https://graph.facebook.com/"+version+"/";
 async function request(path,params={},method="GET"){
  const url=new URL(root+path),body=new URLSearchParams(params);
  if(method==="GET")url.search=body.toString();
  const response=await fetcher(url.toString(),{method,headers:{Authorization:"Bearer "+token,...(method==="POST"?{"Content-Type":"application/x-www-form-urlencoded"}:{})},...(method==="POST"?{body:body.toString()}:{}),redirect:"error",signal:AbortSignal.timeout(30000)});
  if(!response.ok)throw Error("Meta HTTP "+response.status);
  const json=await response.json();if(!json||json.error)throw Error("Meta API error");return json;
 }
 async function status(e){
  if(!/^\d+$/.test(e.containerId||""))throw Error("Invalid container");
  const v=await request(e.containerId,{fields:"status_code"});
  if(typeof v.status_code!=="string")throw Error("Unknown container status");
  return v.status_code;
 }
 return {
  async containerStatus(e){return status(e);},
  async createContainer(e){
   if(e.hostingVerified!==true||!e.videoUrl||!e.coverUrl||!e.caption)throw Error("Missing verified hosting");
   const d=await request(account+"/media",{media_type:"REELS",video_url:e.videoUrl,cover_url:e.coverUrl,caption:e.caption,share_to_feed:"true"},"POST");
   if(typeof d.id!=="string"||!/^\d+$/.test(d.id))throw Error("Uncertain container creation");return d.id;
  },
  async checkReady(e){return e.hostingVerified===true&&e.qaPassed===true&&(await status(e))==="FINISHED";},
  async findReceipt(e,expectedId){
   let after,seen=new Set();
   for(let page=0;page<20;page++){
    const data=await request(account+"/media",{fields:"id,caption,permalink,timestamp,media_product_type",limit:"50",...(after?{after}:{})});
    if(!Array.isArray(data.data))throw Error("Malformed media listing");
    const match=data.data.filter(m=>m.caption===e.caption);
    if(match.length>1)throw Error("Multiple matching media");
    if(match.length===1){
     const m=match[0];if(expectedId&&m.id!==expectedId)throw Error("Unexpected media ID");
     return {mediaId:m.id,ownerVerified:true,productType:m.media_product_type,caption:m.caption,permalink:m.permalink,publishedAt:m.timestamp};
    }
    if(!data.paging?.next){
     if(e.containerId&&(await status(e))==="PUBLISHED")throw Error("Published container without matching media");
     return null;
    }
    after=data.paging?.cursors?.after;
    if(!after||seen.has(after))throw Error("Incomplete media pagination");seen.add(after);
   }
   throw Error("Media search incomplete");
  },
  async publishOnce(e){
   if(!/^\d+$/.test(e.containerId||""))throw Error("Invalid container");
   const d=await request(account+"/media_publish",{creation_id:e.containerId},"POST");
   if(typeof d.id!=="string"||!/^\d+$/.test(d.id))throw Error("Uncertain publish response");return d.id;
  }
 };
}
export {durableStore,metaAdapter};
