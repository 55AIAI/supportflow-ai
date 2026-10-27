import {useEffect,useState} from 'react';
import {Check,RefreshCw,X} from 'lucide-react';
import type {Order,Knowledge,Audit,Checks,Role} from './types';
import {money} from './Inbox';
export function Modal({title,close,children}:{title:string;close:()=>void;children:React.ReactNode}){
 useEffect(()=>{const listener=(e:KeyboardEvent)=>{if(e.key==='Escape')close()};document.addEventListener('keydown',listener);return()=>document.removeEventListener('keydown',listener)},[close]);
 return <div className="modal-backdrop" onMouseDown={e=>{if(e.target===e.currentTarget)close()}}><section role="dialog" aria-modal="true" aria-label={title} className="modal"><header><h2>{title}</h2><button className="icon-button" onClick={close} aria-label="Закрыть окно"><X size={20}/></button></header>{children}</section></div>
}
export function NewTicket({orders,busy,save,close}:{orders:Order[];busy:boolean;save:(body:unknown)=>Promise<void>;close:()=>void}){
 const [order,setOrder]=useState(''),[customer,setCustomer]=useState(''),[name,setName]=useState(''),[subject,setSubject]=useState(''),[message,setMessage]=useState('');
 return <Modal title="Новое обращение" close={close}><form onSubmit={e=>{e.preventDefault();void save({subject,customer_name:name,customer_key:customer,message,order_reference:order||null}).catch(()=>{})}}>
  <label>Имя клиента<input required maxLength={80} value={name} onChange={e=>setName(e.target.value)}/></label>
  <label>Заказ<select value={order} onChange={e=>{setOrder(e.target.value);setCustomer(orders.find(o=>o.reference===e.target.value)?.customer_key||'')}}><option value="">Без заказа</option>{orders.map(o=><option key={o.id} value={o.reference}>№{o.reference} · {o.product}</option>)}</select></label>
  <label>Код клиента<input required maxLength={80} value={customer} readOnly={!!order} onChange={e=>setCustomer(e.target.value)} placeholder="Например, client-01"/></label>
  <label>Тема<input required minLength={3} maxLength={180} value={subject} onChange={e=>setSubject(e.target.value)}/></label>
  <label>Сообщение<textarea required minLength={3} maxLength={6000} value={message} onChange={e=>setMessage(e.target.value)}/></label>
  <footer><button type="button" className="secondary" onClick={close}>Отмена</button><button className="primary" disabled={busy}>Создать обращение</button></footer>
 </form></Modal>
}
const eventNames:Record<string,string>={'analysis.queued':'Запущен анализ обращения','analysis.completed':'Предложение подготовлено','analysis.failed':'Ошибка обработки','return.requested':'Создана заявка на возврат','reply.saved':'Ответ сохранён в переписке','knowledge.updated':'Обновлены правила магазина','proposal.rejected':'Предложение отклонено','ticket.created':'Создано обращение','organization.created':'Создана организация'};
export function OrdersPage({orders}:{orders:Order[]}){
 return <section className="page"><h1>Заказы</h1><p className="page-intro">Данные тестового магазина для проверки обращений.</p><div className="table-scroll"><table><thead><tr><th>Заказ</th><th>Товар</th><th>Клиент</th><th>Сумма</th><th>Статус</th></tr></thead><tbody>{orders.map(o=><tr key={o.id}><td>№{o.reference}</td><td>{o.product}</td><td>{o.customer_key}</td><td>{money(o.amount_minor,o.currency)}</td><td><span className={'status '+(o.status==='delivered'?'closed':'open')}>{o.status==='delivered'?'Доставлен':'В пути'}</span></td></tr>)}</tbody></table></div>{!orders.length&&<p className="empty">Заказов пока нет</p>}</section>
}
export function AuditPage({audit}:{audit:Audit[]}){
 return <section className="page"><h1>История</h1><p className="page-intro">События текущей организации. Текст переписки в журнал не записывается.</p><div className="timeline">{audit.map(a=><article key={a.id}><span className="timeline-dot"/><div><b>{eventNames[a.event]||a.event}</b><p>{a.actor==='worker'?'Помощник':'Пользователь'} · {new Date(a.created_at*1000).toLocaleString('ru-KZ')}</p></div></article>)}</div>{!audit.length&&<p className="empty">История появится после первого действия</p>}</section>
}
export function ChecksPage({checks,refresh,busy}:{checks:Checks|null;refresh:()=>void;busy:boolean}){
 return <section className="page checks-page"><div className="page-top"><h1>Проверки</h1><button className="secondary" onClick={refresh} disabled={busy}><RefreshCw size={16}/>Запустить проверки</button></div><p className="page-intro">Детерминированные сценарии правил возврата. Это не оценка точности языковой модели.</p>{checks&&checks.total>0?<><div className="check-summary"><Check size={22}/><b>{checks.passed} из {checks.total} сценариев пройдено</b></div><div className="check-list">{checks.results.map(c=><div key={c.name}><span className={c.passed?'success':'warning'}>{c.passed?<Check size={17}/>:<X size={17}/>}</span>{c.name}<span className="muted">{c.passed?'Пройден':'Ошибка'}</span></div>)}</div></>:<p className="empty">Серверные проверки доступны при запуске Python backend.</p>}</section>
}
export function KnowledgePage({documents,role,save,busy}:{documents:Knowledge[];role:Role;save:(body:unknown)=>Promise<void>;busy:boolean}){
 const [editing,setEditing]=useState<Knowledge|null>(null),[title,setTitle]=useState(''),[body,setBody]=useState(''),[days,setDays]=useState(14);
 return <section className="page"><h1>База знаний</h1><p className="page-intro">Помощник ссылается на действующую версию правил. Изменение правил делает старые предложения недействительными.</p><div className="knowledge-list">{documents.map(d=><article key={d.id}><div><h2>{d.title}</h2><span className="muted">Версия {d.version}</span></div><p>{d.body}</p>{role==='owner'&&<button className="secondary" onClick={()=>{setEditing(d);setTitle(d.title);setBody(d.body);setDays(d.return_days||14)}}>Изменить правила</button>}</article>)}</div>{!documents.length&&<p className="empty">Правила ещё не добавлены. Их можно создать через API.</p>}
 {editing&&<Modal title="Изменить правила" close={()=>setEditing(null)}><form onSubmit={e=>{e.preventDefault();void save({kind:editing.kind,title,body,return_days:editing.kind==='returns'?days:null,expected_version:editing.version}).then(()=>setEditing(null)).catch(()=>{})}}><label>Название<input required minLength={3} maxLength={150} value={title} onChange={e=>setTitle(e.target.value)}/></label>{editing.kind==='returns'?<label>Срок возврата, дней<input type="number" required min={1} max={60} value={days} onChange={e=>setDays(Number(e.target.value))}/></label>:<label>Текст правил<textarea required maxLength={6000} value={body} onChange={e=>setBody(e.target.value)}/></label>}<p className="muted">Сохраняется новая версия. Срок в тексте правила возврата сформируется автоматически.</p><footer><button type="button" className="secondary" onClick={()=>setEditing(null)}>Отмена</button><button className="primary" disabled={busy}>Сохранить правила</button></footer></form></Modal>}
 </section>
}
