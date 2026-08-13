import json
import os
from typing import Dict, Union

from .config import DB_FILE, user_prices_file
from .models import Cocktail, Database, SemiProduct


def load_database() -> Database:
    with open(DB_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    semi_products = {
        key: SemiProduct(
            name=value["name"],
            output_volume=value["output_volume"],
            recipe=value["recipe"],
            unit=value.get("unit", "л"),
        )
        for key, value in data["semi_products"].items()
    }

    cocktails = {
        key: Cocktail(
            name=value["name"],
            recipe=value["recipe"],
            decorations=value.get("decorations", {}),
            glassware=value.get("glassware", {}),
            category=value.get("category", ""),
            verified=value.get("verified", False),
        )
        for key, value in data["cocktails"].items()
    }

    return Database(
        semi_products=semi_products,
        cocktails=cocktails,
        categories=data["categories"],
        bottle_volumes=data["bottle_volumes"],
        prices=data["prices"],
        ingredient_info=data.get("ingredient_info", {}),
        cocktail_categories=data.get("cocktail_categories", []),
    )


def load_default_prices() -> Dict[str, int]:
    db = load_database()
    return db.prices.copy()


def load_user_prices(user_id: Union[int, str]) -> Dict[str, int]:
    path = user_prices_file(user_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return load_default_prices()


def save_user_prices(user_id: Union[int, str], prices: Dict[str, int]):
    path = user_prices_file(user_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(prices, f, ensure_ascii=False, indent=2)


def reset_user_prices(user_id: Union[int, str]) -> Dict[str, int]:
    prices = load_default_prices()
    save_user_prices(user_id, prices)
    return prices
