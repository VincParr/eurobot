import os
import asyncio
import nest_asyncio
import requests
from datetime import datetime
from telegram.ext import Application, CommandHandler
from flask import Flask
import threading
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

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
ITALY_TZ = pytz.timezone("Europe/Rome")

API_URL = "https://euromillions.api.pedromealha.dev/v1/draws"

# === Funzioni utili ===
def format_numbers(nums):
    main_nums = " - ".join(str(n) for n in nums[:5])
    stars = " 🌟 ".join(str(n) for n in nums[5:])
    return f"{main_nums} | 🌟 {stars}"

def format_hits(hits):
    if not hits:
        return "Nessuno 😢"
    return " - ".join(str(n) for n in hits)

async def fetch_latest_draw():
    try:
        resp = requests.get(API_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        last_draw = data[-1]  # ultima estrazione
        return last_draw
    except Exception as e:
        print("Errore fetch estrazione:", e)
        return None

# === Comandi bot ===
async def start(update, context):
    await update.message.reply_text("👋 Benvenuto nel bot Euromillions!\nUsa /gioca per salvare i tuoi numeri.")

async def gioca(update, context):
    if len(context.args) != 7:
        await update.message.reply_text("❌ Devi inserire esattamente 7 numeri (5 principali + 2 stelle).")
        return
    try:
        nums = [int(x) for x in context.args]
    except ValueError:
        await update.message.reply_text("⚠️ Inserisci solo numeri!")
        return
    USER_NUMBERS[update.effective_user.id] = nums
    await update.message.reply_text(f"✅ I tuoi numeri sono stati salvati: 🎯 {format_numbers(nums)}")

async def controlla(update, context):
    user_id = update.effective_user.id
    await check_draws(user_id, context)

async def check_draws(user_id, context):
    draw = await fetch_latest_draw()
    if not draw:
        await context.bot.send_message(chat_id=user_id, text="⚠️ Non riesco a recuperare l’estrazione.")
        return

    winning_nums = draw["numbers"]
    winning_stars = draw["stars"]
    draw_date = draw["date"]

    user_nums = USER_NUMBERS.get(user_id)
    if not user_nums:
        await context.bot.send_message(chat_id=user_id, text="❌ Non hai ancora registrato numeri con /gioca")
        return

    hits_nums = set(user_nums[:5]) & set(winning_nums)
    hits_stars = set(user_nums[5:]) & set(winning_stars)

    msg = (
        f"🎲 Estrazione Euromillions del {draw_date}\n\n"
        f"🟢 Numeri vincenti: {' - '.join(map(str, winning_nums))} | 🌟 {' - '.join(map(str, winning_stars))}\n"
        f"🎯 I tuoi: {format_numbers(user_nums)}\n\n"
        f"✅ Hai indovinato: {format_hits(hits_nums)} numeri e {format_hits(hits_stars)} stelle"
    )

    await context.bot.send_message(chat_id=user_id, text=msg)

# === Scheduler automatico ===
async def scheduled_task(app):
    for user_id in USER_NUMBERS.keys():
        await check_draws(user_id, app.bot)

async def main():
    app = Application.builder().token(TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("gioca", gioca))
    app.add_handler(CommandHandler("controlla", controlla))

    # Scheduler
    scheduler = AsyncIOScheduler(timezone=ITALY_TZ)
    scheduler.add_job(lambda: asyncio.create_task(scheduled_task(app)),
                      CronTrigger(hour=21, minute=0))
    scheduler.start()

    print("✅ Bot avviato...")
    await app.run_polling()

# === Avvio ===
if __name__ == "__main__":
    nest_asyncio.apply()

    # Flask in thread separato
    threading.Thread(target=lambda: flask_app.run(host="0.0.0.0", port=8000), daemon=True).start()

    # Telegram bot
    loop = asyncio.get_event_loop()
    loop.create_task(main())
    loop.run_forever()