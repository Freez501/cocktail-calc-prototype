import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(BASE_DIR, "data", "cocktails_db.json")
JS_PATH = os.path.join(BASE_DIR, "web_static", "db.js")


def main():
    if not os.path.exists(JSON_PATH):
        print(f"❌ Не найден файл: {JSON_PATH}")
        sys.exit(1)

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    with open(JS_PATH, "w", encoding="utf-8") as f:
        f.write("const DB = ")
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write(";\n")

    print(f"✅ Обновлён: {JS_PATH}")
    print(f"   Источник: {JSON_PATH}")


if __name__ == "__main__":
    main()
