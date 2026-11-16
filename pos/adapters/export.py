import csv
from decimal import ROUND_HALF_UP, Decimal, localcontext
from pathlib import Path

from pos.domain.calculation import Total


def format_score(score: Decimal | None) -> str:
    if score is None:
        return ""
    with localcontext() as context:
        context.prec = max(28, len(score.as_tuple().digits) + 2)
        return str(score.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


class CsvExporter:
    def __init__(self, protected_path: str | None = None):
        self._protected_path = Path(protected_path).resolve() if protected_path else None

    def export(self, totals: tuple[Total, ...], destination: str, mode: str):
        path = Path(destination)
        if path.resolve() == self._protected_path:
            raise ValueError("Нельзя экспортировать CSV поверх хранилища JSON.")
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(
                ["student_id", "student_name", "total_out_of_10", "graded", "criteria", "mode"]
            )
            for total in totals:
                writer.writerow(
                    [
                        total.student_id,
                        total.student_name,
                        format_score(total.score),
                        total.graded_count,
                        total.criteria_count,
                        mode,
                    ]
                )
