import json
from copy import deepcopy
from pathlib import Path
from tempfile import NamedTemporaryFile

from pos.domain.model import Criterion, EvaluationFactory, Gradebook, Student


class MemoryRepository:
    def __init__(self):
        self._book = Gradebook()

    def load(self) -> Gradebook:
        return deepcopy(self._book)

    def save(self, book: Gradebook):
        self._book = deepcopy(book)


class JsonRepository:
    def __init__(self, path: str):
        self.path = Path(path)

    def load(self) -> Gradebook:
        book = Gradebook()
        if not self.path.exists():
            return book
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if data["version"] != 1:
                raise ValueError("Неподдерживаемая версия хранилища.")
            for row in data["students"]:
                book.add_student(Student(row["id"], row["name"]))
            for row in data["criteria"]:
                book.add_criterion(
                    Criterion(row["id"], row["name"], row["max_score"], row["weight"])
                )
            seen = set()
            factory = EvaluationFactory()
            for row in data["evaluations"]:
                evaluation = factory.create(
                    book, row["student_id"], row["criterion_id"], row["score"]
                )
                key = evaluation.student_id, evaluation.criterion_id
                if key in seen:
                    raise ValueError("Повтор оценки в хранилище.")
                book.record(evaluation)
                seen.add(key)
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            raise ValueError(f"Некорректное хранилище: {error}") from error
        return book

    def save(self, book: Gradebook):
        data = {
            "version": 1,
            "students": [{"id": s.id, "name": s.name} for s in book.students],
            "criteria": [
                {"id": c.id, "name": c.name, "max_score": str(c.max_score), "weight": str(c.weight)}
                for c in book.criteria
            ],
            "evaluations": [
                {
                    "student_id": e.student_id,
                    "criterion_id": e.criterion_id,
                    "score": str(e.score.value),
                }
                for e in book.evaluations
            ],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.path.parent, delete=False
            ) as stream:
                temporary = Path(stream.name)
                json.dump(data, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
            temporary.replace(self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
