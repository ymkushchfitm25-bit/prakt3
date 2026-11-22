"""Паттерни Observer, Strategy та архітектурний шаблон MVC."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable


# --- Observer ---

class EventEmitter:
    """Базовий клас для підтримки системи подій (Observer)."""

    def __init__(self):
        self._listeners: dict[str, list[Callable]] = {}

    def on(self, event: str, callback: Callable):
        """Підписатися на подію."""
        listeners = self._listeners.setdefault(event, [])
        if callback not in listeners:
            listeners.append(callback)

    def off(self, event: str, callback: Callable):
        """Відписатися від події."""
        listeners = self._listeners.get(event, [])
        if callback in listeners:
            listeners.remove(callback)
        if not listeners:
            self._listeners.pop(event, None)

    def emit(self, event: str, *args, **kwargs):
        """Сповістити всіх слухачів про подію."""
        # Копія списку — слухач може відписатися прямо під час сповіщення
        for callback in list(self._listeners.get(event, [])):
            callback(*args, **kwargs)


# --- Strategy ---

class SortStrategy(ABC):
    """Абстрактна стратегія сортування завдань."""

    name = "базова"

    @abstractmethod
    def sort(self, tasks: list["Task"]) -> list["Task"]:
        ...


class SortByPriority(SortStrategy):
    """Сортування за пріоритетом (високий → низький)."""

    name = "за пріоритетом"

    def sort(self, tasks: list["Task"]) -> list["Task"]:
        # 1 — найвищий пріоритет; при рівних — раніший дедлайн
        return sorted(tasks, key=lambda t: (t.priority, t.deadline))


class SortByDeadline(SortStrategy):
    """Сортування за терміном виконання (найближчий першим)."""

    name = "за дедлайном"

    def sort(self, tasks: list["Task"]) -> list["Task"]:
        return sorted(tasks, key=lambda t: t.deadline)


class SortByCreationDate(SortStrategy):
    """Сортування за датою створення (найновіші першими)."""

    name = "за датою створення"

    def sort(self, tasks: list["Task"]) -> list["Task"]:
        return sorted(tasks, key=lambda t: t.created_at, reverse=True)


# --- Model ---

@dataclass
class Task:
    title: str
    priority: int  # 1 (найвищий) – 5 (найнижчий)
    deadline: datetime
    completed: bool = False
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if not self.title.strip():
            raise ValueError("Назва завдання не може бути порожньою")
        if not 1 <= self.priority <= 5:
            raise ValueError(f"Пріоритет має бути від 1 до 5, отримано {self.priority}")

    @property
    def is_overdue(self) -> bool:
        return not self.completed and self.deadline < datetime.now()


class TaskModel(EventEmitter):
    """Model: дані та бізнес-логіка завдань."""

    def __init__(self):
        super().__init__()
        self._tasks: list[Task] = []

    def _get(self, index: int) -> Task:
        if not 0 <= index < len(self._tasks):
            raise IndexError(f"Завдання №{index + 1} не існує (усього {len(self._tasks)})")
        return self._tasks[index]

    def add_task(self, title: str, priority: int, deadline: datetime) -> Task:
        task = Task(title, priority, deadline)
        self._tasks.append(task)
        self.emit("task_added", task)
        return task

    def complete_task(self, index: int):
        task = self._get(index)
        if task.completed:
            return
        task.completed = True
        self.emit("task_completed", task)

    def remove_task(self, index: int):
        task = self._get(index)
        self._tasks.remove(task)
        self.emit("task_removed", task)

    def find_index(self, title: str) -> int:
        for i, task in enumerate(self._tasks):
            if task.title == title:
                return i
        raise ValueError(f"Завдання '{title}' не знайдено")

    def get_tasks(self, include_completed: bool = True) -> list[Task]:
        if include_completed:
            return list(self._tasks)
        return [t for t in self._tasks if not t.completed]

    def get_statistics(self) -> dict:
        total = len(self._tasks)
        completed = sum(1 for t in self._tasks if t.completed)
        return {
            "total": total,
            "completed": completed,
            "active": total - completed,
            "overdue": sum(1 for t in self._tasks if t.is_overdue),
            "progress": round(completed / total * 100) if total else 0,
        }


# --- View ---

class TaskView:
    """View: відображення даних у консолі."""

    PRIORITY_LABELS = {1: "1 !!!", 2: "2 !!", 3: "3 !", 4: "4", 5: "5"}

    def show_tasks(self, tasks: list[Task], title: str = "Завдання"):
        print(f"\n{title} ({len(tasks)}):")
        if not tasks:
            print("  (немає завдань)")
            return
        header = f"  {'№':>2} | {'Назва':<28} | {'Пріоритет':<9} | {'Дедлайн':<16} | Статус"
        print(header)
        print("  " + "-" * (len(header) - 2))
        for i, t in enumerate(tasks, 1):
            if t.completed:
                status = "✔ виконано"
            elif t.is_overdue:
                status = "⚠ прострочено"
            else:
                status = "○ активне"
            print(f"  {i:>2} | {t.title:<28.28} | {self.PRIORITY_LABELS[t.priority]:<9} | "
                  f"{t.deadline:%d.%m.%Y %H:%M} | {status}")

    def show_message(self, message: str):
        print(f"[INFO] {message}")

    def show_statistics(self, stats: dict):
        bar_len = 20
        filled = round(stats["progress"] / 100 * bar_len)
        print("\nСтатистика:")
        print(f"  Усього: {stats['total']} | виконано: {stats['completed']} | "
              f"активних: {stats['active']} | прострочено: {stats['overdue']}")
        print(f"  Прогрес: [{'█' * filled}{'░' * (bar_len - filled)}] {stats['progress']}%")


# --- Controller ---

class TaskController:
    """Controller: координація Model та View з підтримкою Strategy."""

    def __init__(self, model: TaskModel, view: TaskView):
        self._model = model
        self._view = view
        self._sort_strategy: SortStrategy = SortByPriority()

        # Observer: контролер підписується на події моделі
        model.on("task_added", self._on_task_added)
        model.on("task_completed", self._on_task_completed)
        model.on("task_removed", self._on_task_removed)

    # обробники подій
    def _on_task_added(self, task: Task):
        self._view.show_message(f"Додано: «{task.title}» (пріоритет {task.priority})")

    def _on_task_completed(self, task: Task):
        self._view.show_message(f"Виконано: «{task.title}»")

    def _on_task_removed(self, task: Task):
        self._view.show_message(f"Видалено: «{task.title}»")

    def set_sort_strategy(self, strategy: SortStrategy):
        """Змінити стратегію сортування (Strategy)."""
        self._sort_strategy = strategy
        self._view.show_message(f"Стратегія сортування: {strategy.name}")

    def add_task(self, title: str, priority: int, deadline: datetime):
        try:
            self._model.add_task(title, priority, deadline)
        except ValueError as e:
            self._view.show_message(f"Помилка: {e}")

    def complete_task(self, index: int):
        self._model.complete_task(index)

    def complete_by_title(self, title: str):
        self._model.complete_task(self._model.find_index(title))

    def remove_task(self, index: int):
        self._model.remove_task(index)

    def show_all(self):
        tasks = self._model.get_tasks()
        sorted_tasks = self._sort_strategy.sort(tasks)
        self._view.show_tasks(sorted_tasks, title=f"Усі завдання — {self._sort_strategy.name}")

    def show_active(self):
        tasks = self._model.get_tasks(include_completed=False)
        sorted_tasks = self._sort_strategy.sort(tasks)
        self._view.show_tasks(sorted_tasks, title=f"Активні завдання — {self._sort_strategy.name}")

    def show_stats(self):
        self._view.show_statistics(self._model.get_statistics())


def main():
    model = TaskModel()
    view = TaskView()
    ctrl = TaskController(model, view)

    now = datetime.now().replace(second=0, microsecond=0)

    # Додатковий слухач (Observer): журнал змін, який можна відписати
    journal: list[str] = []

    def audit(task: Task):
        journal.append(task.title)

    model.on("task_added", audit)

    print("=== Додавання завдань ===")
    ctrl.add_task("Здати практичну роботу", 1, now + timedelta(days=2))
    ctrl.add_task("Прочитати розділ про патерни", 3, now + timedelta(days=5))
    ctrl.add_task("Оплатити інтернет", 2, now + timedelta(hours=6))
    ctrl.add_task("Записатися до лікаря", 4, now - timedelta(days=1))
    ctrl.add_task("Прибрати робочий стіл", 5, now + timedelta(days=10))
    ctrl.add_task("", 3, now)                   # некоректне — ValueError
    ctrl.add_task("Завдання з пріоритетом 9", 9, now)

    print(f"\nЖурнал слухача audit: {journal}")
    model.off("task_added", audit)              # відписка
    ctrl.add_task("Купити каву", 3, now + timedelta(days=1))
    print(f"Після off() audit не отримав нове завдання: {journal}")

    ctrl.show_all()                             # за пріоритетом (стратегія за замовчуванням)

    print()
    ctrl.set_sort_strategy(SortByDeadline())    # динамічна зміна стратегії
    ctrl.show_all()

    print()
    ctrl.set_sort_strategy(SortByCreationDate())
    ctrl.show_all()

    print("\n=== Зміна стану ===")
    ctrl.complete_by_title("Оплатити інтернет")
    ctrl.complete_by_title("Здати практичну роботу")
    ctrl.remove_task(model.find_index("Купити каву"))
    try:
        ctrl.complete_task(99)
    except IndexError as e:
        view.show_message(f"Помилка: {e}")

    ctrl.set_sort_strategy(SortByPriority())
    ctrl.show_active()
    ctrl.show_stats()


if __name__ == "__main__":
    main()
