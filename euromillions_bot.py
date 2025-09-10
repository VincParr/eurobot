import os
import json
import requests
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# === CONFIG ===
TOKEN = os.getenv("TELEGRAM_TOKEN", "INSERISCI_IL_TUO_BOT_TOKEN")
USER_NUMBERS_FILE = "user_numbers.json"
LAST_DRAW_FILE = "last_draw.json"
BASE_URL = "https://euromillions.api.pedromealha.dev/v1/draws?limit=1"

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
    resp = requests.get(BASE_URL)
    resp.raise_for_status()
    data = resp.json()
    draw = data[0]
    return draw["date"], draw["numbers"], draw.get("stars", [])

# === HANDLER TELEGRAM ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ciao! Usa /setnumeri per impostare i tuoi 7 numeri Euromillions.")

async def set_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        numbers = list(map(int, context.args))
        if len(numbers) != 7:
            raise ValueError
        save_numbers(update.effective_user.id, numbers)
        await update.message.reply_text(f"Numeri salvati: {numbers}")
    except:
        await update.message.reply_text("Errore di formato. Usa: /setnumeri n1 n2 n3 n4 n5 n6 n7")

async def check_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_numbers = load_numbers(update.effective_user.id)
    if not user_numbers:
        await update.message.reply_text("Non hai ancora salvato i tuoi numeri. Usa /setnumeri.")
        return
    date, numbers, stars = get_latest_draw()
    all_nums = numbers + stars
    matched = [n for n in user_numbers if n in all_nums]
    await update.message.reply_text(
        f"Estrazione del {date}: Numeri {numbers}, Stelle {stars}\n"
        f"I tuoi numeri: {user_numbers}\nHai indovinato: {matched}"
    )

async def scheduled_check(context: ContextTypes.DEFAULT_TYPE):
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
            await context.bot.send_message(chat_id=int(uid), text=text)

# === MAIN ===
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setnumeri", set_numbers))
    app.add_handler(CommandHandler("controlla", check_results))

    scheduler = AsyncIOScheduler()
    scheduler.add_job(scheduled_check, "cron", day_of_week="tue,fri", hour=22, minute=0, args=[app])
    scheduler.start()

    print("Bot avviato e pronto!")
    app.run_polling()

if __name__ == "__main__":
    main()