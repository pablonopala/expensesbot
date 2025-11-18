from flask import Flask, request
import requests
import csv
import os
from datetime import datetime

TOKEN = os.getenv("TELEGRAM_TOKEN")
BASE_URL = f"https://api.telegram.org/bot{TOKEN}/"
CSV_FILE = "expenses.csv"

app = Flask(__name__)

# Create CSV if not exists
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "category", "amount", "raw_text"])


def send_message(chat_id, text):
    url = BASE_URL + "sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    requests.post(url, json=payload)


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    if "message" not in data:
        return "ok"

    chat_id = data["message"]["chat"]["id"]
    text = data["message"]["text"]

    # If message is "/total"
    if text == "/total":
        total = 0
        if os.path.exists(CSV_FILE):
            with open(CSV_FILE, "r") as f:
                next(f)
                for row in csv.reader(f):
                    total += float(row[2])

        send_message(chat_id, f"💰 Total gastado: ${total}")
        return "ok"

    # AUTO-PARSE: "<category> <amount>"
    try:
        parts = text.split()
        amount = float(parts[-1])
        category = " ".join(parts[:-1]) if len(parts) > 1 else "other"
    except:
        send_message(chat_id, "Formato inválido. Ejemplo:\n\ncomida 120")
        return "ok"

    # Save to CSV
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(CSV_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([now, category, amount, text])

    send_message(chat_id, f"✔️ Guardado: {category} — ${amount}")

    return "ok"


@app.route("/webhook", methods=["POST"])
def health():
    return "Bot is running."


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

