"""Deterministic policy contracts, not an LLM accuracy benchmark."""
from .agent import eligibility


def run_checks():
    timestamp = 2_000_000_000
    order = {"customer_key": "alina", "status": "delivered", "delivered_at": timestamp - 7*86400,
             "return_eligible": True}
    ticket, policy = {"customer_key": "alina"}, {"return_days": 14}
    cases = [
        ("Возврат в пределах срока", order, ticket, policy, True),
        ("Срок истёк", {**order, "delivered_at": timestamp - 15*86400}, ticket, policy, False),
        ("Точная граница 14 дней", {**order, "delivered_at": timestamp - 14*86400}, ticket, policy, True),
        ("Граница превышена на секунду", {**order, "delivered_at": timestamp - 14*86400 - 1}, ticket, policy, False),
        ("Заказ не доставлен", {**order, "status": "shipped"}, ticket, policy, False),
        ("Нет даты доставки", {**order, "delivered_at": None}, ticket, policy, False),
        ("Дата доставки в будущем", {**order, "delivered_at": timestamp + 1}, ticket, policy, False),
        ("Другой клиент", order, {"customer_key": "other"}, policy, False),
        ("Нет заказа", None, ticket, policy, False),
        ("Нет правил", order, ticket, None, False),
        ("Товар требует ручной проверки", {**order, "return_eligible": False}, ticket, policy, False),
        ("Другая организация: срок 3 дня", order, ticket, {"return_days": 3}, False)
    ]
    results = [{"name": name, "passed": eligibility(o, t, p, timestamp)[0] == expected}
               for name, o, t, p, expected in cases]
    return {"scope": "deterministic-policy", "results": results,
            "passed": sum(row["passed"] for row in results), "total": len(results)}
