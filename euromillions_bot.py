# euromillions_bot.py
import os
import json
import requests
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import nest_asyncio
import asyncio
from pytz import timezone

# Applichiamo nest_asyncio per Render
nest_asyncio.apply()

# === CONFIG ===
TOKEN = os.getenv("TELEGRAM_TOKEN")
USER_NUMBERS_FILE = "user_numbers.json"
LAST_DRAW_FILE = "last_draw.json"
BASE_URL = "https://euromillions.api.pedromealha.dev"
ITALY_TZ = timezone('Europe/Rome')

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
    if isinstance(data, list):
        draw = data[-1]
    else:
        draw = data
    return draw['date'], draw['numbers'], draw.get('stars', [])

# === HANDLER TELEGRAM ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = (
        "🎲 *Euromillions Bot* 🎲\n\n"
        "Benvenuto! Usa i comandi qui sotto per interagire con me:\n"
        "\n✨ /setnumeri - Imposta i tuoi 7 numeri\n"
        "🔍 /controlla - Controlla l'ultima estrazione"
    )
    await update.message.reply_markdown(message)

async def set_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        nums = list(map(int, context.args))
        if len(nums) != 7:
            raise ValueError
        save_numbers(update.effective_user.id, nums)
        main_nums = nums[:5]
        stars = nums[5:]
        message = (
            f"✅ I tuoi numeri sono stati salvati:\n"
            f"🎯 Numeri principali: {' - '.join(map(str, main_nums))}\n"
            f"⭐ Numeri Stella: {' - '.join(map(str, stars))}"
        )
        await update.message.reply_text(message)
    except:
        await update.message.reply_text("⚠️ Errore! Usa il formato: /setnumeri n1 n2 n3 n4 n5 s1 s2")

async def check_results_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_nums = load_numbers(update.effective_user.id)
    if not user_nums:
        await update.message.reply_text("⚠️ Non hai ancora impostato i tuoi numeri. Usa /setnumeri.")
        return
    date, numbers, stars = get_latest_draw()
    main_nums = user_nums[:5]
    star_nums = user_nums[5:]
    all_nums = numbers + stars
    matched_main = [n for n in main_nums if n in all_nums]
    matched_stars = [n for n in star_nums if n in all_nums]

    message = (
        f"📅 *Estrazione del {date}*\n"
        f"🎲 Numeri estratti: {' - '.join(map(str, numbers))}\n"
        f"⭐ Stelle estratte: {' - '.join(map(str, stars))}\n\n"
        f"🎯 I tuoi numeri: {' - '.join(map(str, main_nums))}\n"
        f"⭐ I tuoi numeri Stella: {' - '.join(map(str, star_nums))}\n"
        f"🏆 Numeri indovinati: {' - '.join(map(str, matched_main)) if matched_main else 'Nessuno'}\n"
        f"🏅 Stelle indovinate: {' - '.join(map(str, matched_stars)) if matched_stars else 'Nessuna'}"
    )
    await update.message.reply_markdown(message)

# === SCHEDULER INTERNO ===
async def scheduled_check(app):
    while True:
        try:
            date, numbers, stars = get_latest_draw()
            last_date = load_last_draw_date()
            if date != last_date:
                save_last_draw_date(date)
                users = json.load(open(USER_NUMBERS_FILE)) if os.path.exists(USER_NUMBERS_FILE) else {}
                for uid, user_nums in users.items():
                    main_nums = user_nums[:5]
                    star_nums = user_nums[5:]
                    all_nums = numbers + stars
                    matched_main = [n for n in main_nums if n in all_nums]
                    matched_stars = [n for n in star_nums if n in all_nums]

                    header = f"🆕 *Nuova estrazione Euromillions del {date}*\n"
                    message = (
                        f"{header}"
                        f"🎲 Numeri estratti: {' - '.join(map(str, numbers))}\n"
                        f"⭐ Stelle estratte: {' - '.join(map(str, stars))}\n\n"
                        f"🎯 I tuoi numeri: {' - '.join(map(str, main_nums))}\n"
                        f"⭐ I tuoi numeri Stella: {' - '.join(map(str, star_nums))}\n"
                        f"🏆 Numeri indovinati: {' - '.join(map(str, matched_main)) if matched_main else 'Nessuno'}\n"
                        f"🏅 Stelle indovinate: {' - '.join(map(str, matched_stars)) if matched_stars else 'Nessuna'}"
                    )
                    await app.bot.send_message(chat_id=int(uid), text=message, parse_mode='Markdown')
        except Exception as e:
            print("Errore scheduler:", e)

        # Calcola secondi fino alle 23:45 ora italiana tutti i giorni
        now = datetime.now(ITALY_TZ)
        next_run = now.replace(second=0, microsecond=0)
        if now.hour > 23 or (now.hour == 23 and now.minute >= 47):
            next_run += timedelta(days=1)
        next_run = next_run.replace(hour=23, minute=47)
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

    print("🤖 Bot avviato e pronto!")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())