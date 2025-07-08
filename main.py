from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import smtplib
import ssl
import os
import json
import random
import logging
import base64
from firebase_admin import auth, credentials, initialize_app
import firebase_admin

# ✅ Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nike-otp-backend")

# ✅ Firebase initialization using FIREBASE_CONFIG_B64
try:
    firebase_b64 = os.getenv("FIREBASE_CONFIG_B64")
    if not firebase_b64:
        raise Exception("❌ FIREBASE_CONFIG_B64 is not set in environment.")

    decoded = base64.b64decode(firebase_b64).decode("utf-8")
    cred_dict = json.loads(decoded)
    cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")

    cred = credentials.Certificate(cred_dict)
    initialize_app(cred)
    logger.info("✅ Firebase initialized using FIREBASE_CONFIG_B64")
except Exception as e:
    logger.error(f"❌ Firebase initialization failed: {str(e)}")
    raise Exception(f"❌ Firebase initialization failed: {str(e)}")

# ✅ FastAPI app
app = FastAPI()

# ✅ CORS config
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://nike-access-x.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ SMTP setup
SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
if not SMTP_EMAIL or not SMTP_PASSWORD:
    logger.warning("⚠️ SMTP credentials are missing!")

# ✅ OTP store
otp_store = {}

# ✅ Pydantic models
class OTPRequest(BaseModel):
    email: str

class PasswordResetRequest(BaseModel):
    email: str
    new_password: str

# ✅ Email sender
def send_email(subject: str, body: str, recipient: str):
    try:
        message = f"Subject: {subject}\n\n{body}"
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, recipient, message)
        logger.info(f"📨 Email sent to {recipient}")
        return {"success": True, "message": "Email sent"}
    except Exception as e:
        logger.error(f"❌ Email failed: {str(e)}")
        return {"success": False, "error": str(e)}

# ✅ Routes
@app.get("/")
def root():
    logger.info("✅ Server is up")
    return {"message": "✅ OTP Server is running!"}

@app.post("/send-otp")
async def send_registration_otp(data: OTPRequest):
    logger.info(f"📩 Registration OTP requested for: {data.email}")
    try:
        auth.get_user_by_email(data.email)
        return {"success": False, "error": "Email is already registered"}
    except firebase_admin.auth.UserNotFoundError:
        otp = str(random.randint(100000, 999999))
        otp_store[data.email] = otp
        logger.info(f"🔐 OTP for {data.email}: {otp}")
        return send_email(
            subject="Nike Registration OTP",
            body=f"Use this OTP to complete your registration: {otp}",
            recipient=data.email
        )
    except Exception as e:
        logger.error(f"🔥 Firebase error: {str(e)}")
        return {"success": False, "error": f"Firebase error: {str(e)}"}

@app.post("/send-reset-otp")
async def send_reset_otp(data: OTPRequest):
    logger.info(f"📩 Reset OTP requested for: {data.email}")
    otp = str(random.randint(100000, 999999))
    otp_store[data.email] = otp
    logger.info(f"🔐 Reset OTP for {data.email}: {otp}")
    return send_email(
        subject="Nike Password Reset",
        body=f"Use this OTP to reset your password: {otp}",
        recipient=data.email
    )

@app.post("/verify-otp")
async def verify_otp(request: Request):
    data = await request.json()
    email = data.get("email")
    otp_input = data.get("otp")
    logger.info(f"🔍 Verifying OTP for {email}")
    if email in otp_store and otp_store[email] == otp_input:
        del otp_store[email]
        logger.info(f"✅ OTP verified for {email}")
        return {"verified": True}
    logger.warning(f"❌ OTP verification failed for {email}")
    return {"verified": False}

@app.post("/reset-password")
async def reset_password(data: PasswordResetRequest):
    logger.info(f"🔁 Resetting password for {data.email}")
    try:
        user = auth.get_user_by_email(data.email)
        auth.update_user(user.uid, password=data.new_password)
        logger.info(f"✅ Password updated for {data.email}")
        return {"success": True, "message": "Password updated successfully"}
    except firebase_admin.auth.UserNotFoundError:
        logger.warning(f"❌ Email not found: {data.email}")
        return {"success": False, "error": "Email not found"}
    except Exception as e:
        logger.error(f"❌ Password update failed: {str(e)}")
        return {"success": False, "error": f"Update failed: {str(e)}"}
