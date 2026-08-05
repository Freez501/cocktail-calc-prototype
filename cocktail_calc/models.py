from dataclasses import dataclass, field
from typing import Dict


@dataclass
class SemiProduct:
    name: str
    output_volume: float
    recipe: Dict[str, float]
    unit: str = "л"


@dataclass
class Cocktail:
    name: str
    recipe: Dict[str, float]
    decorations: Dict[str, float] = field(default_factory=dict)
    glassware: Dict[str, float] = field(default_factory=dict)
    category: str = ""


@dataclass
class Database:
    semi_products: Dict[str, SemiProduct]
    cocktails: Dict[str, Cocktail]
    categories: Dict[str, str]
    bottle_volumes: Dict[str, float]
    prices: Dict[str, int]
    ingredient_info: Dict[str, Dict] = field(default_factory=dict)
