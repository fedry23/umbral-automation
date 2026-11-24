import {archiveStore} from "./ledger.mjs";
import {tick,reserveLevel} from "./publisher.mjs";
import {prepare} from "./prepare.mjs";
import {metaAdapter} from "./adapters.mjs";

export async function runCycle(store,meta,nowIso){
 const result=await tick(store,meta,nowIso);
 if(["NOT_DUE","CONTAINER_NOT_READY","BLOCKED_NOT_READY"].includes(result)){
  return {publication:result,preparation:await prepare(store,meta,nowIso)};
 }
 return {publication:result};
}
function json(data,status=200){return new Response(JSON.stringify(data),{status,headers:{"Content-Type":"application/json","Cache-Control":"no-store"}});}
function allowed(req,secret){
 if(typeof secret!=="string"||secret.length<32||secret.length>256)return false;
 const supplied=req.headers.get("Authorization")||"",target="Bearer "+secret;
 if(supplied.length!==target.length)return false;
 let diff=0;for(let i=0;i<target.length;i++)diff|=supplied.charCodeAt(i)^target.charCodeAt(i);
 return diff===0;
}
function account(env){return env.ACCOUNT.get(env.ACCOUNT.idFromName("umbral-single-account"));}
export class Account{
 constructor(state,env){this.storage=state.storage;this.env=env;}
 async fetch(req){
  const path=new URL(req.url).pathname;
  if(path!=="/tick"&&path!=="/status")return json({error:"not_found"},404);
  const store=archiveStore(this.storage);
  if(path==="/status"&&req.method==="GET"){
   try{
    const {value}=await store.read(),ready=value.episodes.filter(e=>["READY","PREPARING","SCHEDULED"].includes(e.state)).length;
    return json({mode:this.env.UMBRAL4_MODE,head:value.episodes[0].key,state:value.episodes[0].state,ready,reserveLevel:reserveLevel(ready),lastNumber:value.lastNumber});
   }catch{return json({state:"UNINITIALIZED_OR_INVALID"},503);}
  }
  if(path!=="/tick"||req.method!=="POST")return json({error:"method"},405);
  // No live operations unless separately provisioned AND explicitly authorized after cutover.
  if(this.env.UMBRAL4_MODE!=="live")return json({state:"DISABLED"},409);
  const authorization=await this.storage.get("cutover4");
  if(authorization?.authorized!==true||authorization?.legacyDisabled!==true||authorization?.account!==this.env.IG_ACCOUNT)return json({state:"CUTOVER_NOT_AUTHORIZED"},409);
  try{
   const m=metaAdapter({token:this.env.IG_ACCESS_TOKEN,account:this.env.IG_ACCOUNT});
   const outcome=await runCycle(store,m,new Date().toISOString());
   const failed=["INVALID_EPISODE","BLOCKED_UNCONFIRMED","BLOCKED_NOT_READY","CONTAINER_NOT_READY"].includes(outcome.publication);
   return json(outcome,failed?503:200);
  }catch{return json({state:"ERROR_REQUIRES_RECONCILIATION"},503);}
 }
}
export default {
 async fetch(req,env){
  if(!allowed(req,env.UMBRAL4_BACKUP_TOKEN))return json({error:"unauthorized"},401);
  const path=new URL(req.url).pathname;
  if(path==="/tick"&&req.method==="POST")return account(env).fetch("https://internal/tick",{method:"POST"});
  if(path==="/status"&&req.method==="GET")return account(env).fetch("https://internal/status");
  return json({error:"not_found"},404);
 },
 async scheduled(_controller,env){
  if(env.UMBRAL4_MODE!=="live")return;
  const response=await account(env).fetch("https://internal/tick",{method:"POST"});
  if(!response.ok)throw Error("Publication cycle requires attention: "+response.status);
 }
};
