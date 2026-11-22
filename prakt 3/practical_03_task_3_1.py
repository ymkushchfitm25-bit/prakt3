"""Паттерни Singleton та Factory Method."""

import json
import threading
from abc import ABC, abstractmethod
from datetime import datetime


class SingletonMeta(type):
    """Метаклас для реалізації патерну Singleton."""

    _instances: dict[type, object] = {}
    _lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        # Подвійна перевірка з блокуванням — безпечно і в багатопотоковому коді
        if cls not in cls._instances:
            with cls._lock:
                if cls not in cls._instances:
                    cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class LogFormatter(ABC):
    """Абстрактний базовий клас форматера логів."""

    @abstractmethod
    def format(self, level: str, message: str, timestamp: datetime) -> str:
        """Форматувати повідомлення логу."""
        ...


class PlainFormatter(LogFormatter):
    """Простий текстовий формат: [РІВЕНЬ] ЧАС - Повідомлення"""

    def format(self, level: str, message: str, timestamp: datetime) -> str:
        return f"[{level}] {timestamp:%Y-%m-%d %H:%M:%S} - {message}"


class JSONFormatter(LogFormatter):
    """JSON-формат: {"level": "...", "time": "...", "message": "..."}"""

    def format(self, level: str, message: str, timestamp: datetime) -> str:
        return json.dumps(
            {"level": level, "time": timestamp.isoformat(timespec="seconds"), "message": message},
            ensure_ascii=False,
        )


class ColorFormatter(LogFormatter):
    """Кольоровий формат для терміналу (ANSI-коди).

    DEBUG=сірий, INFO=зелений, WARNING=жовтий, ERROR=червоний.
    """

    COLORS = {
        "DEBUG": "\033[90m",
        "INFO": "\033[92m",
        "WARNING": "\033[93m",
        "ERROR": "\033[91m",
    }
    RESET = "\033[0m"

    def format(self, level: str, message: str, timestamp: datetime) -> str:
        color = self.COLORS.get(level, "")
        return f"{color}{timestamp:%H:%M:%S} {level:<7}{self.RESET} {message}"


class FormatterFactory:
    """Фабрика форматерів із підтримкою реєстрації нових типів."""

    _formatters: dict[str, type[LogFormatter]] = {
        "plain": PlainFormatter,
        "json": JSONFormatter,
        "color": ColorFormatter,
    }

    @classmethod
    def register(cls, name: str, formatter_cls: type[LogFormatter]):
        """Зареєструвати новий тип форматера."""
        if not (isinstance(formatter_cls, type) and issubclass(formatter_cls, LogFormatter)):
            raise TypeError(f"{formatter_cls!r} не є підкласом LogFormatter")
        cls._formatters[name] = formatter_cls

    @classmethod
    def create(cls, name: str) -> LogFormatter:
        """Створити форматер за іменем. Викинути ValueError, якщо невідомий."""
        try:
            return cls._formatters[name]()
        except KeyError:
            raise ValueError(
                f"Невідомий форматер '{name}'. Доступні: {', '.join(cls.available())}"
            ) from None

    @classmethod
    def available(cls) -> list[str]:
        """Повернути список доступних форматерів."""
        return list(cls._formatters)


class Logger(metaclass=SingletonMeta):
    """Логер із підтримкою рівнів та змінних форматерів."""

    LEVELS = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3}

    def __init__(self, formatter_name: str = "plain", min_level: str = "DEBUG"):
        self._formatter = FormatterFactory.create(formatter_name)
        self._formatter_name = formatter_name
        self._min_level = self._check_level(min_level)
        self._log_history: list[str] = []

    def _check_level(self, level: str) -> str:
        level = level.upper()
        if level not in self.LEVELS:
            raise ValueError(f"Невідомий рівень '{level}'. Допустимі: {list(self.LEVELS)}")
        return level

    def set_formatter(self, name: str):
        self._formatter = FormatterFactory.create(name)
        self._formatter_name = name

    def set_min_level(self, level: str):
        self._min_level = self._check_level(level)

    def log(self, level: str, message: str):
        level = self._check_level(level)
        if self.LEVELS[level] < self.LEVELS[self._min_level]:
            return  # нижче мінімального рівня — не виводимо
        line = self._formatter.format(level, message, datetime.now())
        print(line)
        self._log_history.append(line)

    def debug(self, msg: str):
        self.log("DEBUG", msg)

    def info(self, msg: str):
        self.log("INFO", msg)

    def warning(self, msg: str):
        self.log("WARNING", msg)

    def error(self, msg: str):
        self.log("ERROR", msg)

    def get_history(self) -> list[str]:
        return self._log_history[:]


# Новий форматер додається БЕЗ зміни коду фабрики (Open/Closed principle)
class CSVFormatter(LogFormatter):
    """CSV-формат: час;рівень;повідомлення"""

    def format(self, level: str, message: str, timestamp: datetime) -> str:
        safe = message.replace('"', '""')
        return f'{timestamp:%Y-%m-%d %H:%M:%S};{level};"{safe}"'


def main():
    print("=== Singleton ===")
    logger1 = Logger("plain", "DEBUG")
    logger2 = Logger("json", "INFO")
    print(f"Singleton: {logger1 is logger2}")  # True
    print(f"id(logger1) = {id(logger1)}, id(logger2) = {id(logger2)}")
    print(f"Аргументи другого виклику ігноруються: форматер = '{logger2._formatter_name}'")

    # Перевірка з кількох потоків
    found = set()
    threads = [threading.Thread(target=lambda: found.add(id(Logger()))) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    print(f"10 потоків отримали {len(found)} унікальний(их) екземпляр(ів)")

    print("\n=== Рівні логування (plain) ===")
    logger1.info("Система запущена")
    logger1.warning("Мало пам'яті")
    logger1.error("Помилка з'єднання")

    print("\n=== Зміна форматера через фабрику ===")
    logger1.set_formatter("json")
    logger1.debug("Діагностика")
    logger1.info("Користувач увійшов")

    logger1.set_formatter("color")
    for level in Logger.LEVELS:
        logger1.log(level, f"Кольорове повідомлення рівня {level}")

    print("\n=== Фільтр за мінімальним рівнем (WARNING) ===")
    logger1.set_formatter("plain")
    logger1.set_min_level("WARNING")
    logger1.debug("Це не буде виведено")
    logger1.info("І це теж")
    logger1.warning("А це буде")
    logger1.set_min_level("DEBUG")

    print("\n=== Реєстрація нового форматера (Open/Closed) ===")
    FormatterFactory.register("csv", CSVFormatter)
    logger2.set_formatter("csv")          # logger2 — той самий об'єкт
    logger1.info('Звіт "Q4" збережено')

    print("\n=== Помилки фабрики ===")
    try:
        FormatterFactory.create("xml")
    except ValueError as e:
        print(f"ValueError: {e}")
    try:
        FormatterFactory.register("bad", dict)
    except TypeError as e:
        print(f"TypeError: {e}")

    print(f"\nФорматери: {FormatterFactory.available()}")
    print(f"Історія: {len(logger1.get_history())} записів")


if __name__ == "__main__":
    main()
