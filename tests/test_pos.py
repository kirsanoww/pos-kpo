import csv
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import FrozenInstanceError
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, patch

from dependency_injector import providers

from pos.__main__ import main
from pos.adapters.storage import MemoryRepository
from pos.container import Container
from pos.domain.calculation import AllCriteria, GradedCriteria, TotalCalculator
from pos.domain.model import Criterion, Evaluation, EvaluationFactory, Gradebook, Score, Student


class DomainTests(unittest.TestCase):
    def setUp(self):
        self.book = Gradebook()
        self.book.add_student(Student("s1", "Анна"))
        self.book.add_criterion(Criterion("a", "Практика", "20", "2"))
        self.book.add_criterion(Criterion("b", "Экзамен", "10", "3"))
        self.factory = EvaluationFactory()
        self.calculator = TotalCalculator(AllCriteria())

    def grade(self, criterion, score):
        self.book.record(self.factory.create(self.book, "s1", criterion, score))

    def test_invalid_scores(self):
        for value in ("-1", "21", "NaN", "Infinity", "-Infinity", "abc", True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.grade("a", value)
        self.assertEqual(self.book.evaluations, ())

    def test_score_bounds_and_comma(self):
        for value in ("0", "20", "2,5"):
            self.grade("a", value)
        self.assertEqual(self.book.evaluations[0].score.value, Decimal("2.5"))

    def test_unknown_student_or_criterion(self):
        for student, criterion in (("missing", "a"), ("s1", "missing")):
            with self.subTest(student=student, criterion=criterion), self.assertRaises(ValueError):
                self.factory.create(self.book, student, criterion, "5")

    def test_aggregate_rejects_wrong_scale_and_unknown_references(self):
        for evaluation in (
            Evaluation("s1", "a", Score(21, 100)),
            Evaluation("unknown", "a", Score(5, 20)),
            Evaluation("s1", "unknown", Score(5, 20)),
        ):
            with self.subTest(evaluation=evaluation), self.assertRaises(ValueError):
                self.book.record(evaluation)

    def test_invalid_criterion(self):
        for maximum, weight in ((0, 1), (-1, 1), (10, 0), (10, -1), ("NaN", 1), (10, "Infinity")):
            with self.subTest(maximum=maximum, weight=weight), self.assertRaises(ValueError):
                Criterion("x", "Критерий", maximum, weight)

    def test_blank_fields(self):
        for student_id, name in (("", "Анна"), ("s", " "), (None, "Анна")):
            with self.subTest(student_id=student_id, name=name), self.assertRaises(ValueError):
                Student(student_id, name)

    def test_duplicates_rejected_and_names_need_not_be_unique(self):
        with self.assertRaises(ValueError):
            self.book.add_student(Student("s1", "Другой студент"))
        with self.assertRaises(ValueError):
            self.book.add_criterion(Criterion("a", "Иной критерий", 1, 1))
        self.book.add_student(Student("s2", "Анна"))
        self.assertEqual(len(self.book.students), 2)

    def test_value_objects_immutable(self):
        self.assertEqual(Score("2", "10"), Score(2, 10))
        with self.assertRaises(FrozenInstanceError):
            self.book.criterion("a").max_score = Decimal(1)
        snapshot = self.book.students
        self.book.add_student(Student("s2", "Иван"))
        self.assertEqual(len(snapshot), 1)

    def test_weighted_result_normalizes_weights_and_maxima(self):
        self.grade("a", "15")
        self.grade("b", "8")
        self.assertEqual(self.calculator.calculate(self.book, "s1").score, Decimal("7.8"))

    def test_correction_cancellation_and_new_criterion_recalculate_total(self):
        self.grade("a", 20)
        self.grade("b", 10)
        self.assertEqual(self.calculator.calculate(self.book, "s1").score, 10)
        self.grade("b", 0)
        self.assertEqual(len(self.book.evaluations), 2)
        self.assertEqual(self.calculator.calculate(self.book, "s1").score, 4)
        self.book.cancel("s1", "a")
        self.assertEqual(self.calculator.calculate(self.book, "s1").score, 0)
        self.grade("a", 20)
        self.book.add_criterion(Criterion("c", "Проект", 100, 5))
        self.assertEqual(self.calculator.calculate(self.book, "s1").score, 2)

    def test_invalid_correction_preserves_previous_score(self):
        self.grade("a", 10)
        with self.assertRaises(ValueError):
            self.grade("a", 21)
        self.assertEqual(self.book.evaluations[0].score.value, 10)

    def test_cancel_missing_grade(self):
        with self.assertRaises(ValueError):
            self.book.cancel("s1", "a")

    def test_missing_grades_differ_between_strategies(self):
        partial = TotalCalculator(GradedCriteria())
        self.assertIsNone(partial.calculate(self.book, "s1").score)
        self.assertEqual(self.calculator.calculate(self.book, "s1").score, 0)
        self.grade("a", 10)
        self.assertEqual(partial.calculate(self.book, "s1").score, 5)
        self.assertEqual(self.calculator.calculate(self.book, "s1").score, 2)

    def test_no_rubric_is_not_a_zero_total(self):
        book = Gradebook()
        book.add_student(Student("s", "Анна"))
        with self.assertRaises(ValueError):
            self.calculator.calculate(book, "s")

    def test_direct_evaluation_normalizes_identifiers(self):
        self.book.record(Evaluation(" s1 ", " a ", Score(10, 20)))
        self.assertEqual(len(self.book.evaluations_for("s1")), 1)
        self.assertEqual(self.book.evaluations[0].criterion_id, "a")
        self.assertEqual(self.calculator.calculate(self.book, "s1").score, 2)

    def test_evaluation_rejects_blank_identifiers_and_invalid_score_type(self):
        for student, criterion, score in (
            (" ", "a", Score(5, 20)),
            ("s1", " ", Score(5, 20)),
            ("s1", "a", 5),
        ):
            with self.subTest(student=student, criterion=criterion, score=score):
                with self.assertRaises(ValueError):
                    Evaluation(student, criterion, score)


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "book.json"
        self.container = Container()
        self.container.config.data_path.from_value(str(self.path))
        self.app = self.container.facade()

    def populate(self):
        self.app.add_student("s", "Анна, Иванова")
        self.app.add_criterion("c", "Критерий", "20", "1")
        self.app.grade("s", "c", "15")

    def test_json_roundtrip_and_new_container(self):
        self.populate()
        other = Container()
        other.config.data_path.from_value(str(self.path))
        self.assertEqual(other.facade().total("s").score, Decimal("7.5"))
        self.assertEqual(other.facade().students()[0].name, "Анна, Иванова")

    def test_invalid_command_does_not_change_saved_file(self):
        self.populate()
        original = self.path.read_bytes()
        with self.assertRaises(ValueError):
            self.app.grade("s", "c", "21")
        self.assertEqual(original, self.path.read_bytes())

    def test_broken_storage_is_not_overwritten(self):
        for contents in ("{", "{}", "null", '{"version": 2}', '{"version": 1, "students": [null]}'):
            self.path.write_text(contents)
            with self.subTest(contents=contents), self.assertRaises(ValueError):
                self.app.add_student("s", "Анна")
            self.assertEqual(self.path.read_text(), contents)

    def test_storage_rechecks_domain_rules(self):
        self.populate()
        original = json.loads(self.path.read_text())
        for key, value in (("score", "21"), ("criterion_id", "missing")):
            data = json.loads(json.dumps(original))
            data["evaluations"][0][key] = value
            self.path.write_text(json.dumps(data))
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.app.grades("s")
        original["evaluations"] *= 2
        self.path.write_text(json.dumps(original))
        with self.assertRaises(ValueError):
            self.app.grades("s")

    def test_csv_export_and_empty_report(self):
        output = Path(self.temp.name) / "results.csv"
        self.app.export(str(output))
        self.populate()
        self.app.export(str(output))
        with output.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(rows[0]["student_name"], "Анна, Иванова")
        self.assertEqual(rows[0]["total_out_of_10"], "7.50")
        self.assertEqual(rows[0]["mode"], "all")

    def test_export_cannot_overwrite_database(self):
        self.populate()
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            self.app.export(str(self.path))
        self.assertEqual(self.path.read_bytes(), before)

    def test_save_failure_preserves_database(self):
        self.populate()
        before = self.path.read_bytes()
        with patch.object(Path, "replace", side_effect=OSError("Нет доступа")):
            with self.assertRaises(OSError):
                self.app.add_student("new", "Иван")
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(Path(self.temp.name).iterdir()), [self.path])

    def test_di_repository_and_exporter_overrides(self):
        repository = MemoryRepository()
        exporter = Mock()
        with self.container.repository.override(providers.Object(repository)):
            with self.container.exporter.override(providers.Object(exporter)):
                facade = self.container.facade()
                facade.add_student("s", "Анна")
                facade.add_criterion("c", "Критерий", "10", "1")
                facade.grade("s", "c", "8")
                facade.export("unused.csv")
                exporter.export.assert_called_once_with(facade.report(), "unused.csv", "all")
        self.assertFalse(self.path.exists())

    def test_repository_returns_independent_snapshots(self):
        repository = MemoryRepository()
        book = repository.load()
        book.add_student(Student("s", "Анна"))
        self.assertEqual(repository.load().students, ())
        repository.save(book)
        book.add_student(Student("s2", "Иван"))
        self.assertEqual(len(repository.load().students), 1)

    def test_invalid_strategy(self):
        with self.assertRaises(ValueError):
            self.app.report("missing")

    def test_complete_demo(self):
        demo = Path(__file__).resolve().parents[1] / "examples" / "demo.txt"
        script = demo.read_text().replace(
            "export results.csv", f'export "{self.temp.name}/results.csv"'
        )
        output = io.StringIO()
        code = self.container.console().run(io.StringIO(script), output, script=True)
        self.assertEqual(code, 0)
        self.assertIn("7.80", output.getvalue())
        self.assertEqual(self.app.total("s2").score, Decimal("6.2"))
        self.assertEqual(len(self.app.students()), 2)
        self.assertTrue((Path(self.temp.name) / "results.csv").exists())

    def test_console_recovers_from_bad_input(self):
        source = io.StringIO('unknown\nstudent\nstudent "\nstudent s "Анна"\nhelp\nquit\n')
        output = io.StringIO()
        self.assertEqual(self.container.console().run(source, output, script=True), 1)
        self.assertEqual(len(self.app.students()), 1)
        self.assertEqual(output.getvalue().count("Ошибка:"), 3)

    def test_console_empty_eof_and_interrupt(self):
        for source in (io.StringIO("\nstudents\ncriteria\nreport\n"), Mock()):
            if isinstance(source, Mock):
                source.readline.side_effect = KeyboardInterrupt
            self.assertEqual(self.container.console().run(source, io.StringIO()), 0)

    def test_invalid_script_encoding_returns_code_two(self):
        script = Path(self.temp.name) / "invalid.txt"
        script.write_bytes(b"\xff\xfe\x00")
        errors = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(errors):
            code = main(["--data", str(self.path), "--script", str(script)])
        self.assertEqual(code, 2)
        self.assertIn("Не удалось прочитать ввод", errors.getvalue())
        self.assertFalse(self.path.exists())

    def test_entry_point_and_missing_script(self):
        script = Path(self.temp.name) / "commands.txt"
        script.write_text('student s "Анна"\nquit\n', encoding="utf-8-sig")
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(main(["--data", str(self.path), "--script", str(script)]), 0)
            self.assertEqual(main(["--script", str(script) + ".missing"]), 2)
            with patch("sys.stdin", io.StringIO("quit\n")):
                self.assertEqual(main(["--data", str(self.path)]), 0)


if __name__ == "__main__":
    unittest.main()
