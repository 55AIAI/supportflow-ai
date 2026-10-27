import type {Session,Ticket,Detail,Order,Knowledge,Audit,Checks,Role} from './types';
import {preview} from './preview';

export const previewMode=import.meta.env.VITE_DEMO_ONLY==='1';
let csrf='';
async function request<T>(path:string,method='GET',body?:unknown):Promise<T>{
  if(previewMode) return preview(path,method,body) as Promise<T>;
  const response=await fetch('/api'+path,{method,credentials:'same-origin',
    headers:method==='GET'?{}:{'Content-Type':'application/json','X-SupportFlow':'1','X-CSRF-Token':csrf},
    ...(method==='GET'?{}:{body:JSON.stringify(body??{})})});
  if(!response.ok){
    const data=await response.json().catch(()=>({detail:'Сервис недоступен'}));
    throw new Error(typeof data.detail==='string'?data.detail:'Проверьте заполненные поля');
  }
  return response.json() as Promise<T>;
}
function authenticated(result:Session){csrf=result.csrf_token;return result}
const base=(org:string)=>'/orgs/'+encodeURIComponent(org);
export const api={
  config:()=>request<{demo_available:boolean;provider:string;authenticated:boolean}>('/config'),
  session:()=>request<Session>('/auth/session').then(authenticated),
  login:(body:unknown,register=false)=>request<Session>('/auth/'+(register?'register':'login'),'POST',body).then(authenticated),
  demo:()=>request<Session>('/demo','POST',{role:'operator'}).then(authenticated),
  logout:()=>request('/auth/logout','POST').then(()=>{csrf=''}),
  role:(org:string,role:Role)=>request(base(org)+'/demo-role','POST',{role}),
  tickets:(org:string)=>request<Ticket[]>(base(org)+'/tickets'),
  detail:(org:string,id:string)=>request<Detail>(base(org)+'/tickets/'+id),
  create:(org:string,body:unknown)=>request<Detail>(base(org)+'/tickets','POST',body),
  analyze:(org:string,id:string)=>request(base(org)+'/tickets/'+id+'/analyze','POST'),
  approve:(org:string,id:string,fingerprint:string,confirmed_unused:boolean)=>request(base(org)+'/proposals/'+id+'/approve','POST',{fingerprint,confirmed_unused}),
  reject:(org:string,id:string)=>request(base(org)+'/proposals/'+id+'/reject','POST'),
  reply:(org:string,id:string,body:string)=>request(base(org)+'/tickets/'+id+'/reply','POST',{body}),
  orders:(org:string)=>request<Order[]>(base(org)+'/orders'),
  knowledge:(org:string)=>request<Knowledge[]>(base(org)+'/knowledge'),
  saveKnowledge:(org:string,body:unknown)=>request<Knowledge>(base(org)+'/knowledge','PUT',body),
  audit:(org:string)=>request<Audit[]>(base(org)+'/audit'),
  checks:(org:string)=>request<Checks>(base(org)+'/checks'),
};
