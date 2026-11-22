"""Декоратори функцій з параметрами."""

import functools
import time


def cache(max_size: int = 128):
    """Декоратор кешування результатів функції (спрощений LRU-кеш).

    Args:
        max_size: максимальна кількість закешованих результатів.
    """
    def decorator(func):
        _cache = {}
        _call_order = []          # від найдавніше використаного до найсвіжішого
        stats = {"hits": 0, "misses": 0, "evictions": 0}
        depth = 0                 # глибина рекурсії: друкуємо лише зовнішні виклики

        @functools.wraps(func)
        def wrapper(*args):
            nonlocal depth
            call = f"{func.__name__}({', '.join(map(repr, args))})"
            if args in _cache:
                stats["hits"] += 1
                _call_order.remove(args)       # LRU: запис став «свіжим»
                _call_order.append(args)
                if depth == 0:
                    print(f"  cache hit:  {call}")
                return _cache[args]

            stats["misses"] += 1
            depth += 1
            try:
                result = func(*args)
            finally:
                depth -= 1

            _cache[args] = result
            _call_order.append(args)
            if len(_cache) > max_size:
                oldest = _call_order.pop(0)
                del _cache[oldest]
                stats["evictions"] += 1
            if depth == 0:
                print(f"  cache miss: {call} "
                      f"(усього hits={stats['hits']}, misses={stats['misses']})")
            return result

        wrapper.cache_info = lambda: {
            "size": len(_cache), "max_size": max_size, **stats,
        }

        def _clear():
            _cache.clear()
            _call_order.clear()
            stats.update(hits=0, misses=0, evictions=0)

        wrapper.cache_clear = _clear
        return wrapper
    return decorator


def rate_limit(max_calls: int, period: float = 60.0):
    """Декоратор обмеження частоти викликів функції.

    Args:
        max_calls: максимальна кількість викликів за період.
        period: тривалість періоду в секундах.
    """
    def decorator(func):
        call_times = []

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            now = time.monotonic()
            # Залишаємо лише виклики в межах «ковзного вікна» period
            while call_times and now - call_times[0] >= period:
                call_times.pop(0)
            if len(call_times) >= max_calls:
                wait = period - (now - call_times[0])
                raise RuntimeError(
                    f"{func.__name__}: перевищено ліміт {max_calls} викликів "
                    f"за {period} с, повторіть через {wait:.1f} с"
                )
            call_times.append(now)
            return func(*args, **kwargs)

        wrapper.remaining = lambda: max_calls - sum(
            1 for t in call_times if time.monotonic() - t < period
        )
        return wrapper
    return decorator


def log(level: str = "INFO"):
    """Декоратор логування виклику функції з зазначенням рівня.

    Args:
        level: рівень логування (DEBUG, INFO, WARNING, ERROR).
    """
    allowed = ("DEBUG", "INFO", "WARNING", "ERROR")
    level = level.upper()
    if level not in allowed:
        raise ValueError(f"Невідомий рівень '{level}', допустимі: {allowed}")

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            params = [repr(a) for a in args] + [f"{k}={v!r}" for k, v in kwargs.items()]
            print(f"  [{level}] Виклик {func.__name__}({', '.join(params)})")
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
            except Exception as exc:
                elapsed = time.perf_counter() - start
                print(f"  [ERROR] {func.__name__} → {type(exc).__name__}: {exc} "
                      f"(час: {elapsed:.4f}с)")
                raise
            elapsed = time.perf_counter() - start
            print(f"  [{level}] {func.__name__} → {result!r} (час: {elapsed:.4f}с)")
            return result

        return wrapper
    return decorator


@cache(max_size=64)
def fibonacci(n: int) -> int:
    """Обчислює n-е число Фібоначчі рекурсивно."""
    if n < 2:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)


@cache(max_size=3)
def slow_square(x: int) -> int:
    """Повільне піднесення до квадрата (для демонстрації витіснення з кешу)."""
    time.sleep(0.05)
    return x * x


@rate_limit(max_calls=5, period=10.0)
def send_notification(message: str) -> str:
    """Імітує відправку сповіщення."""
    return f"Надіслано: {message}"


@rate_limit(max_calls=2, period=0.5)
def ping() -> str:
    """Короткий ліміт — щоб показати відновлення після закінчення періоду."""
    return "pong"


@log(level="DEBUG")
def divide(a: float, b: float) -> float:
    """Ділення з можливим ZeroDivisionError."""
    return a / b


def main():
    print("=== @cache ===")
    start = time.perf_counter()
    result = fibonacci(30)
    elapsed = time.perf_counter() - start
    print(f"fibonacci(30) = {result} за {elapsed * 1000:.2f} мс")
    print(f"cache_info: {fibonacci.cache_info()}")
    fibonacci(30)          # повторний виклик — одразу з кешу
    fibonacci(35)          # використовує вже обчислені 0..30
    print(f"cache_info: {fibonacci.cache_info()}")

    print("\nОбмеження розміру (max_size=3, LRU):")
    for x in (1, 2, 3, 1, 4, 2):
        slow_square(x)
    print(f"cache_info: {slow_square.cache_info()}")
    print("  (2 витіснено, бо 1 був використаний пізніше; тому slow_square(2) — miss)")

    print(f"\nfunctools.wraps зберіг метадані: "
          f"{fibonacci.__name__!r}, doc={fibonacci.__doc__!r}")

    print("\n=== @rate_limit(max_calls=5, period=10.0) ===")
    for i in range(1, 7):
        try:
            print(f"  {i}. {send_notification(f'Повідомлення #{i}')}")
        except RuntimeError as e:
            print(f"  {i}. RuntimeError: {e}")

    print("\nВідновлення після закінчення періоду (ping: 2 виклики за 0.5 с):")
    for i in range(1, 4):
        try:
            print(f"  {i}. {ping()}")
        except RuntimeError as e:
            print(f"  {i}. RuntimeError: {e}")
    time.sleep(0.55)
    print(f"  після паузи 0.55 с: {ping()}")

    print("\n=== @log(level='DEBUG') ===")
    divide(10, 3)
    try:
        divide(10, 0)
    except ZeroDivisionError:
        print("  ZeroDivisionError оброблено у main()")
    divide(a=7, b=2)


if __name__ == "__main__":
    main()
