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
        name = row.get("Name")
        phone = row.get("Phone")
        time_str = row.get("Time")
        date_str = row.get("Date")
        status = row.get("Status")

        # ✅ Skip invalid rows
        if not time_str or not date_str:
            print(f"Skipping row {i} → Missing time/date")
            continue

        # ✅ Skip already sent reminders
        if status == "Reminder Sent":
            continue

        # ✅ Clean values (VERY IMPORTANT)
        time_str = str(time_str).strip()
        date_str = str(date_str).strip()

        # ❌ Skip corrupted rows like "Pending 2026-05-01"
        if "Pending" in time_str or "Pending" in date_str:
            print(f"Skipping row {i} → Corrupted data")
            continue

        # ✅ Parse safely
        appointment = datetime.strptime(
            f"{date_str} {time_str}",
            "%Y-%m-%d %I:%M %p"
        )

        # 👉 continue your reminder logic...

    except Exception as e:
        print(f"Error in row {i}: {e}")
    
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