from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import smtplib
import ssl
import os
import random
import json

# Firebase Admin SDK
import firebase_admin
from firebase_admin import auth, credentials

# Secure Firebase Init
if not firebase_admin._apps:
    try:
        firebase_json = os.getenv("FIREBASE_CREDENTIALS")
        cred_dict = json.loads(firebase_json)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
    except Exception as e:
        raise Exception(f"❌ Firebase initialization failed: {str(e)}")

app = FastAPI()

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

otp_store = {}

class OTPRequest(BaseModel):
    email: str

class PasswordResetRequest(BaseModel):
    email: str
    new_password: str

def send_email(subject, body, to_email):
    message = f"Subject: {subject}\n\n{body}"
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, to_email, message)
        return {"success": True, "message": f"Email sent to {to_email}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/")
def root():
    return {"message": "✅ OTP Server is running!"}

@app.post("/send-otp")
async def send_registration_otp(data: OTPRequest):
    try:
        auth.get_user_by_email(data.email)
        return {"success": False, "error": "Email is already registered"}
    except firebase_admin.auth.UserNotFoundError:
        otp = str(random.randint(100000, 999999))
        otp_store[data.email] = otp
        return send_email("Welcome to Nike", f"Use this OTP to complete registration: {otp}", data.email)
    except Exception as e:
        return {"success": False, "error": f"Firebase error: {str(e)}"}

@app.post("/send-reset-otp")
async def send_reset_otp(data: OTPRequest):
    otp = str(random.randint(100000, 999999))
    otp_store[data.email] = otp
    return send_email("Nike Password Reset", f"Use this OTP to reset your password: {otp}", data.email)

@app.post("/verify-otp")
async def verify_otp(request: Request):
    body = await request.json()
    email = body.get("email")
    otp_input = body.get("otp")

    if email in otp_store and otp_store[email] == otp_input:
        del otp_store[email]
        return {"verified": True}
    return {"verified": False}

@app.post("/reset-password")
async def reset_password(data: PasswordResetRequest):
    try:
        user = auth.get_user_by_email(data.email)
        auth.update_user(user.uid, password=data.new_password)
        return {"success": True, "message": "Password updated successfully"}
    except firebase_admin.auth.UserNotFoundError:
        return {"success": False, "error": "Email not found"}
    except Exception as e:
        return {"success": False, "error": f"Password update failed: {str(e)}"}

if __name__ == "__main__":
    print("🚀 OTP Server is running at http://localhost:8000")
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
