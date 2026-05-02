import os
import json
from fastapi import FastAPI, Form
from fastapi.responses import Response
from datetime import datetime
import gspread
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
# ⏰ Flexible time parser
# -----------------------------
def parse_time(input_time: str):
    raw = input_time.lower().replace(".", "").replace(" ", "")
    raw = raw.replace("am", " AM").replace("pm", " PM")

    if ":" in raw:
        return datetime.strptime(raw, "%I:%M %p")
    else:
        return datetime.strptime(raw, "%I %p")


# -----------------------------
# 📩 WhatsApp Webhook
# -----------------------------
@app.post("/whatsapp")
async def whatsapp_reply(
    Body: str = Form(...),
    From: str = Form(...)
):
    incoming_msg = Body.strip()
    incoming_msg_lower = incoming_msg.lower()   # 👈 ADD HERE
    response = MessagingResponse()

    # -----------------------------
    # 🟢 First interaction
    # -----------------------------
    if incoming_msg_lower in ["hi", "hello", "start", "menu"]:
        user_state[From] = {"step": "menu"}

        msg = """👋 Welcome to ABC Clinic!

1️⃣ Book Appointment  
2️⃣ Doctor Timings  
3️⃣ Location  

Please reply with option number."""
        response.message(msg)
        return Response(str(response), media_type="application/xml")

    state = user_state[From]

    # -----------------------------
    # 📋 MENU
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

        return Response(str(response), media_type="application/xml")

    # -----------------------------
    # 📝 BOOKING
    # -----------------------------
    if state["step"] == "booking":
        try:
            parts = incoming_msg.split()
            name = parts[0]
            time_input = " ".join(parts[1:])

            # ✅ Parse time (flexible)
            parsed_time = parse_time(time_input)

            now = datetime.now()

            appointment_datetime = now.replace(
                hour=parsed_time.hour,
                minute=parsed_time.minute,
                second=0,
                microsecond=0
            )

            date_str = now.strftime("%Y-%m-%d")
            time_str = parsed_time.strftime("%I:%M %p")

            # -----------------------------
            # 🔁 Duplicate check (same slot only)
            # -----------------------------
            records = sheet.get_all_records()

            for row in records:
                if (
                    str(row.get("Phone")).strip() == From and
                    str(row.get("Date")).strip() == date_str and
                    str(row.get("Time")).strip().lower() == time_str.lower()
                ):
                    response.message("⚠️ You already booked this time slot.")
                    return Response(str(response), media_type="application/xml")

            # -----------------------------
            # ✅ Save booking
            # -----------------------------
            records = sheet.get_all_records()
            booking_id = len(records) + 1
            
            sheet.append_row([
                booking_id,  # Booking_ID (optional auto)
                name,
                From,
                time_str,
                date_str,
                "Pending",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ])

            # -----------------------------
            # ✅ Confirmation message
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
            print("ERROR:", e)
            response.message(
                "⚠️ Invalid format.\n\nTry like:\nRavi 5 PM\nRavi 2:30 PM"
            )

        return Response(str(response), media_type="application/xml")

    # -----------------------------
    # 🔄 Fallback
    # -----------------------------
    response.message("Something went wrong. Please type 'hi' to restart.")
    user_state[From] = {"step": "menu"}

    return Response(str(response), media_type="application/xml")