"""Декоратори класів."""

import functools
import inspect
import time


def auto_repr(cls):
    """Декоратор класу: додає __repr__ на основі __init__ параметрів."""
    # inspect.unwrap знімає обгортки functools.wraps (напр. від @frozen),
    # тож auto_repr бачить параметри ОРИГІНАЛЬНОГО __init__.
    init = inspect.unwrap(cls.__init__)
    code = init.__code__
    # co_varnames містить і локальні змінні, тому беремо лише аргументи
    params = code.co_varnames[1:code.co_argcount + code.co_kwonlyargcount]

    def __repr__(self):
        values = ", ".join(f"{p}={getattr(self, p, '?')!r}" for p in params)
        return f"{type(self).__name__}({values})"

    cls.__repr__ = __repr__
    return cls


def frozen(cls):
    """Декоратор класу: забороняє зміну атрибутів після __init__.

    Після ініціалізації будь-яка спроба змінити атрибут
    викликає AttributeError.
    """
    original_init = cls.__init__

    @functools.wraps(original_init)
    def __init__(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        # Обходимо власний __setattr__, щоб встановити прапорець
        object.__setattr__(self, "_frozen", True)

    def __setattr__(self, name, value):
        if getattr(self, "_frozen", False):
            raise AttributeError(
                f"{type(self).__name__} заморожений: неможливо змінити '{name}'"
            )
        object.__setattr__(self, name, value)

    def __delattr__(self, name):
        if getattr(self, "_frozen", False):
            raise AttributeError(
                f"{type(self).__name__} заморожений: неможливо видалити '{name}'"
            )
        object.__delattr__(self, name)

    cls.__init__ = __init__
    cls.__setattr__ = __setattr__
    cls.__delattr__ = __delattr__
    return cls


def log_methods(cls):
    """Декоратор класу: логує виклики всіх публічних методів."""
    for name, attr in list(vars(cls).items()):
        if name.startswith("_") or not inspect.isfunction(attr):
            continue

        def make_wrapper(method):
            @functools.wraps(method)
            def wrapper(self, *args, **kwargs):
                params = ", ".join(
                    [repr(a) for a in args] + [f"{k}={v!r}" for k, v in kwargs.items()]
                )
                call = f"{cls.__name__}.{method.__name__}({params})"
                start = time.perf_counter()
                try:
                    result = method(self, *args, **kwargs)
                except Exception as exc:
                    print(f"  [LOG] {call} ✗ {type(exc).__name__}: {exc}")
                    raise
                ms = (time.perf_counter() - start) * 1000
                print(f"  [LOG] {call} → {result!r} ({ms:.3f} мс)")
                return result
            return wrapper

        setattr(cls, name, make_wrapper(attr))
    return cls


@auto_repr
class Point:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y

    def distance_to(self, other: "Point") -> float:
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5


@frozen
class ImmutableConfig:
    def __init__(self, host: str, port: int, debug: bool = False):
        self.host = host
        self.port = port
        self.debug = debug


@log_methods
class MathService:
    def add(self, a: float, b: float) -> float:
        return a + b

    def multiply(self, a: float, b: float) -> float:
        return a * b

    def divide(self, a: float, b: float) -> float:
        if b == 0:
            raise ValueError("Ділення на нуль")
        return a / b

    def _internal_helper(self) -> str:
        return "приватний метод — не логується"


# Комбінування всіх трьох декораторів
@auto_repr
@frozen
@log_methods
class Money:
    def __init__(self, amount: float, currency: str = "UAH"):
        self.amount = amount
        self.currency = currency

    def convert(self, rate: float, to: str) -> "Money":
        return Money(round(self.amount * rate, 2), to)

    def add(self, other: "Money") -> "Money":
        if other.currency != self.currency:
            raise ValueError(f"Різні валюти: {self.currency} і {other.currency}")
        return Money(self.amount + other.amount, self.currency)


def main():
    print("=== @auto_repr ===")
    p = Point(3.0, 4.0)
    print(repr(p))  # Point(x=3.0, y=4.0)
    print(f"Відстань до {Point(0, 0)!r}: {p.distance_to(Point(0, 0))}")
    print(f"Інші методи не змінено: distance_to = {Point.distance_to.__qualname__}")

    print("\n=== @frozen ===")
    cfg = ImmutableConfig("localhost", 8080, debug=True)
    print(f"Config: {cfg.host}:{cfg.port}, debug={cfg.debug}")
    try:
        cfg.host = "remote"  # має викинути AttributeError
    except AttributeError as e:
        print(f"Очікувана помилка: {e}")
    try:
        cfg.new_attr = 1
    except AttributeError as e:
        print(f"Очікувана помилка: {e}")
    try:
        del cfg.port
    except AttributeError as e:
        print(f"Очікувана помилка: {e}")
    print(f"Значення не змінилися: {cfg.host}:{cfg.port}")

    print("\n=== @log_methods ===")
    svc = MathService()
    svc.add(10, 20)
    svc.multiply(3, 7)
    try:
        svc.divide(10, 0)
    except ValueError:
        pass
    print(f"  _internal_helper без логування: {svc._internal_helper()}")
    print(f"  wraps зберіг ім'я методу: {MathService.add.__name__}")

    print("\n=== Комбінація @auto_repr + @frozen + @log_methods ===")
    wallet = Money(100, "UAH")
    print(f"  repr: {wallet!r}")
    usd = wallet.convert(0.024, to="USD")
    print(f"  результат: {usd!r}")
    try:
        wallet.amount = 1_000_000
    except AttributeError as e:
        print(f"  frozen: {e}")
    try:
        wallet.add(usd)
    except ValueError:
        pass


if __name__ == "__main__":
    main()
