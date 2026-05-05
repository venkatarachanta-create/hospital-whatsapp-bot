import os
import json
import time
import re
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
# 👨‍⚕️ Doctors + Slots
# -----------------------------
DOCTORS = {
    "1": {
        "name": "Dr. Sharma",
        "slots": ["09:00 AM", "10:00 AM", "11:00 AM", "02:00 PM"]
    },
    "2": {
        "name": "Dr. Reddy",
        "slots": ["12:00 PM", "01:00 PM", "03:00 PM", "04:00 PM"]
    }
}

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

sheet = gs_client.open_by_key(os.getenv("1ya-5LcWhbM9w4p0BRPazsVamTiX1G5F0MG3MhpNuFAw")).sheet1

# -----------------------------
# 🧠 User state
# -----------------------------
user_state = {}

# -----------------------------
# ⏰ Robust Time Extractor
# -----------------------------
def extract_time(text):
    text = text.lower().replace(".", "").strip()
    text = text.replace(";", ":").replace("-", ":").replace(" ", "")

    match = re.search(r'(\d{1,2})(:?(\d{2}))?(am|pm)', text)

    if not match:
        raise ValueError("Invalid time format")

    hour = match.group(1)
    minute = match.group(3) if match.group(3) else "00"
    period = match.group(4).upper()

    clean_time = f"{hour}:{minute} {period}"
    return datetime.strptime(clean_time, "%I:%M %p")

# -----------------------------
# 📩 WhatsApp Webhook
# -----------------------------
@app.post("/whatsapp")
async def whatsapp_reply(Body: str = Form(...), From: str = Form(...)):

    incoming_msg = Body.strip()
    msg = incoming_msg.lower()

    response = MessagingResponse()

    # -----------------------------
    # 🟢 START
    # -----------------------------
    if msg in ["hi", "hello", "start", "menu"]:
        user_state[From] = {"step": "menu"}

        response.message("""👋 Welcome to ABC Clinic!

1️⃣ Book Appointment  
2️⃣ Doctor Timings  
3️⃣ Location  
""")
        return Response(str(response), media_type="application/xml")

    state = user_state.get(From, {"step": "menu"})
    user_state[From] = state

    # -----------------------------
    # 📋 MENU
    # -----------------------------
    if state["step"] == "menu":

        if incoming_msg == "1":
            state["step"] = "select_doctor"

            msg_text = "👨‍⚕️ Select Doctor:\n\n"
            for k, v in DOCTORS.items():
                msg_text += f"{k}. {v['name']}\n"

            response.message(msg_text)

        elif incoming_msg == "2":
            response.message("🩺 Doctor available 9 AM to 6 PM")

        elif incoming_msg == "3":
            response.message("📍 ABC Clinic, Main Road")

        else:
            response.message("Reply with 1, 2 or 3")

        return Response(str(response), media_type="application/xml")

    # -----------------------------
    # 👨‍⚕️ DOCTOR SELECT
    # -----------------------------
    if state["step"] == "select_doctor":

        if incoming_msg in DOCTORS:
            state["doctor"] = DOCTORS[incoming_msg]["name"]
            state["slots"] = DOCTORS[incoming_msg]["slots"]
            state["step"] = "booking"

            slots = "\n".join(state["slots"])

            response.message(f"""🧑‍⚕️ {state['doctor']}

Available Slots:
{slots}

👉 Enter:
Name + Date + Time

Examples:
Ravi 5 PM
Ravi tomorrow 4 PM
Ravi 10 May 10 AM
""")
        else:
            response.message("Select 1 or 2")

        return Response(str(response), media_type="application/xml")

    # -----------------------------
    # 📝 BOOKING (FINAL FIXED)
    # -----------------------------
    if state["step"] == "booking":
        try:
            parts = msg.split()
            name = parts[0].capitalize()
            now = datetime.now(IST)

            # -----------------------------
            # 📅 DATE
            # -----------------------------
            if "tomorrow" in msg:
                booking_date = now + timedelta(days=1)
                clean_msg = msg.replace(name.lower(), "").replace("tomorrow", "")

            elif re.search(r'\d{1,2}\s+[a-zA-Z]+', msg):
                date_match = re.search(r'(\d{1,2}\s+[a-zA-Z]+)', msg)
                date_part = date_match.group(1)

                booking_date = datetime.strptime(date_part, "%d %b")
                booking_date = booking_date.replace(year=now.year)

                clean_msg = msg.replace(name.lower(), "").replace(date_part, "")

            else:
                booking_date = now
                clean_msg = msg.replace(name.lower(), "")

            # -----------------------------
            # ⏰ TIME (FIXED)
            # -----------------------------
            parsed_time = extract_time(clean_msg)

            final_time = parsed_time.strftime("%I:%M %p")
            date_str = booking_date.strftime("%Y-%m-%d")

            # -----------------------------
            # 🚫 SLOT VALIDATION
            # -----------------------------
            if final_time not in state.get("slots", []):
                response.message("❌ Invalid slot. Choose from list.")
                return Response(str(response), media_type="application/xml")

            # -----------------------------
            # 🚫 DOUBLE BOOKING
            # -----------------------------
            records = sheet.get_all_records()

            for row in records:
                if (
                    str(row.get("Date")) == date_str and
                    str(row.get("Time")).lower() == final_time.lower() and
                    str(row.get("Doctor")) == state.get("doctor")
                ):
                    response.message("❌ Slot already booked.")
                    return Response(str(response), media_type="application/xml")

            # -----------------------------
            # 💾 SAVE
            # -----------------------------
            sheet.append_row([
                name,
                From,
                state.get("doctor"),
                final_time,
                date_str,
                "Pending",
                datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
            ])

            response.message(f"""✅ Appointment Confirmed!

👤 {name}
👨‍⚕️ {state.get("doctor")}
📅 {date_str}
⏰ {final_time}
""")

            user_state[From] = {"step": "menu"}

        except Exception as e:
            print("ERROR:", e)
            response.message("""⚠️ Invalid format

Try:
Ravi 5 PM
Ravi tomorrow 4 PM
Ravi 10 May 10 AM""")

        return Response(str(response), media_type="application/xml")

    # -----------------------------
    # FALLBACK
    # -----------------------------
    response.message("Type 'hi' to restart")
    user_state[From] = {"step": "menu"}

    return Response(str(response), media_type="application/xml")