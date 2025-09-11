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
def format_numbers(nums, hits_nums=None, hits_stars=None):
    hits_nums = hits_nums or set()
    hits_stars = hits_stars or set()

    main_nums = []
    for n in nums[:5]:
        if n in hits_nums:
            main_nums.append(f"✅{n}✅")
        else:
            main_nums.append(str(n))
    main_str = " - ".join(main_nums)

    star_nums = []
    for n in nums[5:]:
        if n in hits_stars:
            star_nums.append(f"✨{n}✨")
        else:
            star_nums.append(f"💛{n}💛")
    star_str = " - ".join(star_nums)

    return f"{main_str} | {star_str}"

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
        f"🎲 Estrazione Euromillions del <b>{draw_date}</b>\n\n"
        f"🟢 Numeri vincenti: {' - '.join(map(str, winning_nums))} | 🌟 {' - '.join(map(str, winning_stars))}\n"
        f"🎯 I tuoi: {format_numbers(user_nums, hits_nums, hits_stars)}\n\n"
        f"✅ Hai indovinato: {format_hits(hits_nums)} numeri e {format_hits(hits_stars)} stelle"
    )

    await context.bot.send_message(chat_id=user_id, text=msg, parse_mode="HTML")

# === Scheduler automatico ===
async def scheduled_task(app):
    for user_id in USER_NUMBERS.keys():
        await check_draws(user_id, app.bot)

# Funzione helper per mettere il job sul loop esistente
def schedule_task_in_loop():
    loop = asyncio.get_event_loop()
    loop.create_task(scheduled_task(app))

# === Avvio ===
if __name__ == "__main__":
    nest_asyncio.apply()

    # Flask in thread separato
    threading.Thread(target=lambda: flask_app.run(host="0.0.0.0", port=8000), daemon=True).start()

    # Telegram bot
    loop = asyncio.get_event_loop()
    app = Application.builder().token(TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("gioca", gioca))
    app.add_handler(CommandHandler("controlla", controlla))

    # Scheduler: automatico alle 21:00 italiane (puoi cambiare per test)
    scheduler = AsyncIOScheduler(timezone=ITALY_TZ)
    scheduler.add_job(schedule_task_in_loop,
                      CronTrigger(hour=21, minute=0))  # Cambia qui per test temporaneo
    scheduler.start()

    print(f"✅ Bot avviato. Prossimo controllo alle {scheduler.get_jobs()[0].next_run_time}")

    loop.create_task(app.run_polling())
    loop.run_forever()