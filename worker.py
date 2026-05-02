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

creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")

if not creds_json:
    raise ValueError("GOOGLE_CREDENTIALS_JSON is missing")

creds_dict = json.loads(creds_json)
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

print("🚀 Worker started...")

# -----------------------------
# 🔁 Loop
# -----------------------------
while True:
    try:
        records = sheet.get_all_records()
        from datetime import datetime, timedelta, timezone

        IST = timezone(timedelta(hours=5, minutes=30))
        now = datetime.now(IST)

        for i, row in enumerate(records, start=2):
            try:
                name = row.get("Name")
                phone = row.get("Phone")
                time_str = row.get("Time")
                date_str = row.get("Date")
                status = row.get("Status")

                # -----------------------------
                # ✅ Skip invalid rows
                # -----------------------------
                if not time_str or not date_str:
                    print(f"Skipping row {i} → Missing data")
                    continue

                if status == "Reminder Sent":
                    continue

                # -----------------------------
                # ✅ Clean values
                # -----------------------------
                time_str = str(time_str).strip()
                date_str = str(date_str).strip()

                # ❌ Skip corrupted rows
                if "Pending" in time_str or "Pending" in date_str:
                    print(f"Skipping row {i} → Corrupted")
                    continue

                # -----------------------------
                # ✅ Convert to datetime
                # -----------------------------
                appointment = datetime.strptime(
                    f"{date_str} {time_str}",
                    "%Y-%m-%d %I:%M %p"
                ).replace(tzinfo=IST)

                # ⏰ Reminder 1 hour before
                reminder_time = appointment - timedelta(hours=1)

                # -----------------------------
                # 🧪 Debug logs
                # -----------------------------
                print(f"Row {i} | {name}")
                print("NOW:", now.strftime("%Y-%m-%d %I:%M:%S %p"))
                print("APPOINTMENT:", appointment)
                print("REMINDER:", reminder_time)
                print("-----------------------------")

                # -----------------------------
                # ✅ Send reminder (5 min window)
                # -----------------------------
                if reminder_time <= now <= reminder_time + timedelta(minutes=5):

                    print(f"📤 Sending reminder to {name}")

                    client.messages.create(
                        body=f"⏰ Reminder: Hi {name}, your appointment is at {time_str}",
                        from_=FROM_WHATSAPP,
                        to=phone
                    )

                    # ✅ Update status (Column 6 = Status)
                    sheet.update_cell(i, 6, "Reminder Sent")

                    print(f"✅ Reminder sent to {name}")

            except Exception as row_error:
                print(f"❌ Row {i} error:", row_error)

    except Exception as main_error:
        print("🔥 Worker error:", main_error)

    # ⏳ Wait 1 minute
    time.sleep(60)