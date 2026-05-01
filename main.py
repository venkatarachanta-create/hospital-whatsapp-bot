import os
from fastapi import FastAPI, Form
from fastapi.responses import Response
from datetime import datetime
import gspread
import json
import uuid
from oauth2client.service_account import ServiceAccountCredentials
from twilio.twiml.messaging_response import MessagingResponse

app = FastAPI()

# -----------------------------
# 🔐 Google Sheets Setup
# -----------------------------
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
if not creds_json:
    raise ValueError("GOOGLE_CREDENTIALS_JSON is missing!")

creds_dict = json.loads(creds_json)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
gs_client = gspread.authorize(creds)

sheet = gs_client.open_by_key(os.getenv("SHEET_ID")).sheet1

# -----------------------------
# 🧠 User state
# -----------------------------
user_state = {}

# -----------------------------
# 📩 WhatsApp Webhook
# -----------------------------
@app.post("/whatsapp")
async def whatsapp_reply(
    Body: str = Form(...),
    From: str = Form(...)
):
    incoming_msg = Body.strip()
    response = MessagingResponse()

    # -----------------------------
    # 🟢 First time
    # -----------------------------
    if From not in user_state:
        user_state[From] = {"step": "menu"}

        response.message("""👋 Welcome to ABC Clinic!

1️⃣ Book Appointment  
2️⃣ Doctor Timings  
3️⃣ Location  

Please reply with option number.""")
        return Response(str(response), media_type="application/xml")

    state = user_state[From]

    # -----------------------------
    # 📋 MENU
    # -----------------------------
    if state["step"] == "menu":
        if incoming_msg == "1":
            state["step"] = "booking"
            response.message("Please share your name and time\nExample: Ravi 5 PM")

        elif incoming_msg == "2":
            response.message("🩺 Doctor available from 9 AM to 6 PM")

        elif incoming_msg == "3":
            response.message("📍 ABC Clinic, Main Road, Hyderabad")

        else:
            response.message("Please select 1, 2 or 3")

        return Response(str(response), media_type="application/xml")

    # -----------------------------
    # 📝 BOOKING
    # -----------------------------
    if state["step"] == "booking":
        try:
            parts = incoming_msg.split()
            name = parts[0]
            time_str = " ".join(parts[1:]).upper().replace(".", "")

            # Handle formats like 5 PM / 5:30 PM
            if ":" in time_str:
                appointment_time = datetime.strptime(time_str, "%I:%M %p")
            else:
                appointment_time = datetime.strptime(time_str, "%I %p")

            now = datetime.now()

            appointment_datetime = now.replace(
                hour=appointment_time.hour,
                minute=appointment_time.minute,
                second=0,
                microsecond=0
            )

            date_str = now.strftime("%Y-%m-%d")

            # -----------------------------
            # ❌ Prevent duplicate booking
            # -----------------------------
            records = sheet.get_all_records()
            for row in records:
                if row["Phone"] == From and row["Date"] == date_str:
                    response.message("⚠️ You already booked today.")
                    return Response(str(response), media_type="application/xml")

            # -----------------------------
            # ✅ Save booking
            # -----------------------------
            booking_id = str(uuid.uuid4())[:8]
            created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            sheet.append_row([
                booking_id,
                name,
                From,
                time_str,
                date_str,
                "Pending",
                created_at
            ])

            # -----------------------------
            # ✅ Confirmation
            # -----------------------------
            response.message(f"""✅ Appointment Confirmed!

👤 Name: {name}
⏰ Time: {time_str}

⏳ Reminder will be sent 1 hour before.

Thank you! 🙏""")

            user_state[From] = {"step": "menu"}

        except:
            response.message("⚠️ Format error\nExample: Ravi 5 PM")

        return Response(str(response), media_type="application/xml")

    # -----------------------------
    # 🔄 fallback
    # -----------------------------
    user_state[From] = {"step": "menu"}
    response.message("Type 'hi' to restart")

    return Response(str(response), media_type="application/xml")