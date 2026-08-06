"""Тесты для ядра расчётов cocktail_calc.

Используют маленькую тестовую базу, собранную в памяти, —
реальный data/cocktails_db.json не нужен и не читается.
"""
import pytest

from cocktail_calc.calculator import (
    calculate_shopping_list,
    find_cocktail,
    parse_order,
)
from cocktail_calc.models import Cocktail, Database, SemiProduct


@pytest.fixture
def db() -> Database:
    """Мини-база: один коктейль с вложенным ПФ, украшением и посудой.

    Структура ПФ:
        (ПФ) микс = 0.5 л (ПФ) база + 0.5 л сок лайма (на 1 л выхода)
        (ПФ) база = 1.0 л ром белый      (на 1 л выхода)
    """
    semi_products = {
        "микс": SemiProduct(
            name="Микс",
            output_volume=1.0,
            recipe={"(ПФ) база": 0.5, "сок лайма": 0.5},
        ),
        "база": SemiProduct(
            name="База",
            output_volume=1.0,
            recipe={"ром белый": 1.0},
        ),
    }
    cocktails = {
        "тест коктейль": Cocktail(
            name="Тест Коктейль",
            recipe={"(ПФ) микс": 0.2, "ром белый": 0.05},
            decorations={"лист мяты": 2},
            glassware={"хайбол": 1},
        ),
    }
    categories = {
        "ром белый": "алкоголь",
        "сок лайма": "безалкогольное",
        "лист мяты": "украшение_шт",
        "хайбол": "посуда",
    }
    bottle_volumes = {"ром белый": 0.7}
    prices = {"ром белый": 1500, "сок лайма": 200, "лист мяты": 5}
    return Database(
        semi_products=semi_products,
        cocktails=cocktails,
        categories=categories,
        bottle_volumes=bottle_volumes,
        prices=prices,
    )


# ─── parse_order ─────────────────────────────────────────────────────────────

def test_parse_order_comma_separated():
    assert parse_order("Кокосовый ром 10, Мохито 5") == {
        "кокосовый ром": 10,
        "мохито": 5,
    }


def test_parse_order_newlines_and_spaces():
    assert parse_order("Мохито 5\n  Негрони 3 ") == {"мохито": 5, "негрони": 3}


def test_parse_order_garbage_returns_empty():
    assert parse_order("просто текст без цифр") == {}


# ─── find_cocktail ───────────────────────────────────────────────────────────

def test_find_cocktail_exact_key(db):
    assert find_cocktail("тест коктейль", db.cocktails) == "тест коктейль"


def test_find_cocktail_by_display_name(db):
    assert find_cocktail("Тест Коктейль", db.cocktails) == "тест коктейль"


def test_find_cocktail_partial(db):
    assert find_cocktail("тест", db.cocktails) == "тест коктейль"


def test_find_cocktail_with_typo(db):
    # Одна опечатка в длинном названии должна находиться нечётким поиском
    assert find_cocktail("тест коктель", db.cocktails) == "тест коктейль"


def test_find_cocktail_not_found(db):
    assert find_cocktail("мохито", db.cocktails) is None


# ─── calculate_shopping_list ─────────────────────────────────────────────────

def test_calculate_full_aggregation(db):
    """10 коктейлей: проверяем разворачивание ПФ, категории и итоговую сумму."""
    result = calculate_shopping_list({"тест коктейль": 10}, db.prices, db)

    # Коктейль найден
    assert result["found_cocktails"] == [("Тест Коктейль", 10)]
    assert result["unknown"] == []

    # ПФ к приготовлению: 0.2 л × 10 = 2 л
    assert result["pf_to_make"] == {"микс": pytest.approx(2.0)}

    # Ром: напрямую 0.05×10 = 0.5 л + через ПФ 2×0.5×1.0 = 1.0 л → 1.5 л
    # Бутылки: ceil(1.5 / 0.7) = 3, стоимость 3 × 1500 = 4500
    rom = result["alcohol"]["ром белый"]
    assert rom["liters"] == pytest.approx(1.5)
    assert rom["bottles"] == 3
    assert rom["cost"] == 4500

    # Сок лайма через ПФ: 2 × 0.5 = 1.0 л, стоимость 1.0 × 200 = 200
    juice = result["non_alcohol"]["сок лайма"]
    assert juice["liters"] == pytest.approx(1.0)
    assert juice["cost"] == 200

    # Украшения: 2 × 10 = 20 шт, 20 × 5 = 100
    mint = result["decorations_pcs"]["лист мяты"]
    assert mint["pcs"] == 20
    assert mint["cost"] == 100

    # Посуда: только количество, без цены
    assert result["glassware"] == {"хайбол": 10}

    # Итого: 4500 + 200 + 100 = 4800
    assert result["total_cost"] == 4800


def test_calculate_unknown_cocktail(db):
    result = calculate_shopping_list({"мохито": 5}, db.prices, db)
    assert result["found_cocktails"] == []
    assert result["unknown"] == ["мохито"]
    assert result["total_cost"] == 0
