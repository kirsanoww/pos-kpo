import argparse
import sys
from pathlib import Path

from pos.container import Container


def main(argv=None):
    parser = argparse.ArgumentParser(description="Преподавательская оценка студентов")
    parser.add_argument("--data", default="data/gradebook.json", help="JSON-хранилище")
    parser.add_argument("--script", type=Path, help="файл команд UTF-8")
    args = parser.parse_args(argv)
    container = Container()
    container.config.data_path.from_value(args.data)
    app = container.console()
    try:
        if args.script:
            with args.script.open(encoding="utf-8-sig") as source:
                return app.run(source, sys.stdout, script=True)
        return app.run(sys.stdin, sys.stdout)
    except (OSError, UnicodeError) as error:
        print(f"Не удалось прочитать ввод: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
