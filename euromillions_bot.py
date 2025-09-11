import os
import json
import asyncio
import requests
from datetime import datetime, timedelta
import pytz
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from flask import Flask
import threading

TOKEN = os.getenv("BOT_TOKEN")
USER_NUMBERS_FILE = "user_numbers.json"
ITALY_TZ = pytz.timezone("Europe/Rome")

API_URL = "https://euromillions.api.pedromealha.dev/v1/draws"


# ----------------------------
# Funzioni di utilità
# ----------------------------
def load_user_numbers():
    if os.path.exists(USER_NUMBERS_FILE):
        with open(USER_NUMBERS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_user_numbers(data):
    with open(USER_NUMBERS_FILE, "w") as f:
        json.dump(data, f)

def format_numbers(nums):
    # primi 5 normali, ultimi 2 stelle
    balls = " - ".join(str(n) for n in nums[:5])
    stars = " ⭐ ".join(str(n) for n in nums[5:])
    return f"{balls} ✨ {stars}"

async def fetch_latest_draw():
    try:
        resp = requests.get(API_URL, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            # l’API restituisce una lista, prendiamo l’ultima estrazione
            last_draw = data[-1]
            balls = last_draw["numbers"]
            stars = last_draw["stars"]
            return balls + stars
    except Exception as e:
        print("Errore fetch estrazione:", e)
    return None


# ----------------------------
# Comandi bot
# ----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ciao 👋 Inviami i tuoi 7 numeri con /gioca.")

async def gioca(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 7:
        await update.message.reply_text("Devi inserire esattamente 7 numeri 🎯")
        return

    try:
        nums = [int(x) for x in context.args]
    except ValueError:
        await update.message.reply_text("❌ Inserisci solo numeri!")
        return

    users = load_user_numbers()
    users[str(update.effective_user.id)] = nums
    save_user_numbers(users)

    await update.message.reply_text(f"I tuoi numeri sono stati salvati: {format_numbers(nums)}")

async def controlla(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = load_user_numbers()
    uid = str(update.effective_user.id)
    if uid not in users:
        await update.message.reply_text("Non hai numeri salvati! Usa /gioca prima.")
        return

    draw = await fetch_latest_draw()
    if not draw:
        await update.message.reply_text("⚠️ Non riesco a recuperare l’estrazione.")
        return

    tuoi = set(users[uid])
    usciti = set(draw)
    indovinati = tuoi.intersection(usciti)

    await update.message.reply_text(
        f"📅 Ultima estrazione: {format_numbers(draw)}\n\n"
        f"🎯 I tuoi numeri: {format_numbers(users[uid])}\n\n"
        f"✅ Hai indovinato: {', '.join(map(str, indovinati)) if indovinati else 'Niente 😢'}"
    )


# ----------------------------
# Scheduler automatico
# ----------------------------
async def scheduler(app: Application):
    while True:
        try:
            now = datetime.now(ITALY_TZ)
            target = now.replace(hour=21, minute=0, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)
            sleep_seconds = (target - now).total_seconds()
            print(f"[Scheduler] Prossimo controllo alle {target} (tra {sleep_seconds/60:.1f} min)")
            await asyncio.sleep(sleep_seconds)

            draw = await fetch_latest_draw()
            if not draw:
                continue

            users = load_user_numbers()
            for uid, nums in users.items():
                tuoi = set(nums)
                usciti = set(draw)
                indovinati = tuoi.intersection(usciti)

                await app.bot.send_message(
                    chat_id=int(uid),
                    text=(
                        f"📅 Estrazione di oggi: {format_numbers(draw)}\n\n"
                        f"🎯 I tuoi numeri: {format_numbers(nums)}\n\n"
                        f"✅ Hai indovinato: {', '.join(map(str, indovinati)) if indovinati else 'Niente 😢'}"
                    )
                )
        except Exception as e:
            print("Errore scheduler:", e)
            await asyncio.sleep(60)


# ----------------------------
# Main
# ----------------------------
async def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("gioca", gioca))
    app.add_handler(CommandHandler("controlla", controlla))

    # avvia scheduler in background
    asyncio.create_task(scheduler(app))

    print("✅ Bot avviato...")
    await app.run_polling()


# ----------------------------
# Flask server per Render
# ----------------------------
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "✅ Euromillions Bot attivo su Render!"

def run_flask():
    flask_app.run(host="0.0.0.0", port=8000)

# Avvia Flask in un thread separato
threading.Thread(target=run_flask, daemon=True).start()


# ----------------------------
# Avvio
# ----------------------------
if __name__ == "__main__":
    asyncio.run(main())
