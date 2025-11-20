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

    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

    client = gspread.authorize(credentials)
    try:
        sheet = client.open("expenses_bot_sheet")
        return sheet
    except gspread.exceptions.APIError as e:
        print("Failed to open sheet:", e)
        raise
# -------------------------------------------------------
#  ENSURE MONTH-YEAR SHEET EXISTS
# -------------------------------------------------------
def get_month_sheet():
    sheet = get_gsheet()
    
    month_name = datetime.datetime.now().strftime("%B")       # "Month"
    year = datetime.datetime.now().strftime("%Y")             # "Year"
    sheet_name = f"{month_name} {year}"                      
    
    try:
        ws = sheet.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        ws = sheet.add_worksheet(title=sheet_name, rows=2000, cols=10)
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
#  READ MONTH DATA
# -------------------------------------------------------
def read_month_data():
    ws = get_month_sheet()              
    data = ws.get_all_records()         
    return ws, data
# -------------------------------------------------------
#  SEND TELEGRAM MESSAGE
# -------------------------------------------------------
def send_message(chat_id, text):
    import requests
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text})
# -------------------------------------------------------
#  DELETE A ROW
# -------------------------------------------------------
def delete_expense(text):
    parts = text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        return "Usage: /delete <row_number>"

    row_number = int(parts[1])
    ws = get_month_sheet()

    try:
        ws.delete_rows(row_number)
        return f"🗑️ Deleted row {row_number}"
    except Exception as e:
        return f"Error deleting row: {e}"
# -------------------------------------------------------
#  SUMMARY BY CATEGORY
# -------------------------------------------------------
def get_category_summary():
    ws, data = read_month_data()

    if not data:
        return "No expenses recorded this month."

    category_totals = {}
    category_counts = {}

    for row in data:
        cat = row.get("Category", "general").lower()
        amt = float(row.get("Amount", 0))

        category_totals[cat] = category_totals.get(cat, 0) + amt
        category_counts[cat] = category_counts.get(cat, 0) + 1

    msg = "📊 *Category Summary (Total & Average)*\n\n"
    for cat in category_totals:
        total = category_totals[cat]
        count = category_counts[cat]
        avg = total / count if count else 0
        msg += f"- *{cat.capitalize()}* → Total: {total:.2f}, Avg: {avg:.2f}\n"

    return msg

# -------------------------------------------------------
# TELEGRAM WEBHOOK
# -------------------------------------------------------
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "").lower()

        # Special command: get current month's sheet URL
        if text == "csv":
            sheet = get_gsheet()
            month_name = datetime.datetime.now().strftime("%B")
            year = datetime.datetime.now().strftime("%Y")
            sheet_name = f"{month_name} {year}"
            ws = sheet.worksheet(sheet_name)
            url = sheet.url
            send_message(chat_id, f"Your sheet:\n{url}")
            return "ok"

        # TELEGRAM COMMANDS
        if text.startswith("/delete"):
            send_message(chat_id, delete_expense(text))
            return "ok"

        if text == "/catsummary":
            send_message(chat_id, get_category_summary())
            return "ok"

        # If not a command → treat as expense
        response = save_expense(text)
        send_message(chat_id, response)

    return "ok"



@app.route("/")
def home():
    return "Bot running!"


if __name__ == "__main__":
    app.run()








