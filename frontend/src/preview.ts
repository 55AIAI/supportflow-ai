/* Static visual sandbox only. Server authorization is implemented and tested in Python. */
import type {Session,Detail,Knowledge,Order} from './types';
type Store={session:Session;organizations:Record<string,{tickets:Detail[];knowledge:Knowledge[];orders:Order[];audit:any[]}>};
let store:Store|null=null;
try{store=JSON.parse(sessionStorage.getItem('sf-preview')||'null')}catch{/* empty sandbox */}
const save=()=>sessionStorage.setItem('sf-preview',JSON.stringify(store));
const stamp=()=>Math.floor(Date.now()/1000);
const id=()=>crypto.randomUUID();
function seed(){
 const organizations:Store['organizations']={};
 for(const [org,name,days] of [['aster','Aster Store',14],['north','North Supply',30]] as const){
  const knowledge:Knowledge[]=[{id:org+'-policy',kind:'returns',title:'Правила возврата · п. 2.1',body:`Неиспользованный товар можно вернуть в течение ${days} дней после доставки.`,return_days:days,version:1},
    {id:org+'-delivery',kind:'delivery',title:'Доставка · п. 1.2',body:'После передачи заказа перевозчику статус доставки обновляется в карточке заказа.',return_days:null,version:1}];
  const names=['Алина К.','Данияр С.','Мария Е.','Игорь И.','Наталья П.','Артём Р.'];
  const subjects=['Возврат заказа №1042','Вопрос по доставке','Не работает промокод','Обмен товара','Повреждена упаковка','Вопрос по гарантии'];
  const keys=['alina','daniyar','maria','igor','natalia','artem'];
  const refs=['1042','1037','1038','1039','1031','1040'];
  const orders:Order[]=refs.map((reference,i)=>({id:org+'-o'+i,org_id:org,reference,customer_key:keys[i],product:['Беспроводные наушники','Настольная лампа','Рюкзак','Клавиатура','Увлажнитель','Монитор'][i],amount_minor:[2490000,1890000,1590000,3290000,2790000,9990000][i],currency:'KZT',status:i===1?'shipped':'delivered',delivered_at:i===1?null:stamp()-[7,0,25,2,4,5][i]*86400,return_eligible:i!==4,version:1}));
  const messages=['Здравствуйте! Хочу вернуть наушники из заказа №1042. Упаковка целая, товаром не пользовалась.','Где сейчас находится мой заказ №1037?','Промокод SUMMER24 не применяется. Помогите разобраться.','Можно ли обменять клавиатуру на другую модель?','Заказ пришёл с повреждённой упаковкой. Хочу оформить возврат.','Сколько действует гарантия на мой монитор?'];
  const tickets:Detail[]=subjects.map((subject,i)=>({id:org+'-t'+i,org_id:org,subject,customer_name:names[i],customer_key:keys[i],message:messages[i],order_id:orders[i].id,status:'open',category:'general',draft:'',escalation:'',sources:[],version:1,current_job:null,created_at:stamp()-i*3600,updated_at:stamp(),messages:[{id:id(),author:'customer',body:messages[i],created_at:stamp()-i*3600}],order:orders[i],proposal:null,job:null}));
  organizations[org]={tickets,knowledge,orders,audit:[]};
 }
 store={session:{user:{id:'preview',name:'Оператор Демо',email:'demo@example.test'},csrf_token:'preview',organizations:[{id:'aster',name:'Aster Store',role:'operator',is_demo:true},{id:'north',name:'North Supply',role:'operator',is_demo:true}]},organizations};save();
}
export async function preview(path:string,method:string,body:any):Promise<any>{
 if(path==='/config')return{demo_available:true,provider:'browser-demo',authenticated:!!store};
 if(path==='/demo'){seed();return structuredClone(store!.session)}
 if(!store)throw new Error('Начните демо-сессию');
 if(path==='/auth/session')return structuredClone(store.session);
 if(path==='/auth/logout'){store=null;sessionStorage.removeItem('sf-preview');return{ok:true}}
 const parts=path.split('/'),org=parts[2],resource=parts[3],entity=parts[4],operation=parts[5];
 const scope=store.organizations[org],member=store.session.organizations.find(o=>o.id===org);
 if(!scope||!member)throw new Error('Организация не найдена');
 if(method!=='GET'&&member.role==='viewer'&&resource!=='demo-role')throw new Error('Недостаточно прав');
 const event=(name:string)=>{scope.audit.unshift({id:id(),actor:'preview',event:name,entity_id:entity||org,detail:{},created_at:stamp()})};
 let result:any;
 if(resource==='demo-role'){member.role=body.role;result={role:member.role}}
 else if(resource==='orders')result=scope.orders;
 else if(resource==='knowledge'){
   if(method==='GET')result=scope.knowledge;
   else{
    if(member.role!=='owner')throw new Error('Недостаточно прав');
    const doc=scope.knowledge.find(d=>d.kind===body.kind);
    if(!doc||doc.version!==body.expected_version)throw new Error('Правила изменились');
    Object.assign(doc,body,{version:doc.version+1,body:body.kind==='returns'?`Неиспользованный товар можно вернуть в течение ${body.return_days} дней после доставки.`:body.body});
    event('knowledge.updated');result=doc;
   }
 }else if(resource==='audit')result=scope.audit;
 else if(resource==='checks')result={scope:'browser-preview',total:0,passed:0,results:[]};
 else if(resource==='tickets'){
  if(!entity&&method==='GET')result=scope.tickets;
  else if(!entity){
   const order=scope.orders.find(o=>o.reference===body.order_reference)||null;
   if(body.order_reference&&(!order||order.customer_key!==body.customer_key))throw new Error('Заказ не принадлежит клиенту');
   const ticket:Detail={...body,id:id(),org_id:org,order_id:order?.id||null,status:'open',category:'general',draft:'',escalation:'',sources:[],version:1,current_job:null,created_at:stamp(),updated_at:stamp(),order,proposal:null,job:null,messages:[{id:id(),author:'customer',body:body.message,created_at:stamp()}]};
   scope.tickets.unshift(ticket);event('ticket.created');result=ticket;
  }else{
   const ticket=scope.tickets.find(t=>t.id===entity);if(!ticket)throw new Error('Обращение не найдено');
   if(!operation)result=ticket;
   else if(operation==='analyze'){
    const returns=/возврат|вернуть|return|refund/i.test(ticket.subject+' '+ticket.message);
    const doc=scope.knowledge.find(d=>d.kind===(returns?'returns':'delivery')),order=ticket.order;
    const eligible=returns&&order&&doc&&order.status==='delivered'&&order.return_eligible&&stamp()-(order.delivered_at||0)<=(doc.return_days||0)*86400;
    ticket.version++;ticket.status='review';ticket.category=returns?'returns':'delivery';
    ticket.sources=doc?[{document_id:doc.id,version:doc.version,title:doc.title,quote:doc.body}]:[];
    ticket.escalation=returns&&!eligible?'Нужна ручная проверка условий':'';
    ticket.draft=eligible?`Здравствуйте! Возврат заказа №${order!.reference} возможен по правилам магазина. ${doc!.body} Оператор проверит условия и подтвердит дальнейшие действия.`:'Здравствуйте! Оператор проверит детали вашего обращения и подготовит дальнейший ответ.';
    if(eligible&&ticket.proposal?.state!=='approved')ticket.proposal={id:id(),fingerprint:'a'.repeat(64),state:'pending',expires_at:stamp()+900,payload:{order_reference:order!.reference,amount_minor:order!.amount_minor,currency:order!.currency}};
    ticket.job={id:id(),state:'completed',error:'',attempts:1};event('analysis.completed');result=ticket.job;
   }else if(operation==='reply'){ticket.messages.push({id:id(),author:'operator',body:body.body,created_at:stamp()});ticket.status='closed';ticket.version++;event('reply.saved');result=ticket}
  }
 }else if(resource==='proposals'){
  const ticket=scope.tickets.find(t=>t.proposal?.id===entity);if(!ticket||!ticket.proposal)throw new Error('Предложение не найдено');
  if(operation==='approve'){
   if(!body.confirmed_unused)throw new Error('Подтвердите проверку товара');
   if(ticket.proposal.state==='pending'){ticket.proposal.state='approved';ticket.version++;ticket.draft=`Здравствуйте! Заявка на возврат заказа №${ticket.order!.reference} создана. Оператор сообщит дальнейшие инструкции.`;event('return.requested')}
  }else{ticket.proposal.state='rejected';event('proposal.rejected')}
  result={ok:true};
 }
 if(result===undefined)throw new Error('Операция недоступна в визуальном демо');
 save();return structuredClone(result);
}
