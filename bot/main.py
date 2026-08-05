import os

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.handlers import (
    WAITING_PRICE_INGREDIENT,
    WAITING_PRICE_VALUE,
    cancel_conversation,
    edit_price_start,
    export_txt,
    help_command,
    menu_command,
    pf_command,
    prices_command,
    process_order,
    receive_price_ingredient,
    receive_price_value,
    reset_prices_command,
    start,
)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")


def main():
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ Укажи BOT_TOKEN в переменной окружения!")
        return

    application = Application.builder().token(BOT_TOKEN).build()

    price_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_price_start, pattern="^edit_price$")],
        states={
            WAITING_PRICE_INGREDIENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_price_ingredient)
            ],
            WAITING_PRICE_VALUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_price_value)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("pf", pf_command))
    application.add_handler(CommandHandler("prices", prices_command))
    application.add_handler(CommandHandler("reset_prices", reset_prices_command))
    application.add_handler(price_conv)
    application.add_handler(CallbackQueryHandler(export_txt, pattern="^export_txt$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_order))

    print("🍹 CocktailCalc Pro (Telegram) запущен!")
    application.run_polling()


if __name__ == "__main__":
    main()
