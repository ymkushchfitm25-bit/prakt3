"""Типізовані дескриптори та __init_subclass__ для системи конфігурації."""


class ValidatedField:
    """Дескриптор із валідацією типу та діапазону значень.

    Використовує __set_name__ для автоматичного визначення імені атрибута.
    """

    def __init__(self, expected_type: type, min_value=None, max_value=None):
        self.expected_type = expected_type
        self.min_value = min_value
        self.max_value = max_value

    def __set_name__(self, owner, name):
        # Викликається автоматично при створенні класу owner
        self.public_name = name             # напр. "port"
        self.private_name = f"_{name}"      # де зберігається значення: "_port"
        self.owner_name = owner.__name__

    def __get__(self, obj, objtype=None):
        if obj is None:
            # Доступ через клас (DatabaseConfig.port) — повертаємо сам дескриптор
            return self
        try:
            return getattr(obj, self.private_name)
        except AttributeError:
            raise AttributeError(
                f"Поле '{self.public_name}' у {self.owner_name} ще не встановлено"
            ) from None

    def __set__(self, obj, value):
        # bool є підкласом int — явно забороняємо True/False для числових полів
        wrong_bool = isinstance(value, bool) and self.expected_type is not bool
        if not isinstance(value, self.expected_type) or wrong_bool:
            raise TypeError(
                f"{self.owner_name}.{self.public_name}: очікується "
                f"{self.expected_type.__name__}, отримано "
                f"{type(value).__name__} ({value!r})"
            )
        if self.min_value is not None and value < self.min_value:
            raise ValueError(
                f"{self.owner_name}.{self.public_name}: значення {value!r} "
                f"менше мінімального {self.min_value}"
            )
        if self.max_value is not None and value > self.max_value:
            raise ValueError(
                f"{self.owner_name}.{self.public_name}: значення {value!r} "
                f"більше максимального {self.max_value}"
            )
        setattr(obj, self.private_name, value)

    def describe(self) -> str:
        """Текстовий опис обмежень поля."""
        limits = ""
        if self.min_value is not None or self.max_value is not None:
            limits = f" [{self.min_value if self.min_value is not None else '-∞'}.." \
                     f"{self.max_value if self.max_value is not None else '+∞'}]"
        return f"{self.expected_type.__name__}{limits}"


class ConfigSection:
    """Базовий клас секції конфігурації з автоматичною реєстрацією."""

    _sections: dict[str, type] = {}

    def __init_subclass__(cls, section_name: str = "", **kwargs):
        super().__init_subclass__(**kwargs)
        name = section_name or cls.__name__.lower()
        if name in ConfigSection._sections:
            raise TypeError(f"Секцію '{name}' вже зареєстровано")
        cls.section_name = name
        ConfigSection._sections[name] = cls

    @classmethod
    def get_section(cls, name: str):
        """Повертає клас секції за іменем."""
        try:
            return ConfigSection._sections[name]
        except KeyError:
            raise KeyError(f"Секцію '{name}' не знайдено") from None

    @classmethod
    def list_sections(cls) -> list[str]:
        """Повертає список усіх зареєстрованих секцій."""
        return list(ConfigSection._sections)

    @classmethod
    def fields(cls) -> dict[str, ValidatedField]:
        """Повертає всі дескриптори ValidatedField секції."""
        return {k: v for k, v in vars(cls).items() if isinstance(v, ValidatedField)}

    def to_dict(self) -> dict:
        """Значення всіх полів секції."""
        return {name: getattr(self, name) for name in self.fields()}

    def __repr__(self) -> str:
        params = ", ".join(f"{k}={v!r}" for k, v in self.to_dict().items())
        return f"{type(self).__name__}({params})"


class DatabaseConfig(ConfigSection, section_name="database"):
    host = ValidatedField(str)
    port = ValidatedField(int, min_value=1, max_value=65535)
    max_connections = ValidatedField(int, min_value=1, max_value=1000)

    def __init__(self, host: str, port: int, max_connections: int = 10):
        self.host = host
        self.port = port
        self.max_connections = max_connections


class LoggingConfig(ConfigSection, section_name="logging"):
    level = ValidatedField(str)
    max_file_size_mb = ValidatedField(int, min_value=1, max_value=1024)

    def __init__(self, level: str = "INFO", max_file_size_mb: int = 10):
        self.level = level
        self.max_file_size_mb = max_file_size_mb


class CacheConfig(ConfigSection):  # section_name не задано -> "cacheconfig"
    enabled = ValidatedField(bool)
    ttl_seconds = ValidatedField(float, min_value=0.0)

    def __init__(self, enabled: bool = True, ttl_seconds: float = 60.0):
        self.enabled = enabled
        self.ttl_seconds = ttl_seconds


def try_set(obj, attr: str, value) -> None:
    """Пробує встановити атрибут і виводить результат."""
    try:
        setattr(obj, attr, value)
        print(f"  OK: {attr} = {value!r}")
    except (TypeError, ValueError) as e:
        print(f"  {type(e).__name__}: {e}")


def main():
    print("Зареєстровані секції:", ConfigSection.list_sections())
    for name in ConfigSection.list_sections():
        section = ConfigSection.get_section(name)
        fields = ", ".join(f"{k}: {v.describe()}" for k, v in section.fields().items())
        print(f"  [{name}] {section.__name__} -> {fields}")

    print("\nСтворення DatabaseConfig з коректними значеннями:")
    db = DatabaseConfig("localhost", 5432, max_connections=50)
    print(f"  {db}")
    print(f"  __set_name__ визначив: public_name='{DatabaseConfig.port.public_name}', "
          f"private_name='{DatabaseConfig.port.private_name}'")
    print(f"  значення лежить у __dict__ екземпляра: {vars(db)}")

    print("\nВалідація типу (TypeError):")
    try_set(db, "port", "5432")
    try_set(db, "host", 127)
    try_set(db, "max_connections", True)

    print("\nВалідація діапазону (ValueError):")
    try_set(db, "port", 70000)
    try_set(db, "port", 0)
    try_set(db, "max_connections", 5000)
    try_set(db, "port", 3306)

    print("\nПомилка вже в конструкторі:")
    try:
        LoggingConfig(level="DEBUG", max_file_size_mb=2048)
    except ValueError as e:
        print(f"  ValueError: {e}")

    print("\nЕкземпляри незалежні (значення зберігаються в кожному об'єкті):")
    log1 = LoggingConfig("DEBUG", 5)
    log2 = LoggingConfig("ERROR", 100)
    print(f"  {log1}\n  {log2}")

    print("\nСекція через get_section('cacheconfig'):")
    cache_cls = ConfigSection.get_section("cacheconfig")
    cache = cache_cls(enabled=False, ttl_seconds=30.5)
    print(f"  {cache}")
    try_set(cache, "ttl_seconds", -1.0)


if __name__ == "__main__":
    main()
