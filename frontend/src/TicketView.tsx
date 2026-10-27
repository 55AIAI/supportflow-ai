import {useEffect,useRef,useState} from 'react';
import {ArrowLeft,Package,CornerUpLeft,Check,Clock,RefreshCw,Send,LoaderCircle} from 'lucide-react';
import type {Detail,Role} from './types';
import {initials,money,statusName} from './Inbox';
type Props={ticket:Detail;role:Role;busy:boolean;onBack:()=>void;analyze:()=>Promise<void>;approve:(confirmed:boolean)=>Promise<void>;reject:()=>Promise<void>;reply:(text:string)=>Promise<void>};
export function TicketView({ticket:t,role,busy,onBack,analyze,approve,reject,reply}:Props){
 const [tab,setTab]=useState('conversation'),[draft,setDraft]=useState(t.draft),[confirmed,setConfirmed]=useState(false);
 const dirty=useRef(false),canWrite=role!=='viewer';
 useEffect(()=>{if(!dirty.current)setDraft(t.draft)},[t.draft]);
 const done=t.job?.state==='completed', pending=t.proposal?.state==='pending';
 const send=async()=>{await reply(draft);dirty.current=false;setDraft('')};
 return <>
 <section className="ticket-detail">
  <div className="detail-heading"><button className="back-link mobile-only" onClick={onBack}><ArrowLeft size={17}/>Обращения</button><div className="breadcrumb">Обращения / SF-{t.order?.reference||t.id.slice(0,4).toUpperCase()}</div><h2>{t.subject}</h2>
   <div className="customer"><span className="avatar color-0">{initials(t.customer_name)}</span><div><strong>{t.customer_name}</strong><span>Клиент магазина · {statusName(t.status)}</span></div></div>
  </div>
  <div className="detail-tabs"><button className={tab==='conversation'?'active':''} onClick={()=>setTab('conversation')}>Переписка</button><button className={tab==='activity'?'active':''} onClick={()=>setTab('activity')}>Активность</button></div>
  <div className="conversation">{tab==='conversation'?<>
   {t.messages.map(m=><article key={m.id} className={'message '+m.author}><span className={'avatar small '+(m.author==='customer'?'color-0':'color-3')}>{m.author==='customer'?initials(t.customer_name):'SF'}</span><div><div className="message-label"><b>{m.author==='customer'?t.customer_name:'Оператор'}</b><time>{new Date(m.created_at*1000).toLocaleTimeString('ru',{hour:'2-digit',minute:'2-digit'})}</time></div><p>{m.body}</p></div></article>)}
   {t.order&&<div className="order-strip"><Package size={25}/><div><b>Заказ №{t.order.reference}</b><span>{t.order.product}</span></div><span className={'status '+(t.order.status==='delivered'?'closed':'open')}>{t.order.status==='delivered'?'Доставлен':'В пути'}</span><strong>{money(t.order.amount_minor,t.order.currency)}</strong></div>}
  </>:<div className="activity-summary"><h3>Состояние обработки</h3><p>{statusName(t.status)}</p><p>{t.job?'Попыток анализа: '+t.job.attempts:'Анализ ещё не запускался'}</p>{t.job?.error&&<p className="warning">Не удалось завершить анализ. Повторите попытку.</p>}<p>Подробная история доступна в разделе «История».</p></div>}</div>
  <form className="reply-form" onSubmit={e=>{e.preventDefault();void send().catch(()=>{})}}>
   <label htmlFor="reply">Ответ клиенту</label><textarea id="reply" maxLength={4000} placeholder="Подготовьте ответ или запустите помощника…" value={draft} onChange={e=>{dirty.current=true;setDraft(e.target.value)}} disabled={!canWrite||busy}/>
   <div className="reply-footer"><span>{canWrite?'Ответ сохранится в переписке демо-магазина':'Режим наблюдателя: только чтение'}</span><button className="primary" disabled={!canWrite||busy||!draft.trim()}><Send size={15}/>Отправить ответ</button></div>
  </form>
 </section>
 <aside className="assistant" aria-label="Помощник">
  <div className="assistant-heading"><h2>Помощник</h2><span>Демо-режим</span></div>
  {!done?<div className="assistant-start"><div className="assistant-symbol"><CornerUpLeft size={27}/></div><h3>{t.status==='processing'?'Готовим предложение':'Ответ с подтверждёнными источниками'}</h3><p>Помощник проверит заказ и правила магазина. Решение о действии принимает оператор.</p><button className="primary" disabled={!canWrite||busy||t.status==='processing'} onClick={()=>void analyze()}>{t.status==='processing'?<LoaderCircle size={17} className="spin"/>:<RefreshCw size={17}/>} {t.status==='processing'?'Анализ выполняется':'Подготовить ответ'}</button>{t.status==='failed'&&<p className="warning">Задача завершилась с ошибкой. Можно повторить анализ.</p>}</div>:<>
   <ol className="steps"><li><span>1</span><div><b>Обращение классифицировано</b><p>Тема: {t.category==='returns'?'Возврат товара':t.category==='delivery'?'Доставка заказа':'Общий вопрос'}</p></div></li><li><span>2</span><div><b>{t.order?'Заказ найден':'Заказ не указан'}</b><p>{t.order?'Заказ №'+t.order.reference+' · '+money(t.order.amount_minor,t.order.currency):'Оператору нужно уточнить детали'}</p></div></li><li><span>3</span><div><b>{t.sources.length?'Правила проверены':'Нужна проверка'}</b><p>{t.escalation||'Подготовлено предложение для оператора'}</p></div></li></ol>
   {t.sources.length>0&&<div className="source-group"><h3>Источник</h3>{t.sources.map((s,i)=><div className="source" key={s.document_id+'-'+i}><b>{s.title}</b><blockquote>«{s.quote}»</blockquote><small>Версия {s.version}</small></div>)}</div>}
   {t.escalation&&<p className="warning">{t.escalation}</p>}
   {t.proposal&&<div className="proposal-group"><h3>Предлагаемое действие</h3><div className="proposal"><div className="proposal-title"><span><CornerUpLeft size={25}/></span><div><b>{t.proposal.state==='approved'?'Заявка создана':'Создать возврат'}</b><p>Заказ №{t.proposal.payload.order_reference} · {money(t.proposal.payload.amount_minor,t.proposal.payload.currency)}</p></div></div>
    {pending?<><p>Действие выполнится после подтверждения оператора.</p><label className="confirmation"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)} disabled={!canWrite||busy}/>Подтверждаю, что товар не использован</label><button className="primary" disabled={!canWrite||busy||!confirmed} onClick={()=>void approve(confirmed)}>Подтвердить возврат</button><button className="secondary" disabled={!canWrite||busy} onClick={()=>void reject()}>Отклонить</button></>:<p className={'decision '+(t.proposal.state==='approved'?'success':'')}>{t.proposal.state==='approved'?<Check size={16}/>:null}{t.proposal.state==='approved'?'Повторная заявка не создастся':t.proposal.state==='rejected'?'Предложение отклонено':'Предложение устарело'}</p>}
   </div></div>}
   <button className="text-button" disabled={!canWrite||busy} onClick={()=>void analyze()}><RefreshCw size={14}/>Повторить анализ</button>
  </>}
  <div className="audit-note"><Clock size={20}/>Каждое действие сохраняется в истории</div>
 </aside></>
}
