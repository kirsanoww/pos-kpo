from collections.abc import Callable

from pos.application.ports import GradebookRepository, ResultsExporter
from pos.domain.calculation import Total, TotalCalculator
from pos.domain.model import Criterion, EvaluationFactory, Gradebook, Student


class AssessmentFacade:
    def __init__(
        self,
        repository: GradebookRepository,
        factory: EvaluationFactory,
        calculators: dict[str, TotalCalculator],
        exporter: ResultsExporter,
    ):
        self._repository = repository
        self._factory = factory
        self._calculators = calculators
        self._exporter = exporter

    def _change(self, action: Callable[[Gradebook], None]):
        book = self._repository.load()
        action(book)
        self._repository.save(book)

    def add_student(self, student_id: str, name: str):
        self._change(lambda book: book.add_student(Student(student_id, name)))

    def add_criterion(self, criterion_id: str, name: str, maximum: str, weight: str):
        self._change(
            lambda book: book.add_criterion(Criterion(criterion_id, name, maximum, weight))
        )

    def grade(self, student_id: str, criterion_id: str, value: str):
        self._change(
            lambda book: book.record(self._factory.create(book, student_id, criterion_id, value))
        )

    def cancel(self, student_id: str, criterion_id: str):
        self._change(lambda book: book.cancel(student_id, criterion_id))

    def students(self):
        return self._repository.load().students

    def criteria(self):
        return self._repository.load().criteria

    def grades(self, student_id: str):
        return self._repository.load().evaluations_for(student_id)

    def _calculator(self, mode: str) -> TotalCalculator:
        if mode not in self._calculators:
            raise ValueError("Режим расчёта: all или graded.")
        return self._calculators[mode]

    def total(self, student_id: str, mode: str = "all") -> Total:
        return self._calculator(mode).calculate(self._repository.load(), student_id)

    def report(self, mode: str = "all") -> tuple[Total, ...]:
        calculator = self._calculator(mode)
        book = self._repository.load()
        return tuple(calculator.calculate(book, s.id) for s in book.students)

    def export(self, destination: str, mode: str = "all"):
        self._exporter.export(self.report(mode), destination, mode)
