import {useCallback,useEffect,useRef,useState} from 'react';
import {Inbox as InboxIcon,BookOpen,Package,History,ShieldCheck,LogOut,Plus,LoaderCircle,Menu} from 'lucide-react';
import {api,previewMode} from './api';
import type {Session,Org,Detail,Ticket,Order,Knowledge,Audit,Checks,Role} from './types';
import {Inbox} from './Inbox';
import {TicketView} from './TicketView';
import {OrdersPage,AuditPage,ChecksPage,KnowledgePage,NewTicket,Modal} from './Pages';
const nav=[['tickets','Обращения',InboxIcon],['knowledge','База знаний',BookOpen],['orders','Заказы',Package],['audit','История',History],['checks','Проверки',ShieldCheck]] as const;
export default function App(){
 const [session,setSession]=useState<Session|null>(null),[ready,setReady]=useState(false),[demoAvailable,setDemoAvailable]=useState(previewMode);
 const [orgId,setOrgId]=useState(''),[view,setView]=useState('tickets'),[selected,setSelected]=useState<string|null>(null),[mobileDetail,setMobileDetail]=useState(false);
 const [tickets,setTickets]=useState<Ticket[]>([]),[detail,setDetail]=useState<Detail|null>(null),[orders,setOrders]=useState<Order[]>([]),[documents,setDocuments]=useState<Knowledge[]>([]),[history,setHistory]=useState<Audit[]>([]),[checks,setChecks]=useState<Checks|null>(null);
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState(''),[newTicket,setNewTicket]=useState(false),[register,setRegister]=useState(false),[accountOpen,setAccountOpen]=useState(false);
 const generation=useRef(0),selectedRef=useRef(selected),orgRef=useRef(orgId);selectedRef.current=selected;orgRef.current=orgId;
 const org=session?.organizations.find(o=>o.id===orgId);
 const validSelection=!!session&&!!orgId&&tickets.some(t=>t.id===selected&&t.org_id===orgId);
 const installSession=(value:Session)=>{setSession(value);setOrgId(value.organizations[0]?.id||'');setSelected(null);setError('')};
 useEffect(()=>{let active=true;api.config().then(async c=>{if(!active)return;setDemoAvailable(c.demo_available);if(c.authenticated){const value=await api.session();if(active)installSession(value)}}).catch(e=>{if(active)setError(e.message)}).finally(()=>{if(active)setReady(true)});return()=>{active=false}},[]);
 const refresh=useCallback(async()=>{
   if(!orgId)return;
   const token=generation.current;
   const [ts,os,ds,hs]=await Promise.all([api.tickets(orgId),api.orders(orgId),api.knowledge(orgId),api.audit(orgId)]);
   if(token!==generation.current||orgRef.current!==orgId)return;
   setTickets(ts);setOrders(os);setDocuments(ds);setHistory(hs);
   setSelected(old=>old&&ts.some(t=>t.id===old)?old:ts[0]?.id||null);
 },[orgId]);
 useEffect(()=>{generation.current++;setDetail(null);setTickets([]);setOrders([]);setDocuments([]);setHistory([]);setChecks(null);setSelected(null);setMobileDetail(false);if(session&&orgId)void refresh().catch(e=>setError(e.message));},[orgId,!!session,refresh]);
 const loadDetail=useCallback(async()=>{if(!orgId||!selected||!validSelection)return;const token=generation.current;const value=await api.detail(orgId,selected);if(token===generation.current&&selectedRef.current===selected)setDetail(value)},[orgId,selected,validSelection]);
 useEffect(()=>{setDetail(null);let active=true;if(selected&&validSelection)void api.detail(orgId,selected).then(t=>{if(active)setDetail(t)}).catch(e=>{if(active)setError(e.message)});return()=>{active=false}},[orgId,selected,validSelection]);
 useEffect(()=>{if(!selected||!validSelection||previewMode)return;const source=new EventSource('/api/orgs/'+orgId+'/tickets/'+selected+'/events');source.addEventListener('ticket',()=>{void loadDetail().catch(()=>{});void refresh().catch(()=>{})});return()=>source.close()},[orgId,selected,validSelection,loadDetail,refresh]);
 async function act(work:()=>Promise<unknown>,message='',reload=true){
   setBusy(true);setError('');setNotice('');
   try{await work();if(reload){await refresh();await loadDetail()}if(message)setNotice(message)}
   catch(e){setError(e instanceof Error?e.message:'Не удалось выполнить действие');throw e}
   finally{setBusy(false)}
 }
 const guarded=(work:()=>Promise<unknown>,message='',reload=true)=>act(work,message,reload).catch(()=>{});
 const choose=(id:string)=>{generation.current++;setSelected(id);setMobileDetail(true);setError('')};
 if(!ready)return <div className="loading"><LoaderCircle className="spin"/>Загружаем рабочее пространство…</div>;
 if(!session)return <div className="auth-shell"><div className="auth-brand"><span className="brand-mark"/>SupportFlow AI</div><main className="auth-panel"><div className="auth-symbol"><InboxIcon size={32}/></div><h1>Поддержка с ясным<br/>следующим действием.</h1><p>Обращения, подтверждённые источники и решения под контролем оператора.</p>{demoAvailable&&<button className="primary demo-cta" disabled={busy} onClick={()=>void guarded(async()=>installSession(await api.demo()),'',false)}>Открыть демо-магазин</button>}<small>Синтетические заказы · Без подключения платного API</small>{!previewMode&&<><div className="auth-divider">или войдите в своё пространство</div><form onSubmit={e=>{e.preventDefault();const data=new FormData(e.currentTarget);void guarded(async()=>installSession(await api.login(Object.fromEntries(data),register)),'',false)}}>{register&&<><label>Имя<input name="name" required maxLength={80}/></label><label>Организация<input name="organization" required maxLength={100}/></label></>}<label>Email<input name="email" type="email" required autoComplete="email"/></label><label>Пароль<input name="password" type="password" required minLength={register?10:1} maxLength={128} autoComplete={register?'new-password':'current-password'}/></label><button className="secondary" disabled={busy}>{register?'Создать пространство':'Войти'}</button></form><button className="text-button" onClick={()=>setRegister(!register)}>{register?'Уже есть аккаунт? Войти':'Создать своё пространство'}</button></>}{error&&<p className="error" role="alert">{error}</p>}</main><p className="auth-footer">AI предлагает. Оператор решает. Каждое действие проверяет сервер.</p></div>;
 return <div className={'app '+(mobileDetail?'mobile-detail':'')}>
  <div className="demo-banner">{previewMode?'Визуальное демо в браузере · серверные действия имитируются':org?.is_demo?'Демонстрационная организация · синтетические данные':'Рабочее пространство · ответы требуют проверки'}</div>
  <header className="topbar"><a href="/" className="brand"><span className="brand-mark"/>SupportFlow AI</a><button className="primary" disabled={!org||org.role==='viewer'||busy} onClick={()=>setNewTicket(true)}><Plus size={17}/><span>Новое обращение</span></button><button className="icon-button mobile-only" aria-label="Открыть профиль" onClick={()=>setAccountOpen(true)}><Menu size={20}/></button></header>
  <aside className="sidebar"><label className="org-select"><span className="sr-only">Организация</span><select aria-label="Организация" value={orgId} onChange={e=>{generation.current++;setSelected(null);setDetail(null);setOrgId(e.target.value)}}>{session.organizations.map(o=><option key={o.id} value={o.id}>{o.name}</option>)}</select></label><nav>{nav.map(([key,label,Icon])=><button key={key} className={view===key?'active':''} onClick={()=>{setView(key);setMobileDetail(false);setError('');if(key==='checks')void guarded(async()=>setChecks(await api.checks(orgId)),'',false)}}><Icon size={20}/><span>{label}</span></button>)}</nav><div className="user-block"><span className="avatar small color-1">ОД</span><div><b>{session.user.name}</b>{org?.is_demo?<select aria-label="Роль в демо" value={org.role} disabled={busy} onChange={e=>void guarded(async()=>{await api.role(orgId,e.target.value as Role);setSession(await api.session())},'',false)}><option value="operator">Оператор</option><option value="owner">Администратор</option><option value="viewer">Наблюдатель</option></select>:<span>{org?.role}</span>}</div><button className="icon-button" aria-label="Выйти" onClick={()=>void guarded(async()=>{await api.logout();generation.current++;setSession(null);setOrgId('');setDetail(null);setTickets([])},'',false)}><LogOut size={17}/></button></div></aside>
  <main className={'workspace '+(view!=='tickets'?'single-page':'')} aria-busy={busy}>
   {error&&<div className="toast error" role="alert">{error}<button onClick={()=>setError('')} aria-label="Скрыть ошибку">×</button></div>}
   {notice&&<div className="toast success" role="status">{notice}<button onClick={()=>setNotice('')} aria-label="Скрыть уведомление">×</button></div>}
   {view==='tickets'?<><Inbox tickets={tickets} selected={selected} onSelect={choose}/>{detail&&org?<TicketView key={orgId+'-'+detail.id} ticket={detail} role={org.role} busy={busy} onBack={()=>setMobileDetail(false)}
    analyze={()=>guarded(()=>api.analyze(orgId,detail.id))}
    approve={confirmed=>guarded(()=>api.approve(orgId,detail.proposal!.id,detail.proposal!.fingerprint,confirmed),'Заявка на возврат создана')}
    reject={()=>guarded(()=>api.reject(orgId,detail.proposal!.id),'Предложение отклонено')}
    reply={text=>act(()=>api.reply(orgId,detail.id,text),'Ответ сохранён в переписке').then(()=>{})}/>:<div className="empty detail-empty">{selected?'Загружаем обращение…':'Создайте первое обращение'}</div>}</>:
    view==='orders'?<OrdersPage orders={orders}/>:view==='knowledge'?<KnowledgePage documents={documents} role={org?.role||'viewer'} busy={busy} save={body=>act(()=>api.saveKnowledge(orgId,body),'Правила обновлены').then(()=>{})}/>:view==='audit'?<AuditPage audit={history}/>:<ChecksPage checks={checks} busy={busy} refresh={()=>void guarded(async()=>setChecks(await api.checks(orgId)),'Проверки завершены',false)}/>}
  </main>{newTicket&&<NewTicket orders={orders} busy={busy} close={()=>setNewTicket(false)} save={body=>act(async()=>{const ticket=await api.create(orgId,body);setSelected(ticket.id);setMobileDetail(true);setView('tickets');setNewTicket(false)},'Обращение создано').then(()=>{})}/>}
 {accountOpen&&<Modal title="Рабочее пространство" close={()=>setAccountOpen(false)}>
  <div className="account-settings">
   <label>Организация<select aria-label="Организация в профиле" value={orgId} onChange={e=>{generation.current++;setSelected(null);setDetail(null);setOrgId(e.target.value)}}>
    {session.organizations.map(o=><option key={o.id} value={o.id}>{o.name}</option>)}
   </select></label>
   {org?.is_demo&&<label>Роль<select aria-label="Роль в профиле" value={org.role} disabled={busy} onChange={e=>void guarded(async()=>{await api.role(orgId,e.target.value as Role);setSession(await api.session())},'',false)}>
    <option value="operator">Оператор</option><option value="owner">Администратор</option><option value="viewer">Наблюдатель</option>
   </select></label>}
   <button className="secondary" disabled={busy} onClick={()=>void guarded(async()=>{await api.logout();generation.current++;setAccountOpen(false);setSession(null);setOrgId('');setDetail(null);setTickets([])},'',false)}><LogOut size={16}/>Выйти</button>
  </div>
 </Modal>}
 </div>
}
