from typing import Protocol

from pos.domain.calculation import Total
from pos.domain.model import Gradebook


class GradebookRepository(Protocol):
    def load(self) -> Gradebook: ...

    def save(self, book: Gradebook) -> None: ...


class ResultsExporter(Protocol):
    def export(self, totals: tuple[Total, ...], destination: str, mode: str) -> None: ...
