import shlex
from decimal import DecimalException
from typing import TextIO

from pos.adapters.export import format_score
from pos.application.facade import AssessmentFacade

HELP = """student ID "Имя"                  добавить студента
criterion ID "Название" МАКС ВЕС  добавить критерий
students                         список студентов
criteria                         список критериев
grade СТУДЕНТ КРИТЕРИЙ БАЛЛ       выставить или исправить оценку
cancel СТУДЕНТ КРИТЕРИЙ           отменить оценку
grades СТУДЕНТ                   оценки студента
total СТУДЕНТ [all|graded]        итог из 10
report [all|graded]               итоги всех студентов
export "Путь.csv" [all|graded]    экспорт итогов
help                             команды
quit                             выход
all: пропуски считаются нулями; graded: предварительный итог по выставленным оценкам."""


class Console:
    def __init__(self, facade: AssessmentFacade):
        self._facade = facade

    @staticmethod
    def _total(total) -> str:
        score = format_score(total.score) if total.score is not None else "нет оценок"
        return (
            f"{total.student_id} | {total.student_name} | {score} | "
            f"оценено {total.graded_count}/{total.criteria_count}"
        )

    def execute(self, parts: list[str]) -> list[str]:
        command, *args = parts
        facade = self._facade
        if command == "help" and not args:
            return [HELP]
        if command == "student" and len(args) == 2:
            facade.add_student(*args)
        elif command == "criterion" and len(args) == 4:
            facade.add_criterion(*args)
        elif command == "grade" and len(args) == 3:
            facade.grade(*args)
        elif command == "cancel" and len(args) == 2:
            facade.cancel(*args)
        elif command == "students" and not args:
            return [f"{s.id} | {s.name}" for s in facade.students()]
        elif command == "criteria" and not args:
            return [
                f"{c.id} | {c.name} | максимум {c.max_score} | вес {c.weight}"
                for c in facade.criteria()
            ]
        elif command == "grades" and len(args) == 1:
            return [
                f"{e.criterion_id} | {e.score.value}/{e.score.maximum}"
                for e in facade.grades(*args)
            ]
        elif command == "total" and 1 <= len(args) <= 2:
            return [self._total(facade.total(*args))]
        elif command == "report" and len(args) <= 1:
            return [self._total(t) for t in facade.report(*args)]
        elif command == "export" and 1 <= len(args) <= 2:
            facade.export(*args)
        else:
            raise ValueError("Неизвестная команда или неверные аргументы. Введите help.")
        return ["Готово."]

    def run(self, source: TextIO, output: TextIO, *, script: bool = False) -> int:
        print("ПОС — преподавательская оценка студентов. Команды: help.", file=output)
        errors = False
        while True:
            try:
                print("> ", end="", file=output, flush=True)
                line = source.readline()
                if not line:
                    print("Ввод завершён.", file=output)
                    break
                if script:
                    print(line.rstrip(), file=output)
                parts = shlex.split(line)
                if not parts:
                    continue
                if parts == ["quit"]:
                    print("Работа завершена.", file=output)
                    break
                rows = self.execute(parts)
                print("\n".join(rows) if rows else "Список пуст.", file=output)
            except UnicodeError:
                raise
            except (ValueError, OSError, DecimalException) as error:
                errors = True
                print(f"Ошибка: {error}", file=output)
            except KeyboardInterrupt:
                print("\nВвод прерван.", file=output)
                break
        return int(script and errors)
