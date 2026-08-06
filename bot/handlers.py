import os
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

from cocktail_calc.calculator import (
    calculate_shopping_list,
    format_report,
    generate_txt_report,
    parse_order,
)
from cocktail_calc.repository import (
    load_database,
    load_default_prices,
    load_user_prices,
    reset_user_prices,
    save_user_prices,
)

WAITING_PRICE_INGREDIENT, WAITING_PRICE_VALUE = range(2)

DATA_DIR = "bot_data"
os.makedirs(DATA_DIR, exist_ok=True)

db = load_database()


def _escape_md(text: str) -> str:
    """Экранирует спецсимволы MarkdownV2."""
    chars = r"_\*\[\]\(\)\~\`\>\#\+\-\=\|\{\}\.\!"
    return text


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (
        "🍹 *CocktailCalc Pro*\n\n"
        "Расчёт закупок для бара и вечеринок.\n\n"
        "*Формат ввода:*\n"
        "`Кокосовый ром 10, Мохито 5`\n\n"
        "*Команды:*\n"
        "📋 /menu — список коктейлей\n"
        "🔧 /pf — список ПФ\n"
        "💰 /prices — цены\n"
        "🔄 /reset_prices — сброс цен\n"
        "❓ /help — помощь"
    )
    await update.message.reply_text(welcome, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🍹 *CocktailCalc Pro — Помощь*\n\n"
        "*Формат заказа:*\n"
        "`Кокосовый ром 10, Мохито 5, Космополитен 3`\n\n"
        "*Категории в отчёте:*\n"
        "🔧 ПФ для приготовления\n"
        "🥃 Алкоголь (закупить)\n"
        "🥤 Б/А — безалкогольное (закупить)\n"
        "🧪 Сиропы (закупить)\n"
        "🧊 Лёд кубиковый (кг) / фигурный (шт)\n"
        "🍒 Украшения\n"
        "🍷 Посуда (количество)\n"
        "💰 Общая стоимость"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = ["📋 *Доступные коктейли:*\n"]
    for i, (key, cocktail) in enumerate(db.cocktails.items(), 1):
        ings = ", ".join([k for k in cocktail.recipe.keys() if not k.startswith("(ПФ)")][:3])
        lines.append(f"{i}. *{cocktail.name}* — {ings}...")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def pf_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = ["🔧 *Полуфабрикаты в базе:*\n"]
    for key, pf in db.semi_products.items():
        lines.append(f"*{pf.name}* — выход {pf.output_volume} л")
        for ing, amount in pf.recipe.items():
            lines.append(f"  • {ing.title()}: {amount} л")
        lines.append("")
    lines.append("_Если нужен новый ПФ — добавлю по запросу_")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def prices_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    prices = load_user_prices(user_id)
    lines = ["💰 *Текущие цены (руб):*\n"]

    lines.append("🥃 *Алкоголь:*")
    for ing in sorted(db.prices.keys()):
        if db.categories.get(ing) == "алкоголь":
            vol = db.bottle_volumes.get(ing, 0.7)
            lines.append(f"  {ing.title()}: {prices.get(ing, 0)} ₽ ({vol} л)")

    keyboard = [[InlineKeyboardButton("✏️ Изменить цену", callback_data="edit_price")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "\n".join(lines), parse_mode="Markdown", reply_markup=reply_markup
    )


async def reset_prices_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    reset_user_prices(user_id)
    await update.message.reply_text("🔄 Цены сброшены на стандартные!")


# ─── Conversation для изменения цен ──────────────────────────────────────────

async def edit_price_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ingredients = "\n".join([f"• {ing}" for ing in sorted(db.prices.keys())])
    await query.edit_message_text(
        f"✏️ *Изменение цены*\n\n"
        f"Напиши название ингредиента:\n\n{ingredients}\n\n"
        f"_Или \"отмена\"_",
        parse_mode="Markdown",
    )
    return WAITING_PRICE_INGREDIENT


async def receive_price_ingredient(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower().strip()
    if text in ("отмена", "cancel"):
        await update.message.reply_text("❌ Отменено.")
        return ConversationHandler.END

    found = None
    for ing in db.prices:
        if text == ing or text in ing:
            found = ing
            break

    if found is None:
        await update.message.reply_text("❌ Не найдено. Попробуй ещё или \"отмена\".")
        return WAITING_PRICE_INGREDIENT

    context.user_data["price_ingredient"] = found
    current = load_user_prices(update.effective_user.id).get(found, 0)
    await update.message.reply_text(f"💰 {found.title()}: {current} ₽\nВведи новую цену:")
    return WAITING_PRICE_VALUE


async def receive_price_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        new_price = int(update.message.text.strip())
        if new_price < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Введи число ≥ 0.")
        return WAITING_PRICE_VALUE

    ingredient = context.user_data["price_ingredient"]
    user_id = update.effective_user.id
    prices = load_user_prices(user_id)
    prices[ingredient] = new_price
    save_user_prices(user_id, prices)

    await update.message.reply_text(f"✅ {ingredient.title()}: {new_price} ₽")
    return ConversationHandler.END


async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Отменено.")
    return ConversationHandler.END


# ─── Обработка заказа ────────────────────────────────────────────────────────

async def process_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    order = parse_order(text)
    if not order:
        await update.message.reply_text(
            "❌ Не распознал. Пример:\n"
            "`Кокосовый ром 10, Мохито 5`",
            parse_mode="Markdown",
        )
        return

    prices = load_user_prices(user_id)
    result = calculate_shopping_list(order, prices, db)

    if not result["found_cocktails"]:
        await update.message.reply_text("❌ Коктейли не найдены. Список: /menu")
        return

    context.user_data["last_result"] = result

    response = format_report(result, db)
    keyboard = [[InlineKeyboardButton("📄 Экспорт TXT", callback_data="export_txt")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if len(response) > 4000:
        parts = [response[i:i+4000] for i in range(0, len(response), 4000)]
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                await update.message.reply_text(part, reply_markup=reply_markup)
            else:
                await update.message.reply_text(part)
    else:
        await update.message.reply_text(response, reply_markup=reply_markup)


async def export_txt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    result = context.user_data.get("last_result")
    if not result:
        await query.edit_message_text("❌ Результат не найден.")
        return

    report = generate_txt_report(result)
    filename = f"cocktail_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    filepath = os.path.join(DATA_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(report)

    await query.message.reply_document(
        document=open(filepath, "rb"),
        filename=filename,
        caption="📄 Отчёт по закупкам",
    )
