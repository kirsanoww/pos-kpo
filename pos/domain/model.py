from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


def text(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Название или идентификатор не может быть пустым.")
    return value.strip()


def number(value) -> Decimal:
    try:
        result = Decimal(str(value).replace(",", "."))
    except (InvalidOperation, ValueError):
        raise ValueError("Ожидается число.") from None
    if not result.is_finite():
        raise ValueError("Число должно быть конечным.")
    return result


@dataclass(frozen=True)
class Student:
    id: str
    name: str

    def __post_init__(self):
        object.__setattr__(self, "id", text(self.id))
        object.__setattr__(self, "name", text(self.name))


@dataclass(frozen=True)
class Criterion:
    id: str
    name: str
    max_score: Decimal
    weight: Decimal

    def __post_init__(self):
        object.__setattr__(self, "id", text(self.id))
        object.__setattr__(self, "name", text(self.name))
        for field in ("max_score", "weight"):
            value = number(getattr(self, field))
            if value <= 0:
                raise ValueError("Максимум и вес должны быть положительными.")
            object.__setattr__(self, field, value)


@dataclass(frozen=True)
class Score:
    value: Decimal
    maximum: Decimal

    def __post_init__(self):
        value, maximum = number(self.value), number(self.maximum)
        if maximum <= 0 or not 0 <= value <= maximum:
            raise ValueError("Балл должен быть от 0 до максимума критерия.")
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "maximum", maximum)

    @property
    def fraction(self) -> Decimal:
        return self.value / self.maximum


@dataclass(frozen=True)
class Evaluation:
    student_id: str
    criterion_id: str
    score: Score

    def __post_init__(self):
        object.__setattr__(self, "student_id", text(self.student_id))
        object.__setattr__(self, "criterion_id", text(self.criterion_id))
        if not isinstance(self.score, Score):
            raise ValueError("Оценка должна содержать объект Score")


class EvaluationFactory:
    def create(self, book: "Gradebook", student_id: str, criterion_id: str, value):
        student = book.student(student_id)
        criterion = book.criterion(criterion_id)
        return Evaluation(student.id, criterion.id, Score(value, criterion.max_score))


class Gradebook:
    def __init__(self):
        self._students: dict[str, Student] = {}
        self._criteria: dict[str, Criterion] = {}
        self._evaluations: dict[tuple[str, str], Evaluation] = {}

    @property
    def students(self) -> tuple[Student, ...]:
        return tuple(self._students.values())

    @property
    def criteria(self) -> tuple[Criterion, ...]:
        return tuple(self._criteria.values())

    @property
    def evaluations(self) -> tuple[Evaluation, ...]:
        return tuple(self._evaluations.values())

    def student(self, student_id: str) -> Student:
        try:
            return self._students[text(student_id)]
        except KeyError:
            raise ValueError("Студент не найден.") from None

    def criterion(self, criterion_id: str) -> Criterion:
        try:
            return self._criteria[text(criterion_id)]
        except KeyError:
            raise ValueError("Критерий отсутствует в рубрикаторе.") from None

    def add_student(self, student: Student):
        if student.id in self._students:
            raise ValueError("Идентификатор студента уже занят.")
        self._students[student.id] = student

    def add_criterion(self, criterion: Criterion):
        if criterion.id in self._criteria:
            raise ValueError("Идентификатор критерия уже занят.")
        self._criteria[criterion.id] = criterion

    def record(self, evaluation: Evaluation):
        student = self.student(evaluation.student_id)
        criterion = self.criterion(evaluation.criterion_id)
        if evaluation.score.maximum != criterion.max_score:
            raise ValueError("Шкала оценки не соответствует критерию.")
        self._evaluations[student.id, criterion.id] = evaluation

    def cancel(self, student_id: str, criterion_id: str):
        key = self.student(student_id).id, self.criterion(criterion_id).id
        if key not in self._evaluations:
            raise ValueError("Эта оценка ещё не выставлена.")
        del self._evaluations[key]

    def evaluations_for(self, student_id: str) -> tuple[Evaluation, ...]:
        student = self.student(student_id)
        return tuple(e for e in self.evaluations if e.student_id == student.id)
