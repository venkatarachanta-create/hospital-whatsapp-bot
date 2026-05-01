import os
import time
from datetime import datetime, timedelta

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from twilio.rest import Client

# ---------------------------
# GOOGLE SHEETS SETUP
# ---------------------------
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds_dict = json.loads(os.getenv("GOOGLE_CREDENTIALS_JSON"))

creds = ServiceAccountCredentials.from_json_keyfile_dict(
    creds_dict, scope
)

gs_client = gspread.authorize(creds)

sheet = gs_client.open("Hospital Whatsapp Bot").sheet1


# ---------------------------
# TWILIO SETUP
# ---------------------------
twilio_client = Client(
    os.getenv("TWILIO_ACCOUNT_SID"),
    os.getenv("TWILIO_AUTH_TOKEN")
)

FROM_WHATSAPP = "whatsapp:+14155238886"


# ---------------------------
# HELPER FUNCTION
# ---------------------------
def send_reminder(name, phone, time_str, date_str):
    message = f"⏰ Reminder\n\nHi {name},\nYou have an appointment at {time_str} today."

    twilio_client.messages.create(
        from_=FROM_WHATSAPP,
        to=phone,
        body=message
    )


# ---------------------------
# MAIN LOOP
# ---------------------------
print("🚀 Worker started...")

while True:
    try:
        print("🔍 Checking reminders...")

        rows = sheet.get_all_records()

        for i, row in enumerate(rows, start=2):  # row 2 onwards
            name = row.get("Name")
            phone = row.get("Phone")
            time_str = row.get("Time")
            date_str = row.get("Date")
            status = row.get("Status", "")

            if status == "Sent":
                continue

            if not (name and phone and time_str and date_str):
                continue

            try:
                appointment_dt = datetime.strptime(
                    f"{date_str} {time_str}",
                    "%Y-%m-%d %I %p"
                )
            except:
                continue

            reminder_time = appointment_dt - timedelta(hours=1)
            now = datetime.now()

            # 🔔 Trigger condition (within 1 min window)
            if reminder_time <= now <= reminder_time + timedelta(minutes=1):
                send_reminder(name, phone, time_str, date_str)

                print(f"✅ Reminder sent to {name}")

                # Mark as sent (Column E = Status)
                sheet.update_cell(i, 5, "Sent")

        time.sleep(60)

    except Exception as e:
        print("❌ Error:", e)
        time.sleep(30)