# euromillions_bot.py
import os
import json
import requests
from datetime import datetime, timedelta, timezone
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import nest_asyncio
import asyncio

# Applichiamo nest_asyncio per Render
nest_asyncio.apply()

# === CONFIG ===
TOKEN = os.getenv("TELEGRAM_TOKEN")
USER_NUMBERS_FILE = "user_numbers.json"
LAST_DRAW_FILE = "last_draw.json"
BASE_URL = "https://euromillions.api.pedromealha.dev"

# === FUNZIONI DI SUPPORTO ===
def save_numbers(user_id, numbers):
    data = {}
    if os.path.exists(USER_NUMBERS_FILE):
        data = json.load(open(USER_NUMBERS_FILE))
    data[str(user_id)] = numbers
    json.dump(data, open(USER_NUMBERS_FILE, "w"))

def load_numbers(user_id):
    if os.path.exists(USER_NUMBERS_FILE):
        return json.load(open(USER_NUMBERS_FILE)).get(str(user_id))
    return None

def load_last_draw_date():
    if os.path.exists(LAST_DRAW_FILE):
        return json.load(open(LAST_DRAW_FILE)).get("date")
    return None

def save_last_draw_date(date_str):
    json.dump({"date": date_str}, open(LAST_DRAW_FILE, "w"))

def get_latest_draw():
    resp = requests.get(BASE_URL + "/v1/draws")
    resp.raise_for_status()
    data = resp.json()
    # Prende l'ultima estrazione disponibile
    if isinstance(data, list):
        draw = data[-1]
    else:
        draw = data
    return draw['date'], draw['numbers'], draw.get('stars', [])

# === HANDLER TELEGRAM ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ciao! Usa /setnumeri per impostare i tuoi 7 numeri Euromillions.")

async def set_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        nums = list(map(int, context.args))
        if len(nums) != 7:
            raise ValueError
        save_numbers(update.effective_user.id, nums)
        await update.message.reply_text(f"Numeri salvati: {nums}")
    except:
        await update.message.reply_text("Errore di formato. Usa: /setnumeri n1 n2 ... n7")

async def check_results_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_nums = load_numbers(update.effective_user.id)
    if not user_nums:
        await update.message.reply_text("Non hai ancora impostato i tuoi numeri. Usa /setnumeri.")
        return
    date, numbers, stars = get_latest_draw()
    all_nums = numbers + stars
    matched = [n for n in user_nums if n in all_nums]
    await update.message.reply_text(
        f"Estrazione del {date}: Numeri {numbers}, Stelle {stars}\n"
        f"I tuoi numeri: {user_nums}\nHai indovinato: {matched}"
    )

# === SCHEDULER INTERNO ===
async def scheduled_check(app):
    while True:
        try:
            date, numbers, stars = get_latest_draw()
            last_date = load_last_draw_date()
            if date != last_date:
                save_last_draw_date(date)
                all_nums = numbers + stars
                header = f"🆕 Nuova estrazione Euromillions del {date}:\nNumeri: {numbers}, Stelle: {stars}\n"
                users = json.load(open(USER_NUMBERS_FILE)) if os.path.exists(USER_NUMBERS_FILE) else {}
                for uid, nums in users.items():
                    matched = [n for n in nums if n in all_nums]
                    text = header + f"I tuoi numeri: {nums}\nHai indovinato: {matched}"
                    await app.bot.send_message(chat_id=int(uid), text=text)
        except Exception as e:
            print("Errore scheduler:", e)
        # Calcola secondi fino al prossimo martedì o venerdì 22:00 UTC
        now = datetime.now(timezone.utc)
        next_run = now.replace(second=0, microsecond=0)
        while next_run.weekday() not in [2, 4] or next_run.hour >= 23 and next_run.minute>=13:
            next_run += timedelta(days=1)
        next_run = next_run.replace(hour=23, minute=13)
        sleep_seconds = (next_run - now).total_seconds()
        await asyncio.sleep(sleep_seconds)

# === MAIN ===
async def main():
    app = Application.builder().token(TOKEN).build()

    # Ignora eventuali aggiornamenti pendenti per evitare conflitti
    await app.bot.get_updates(offset=-1)

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setnumeri", set_numbers))
    app.add_handler(CommandHandler("controlla", check_results_cmd))

    # Task scheduler
    asyncio.get_event_loop().create_task(scheduled_check(app))

    print("Bot avviato e pronto!")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())