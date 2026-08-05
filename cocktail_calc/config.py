import os
from typing import Union

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_FILE = os.path.join(DATA_DIR, "cocktails_db.json")

USER_DATA_DIR = os.path.join(DATA_DIR, "users")
os.makedirs(USER_DATA_DIR, exist_ok=True)


def user_prices_file(user_id: Union[int, str]) -> str:
    return os.path.join(USER_DATA_DIR, f"{user_id}_prices.json")
