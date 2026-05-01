import os
import time
from datetime import datetime, timedelta
import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials
from twilio.rest import Client

# -----------------------------
# 🔐 Google Sheets
# -----------------------------
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds_dict = json.loads(os.getenv("GOOGLE_CREDENTIALS_JSON"))
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
gs_client = gspread.authorize(creds)

sheet = gs_client.open_by_key(os.getenv("SHEET_ID")).sheet1

# -----------------------------
# 📲 Twilio
# -----------------------------
client = Client(
    os.getenv("TWILIO_ACCOUNT_SID"),
    os.getenv("TWILIO_AUTH_TOKEN")
)

FROM_WHATSAPP = os.getenv("TWILIO_WHATSAPP_NUMBER")

# -----------------------------
# 🔁 Loop
# -----------------------------
while True:
    records = sheet.get_all_records()
    now = datetime.now()

    for i, row in enumerate(records, start=2):
        try:
            name = row["Name"]
            phone = row["Phone"]
            time_str = row["Time"]
            date_str = row["Date"]
            status = row["Status"]

            if status == "Reminder Sent":
                continue

            appointment = datetime.strptime(
                date_str + " " + time_str,
                "%Y-%m-%d %I:%M %p"
            )

            reminder_time = appointment - timedelta(hours=1)

            # 🔥 Safe window
            if reminder_time <= now <= reminder_time + timedelta(minutes=5):

                client.messages.create(
                    body=f"⏰ Reminder: Hi {name}, your appointment is at {time_str}",
                    from_=FROM_WHATSAPP,
                    to=phone
                )

                # ✅ mark sent
                sheet.update_cell(i, 6, "Reminder Sent")

                print(f"✅ Reminder sent to {name}")

        except Exception as e:
            print("Error:", e)

    time.sleep(60)