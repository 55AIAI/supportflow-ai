from sqlalchemy import select
from .models import Organization, Membership, Order, Knowledge, Ticket, Message, now


def return_text(days):
    return f"Неиспользованный товар можно вернуть в течение {days} дней после доставки."


def seed_organization(db, user_id, name="Aster Store", days=14, role="owner"):
    org = Organization(name=name, is_demo=True)
    db.add(org)
    db.flush()
    db.add(Membership(org_id=org.id, user_id=user_id, role=role))
    knowledge = [
        Knowledge(org_id=org.id, kind="returns", title="Правила возврата · п. 2.1",
                  body=return_text(days), return_days=days),
        Knowledge(org_id=org.id, kind="delivery", title="Доставка · п. 1.2",
                  body="После передачи заказа перевозчику статус доставки обновляется в карточке заказа. Если срок истёк, оператор уточняет информацию."),
        Knowledge(org_id=org.id, kind="general", title="Гарантия · п. 3.1",
                  body="По вопросам гарантии оператор проверяет условия конкретного товара и документы заказа.")
    ]
    db.add_all(knowledge)
    rows = [
        ("1042", "alina", "Беспроводные наушники", 2490000, "delivered", 7, True),
        ("1037", "daniyar", "Настольная лампа", 1890000, "shipped", None, True),
        ("1038", "maria", "Рюкзак", 1590000, "delivered", 25, True),
        ("1039", "igor", "Клавиатура", 3290000, "delivered", 2, True),
        ("1031", "natalia", "Увлажнитель", 2790000, "delivered", 4, False),
        ("1040", "artem", "Монитор", 9990000, "delivered", 5, True),
    ]
    orders = {}
    for reference, key, product, amount, status, age, eligible in rows:
        order = Order(org_id=org.id, reference=reference, customer_key=key, product=product,
                      amount_minor=amount, status=status,
                      delivered_at=now() - age * 86400 if age is not None else None,
                      return_eligible=eligible)
        db.add(order)
        db.flush()
        orders[reference] = order
    tickets = [
        ("Возврат заказа №1042", "Алина К.", "alina", "1042",
         "Здравствуйте! Хочу вернуть наушники из заказа №1042. Упаковка целая, товаром не пользовалась."),
        ("Вопрос по доставке", "Данияр С.", "daniyar", "1037", "Где сейчас находится мой заказ №1037?"),
        ("Не работает промокод", "Мария Е.", "maria", "1038", "Промокод SUMMER24 не применяется. Помогите разобраться."),
        ("Обмен товара", "Игорь И.", "igor", "1039", "Можно ли обменять клавиатуру на другую модель?"),
        ("Повреждена упаковка", "Наталья П.", "natalia", "1031", "Заказ пришёл с повреждённой упаковкой. Хочу оформить возврат."),
        ("Вопрос по гарантии", "Артём Р.", "artem", "1040", "Сколько действует гарантия на мой монитор?")
    ]
    for i, (subject, name, key, reference, message) in enumerate(tickets):
        ticket = Ticket(org_id=org.id, subject=subject, customer_name=name, customer_key=key,
                        order_id=orders[reference].id, message=message, created_at=now() - i * 3600,
                        updated_at=now() - i * 3600)
        db.add(ticket)
        db.flush()
        db.add(Message(org_id=org.id, ticket_id=ticket.id, author="customer", body=message,
                       created_at=ticket.created_at))
    return org
