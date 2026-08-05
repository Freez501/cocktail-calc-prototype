import math
import re
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .models import Cocktail, Database, SemiProduct


PF_PREFIX = "(ПФ) "


def parse_order(text: str) -> Dict[str, int]:
    """Парсит текст заказа вида 'Кокосовый ром 10, Мохито 5'."""
    order = {}
    lines = re.split(r"[,\n]+", text)
    for line in lines:
        line = line.strip()
        if not line:
            continue
        match = re.match(r"(.+?)\s+(\d+)", line)
        if match:
            name = match.group(1).strip().lower()
            count = int(match.group(2))
            order[name] = count
    return order


def _levenshtein(a: str, b: str) -> int:
    """Расстояние Левенштейна между двумя строками."""
    if len(a) < len(b):
        return _levenshtein(b, a)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            curr.append(min(curr[-1] + 1, prev[j + 1] + 1, prev[j] + (0 if ca == cb else 1)))
        prev = curr
    return prev[-1]


def find_cocktail(name: str, cocktails: Dict[str, Cocktail]) -> Optional[str]:
    """Ищет коктейль по ключу, названию, частичному и нечёткому совпадению."""
    name = name.lower().strip()
    # 1. Точное совпадение по ключу или названию
    for key, cocktail in cocktails.items():
        if key == name or cocktail.name.lower().strip() == name:
            return key
    # 2. Частичное совпадение по ключу или названию
    for key, cocktail in cocktails.items():
        lowered_name = cocktail.name.lower().strip()
        if name in key or key in name or name in lowered_name or lowered_name in name:
            return key
    # 3. Нечёткое совпадение (опечатки, разные окончания) — если строка достаточно длинная
    if len(name) >= 5:
        threshold = max(1, len(name) // 8)
        best_key = None
        best_dist = None
        for key, cocktail in cocktails.items():
            for candidate in (key, cocktail.name.lower().strip()):
                dist = _levenshtein(name, candidate)
                if dist <= threshold and (best_dist is None or dist < best_dist):
                    best_dist = dist
                    best_key = key
        if best_key is not None:
            return best_key
    return None


def _strip_pf(name: str) -> str:
    return name.replace(PF_PREFIX, "").strip().lower()


def resolve_pf(
    ingredient: str,
    amount: float,
    db: Database,
    pf_totals: Dict[str, float],
    unknown_pf: List[str],
):
    """Рекурсивно разворачивает ПФ в его состав."""
    pf_name = _strip_pf(ingredient)
    if pf_name in db.semi_products:
        pf = db.semi_products[pf_name]
        pf_totals[pf_name] = pf_totals.get(pf_name, 0.0) + amount
        for pf_ing, pf_ratio in pf.recipe.items():
            actual_amount = amount * (pf_ratio / pf.output_volume)
            if pf_ing.startswith(PF_PREFIX):
                resolve_pf(pf_ing, actual_amount, db, pf_totals, unknown_pf)
            else:
                # Возвращаем в общий словарь для дальнейшей агрегации
                pass
        return True
    unknown_pf.append(pf_name)
    return False


def _add_to_category(
    ingredient: str,
    amount: float,
    db: Database,
    alcohol: Dict[str, float],
    non_alcohol: Dict[str, float],
    syrups: Dict[str, float],
    puree: Dict[str, float],
    concentrate: Dict[str, float],
    dry_gr: Dict[str, float],
    ice_cube: Dict[str, float],
    ice_figurine: Dict[str, float],
    decorations_pcs: Dict[str, float],
    decorations_gr: Dict[str, float],
):
    """Распределяет ингредиент по категориям закупок."""
    category = db.categories.get(ingredient, "прочее")
    if category == "алкоголь":
        alcohol[ingredient] += amount
    elif category == "безалкогольное":
        non_alcohol[ingredient] += amount
    elif category == "сироп":
        syrups[ingredient] += amount
    elif category == "пюре":
        puree[ingredient] += amount
    elif category == "концентрат":
        concentrate[ingredient] += amount
    elif category == "сухой_гр":
        dry_gr[ingredient] += amount
    elif category == "лёд_кубик":
        ice_cube[ingredient] += amount
    elif category == "лёд_фигурный":
        ice_figurine[ingredient] += amount
    elif category == "украшение_шт":
        decorations_pcs[ingredient] += amount
    elif category == "украшение_гр":
        decorations_gr[ingredient] += amount


def _collect_pf_ingredients(
    ingredient: str,
    amount: float,
    db: Database,
    alcohol: Dict[str, float],
    non_alcohol: Dict[str, float],
    syrups: Dict[str, float],
    puree: Dict[str, float],
    concentrate: Dict[str, float],
    dry_gr: Dict[str, float],
    ice_cube: Dict[str, float],
    ice_figurine: Dict[str, float],
    decorations_pcs: Dict[str, float],
    decorations_gr: Dict[str, float],
    unknown_pf: List[str],
):
    """Рекурсивно разворачивает ПФ в базовые ингредиенты по категориям."""
    pf_name = _strip_pf(ingredient)
    if pf_name not in db.semi_products:
        unknown_pf.append(pf_name)
        return

    pf = db.semi_products[pf_name]
    for pf_ing, pf_ratio in pf.recipe.items():
        actual_amount = amount * (pf_ratio / pf.output_volume)
        if pf_ing.startswith(PF_PREFIX):
            _collect_pf_ingredients(
                pf_ing,
                actual_amount,
                db,
                alcohol,
                non_alcohol,
                syrups,
                puree,
                concentrate,
                dry_gr,
                ice_cube,
                ice_figurine,
                decorations_pcs,
                decorations_gr,
                unknown_pf,
            )
        else:
            _add_to_category(
                pf_ing,
                actual_amount,
                db,
                alcohol,
                non_alcohol,
                syrups,
                puree,
                concentrate,
                dry_gr,
                ice_cube,
                ice_figurine,
                decorations_pcs,
                decorations_gr,
            )


def calculate_shopping_list(
    order: Dict[str, int], prices: Dict[str, int], db: Database
) -> Dict:
    """Рассчитывает полный список закупок."""

    alcohol = defaultdict(float)
    non_alcohol = defaultdict(float)
    syrups = defaultdict(float)
    puree = defaultdict(float)
    concentrate = defaultdict(float)
    dry_gr = defaultdict(float)
    ice_cube = defaultdict(float)
    ice_figurine = defaultdict(float)
    decorations_pcs = defaultdict(float)
    decorations_gr = defaultdict(float)
    glassware = defaultdict(float)

    pf_to_make = defaultdict(float)

    unknown_cocktails = []
    unknown_pf = []
    found_cocktails = []
    detailed_calc = []

    for cocktail_name, count in order.items():
        key = find_cocktail(cocktail_name, db.cocktails)
        if key is None:
            unknown_cocktails.append(cocktail_name)
            continue

        cocktail = db.cocktails[key]
        found_cocktails.append((cocktail.name, count))

        cocktail_detail = {"name": cocktail.name, "count": count, "ingredients": {}}

        for ingredient, amount_per in cocktail.recipe.items():
            total_amount = amount_per * count
            cocktail_detail["ingredients"][ingredient] = total_amount

            if ingredient.startswith(PF_PREFIX):
                pf_name = _strip_pf(ingredient)
                pf_to_make[pf_name] += total_amount
                _collect_pf_ingredients(
                    ingredient,
                    total_amount,
                    db,
                    alcohol,
                    non_alcohol,
                    syrups,
                    puree,
                    concentrate,
                    dry_gr,
                    ice_cube,
                    ice_figurine,
                    decorations_pcs,
                    decorations_gr,
                    unknown_pf,
                )
            else:
                _add_to_category(
                    ingredient,
                    total_amount,
                    db,
                    alcohol,
                    non_alcohol,
                    syrups,
                    puree,
                    concentrate,
                    dry_gr,
                    ice_cube,
                    ice_figurine,
                    decorations_pcs,
                    decorations_gr,
                )

        for dec, amount_per in cocktail.decorations.items():
            total_dec = amount_per * count
            cocktail_detail["ingredients"][dec] = total_dec
            category = db.categories.get(dec, "украшение_шт")
            if category == "украшение_шт":
                decorations_pcs[dec] += total_dec
            elif category == "украшение_гр":
                decorations_gr[dec] += total_dec

        for glass, amount_per in cocktail.glassware.items():
            total_glass = amount_per * count
            cocktail_detail["ingredients"][glass] = total_glass
            glassware[glass] += total_glass

        detailed_calc.append(cocktail_detail)

    total_cost = 0

    def _calc_bottles(items: Dict[str, float]) -> Dict[str, Dict]:
        nonlocal total_cost
        result = {}
        for ing, amount in items.items():
            bottle_vol = db.bottle_volumes.get(ing, 0.7)
            bottles = math.ceil(amount / bottle_vol) if bottle_vol > 0 else 0
            cost = bottles * prices.get(ing, 0)
            result[ing] = {
                "liters": round(amount, 3),
                "bottles": bottles,
                "bottle_vol": bottle_vol,
                "cost": cost,
            }
            total_cost += cost
        return result

    def _calc_per_liter(items: Dict[str, float]) -> Dict[str, Dict]:
        nonlocal total_cost
        result = {}
        for ing, amount in items.items():
            cost = round(amount * prices.get(ing, 0))
            result[ing] = {"liters": round(amount, 3), "cost": cost}
            total_cost += cost
        return result

    def _calc_pcs(items: Dict[str, float]) -> Dict[str, Dict]:
        nonlocal total_cost
        result = {}
        for ing, amount in items.items():
            pcs = math.ceil(amount)
            cost = pcs * prices.get(ing, 0)
            result[ing] = {"pcs": pcs, "cost": cost}
            total_cost += cost
        return result

    def _calc_grams(items: Dict[str, float]) -> Dict[str, Dict]:
        nonlocal total_cost
        result = {}
        for ing, amount in items.items():
            gr = math.ceil(amount)
            price = prices.get(ing, 0)
            cost = round((gr / 1000) * price) if price > 0 else 0
            result[ing] = {"gr": gr, "cost": cost}
            total_cost += cost
        return result

    alcohol_cost = _calc_bottles(alcohol)
    non_alc_cost = _calc_per_liter(non_alcohol)
    syrup_cost = _calc_bottles(syrups)
    puree_cost = _calc_per_liter(puree)
    concentrate_cost = _calc_per_liter(concentrate)
    dry_gr_cost = _calc_grams(dry_gr)
    ice_cube_cost = _calc_per_liter(ice_cube)
    ice_fig_cost = _calc_pcs(ice_figurine)
    dec_pcs_cost = _calc_pcs(decorations_pcs)
    dec_gr_cost = _calc_grams(decorations_gr)

    return {
        "found_cocktails": found_cocktails,
        "unknown": unknown_cocktails,
        "unknown_pf": list(set(unknown_pf)),
        "detailed_calc": detailed_calc,
        "pf_to_make": dict(pf_to_make),
        "alcohol": alcohol_cost,
        "non_alcohol": non_alc_cost,
        "syrups": syrup_cost,
        "puree": puree_cost,
        "concentrate": concentrate_cost,
        "dry_gr": dry_gr_cost,
        "ice_cube": ice_cube_cost,
        "ice_figurine": ice_fig_cost,
        "decorations_pcs": dec_pcs_cost,
        "decorations_gr": dec_gr_cost,
        "glassware": dict(glassware),
        "total_cost": round(total_cost),
    }


def format_report(result: Dict, categories: Optional[Dict[str, str]] = None) -> str:
    """Форматирует отчёт в красивый текст."""
    categories = categories or {}
    lines = []

    lines.append("╔══════════════════════════════════════════════════╗")
    lines.append("║         🍹 ОТЧЁТ ПО ЗАКУПКАМ КОКТЕЙЛЕЙ          ║")
    lines.append("╚══════════════════════════════════════════════════╝")
    lines.append("")

    lines.append("📋 ЗАКАЗ:")
    for name, count in result["found_cocktails"]:
        lines.append(f"   • {name} — {count} шт.")
    if result["unknown"]:
        lines.append("")
        lines.append(f"⚠️  Не найдены коктейли: {', '.join(result['unknown'])}")
    if result.get("unknown_pf"):
        lines.append("")
        lines.append(f"⚠️  Неизвестные ПФ: {', '.join(result['unknown_pf'])}")
    lines.append("")
    lines.append("─" * 50)
    lines.append("")

    lines.append("📊 ДЕТАЛЬНЫЙ РАСЧЁТ ПО КОКТЕЙЛЯМ:")
    lines.append("")
    for detail in result["detailed_calc"]:
        lines.append(f"▸ {detail['name']} × {detail['count']}:")
        for ing, amount in detail["ingredients"].items():
            unit = _unit_for_ingredient(ing, categories)
            if unit == "л":
                lines.append(f"   {ing}: {amount:.3f} л")
            elif unit == "кг":
                lines.append(f"   {ing}: {amount:.2f} кг")
            else:
                lines.append(f"   {ing}: {math.ceil(amount)} {unit}")
        lines.append("")

    lines.append("─" * 50)
    lines.append("")

    if result["pf_to_make"]:
        lines.append("🔧 ПОЛУФАБРИКАТЫ (нужно приготовить):")
        for pf, amount in result["pf_to_make"].items():
            lines.append(f"   • (ПФ) {pf.title()}: {amount:.3f} л")
        lines.append("")

    lines.append("─" * 50)
    lines.append("")

    _append_section(lines, "🥃 АЛКОГОЛЬ (закупить):", result["alcohol"], "л", "бут.")
    _append_section_liters(lines, "🥤 Б/А — БЕЗАЛКОГОЛЬНОЕ (закупить):", result["non_alcohol"])
    _append_section(lines, "🧪 СИРОПЫ (закупить):", result["syrups"], "л", "бут.")
    _append_section_liters(lines, "🍑 ПЮРЕ (закупить):", result["puree"])
    _append_section_liters(lines, "🧃 КОНЦЕНТРАТЫ (закупить):", result["concentrate"])
    _append_section_grams(lines, "🧂 СУХИЕ ИНГРЕДИЕНТЫ (закупить):", result["dry_gr"])
    _append_section_liters(lines, "🧊 ЛЁД КУБИКОВЫЙ (закупить):", result["ice_cube"], unit="кг")
    _append_section_pcs(lines, "🧊 ЛЁД ФИГУРНЫЙ (закупить):", result["ice_figurine"])
    _append_section_pcs(lines, "🍒 УКРАШЕНИЯ (шт):", result["decorations_pcs"])
    _append_section_grams(lines, "🧂 УКРАШЕНИЯ (гр):", result["decorations_gr"])

    if result["glassware"]:
        lines.append("🍷 ПОСУДА:")
        for glass, count in sorted(result["glassware"].items()):
            lines.append(f"   • {glass.title()}: {math.ceil(count)} шт")
        lines.append("")

    lines.append("═" * 50)
    lines.append(f"💰 ИТОГО: {result['total_cost']} ₽")
    lines.append("═" * 50)

    return "\n".join(lines)


def _unit_for_ingredient(ing: str, categories: Dict[str, str]) -> str:
    """Определяет единицу измерения для ингредиента в детальном расчёте."""
    if ing.startswith(PF_PREFIX):
        return "л"
    category = categories.get(ing, "")
    unit_map = {
        "алкоголь": "л",
        "безалкогольное": "л",
        "сироп": "л",
        "пюре": "л",
        "концентрат": "л",
        "лёд_кубик": "кг",
        "лёд_фигурный": "шт",
        "украшение_шт": "шт",
        "украшение_гр": "гр",
        "сухой_гр": "гр",
        "посуда": "шт",
    }
    return unit_map.get(category, "л")


def _append_section(lines: List[str], title: str, items: Dict, unit: str, bottle_label: str):
    if not items:
        return
    lines.append(title)
    for ing, data in sorted(items.items()):
        lines.append(
            f"   • {ing.title()}: {data['liters']:.3f} {unit} "
            f"({data['bottles']} {bottle_label} × {data['bottle_vol']} {unit}) — {data['cost']} ₽"
        )
    lines.append("")


def _append_section_liters(lines: List[str], title: str, items: Dict, unit: str = "л"):
    if not items:
        return
    lines.append(title)
    for ing, data in sorted(items.items()):
        cost_str = f" — {data['cost']} ₽" if data["cost"] > 0 else ""
        lines.append(f"   • {ing.title()}: {data['liters']:.3f} {unit}{cost_str}")
    lines.append("")


def _append_section_pcs(lines: List[str], title: str, items: Dict):
    if not items:
        return
    lines.append(title)
    for ing, data in sorted(items.items()):
        cost_str = f" — {data['cost']} ₽" if data["cost"] > 0 else ""
        lines.append(f"   • {ing.title()}: {data['pcs']} шт{cost_str}")
    lines.append("")


def _append_section_grams(lines: List[str], title: str, items: Dict):
    if not items:
        return
    lines.append(title)
    for ing, data in sorted(items.items()):
        cost_str = f" — {data['cost']} ₽" if data["cost"] > 0 else ""
        lines.append(f"   • {ing.title()}: {data['gr']} гр{cost_str}")
    lines.append("")


def generate_txt_report(result: Dict) -> str:
    """Генерирует TXT отчёт для экспорта."""
    lines = []
    lines.append("=" * 60)
    lines.append("ОТЧЁТ ПО ЗАКУПКАМ КОКТЕЙЛЕЙ")
    lines.append(f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    lines.append("=" * 60)
    lines.append("")

    lines.append("ЗАКАЗ:")
    for name, count in result["found_cocktails"]:
        lines.append(f"  {name} — {count} шт.")
    if result["unknown"]:
        lines.append(f"Не найдены: {', '.join(result['unknown'])}")
    if result.get("unknown_pf"):
        lines.append(f"Неизвестные ПФ: {', '.join(result['unknown_pf'])}")
    lines.append("")

    lines.append("-" * 60)
    lines.append("ДЕТАЛЬНЫЙ РАСЧЁТ:")
    for detail in result["detailed_calc"]:
        lines.append(f"\n{detail['name']} × {detail['count']}:")
        for ing, amount in detail["ingredients"].items():
            lines.append(f"  {ing}: {amount:.4f}")

    lines.append("\n" + "-" * 60)

    if result["pf_to_make"]:
        lines.append("\nПФ ДЛЯ ПРИГОТОВЛЕНИЯ:")
        for pf, amount in result["pf_to_make"].items():
            lines.append(f"  (ПФ) {pf}: {amount:.3f} л")

    sections = [
        ("\nАЛКОГОЛЬ:", result["alcohol"], "л", "бут."),
        ("\nБ/А:", result["non_alcohol"], "л", None),
        ("\nСИРОПЫ:", result["syrups"], "л", "бут."),
        ("\nПЮРЕ:", result["puree"], "л", None),
        ("\nКОНЦЕНТРАТЫ:", result["concentrate"], "л", None),
        ("\nСУХИЕ ИНГРЕДИЕНТЫ:", result["dry_gr"], "гр", None),
        ("\nЛЁД КУБИКОВЫЙ:", result["ice_cube"], "кг", None),
        ("\nЛЁД ФИГУРНЫЙ:", result["ice_figurine"], "шт", None),
        ("\nУКРАШЕНИЯ (шт):", result["decorations_pcs"], "шт", None),
        ("\nУКРАШЕНИЯ (гр):", result["decorations_gr"], "гр", None),
    ]

    for title, items, unit, bottle_label in sections:
        if not items:
            continue
        lines.append(title)
        for ing, data in sorted(items.items()):
            if "bottles" in data:
                lines.append(
                    f"  {ing}: {data['liters']:.3f} {unit} ({data['bottles']} бут.) — {data['cost']} ₽"
                )
            elif "pcs" in data:
                lines.append(f"  {ing}: {data['pcs']} {unit} — {data['cost']} ₽")
            elif "gr" in data:
                lines.append(f"  {ing}: {data['gr']} {unit} — {data['cost']} ₽")
            else:
                lines.append(f"  {ing}: {data['liters']:.3f} {unit} — {data['cost']} ₽")

    if result["glassware"]:
        lines.append("\nПОСУДА:")
        for glass, count in sorted(result["glassware"].items()):
            lines.append(f"  {glass}: {math.ceil(count)} шт")

    lines.append("\n" + "=" * 60)
    lines.append(f"ИТОГО: {result['total_cost']} ₽")
    lines.append("=" * 60)

    return "\n".join(lines)
