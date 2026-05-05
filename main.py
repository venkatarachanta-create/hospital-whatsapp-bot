import os
import json
import time
from fastapi import FastAPI, Form
from fastapi.responses import Response
from datetime import datetime, timedelta, timezone
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from twilio.twiml.messaging_response import MessagingResponse

# -----------------------------
# ⏰ Timezone (IST)
# -----------------------------
IST = timezone(timedelta(hours=5, minutes=30))

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

sheet = gs_client.open_by_key(os.getenv("1ya-5LcWhbM9w4p0BRPazsVamTiX1G5F0MG3MhpNuFAwSHEET_ID")).sheet1

# -----------------------------
# 🧠 User state
# -----------------------------
user_state = {}

# -----------------------------
# ⏰ Flexible time parser
# -----------------------------
def parse_time(input_time: str):
    raw = input_time.lower().replace(".", "").strip()

    # normalize
    raw = raw.replace("am", " AM").replace("pm", " PM")

    if ":" in raw:
        return datetime.strptime(raw, "%I:%M %p")
    else:
        return datetime.strptime(raw, "%I %p")

# -----------------------------
# ✅ SAFE INSERT (NO DATA LOSS)
# -----------------------------
def safe_insert(sheet, name, phone, time_str, date_str):
    for attempt in range(3):
        try:
            all_rows = sheet.get_all_values()
            next_row = len(all_rows) + 1

            sheet.update(f"A{next_row}:G{next_row}", [[
                next_row - 1,  # Booking_ID
                name,
                phone,
                time_str,
                date_str,
                "Pending",
                datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
            ]])

            print(f"✅ Inserted row {next_row}")
            return True

        except Exception as e:
            print("Retrying insert:", e)
            time.sleep(1)

    return False

# -----------------------------
# 📩 WhatsApp Webhook
# -----------------------------
@app.post("/whatsapp")
async def whatsapp_reply(
    Body: str = Form(...),
    From: str = Form(...)
):
    incoming_msg = Body.strip()
    incoming_msg_lower = incoming_msg.lower()

    response = MessagingResponse()

    # -----------------------------
    # 🟢 ALWAYS allow restart
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

    # -----------------------------
    # 🧠 Safe state handling
    # -----------------------------
    state = user_state.get(From, {"step": "menu"})
    user_state[From] = state

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

            # ✅ Parse flexible time
            parsed_time = parse_time(time_input)

            now = datetime.now(IST)

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
            # ✅ SAFE SAVE
            # -----------------------------
            safe_insert(sheet, name, From, time_str, date_str)

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