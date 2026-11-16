from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from pos.domain.model import Criterion, Gradebook


class CalculationStrategy(Protocol):
    def select(
        self, criteria: tuple[Criterion, ...], graded: set[str]
    ) -> tuple[Criterion, ...]: ...


class AllCriteria:
    def select(self, criteria: tuple[Criterion, ...], graded: set[str]) -> tuple[Criterion, ...]:
        return criteria


class GradedCriteria:
    def select(self, criteria: tuple[Criterion, ...], graded: set[str]) -> tuple[Criterion, ...]:
        return tuple(c for c in criteria if c.id in graded)


@dataclass(frozen=True)
class Total:
    student_id: str
    student_name: str
    score: Decimal | None
    graded_count: int
    criteria_count: int


class TotalCalculator:
    def __init__(self, strategy: CalculationStrategy):
        self._strategy = strategy

    def calculate(self, book: Gradebook, student_id: str) -> Total:
        student = book.student(student_id)
        if not book.criteria:
            raise ValueError("Добавьте хотя бы один критерий для расчёта итога.")
        grades = {e.criterion_id: e.score for e in book.evaluations_for(student.id)}
        criteria = self._strategy.select(book.criteria, set(grades))
        denominator = sum((c.weight for c in criteria), Decimal(0))
        numerator = sum(
            (grades[c.id].fraction * c.weight for c in criteria if c.id in grades), Decimal(0)
        )
        score = Decimal(10) * numerator / denominator if denominator else None
        return Total(student.id, student.name, score, len(grades), len(book.criteria))
