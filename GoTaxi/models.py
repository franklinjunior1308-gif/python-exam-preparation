"""OOP core of the GoTaxi educational prototype. No external services."""
from dataclasses import dataclass, field
from datetime import datetime
from math import ceil
from uuid import uuid4

SERVICES = {
    "taxi": ("Такси", 80, 22, "🚕"),
    "delivery": ("Доставка", 70, 17, "📦"),
    "cargo": ("Грузоперевозки", 280, 55, "🚚"),
    "sprinter": ("Спринтер", 850, 85, "🚐"),
    "bus": ("Автобус", 1500, 125, "🚌"),
    "food": ("Доставка еды", 90, 16, "🍔"),
}

RESTAURANTS = [
    {"name": "Демо: Городское кафе", "category": "Кафе", "note": "Пример, не реальное заведение"},
    {"name": "Демо: Азия Кухня", "category": "Ресторан", "note": "Пример, не реальное заведение"},
    {"name": "Демо: Пицца Парк", "category": "Пиццерия", "note": "Пример, не реальное заведение"},
]


@dataclass
class Customer:
    name: str = "Гость GoTaxi"
    bonuses: int = 120
    cards: list = field(default_factory=list)  # Only mock labels, never actual card data

    def add_mock_card(self, label: str):
        label = label.strip()
        if not label or len(label) > 25:
            raise ValueError("Введите короткое название демо-карты (до 25 символов)")
        if label not in self.cards:
            self.cards.append(label)

    def add_bonus(self, points: int):
        self.bonuses += max(0, points)


@dataclass
class ServiceOrder:
    order_id: str
    service: str
    origin: str
    destination: str
    distance_km: float
    passengers: int
    base_price: int
    discount: int
    bonuses_used: int
    final_price: int
    created_at: str
    status: str = "создан"
    rating: int | None = None


class FarePolicy:
    """Fixed example multipliers, NOT a real-time supply-and-demand price model."""
    @staticmethod
    def level(hour: int):
        if 7 <= hour < 10 or 17 <= hour < 21:
            return "Высокий спрос", 1.4, "peak"
        if 0 <= hour < 7:
            return "Выгодное время", 0.8, "cheap"
        return "Обычный тариф", 1.0, "normal"

    def quote(self, service: str, distance_km: float, hour: int):
        if service not in SERVICES:
            raise ValueError("Неизвестный тип услуги")
        if distance_km <= 0 or distance_km > 1500:
            raise ValueError("Дистанция должна быть от 0 до 1500 км")
        _, start, per_km, _ = SERVICES[service]
        label, coefficient, kind = self.level(hour)
        amount = ceil((start + distance_km * per_km) * coefficient)
        return amount, label, kind


class GoTaxiSystem:
    def __init__(self):
        self.customer = Customer()
        self.fares = FarePolicy()
        self.orders: dict[str, ServiceOrder] = {}

    def book(self, service, origin, destination, distance_km, passengers=1, promo="", use_bonuses=0):
        origin, destination = origin.strip(), destination.strip()
        if not origin or not destination:
            raise ValueError("Укажите адрес отправления и назначения")
        if len(origin) > 120 or len(destination) > 120:
            raise ValueError("Адрес слишком длинный")
        if origin.casefold() == destination.casefold():
            raise ValueError("Начальная и конечная точки должны отличаться")
        if passengers < 1 or passengers > 50:
            raise ValueError("Количество пассажиров: от 1 до 50")
        if service == "taxi" and passengers > 4:
            raise ValueError("В обычном такси не более 4 пассажиров")
        if service in ("delivery", "food", "cargo") and passengers != 1:
            raise ValueError("Для доставки количество пассажиров не применяется")
        now = datetime.now()
        base, _, _ = self.fares.quote(service, distance_km, now.hour)
        promo = promo.strip().upper()
        if promo and promo != "GO10":
            raise ValueError("Промокод не найден. Для демо используйте GO10")
        discount = ceil(base * 0.10) if promo == "GO10" else 0
        after_discount = max(0, base - discount)
        if use_bonuses < 0:
            raise ValueError("Бонусы не могут быть отрицательными")
        bonuses_used = min(use_bonuses, self.customer.bonuses, after_discount // 2)
        final_price = after_discount - bonuses_used
        # Mutations only happen after all validations
        self.customer.bonuses -= bonuses_used
        order = ServiceOrder(
            order_id=uuid4().hex[:8].upper(), service=service,
            origin=origin, destination=destination, distance_km=distance_km,
            passengers=passengers, base_price=base, discount=discount,
            bonuses_used=bonuses_used, final_price=final_price,
            created_at=now.strftime("%d.%m.%Y %H:%M"),
        )
        self.orders[order.order_id] = order
        return order

    def complete(self, order_id: str):
        order = self.orders.get(order_id)
        if order is None:
            raise ValueError("Заказ не найден")
        if order.status != "создан":
            raise ValueError("Заказ уже обработан")
        order.status = "выполнен"
        self.customer.add_bonus(order.final_price // 20)  # 5% demo reward
        return order

    def rate(self, order_id: str, rating: int):
        order = self.orders.get(order_id)
        if order is None or order.status != "выполнен":
            raise ValueError("Оценить можно только выполненный заказ")
        if order.rating is not None:
            raise ValueError("Вы уже оценили этот заказ")
        if rating not in range(1, 6):
            raise ValueError("Оценка должна быть от 1 до 5")
        order.rating = rating
        return order
