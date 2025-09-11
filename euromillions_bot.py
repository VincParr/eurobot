import os
import asyncio
import nest_asyncio
import requests
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram.ext import Application, CommandHandler
from flask import Flask

# === Flask app per Render ===
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "✅ Euromillions Bot è attivo su Render!"

# === Variabili globali ===
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("❌ BOT_TOKEN non trovato. Imposta la variabile d'ambiente su Render.")

USER_NUMBERS = {}  # user_id -> [num1..5, star1, star2]

# === Funzioni utili ===
def format_numbers(numbers):
    """Formatta i numeri utente in modo carino con emoji"""
    nums = [str(n) for n in numbers[:-2]]
    stars = [f"🌟 {n}" for n in numbers[-2:]]
    return " - ".join(nums) + " | " + " - ".join(stars)

async def start(update, context):
    await update.message.reply_text("👋 Benvenuto nel bot Euromillions!\nUsa /gioca per salvare i tuoi numeri.")

async def gioca(update, context):
    try:
        numbers = list(map(int, context.args))
        if len(numbers) != 7:
            await update.message.reply_text("❌ Devi inserire 7 numeri (5 + 2 stelle).")
            return
        USER_NUMBERS[update.effective_user.id] = numbers
        await update.message.reply_text(
            f"✅ I tuoi numeri sono stati salvati: 🎯 {format_numbers(numbers)}"
        )
    except ValueError:
        await update.message.reply_text("⚠️ Inserisci solo numeri.")

async def controlla(update, context):
    await check_draws(update.effective_user.id, context)

async def check_draws(user_id, context):
    try:
        url = "https://euromillions.api.pedromealha.dev/v1/draws"
        response = requests.get(url, timeout=10)
        data = response.json()
        draw = data["draws"][-1]  # ultimo sorteggio

        winning_nums = draw["numbers"]
        winning_stars = draw["stars"]

        user_nums = USER_NUMBERS.get(user_id)
        if not user_nums:
            await context.bot.send_message(chat_id=user_id, text="❌ Non hai ancora registrato numeri con /gioca")
            return

        hits_nums = set(user_nums[:-2]) & set(winning_nums)
        hits_stars = set(user_nums[-2:]) & set(winning_stars)

        msg = (
            f"🎲 Estrazione Euromillions del {draw['date']}\n\n"
            f"🟢 Numeri vincenti: {winning_nums} + ⭐ {winning_stars}\n"
            f"🎯 I tuoi: {format_numbers(user_nums)}\n\n"
            f"✅ Hai indovinato: {len(hits_nums)} numeri ({hits_nums}) "
            f"e {len(hits_stars)} stelle ({hits_stars})"
        )

        await context.bot.send_message(chat_id=user_id, text=msg)
    except Exception as e:
        await context.bot.send_message(chat_id=user_id, text=f"⚠️ Errore nel recupero estrazione: {e}")

# === Scheduler ===
async def scheduled_task(app):
    for user_id in USER_NUMBERS.keys():
        try:
            await check_draws(user_id, app.bot)
        except Exception as e:
            print(f"Errore invio a {user_id}: {e}")

async def main():
    app = Application.builder().token(TOKEN).build()

    # comandi
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("gioca", gioca))
    app.add_handler(CommandHandler("controlla", controlla))

    # scheduler
    scheduler = AsyncIOScheduler(timezone="Europe/Rome")
    scheduler.add_job(lambda: asyncio.create_task(scheduled_task(app)),
                      CronTrigger(hour=21, minute=0))  # tutti i giorni 21:00
    scheduler.start()

    print("✅ Bot avviato...")
    await app.run_polling()

if __name__ == "__main__":
    nest_asyncio.apply()

    # Avvio Flask in un thread separato
    import threading
    threading.Thread(target=lambda: flask_app.run(host="0.0.0.0", port=8000)).start()

    # Avvio Telegram bot
    loop = asyncio.get_event_loop()
    loop.create_task(main())
    loop.run_forever()
