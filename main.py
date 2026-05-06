import os
import json
import re
from fastapi import FastAPI, Form
from fastapi.responses import Response
from datetime import datetime, timedelta, timezone
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from twilio.twiml.messaging_response import MessagingResponse

# -----------------------------
# Timezone (IST)
# -----------------------------
IST = timezone(timedelta(hours=5, minutes=30))

app = FastAPI()

# -----------------------------
# Doctors + Slots
# -----------------------------
DOCTORS = {
    "1": {
        "name": "Dr. Sharma",
        "start": "09:00 AM",
        "end": "02:00 PM"
    },
    "2": {
        "name": "Dr. Reddy",
        "start": "12:00 PM",
        "end": "06:00 PM"
    }
}

# -----------------------------
# Google Sheets Setup
# -----------------------------
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds_dict = json.loads(os.getenv("GOOGLE_CREDENTIALS_JSON"))
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
gs_client = gspread.authorize(creds)

sheet = gs_client.open_by_key(os.getenv("SHEET_ID")).sheet1

# -----------------------------
# User State
# -----------------------------
user_state = {}

# -----------------------------
# Time Extractor
# Supports:
# 5 PM, 5PM, 5:30 PM, 5.30pm, 5-30 pm
# -----------------------------
def extract_time(text):
    text = text.lower().replace(".", ":").strip()
    text = text.replace(";", ":").replace("-", ":").replace(" ", "")

    match = re.search(r"(\d{1,2})(:?(\d{2}))?(am|pm)", text)

    if not match:
        raise ValueError("Invalid time format")

    hour = match.group(1)
    minute = match.group(3) if match.group(3) else "00"
    period = match.group(4).upper()

    clean_time = f"{hour}:{minute} {period}"
    return datetime.strptime(clean_time, "%I:%M %p")


# -----------------------------
# Parse Date
# Supports:
# today, tomorrow, 10 May, 10 May 2026, 10 Mar
# -----------------------------
def parse_booking_date(msg, name, now):
    clean_msg = msg.replace(name.lower(), "", 1).strip()

    if "tomorrow" in msg:
        booking_date = now + timedelta(days=1)
        clean_msg = clean_msg.replace("tomorrow", "").strip()
        return booking_date, clean_msg

    date_match = re.search(
        r"(\d{1,2}\s+[a-zA-Z]+(?:\s+\d{4})?)",
        msg
    )

    if date_match:
        date_part = date_match.group(1)

        for date_format in ("%d %b %Y", "%d %B %Y", "%d %b", "%d %B"):
            try:
                booking_date = datetime.strptime(date_part, date_format)

                if booking_date.year == 1900:
                    booking_date = booking_date.replace(year=now.year)

                clean_msg = clean_msg.replace(date_part, "").strip()
                return booking_date, clean_msg

            except ValueError:
                continue

        raise ValueError("Invalid date format")

    return now, clean_msg


# -----------------------------
# WhatsApp Webhook
# -----------------------------
@app.post("/whatsapp")
async def whatsapp_reply(Body: str = Form(...), From: str = Form(...)):
    incoming_msg = Body.strip()
    msg = incoming_msg.lower()

    response = MessagingResponse()

    # -----------------------------
    # START / MENU RESET
    # -----------------------------
    if msg in ["hi", "hello", "start", "menu"]:
        user_state[From] = {"step": "menu"}

        response.message("""👋 Welcome to ABC Clinic!

1️⃣ Book Appointment
2️⃣ Doctor Timings
3️⃣ Location
""")
        return Response(str(response), media_type="application/xml")

    if From not in user_state:
        user_state[From] = {"step": "menu"}

    state = user_state[From]

    # -----------------------------
    # MENU
    # -----------------------------
    if state["step"] == "menu":
        if incoming_msg == "1":
            state["step"] = "select_doctor"

            msg_text = "👨‍⚕️ Select Doctor:\n\n"
            for key, doctor in DOCTORS.items():
                msg_text += f"{key}. {doctor['name']}\n"

            response.message(msg_text)

        elif incoming_msg == "2":
            timings = "🩺 Doctor Timings:\n\n"
            for doctor in DOCTORS.values():
                timings += f"{doctor['name']}: {doctor['start']} to {doctor['end']}\n"

            response.message(timings)

        elif incoming_msg == "3":
            response.message("📍 ABC Clinic, Main Road")

        else:
            response.message("Reply with 1, 2 or 3")

        return Response(str(response), media_type="application/xml")

    # -----------------------------
    # DOCTOR SELECT
    # -----------------------------
    if state["step"] == "select_doctor":
        doctor_choice = incoming_msg.strip()

        if doctor_choice in DOCTORS:
            selected_doctor = DOCTORS[doctor_choice]

            state["doctor_id"] = doctor_choice
            state["doctor"] = selected_doctor["name"]
            state["step"] = "booking"

            slots = f"{selected_doctor['start']} to {selected_doctor['end']}"

            response.message(f"""🧑‍⚕️ {state['doctor']}

Available Time:
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
    # BOOKING
    # -----------------------------
    if state["step"] == "booking":
        try:
            parts = msg.split()

            if len(parts) < 2:
                raise ValueError("Incomplete booking details")

            name = parts[0].capitalize()
            now = datetime.now(IST)

            booking_date, clean_msg = parse_booking_date(msg, name, now)

            parsed_time = extract_time(clean_msg)
            final_time = parsed_time.strftime("%I:%M %p")
            date_str = booking_date.strftime("%Y-%m-%d")

            doctor_id = state.get("doctor_id")
            doctor = DOCTORS[doctor_id]

            doctor_start = datetime.strptime(doctor["start"], "%I:%M %p")
            doctor_end = datetime.strptime(doctor["end"], "%I:%M %p")
            booking_time_obj = datetime.strptime(final_time, "%I:%M %p")

            # -----------------------------
            # Slot Validation
            # -----------------------------
            if not (doctor_start <= booking_time_obj <= doctor_end):
                response.message(
                    f"❌ {doctor['name']} is available only between "
                    f"{doctor_start.strftime('%I:%M %p')} and "
                    f"{doctor_end.strftime('%I:%M %p')}"
                )
                return Response(str(response), media_type="application/xml")

            # -----------------------------
            # Double Booking Check
            # -----------------------------
            records = sheet.get_all_records()

            for row in records:
                if (
                    str(row.get("Date")) == date_str
                    and str(row.get("Time")).lower() == final_time.lower()
                    and str(row.get("Doctor")) == state.get("doctor")
                ):
                    response.message("❌ Slot already booked.")
                    return Response(str(response), media_type="application/xml")

            # -----------------------------
            # Save Appointment
            # -----------------------------
            sheet.append_row(
                [
                    name,
                    From,
                    state.get("doctor"),
                    final_time,
                    date_str,
                    "Pending",
                    datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
                ],
                value_input_option="USER_ENTERED"
            )

👤 {name}
👨‍⚕️ {state.get("doctor")}
📅 {date_str}
⏰ {final_time}

🔔 You will receive a reminder 1 hour before your appointment.
""")

            user_state[From] = {"step": "menu"}

        except Exception as e:
            print("ERROR:", e)

            response.message("""⚠️ Invalid format

Try:
Ravi 5 PM
Ravi tomorrow 4 PM
Ravi 10 May 10 AM
Ravi 10 May 2026 10 AM
""")

        return Response(str(response), media_type="application/xml")

    # -----------------------------
    # FALLBACK
    # -----------------------------
    response.message("Type 'hi' to restart")
    user_state[From] = {"step": "menu"}

    return Response(str(response), media_type="application/xml")
