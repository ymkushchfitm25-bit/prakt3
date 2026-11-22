"""Система плагінів з автоматичною реєстрацією через метаклас."""

import hashlib
import re
from abc import abstractmethod


class PluginMeta(type):
    """Метаклас для автоматичної реєстрації та валідації плагінів.

    Кожен клас, створений з цим метакласом, автоматично додається
    до реєстру, якщо він визначає обов'язкові атрибути.
    """

    _registry: dict[str, type] = {}
    REQUIRED_ATTRS = ("name", "version")

    def __new__(mcs, cls_name: str, bases: tuple, namespace: dict):
        # Створюємо клас звичайним способом
        cls = super().__new__(mcs, cls_name, bases, namespace)

        # Базовий клас (без батьків) не реєструємо і не перевіряємо
        if not bases:
            return cls

        # 1. Обов'язкові атрибути мають бути визначені САМЕ в цьому класі
        missing = [attr for attr in mcs.REQUIRED_ATTRS if attr not in namespace]
        if missing:
            raise TypeError(
                f"Плагін '{cls_name}' не визначає обов'язкові атрибути: "
                f"{', '.join(missing)}"
            )

        # 2. Абстрактний метод execute має бути перевизначений
        execute = getattr(cls, "execute", None)
        if execute is None or getattr(execute, "__isabstractmethod__", False):
            raise TypeError(f"Плагін '{cls_name}' має реалізувати метод execute()")

        # 3. Ім'я плагіна має бути унікальним
        plugin_name = namespace["name"]
        if plugin_name in mcs._registry:
            existing = mcs._registry[plugin_name].__name__
            raise TypeError(
                f"Плагін з name='{plugin_name}' вже зареєстровано ({existing})"
            )

        mcs._registry[plugin_name] = cls
        return cls

    @classmethod
    def get_registry(mcs) -> dict[str, type]:
        """Повертає копію реєстру плагінів."""
        return dict(mcs._registry)

    @classmethod
    def create_plugin(mcs, plugin_name: str, *args, **kwargs):
        """Фабричний метод: створює екземпляр плагіна за його name."""
        try:
            plugin_cls = mcs._registry[plugin_name]
        except KeyError:
            available = ", ".join(mcs._registry) or "немає"
            raise ValueError(
                f"Невідомий плагін '{plugin_name}'. Доступні: {available}"
            ) from None
        return plugin_cls(*args, **kwargs)


class BasePlugin(metaclass=PluginMeta):
    """Базовий клас плагіна."""

    @abstractmethod
    def execute(self, data: str) -> str:
        """Обробити вхідні дані."""
        ...


class UpperPlugin(BasePlugin):
    """Перетворює текст у верхній регістр."""

    name = "upper"
    version = "1.0"

    def execute(self, data: str) -> str:
        return data.upper()


class ReversePlugin(BasePlugin):
    """Розвертає текст."""

    name = "reverse"
    version = "1.0"

    def execute(self, data: str) -> str:
        return data[::-1]


class CensorPlugin(BasePlugin):
    """Замінює задані слова на '***' (без урахування регістру)."""

    name = "censor"
    version = "1.1"

    def __init__(self, banned_words: tuple[str, ...] = ("світ", "погано")):
        self.banned_words = banned_words
        pattern = "|".join(re.escape(w) for w in banned_words)
        self._regex = re.compile(rf"\b({pattern})\b", re.IGNORECASE)

    def execute(self, data: str) -> str:
        return self._regex.sub("***", data)


# Динамічне створення класу через type() у тризначній формі:
#   type(ім'я_класу, кортеж_батьків, словник_атрибутів)
def _hash_execute(self, data: str) -> str:
    """Повертає SHA-256 хеш рядка (перші 16 символів)."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]


HashPlugin = type(
    "HashPlugin",
    (BasePlugin,),
    {
        "name": "hash",
        "version": "2.0",
        "execute": _hash_execute,
        "__doc__": "Плагін, створений динамічно через type().",
    },
)


def main():
    print("Зареєстровані плагіни:")
    for name, cls in PluginMeta.get_registry().items():
        print(f"  {name} (v{cls.version}): {cls.__name__}")

    print(f"\nHashPlugin створено через type(): метаклас = {type(HashPlugin).__name__}")

    test_data = "Привіт Світ"
    print(f"\nВиконання плагінів для '{test_data}':")
    for name in PluginMeta.get_registry():
        plugin = PluginMeta.create_plugin(name)
        print(f"  {name}: {plugin.execute(test_data)}")

    # Плагін з власними параметрами через фабрику
    custom = PluginMeta.create_plugin("censor", banned_words=("привіт",))
    print(f"  censor (власний список слів): {custom.execute(test_data)}")

    print("\nПеревірка валідації метакласу:")

    # Клас без обов'язкового атрибута version
    try:
        class BrokenPlugin(BasePlugin):
            name = "broken"

            def execute(self, data: str) -> str:
                return data
    except TypeError as e:
        print(f"  TypeError: {e}")

    # Клас без реалізації execute
    try:
        class LazyPlugin(BasePlugin):
            name = "lazy"
            version = "0.1"
    except TypeError as e:
        print(f"  TypeError: {e}")

    # Повторне ім'я плагіна, створеного через type()
    try:
        type("DuplicateUpper", (BasePlugin,), {
            "name": "upper", "version": "9.9", "execute": lambda self, d: d,
        })
    except TypeError as e:
        print(f"  TypeError: {e}")

    # Невідомий плагін у фабриці
    try:
        PluginMeta.create_plugin("translate")
    except ValueError as e:
        print(f"  ValueError: {e}")

    print(f"\nУ реєстрі після невдалих спроб: {list(PluginMeta.get_registry())}")


if __name__ == "__main__":
    main()
