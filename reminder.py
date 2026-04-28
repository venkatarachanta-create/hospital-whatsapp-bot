import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
from twilio.rest import Client
import os
from dotenv import load_dotenv
import schedule
import time

load_dotenv()

# Google Sheets
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

import json
creds_dict = json.loads(os.getenv("GOOGLE_CREDENTIALS"))

creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

gs_client = gspread.authorize(creds)
sheet = gs_client.open_by_key("1ya-5LcWhbM9w4p0BRPazsVamTiX1G5F0MG3MhpNuFAw").sheet1

# Twilio
client = Client(
    os.getenv("TWILIO_ACCOUNT_SID"),
    os.getenv("TWILIO_AUTH_TOKEN")
)

def send_reminders():
    print("Checking reminders...")

    records = sheet.get_all_records()
    now = datetime.now()

    for row in records:
        try:
            date_str = row["Date"]
            time_str = row["Time"]

            # Handle both formats
            try:
                appointment_time = datetime.strptime(
                    f"{date_str} {time_str}",
                    "%Y-%m-%d %I:%M %p"
                )
            except:
                appointment_time = datetime.strptime(
                    f"{date_str} {time_str}",
                    "%Y-%m-%d %I %p"
                )

            reminder_time = appointment_time - timedelta(hours=1)

            # Check if within 120-minute window
            if abs((now - reminder_time).total_seconds()) < 7200:
                name = row["Name"]
                phone = row["Phone"]

                message = (
                    f"⏰ Reminder: Hi {name}, "
                    f"your appointment is at {time_str} (in 1 hour)."
                )

                client.messages.create(
                    body=message,
                    from_="whatsapp:+14155238886",
                    to=phone
                )

                print(f"✅ Reminder sent to {name}")

        except Exception as e:
            print("Error:", e)


# Run every 120 minute
schedule.every(120).minutes.do(send_reminders)

print("🚀 Reminder service started...")

while True:
    schedule.run_pending()
    time.sleep(120)    