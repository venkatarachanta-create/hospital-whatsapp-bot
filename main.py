import os
from fastapi import FastAPI, Form
from fastapi.responses import Response
from datetime import datetime
import gspread
import json
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

creds_dict = json.loads(os.getenv("GOOGLE_CREDENTIALS_JSON"))
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
gs_client = gspread.authorize(creds)

# 👉 Use SHEET ID (IMPORTANT)
sheet = gs_client.open_by_key(os.getenv("SHEET_ID")).sheet1

# -----------------------------
# 🧠 User state storage
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
    # 🟢 First time / Reset
    # -----------------------------
    if From not in user_state:
        user_state[From] = {"step": "menu"}

        msg = """👋 Welcome to ABC Clinic!

1️⃣ Book Appointment  
2️⃣ Doctor Timings  
3️⃣ Location  

Please reply with option number."""
        response.message(msg)
        return Response(content=str(response), media_type="application/xml")

    state = user_state[From]

    # -----------------------------
    # 📋 MENU HANDLING
    # -----------------------------
    if state["step"] == "menu":
        if incoming_msg == "1":
            state["step"] = "booking"
            response.message(
                "Please share your *name and preferred time*.\n\nExample: Ravi 5 PM"
            )
        elif incoming_msg == "2":
            response.message("🩺 Doctor available from 9 AM to 6 PM")
        elif incoming_msg == "3":
            response.message("📍 ABC Clinic, Main Road, Hyderabad")
        else:
            response.message("Please select a valid option: 1, 2, or 3")

        return Response(content=str(response), media_type="application/xml")

    # -----------------------------
    # 📝 BOOKING HANDLING
    # -----------------------------
    if state["step"] == "booking":
        try:
            parts = incoming_msg.split()
            name = parts[0]
            time_str = " ".join(parts[1:])

            # Convert time to datetime
            appointment_time = datetime.strptime(time_str, "%I:%M %p")

            now = datetime.now()
            appointment_datetime = now.replace(
                hour=appointment_time.hour,
                minute=appointment_time.minute,
                second=0,
                microsecond=0
            )

            date_str = now.strftime("%Y-%m-%d")

            # -----------------------------
            # ✅ Save to Google Sheet (SAFE)
            # -----------------------------
            sheet.append_row([
                name,
                From,
                time_str,
                date_str,
                "Pending",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ])

            # -----------------------------
            # ✅ Confirmation Message
            # -----------------------------
            msg = f"""✅ Appointment Confirmed!

👤 Name: {name}
⏰ Time: {time_str}

⏳ You will receive a reminder 1 hour before your appointment.

Thank you! 🙏"""

            response.message(msg)

            # Reset state
            user_state[From] = {"step": "menu"}

        except Exception as e:
            response.message(
                "⚠️ Invalid format.\n\nPlease enter like:\nRavi 5 PM"
            )

        return Response(content=str(response), media_type="application/xml")

    # -----------------------------
    # 🔄 Fallback
    # -----------------------------
    response.message("Something went wrong. Please type 'hi' to restart.")
    user_state[From] = {"step": "menu"}

    return Response(content=str(response), media_type="application/xml")