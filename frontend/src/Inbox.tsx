import {Search,ArrowLeft} from 'lucide-react';
import type {Ticket} from './types';
import {useState} from 'react';
export const statusName=(value:string)=>({open:'Ожидает',processing:'Обработка',review:'На проверке',closed:'Закрыт',failed:'Ошибка'}[value]||value);
export const initials=(name:string)=>name.split(' ').slice(0,2).map(v=>v[0]).join('');
export const money=(amount:number,currency='KZT')=>new Intl.NumberFormat('ru-KZ',{style:'currency',currency,maximumFractionDigits:0}).format(amount/100);
export function Inbox({tickets,selected,onSelect,onBack}:{tickets:Ticket[];selected:string|null;onSelect:(id:string)=>void;onBack?:()=>void}){
 const [query,setQuery]=useState(''),[filter,setFilter]=useState('all');
 const filtered=tickets.filter(t=>(filter==='all'||(filter==='closed'?t.status==='closed':t.status!=='closed'))&&(t.subject+' '+t.customer_name+' '+t.message).toLocaleLowerCase().includes(query.toLocaleLowerCase()));
 return <section className="inbox" aria-label="Список обращений">
  <div className="inbox-heading"><h1>Обращения <span>{tickets.length}</span></h1>{onBack&&<button className="icon-button mobile-only" onClick={onBack} aria-label="Назад"><ArrowLeft size={18}/></button>}</div>
  <label className="search"><Search size={17}/><input aria-label="Поиск обращений" placeholder="Поиск по обращениям, заказам, клиентам…" value={query} onChange={e=>setQuery(e.target.value)}/></label>
  <div className="filters" aria-label="Фильтр обращений">{[['all','Все'],['waiting','Ожидают'],['closed','Закрыты']].map(([key,name])=><button key={key} className={filter===key?'selected':''} onClick={()=>setFilter(key)} aria-pressed={filter===key}>{name}</button>)}</div>
  <div className="ticket-list">{filtered.map((t,i)=><button key={t.id} className={'ticket-row '+(selected===t.id?'active':'')} onClick={()=>onSelect(t.id)} aria-current={selected===t.id?'true':undefined}>
    <span className={'avatar color-'+i%6}>{initials(t.customer_name)}</span><span className="row-content"><span className="row-top"><strong>{t.customer_name}</strong><time>{new Date(t.created_at*1000).toLocaleTimeString('ru',{hour:'2-digit',minute:'2-digit'})}</time></span><span className="row-subject"><b>{t.subject}</b><span className={'status '+t.status}>{statusName(t.status)}</span></span><span className="row-preview">{t.message}</span></span>
   </button>)}{filtered.length===0&&<div className="empty">Обращений не найдено</div>}</div>
 </section>
}
