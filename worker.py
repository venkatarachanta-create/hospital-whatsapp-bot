import os
import time
import json
from datetime import datetime, timedelta, timezone

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from twilio.rest import Client

# -----------------------------
# ⏰ Timezone (IST)
# -----------------------------
IST = timezone(timedelta(hours=5, minutes=30))

# -----------------------------
# 🔐 Google Sheets Setup
# -----------------------------
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")

if not creds_json:
    raise ValueError("GOOGLE_CREDENTIALS_JSON is missing")

creds_dict = json.loads(creds_json)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
gs_client = gspread.authorize(creds)

sheet = gs_client.open_by_key(os.getenv("SHEET_ID")).sheet1

# -----------------------------
# 📲 Twilio Setup
# -----------------------------
client = Client(
    os.getenv("TWILIO_ACCOUNT_SID"),
    os.getenv("TWILIO_AUTH_TOKEN")
)

FROM_WHATSAPP = os.getenv("TWILIO_WHATSAPP_NUMBER")

if not FROM_WHATSAPP:
    raise ValueError("TWILIO_WHATSAPP_NUMBER missing")

print("🚀 Worker started...")

# -----------------------------
# 🔁 Infinite Loop
# -----------------------------
while True:
    try:
        records = sheet.get_all_records()
        now = datetime.now(IST)

        print("\n⏰ Current Time:", now.strftime("%Y-%m-%d %I:%M:%S %p"))

        for i, row in enumerate(records, start=2):
            try:
                name = row.get("Name")
                phone = row.get("Phone")
                time_str = row.get("Time")
                date_str = row.get("Date")
                status = row.get("Status")

                # -----------------------------
                # ✅ Basic validation
                # -----------------------------
                if not name or not phone or not time_str or not date_str:
                    print(f"⏭️ Skipping row {i} → Missing data")
                    continue

                if str(status).strip() == "Reminder Sent":
                    continue

                # -----------------------------
                # ✅ Clean values
                # -----------------------------
                time_str = str(time_str).strip().upper()
                date_str = str(date_str).strip()

                # -----------------------------
                # ❌ Skip corrupted rows
                # -----------------------------
                if "PENDING" in time_str or "PENDING" in date_str:
                    print(f"⏭️ Skipping row {i} → Corrupted data")
                    continue

                # -----------------------------
                # ✅ Parse datetime safely
                # -----------------------------
                try:
                    appointment = datetime.strptime(
                        f"{date_str} {time_str}",
                        "%Y-%m-%d %I:%M %p"
                    ).replace(tzinfo=IST)
                except Exception as parse_error:
                    print(f"❌ Row {i} parse error:", parse_error)
                    continue

                # -----------------------------
                # ⏰ Reminder time (1 hour before)
                # -----------------------------
                reminder_time = appointment - timedelta(hours=1)

                # -----------------------------
                # 🧪 Debug logs
                # -----------------------------
                print(f"""
📌 Row {i} | {name}
NOW:        {now}
APPOINTMENT:{appointment}
REMINDER:   {reminder_time}
STATUS:     {status}
""")

                # -----------------------------
                # ✅ SAFE WINDOW (5 minutes)
                # -----------------------------
                if reminder_time <= now <= reminder_time + timedelta(minutes=5):

                    print(f"📤 Sending reminder to {name}")

                    # -----------------------------
                    # 📲 Send WhatsApp message
                    # -----------------------------
                    client.messages.create(
                        body=f"⏰ Reminder: Hi {name}, your appointment is at {time_str}",
                        from_=FROM_WHATSAPP,
                        to=phone
                    )

                    # -----------------------------
                    # ✅ Update status
                    # -----------------------------
                    sheet.update_cell(i, 6, "Reminder Sent")

                    print(f"✅ Reminder sent to {name}")

            except Exception as row_error:
                print(f"❌ Row {i} error:", row_error)

    except Exception as main_error:
        print("🔥 Worker main error:", main_error)

    # -----------------------------
    # ⏳ Wait 60 sec
    # -----------------------------
    time.sleep(60)