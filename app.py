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
def delete_expense_last():
    ws = get_month_sheet()
    rows = ws.get_all_values()

    if len(rows) <= 1:
        return "No expenses to delete."

    last_row = len(rows)
    ws.delete_rows(last_row)

    return f"🗑️ Deleted last expense (row {last_row})"
# -------------------------------------------------------
#  SUMMARY BY CATEGORY
# -------------------------------------------------------
def parse_month_year(text):
    """
    Input examples:
      /catsummary
      /catsummary November
      /catsummary November 2025
    """

    parts = text.split()
    month = datetime.datetime.now().strftime("%B")
    year = datetime.datetime.now().strftime("%Y")

    if len(parts) >= 2:
        month_input = parts[1].capitalize()
        try:
            datetime.datetime.strptime(month_input, "%B")
            month = month_input
        except ValueError:
            return None, None

    if len(parts) == 3:
        year_input = parts[2]
        if year_input.isdigit():
            year = year_input

    return month, year

def get_category_summary(text="/catsummary"):
    month, year = parse_month_year(text)

    if not month:
        return "❌ Invalid month. Try: /catsummary November 2025"

    sheet = get_gsheet()
    sheet_name = f"{month} {year}"

    try:
        ws = sheet.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        return f"❌ No sheet found for *{sheet_name}*."

    data = ws.get_all_records()

    if not data:
        return f"No expenses found for {sheet_name}."

    category_totals = {}
    total_general = 0

    for row in data:
        cat = row.get("Category", "general").lower()
        amt = float(row.get("Amount", 0))

        category_totals[cat] = category_totals.get(cat, 0) + amt
        total_general += amt

    msg = f"📊 *Category Summary – {month} {year}*\n\n"
    for cat, total in category_totals.items():
        msg += f"- *{cat.capitalize()}* → {total:.2f}\n"

    msg += f"\n🧮 *Total General:* {total_general:.2f}"

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
        if text == "/delete":
            send_message(chat_id, delete_expense_last())
            return "ok"

        if text.startswith("/catsummary"):
            send_message(chat_id, get_category_summary(text))
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














