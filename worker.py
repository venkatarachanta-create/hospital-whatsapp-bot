import os
import json
import time
from datetime import datetime, timedelta
import pytz

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from twilio.rest import Client
from datetime import datetime

# ==============================
# 1. GOOGLE SHEETS AUTH (ENV BASED)
# ==============================
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds_dict = json.loads(os.getenv("GOOGLE_CREDENTIALS_JSON"))
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
gs_client = gspread.authorize(creds)

# 👉 Use EXACT sheet name OR ID
sheet = gs_client.open_by_key("1ya-5LcWhbM9w4p0BRPazsVamTiX1G5F0MG3MhpNuFAw").sheet1


# ==============================
# 2. TWILIO CONFIG
# ==============================
client = Client(
    os.getenv("TWILIO_ACCOUNT_SID"),
    os.getenv("TWILIO_AUTH_TOKEN")
)

TWILIO_WHATSAPP_NUMBER = "whatsapp:+14155238886"


# ==============================
# 3. REMINDER LOOP
# ==============================
print("🚀 Worker started... Checking reminders...")

while True:
    try:
        rows = sheet.get_all_values()

        # Skip header row
        for i, row in enumerate(rows[1:], start=2):
            try:
                name = row[0]
                phone = row[1]
                time_str = row[2]
                date_str = row[3]
                status = row[4] if len(row) > 4 else ""

                # Skip if already sent
                if status == "Sent":
                    continue

                # Combine date + time
                appointment_time = datetime.strptime(
                    f"{date_str} {time_str}",
                    "%Y-%m-%d %I:%M %p"
                )

                reminder_time = appointment_time - timedelta(hours=1)

                ist = pytz.timezone("Asia/Kolkata")
                now = datetime.now(ist).replace(tzinfo=None)
                
                print(f"Row {i} | Name: {name}")
                print("NOW:", now.strftime("%Y-%m-%d %I:%M:%S %p"))
                print("APPOINTMENT:", appointment_time.strftime("%Y-%m-%d %I:%M:%S %p"))
                print("REMINDER:", reminder_time.strftime("%Y-%m-%d %I:%M:%S %p"))
                print("================================")
                
                # ✅ RANGE CHECK (IMPORTANT FIX)
                if reminder_time <= now <= reminder_time + timedelta(minutes=5):
                    print(f"📤 Sending reminder to {name}...")

                    message = client.messages.create(
                        body=f"⏰ Reminder: Hi {name}, your appointment is at {time_str}.",
                        from_=TWILIO_WHATSAPP_NUMBER,
                        to=phone
                    )

                    print("✅ Sent:", message.sid)

                    # Update status column (5th column)
                    sheet.update_cell(i, 5, "Sent")

            except Exception as e:
                print(f"⚠️ Error in row {i}: {e}")

    except Exception as e:
        print("❌ Worker error:", e)

    # ⏳ Wait before next check
    time.sleep(10)
