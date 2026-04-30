import os
from fastapi import FastAPI, Request
from fastapi.responses import  Response
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime

# Google Sheets
import gspread
from oauth2client.service_account import ServiceAccountCredentials

load_dotenv()

app = FastAPI()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ---------------- GOOGLE SHEETS SETUP ----------------
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

import json
creds_dict = json.loads(os.getenv("GOOGLE_CREDENTIALS"))

creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)


gs_client = gspread.authorize(creds)

sheet = gs_client.open_by_key("1ya-5LcWhbM9w4p0BRPazsVamTiX1G5F0MG3MhpNuFAw").sheet1
# ----------------------------------------------------


# Simple in-memory storage
user_state = {}


@app.post("/whatsapp")
async def whatsapp_reply(request: Request):
    form = await request.form()
    incoming_msg = form.get("Body", "").strip()
    user_number = form.get("From")

    response = MessagingResponse()
    msg = response.message()

    # Initialize user
    if user_number not in user_state:
        user_state[user_number] = {"step": "start"}

    state = user_state[user_number]

    # ---------------- STEP 1: MENU ----------------
    if state["step"] == "start":
        msg.body(
            "👋 Welcome to ABC Clinic!\n\n"
            "1️⃣ Book Appointment\n"
            "2️⃣ Doctor Timings\n"
            "3️⃣ Location"
        )
        state["step"] = "menu"

    # ---------------- STEP 2: MENU HANDLING ----------------
    elif state["step"] == "menu":
        if incoming_msg == "1":
            msg.body("Please share your *name* and preferred *time*.\n\nExample: Ravi 5 PM")
            state["step"] = "booking"

        elif incoming_msg == "2":
            msg.body("🩺 Doctor available from 10 AM – 6 PM.")

        elif incoming_msg == "3":
            msg.body("📍 Kukatpally, Hyderabad.")

        else:
            msg.body("Please select a valid option:\n1️⃣ 2️⃣ 3️⃣")

    # ---------------- STEP 3: BOOKING ----------------
    elif state["step"] == "booking":

        try:
            parts = incoming_msg.split()

            # Basic validation
            if len(parts) < 2:
                msg.body("❌ Please enter in format: Name Time\nExample: Ravi 5 PM")
                return Response(content=str(response), media_type="application/xml")

            name = parts[0].capitalize()
            time = " ".join(parts[1:])

            # Save to Google Sheet
            sheet.append_row([
                name,
                user_number,
                time,
                datetime.now().strftime("%Y-%m-%d")
            ])

            msg.body(
                f"✅ Appointment booked!\n\n"
                f"👤 Name: {name}\n"
                f"⏰ Time: {time}\n\n"
                f"Our team will confirm shortly."
            )

            state["step"] = "start"

        except Exception as e:
            print("ERROR:", e)
            msg.body("⚠️ Something went wrong. Please try again.")

    return Response(content=str(response), media_type="application/xml")