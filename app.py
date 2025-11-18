import os
import json
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask, request

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# -------------------------------------------------------
#  GOOGLE SHEETS CONNECTION USING ENV VARIABLE
# -------------------------------------------------------
def get_gsheet():
    creds_json = os.getenv("GOOGLE_CREDS")
    creds_dict = json.loads(creds_json)

    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

    client = gspread.authorize(credentials)
    sheet = client.open("ExpensesBot")   # ← name of your Google Sheet
    return sheet


# -------------------------------------------------------
#  ENSURE MONTH SHEET EXISTS
# -------------------------------------------------------
def get_month_sheet():
    sheet = get_gsheet()
    month_name = datetime.datetime.now().strftime("%B")  # "November"
    
    try:
        ws = sheet.worksheet(month_name)
    except gspread.exceptions.WorksheetNotFound:
        ws = sheet.add_worksheet(title=month_name, rows=2000, cols=10)
        ws.append_row(["Date", "Description", "Amount", "Category"])
    
    return ws


# -------------------------------------------------------
#  SAVE EXPENSE
# -------------------------------------------------------
def save_expense(text):
    parts = text.split()
    if len(parts) < 2:
        return "Format: description amount [category]"

    description = parts[0]
    amount = parts[1]

    category = parts[2] if len(parts) >= 3 else "general"

    ws = get_month_sheet()

    today = datetime.datetime.now().strftime("%Y-%m-%d")
    ws.append_row([today, description, amount, category])

    return f"Saved: {description} - {amount} ({category})"


# -------------------------------------------------------
#  TELEGRAM WEBHOOK
# -------------------------------------------------------
@app.route(f"/webhook", methods=["POST"])
def webhook():
    data = request.json

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "").lower()

        # Special command: get current month's sheet URL
        if text == "csv":
            sheet = get_gsheet()
            month_name = datetime.datetime.now().strftime("%B")
            ws = sheet.worksheet(month_name)
            url = sheet.url
            send_message(chat_id, f"Your sheet:\n{url}")
            return "ok"

        response = save_expense(text)
        send_message(chat_id, response)

    return "ok"


def send_message(chat_id, text):
    import requests
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text})


@app.route("/")
def home():
    return "Bot running!"


if __name__ == "__main__":
    app.run()


