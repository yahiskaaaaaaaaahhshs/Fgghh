import logging
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime, timedelta
import time
import random
import asyncio
import os
from collections import defaultdict
import re
import io
import requests
import json

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot token
BOT_TOKEN = "8220573698:AAFmClKQoiFIHjhJHfFDGhi55-QOHkWRgn4"
OWNER_ID = 7310898934

# Global rate limiting
user_limits = defaultdict(lambda: {
    "total_used": 0,
    "reset_time": None,
    "gateway_usage": {
        "adyen_auth": 0,
        "adyen_charge": 0,
        "stripe": 0,
        "razorpay": 0
    }
})

TOTAL_LIMIT = 400
LIMIT_MINUTES = 40

# Card tracking for consistent declines
card_attempts = defaultdict(lambda: defaultdict(int))

# ==================== ADYEN AUTH SIMULATOR ====================
class AdyenAuthSimulator:
    def __init__(self, decline_rate=80):
        self.decline_rate = decline_rate
        
    def authorize(self, input_string, card_key):
        delay = random.uniform(2.0, 6.0)
        time.sleep(delay)
        
        try:
            parts = input_string.split('|')
            if len(parts) < 4:
                return self._invalid_response(delay)
            
            # If card checked many times, always decline
            if card_attempts[card_key]["adyen_auth"] > 5000:
                return {
                    "status": "Declined",
                    "response": "Card declined - Too many attempts",
                    "additionalData": {
                        "cardAdded": "false",
                        "processingTime": f"{delay:.2f}s"
                    }
                }
            
            if random.randint(1, 100) <= self.decline_rate:
                return self._decline_response(delay)
            else:
                return self._approve_response(delay)
        except:
            return self._invalid_response(delay)
    
    def _approve_response(self, delay):
        reasons = [
            "Card successfully added",
            "Payment method verified",
            "Authorization successful",
            "Card verified",
            "Approved"
        ]
        return {
            "status": "Approved",
            "response": random.choice(reasons),
            "additionalData": {
                "cardAdded": "true",
                "processingTime": f"{delay:.2f}s"
            }
        }
    
    def _decline_response(self, delay):
        reasons = [
            "Insufficient funds",
            "Card declined by bank",
            "Transaction not permitted",
            "Invalid CVV",
            "Daily limit exceeded",
            "3D Secure required",
            "Card restricted",
            "Issuer unavailable",
            "Fraud suspicion",
            "Do not honor",
            "Pickup card",
            "Invalid card number",
            "CVC verification failed",
            "Expired card",
            "Card not supported"
        ]
        return {
            "status": "Declined",
            "response": random.choice(reasons),
            "additionalData": {
                "cardAdded": "false",
                "processingTime": f"{delay:.2f}s"
            }
        }
    
    def _invalid_response(self, delay):
        return {
            "status": "Declined",
            "response": "Invalid card details format",
            "additionalData": {
                "cardAdded": "false",
                "processingTime": f"{delay:.2f}s"
            }
        }

# ==================== ADYEN CHARGE SIMULATOR ====================
class AdyenChargeSimulator:
    def __init__(self, approve_rate=2):
        self.approve_rate = approve_rate
        
    def charge(self, input_string, card_key):
        delay = random.uniform(2.0, 6.0)
        time.sleep(delay)
        
        try:
            parts = input_string.split('|')
            if len(parts) < 4:
                return self._invalid_response(delay)
            
            # If card checked many times, always decline
            if card_attempts[card_key]["adyen_charge"] > 5000:
                return {
                    "status": "Declined",
                    "response": "Card declined - Too many attempts",
                    "additionalData": {"processingTime": f"{delay:.2f}s"}
                }
            
            if random.randint(1, 100) <= self.approve_rate:
                return self._approve_response(delay)
            else:
                return self._decline_response(delay)
        except:
            return self._invalid_response(delay)
    
    def _approve_response(self, delay):
        reasons = [
            "Payment successful",
            "Transaction completed",
            "Charge authorized",
            "Payment captured",
            "Approved"
        ]
        return {
            "status": "Approved",
            "response": random.choice(reasons),
            "additionalData": {"processingTime": f"{delay:.2f}s"}
        }
    
    def _decline_response(self, delay):
        reasons = [
            "Insufficient funds",
            "Card declined by bank",
            "Transaction not permitted",
            "Invalid CVV",
            "Daily limit exceeded",
            "3D Secure required",
            "Card restricted",
            "Issuer unavailable",
            "Fraud suspicion",
            "Do not honor",
            "Pickup card",
            "Invalid card number",
            "Expired card",
            "CVC verification failed"
        ]
        return {
            "status": "Declined",
            "response": random.choice(reasons),
            "additionalData": {"processingTime": f"{delay:.2f}s"}
        }
    
    def _invalid_response(self, delay):
        return {
            "status": "Declined",
            "response": "Invalid payment details",
            "additionalData": {"processingTime": f"{delay:.2f}s"}
        }

# ==================== STRIPE SIMULATOR ====================
class StripeChargeSimulator:
    def __init__(self):
        pass
        
    def process_payment(self, input_string, card_key):
        delay = random.uniform(2.0, 6.0)
        time.sleep(delay)
        
        try:
            parts = input_string.split('|')
            if len(parts) < 4:
                return self._invalid_response(delay)
            
            # If card checked many times, always decline
            if card_attempts[card_key]["stripe"] > 5000:
                return {
                    "status": "Declined",
                    "response": "Card declined - Too many attempts",
                    "processing_time": f"{delay:.2f}s"
                }
            
            if random.randint(1, 400) == 1:
                return self._approve_response(delay)
            else:
                return self._decline_response(delay)
        except:
            return self._invalid_response(delay)
    
    def _approve_response(self, delay):
        reasons = [
            "Payment Successful",
            "Charge succeeded",
            "Transaction complete",
            "Payment approved",
            "Success"
        ]
        return {
            "status": "Approved",
            "response": random.choice(reasons),
            "processing_time": f"{delay:.2f}s"
        }
    
    def _decline_response(self, delay):
        reasons = [
            "Insufficient funds",
            "Card declined",
            "Invalid CVV",
            "Card expired",
            "Daily limit exceeded",
            "3D Secure required",
            "Card restricted",
            "Bank unavailable",
            "Fraud suspicion",
            "Do not honor",
            "Pickup card",
            "Invalid card number"
        ]
        return {
            "status": "Declined",
            "response": random.choice(reasons),
            "processing_time": f"{delay:.2f}s"
        }
    
    def _invalid_response(self, delay):
        return {
            "status": "Declined",
            "response": "Invalid payment details",
            "processing_time": f"{delay:.2f}s"
        }

# ==================== RAZORPAY SIMULATOR ====================
class RazorpayIndiaSimulator:
    def __init__(self):
        self.approval_quota = 1
        self.approved_cards = set()
        self.total_attempts = 0
        
    def process_payment(self, input_string, card_key):
        self.total_attempts += 1
        delay = random.uniform(2.0, 6.0)
        time.sleep(delay)
        
        try:
            parts = input_string.split('|')
            if len(parts) < 4:
                return self._invalid_response()
            
            card_number = parts[0].strip()
            
            # If card checked many times, always decline
            if card_attempts[card_key]["razorpay"] > 5000:
                return {
                    "status": "failed",
                    "response": "Card declined - Too many attempts"
                }
            
            # Indian cards only check
            if not card_number.startswith(('4', '5', '6', '3')):
                return {
                    "status": "failed",
                    "response": "International payments not allowed"
                }
            
            if card_number in self.approved_cards:
                return self._decline_response()
            
            if len(self.approved_cards) >= self.approval_quota:
                return self._decline_response()
            
            if random.randint(1, 500) == 1:
                self.approved_cards.add(card_number)
                return self._approve_response()
            else:
                return self._decline_response()
        except:
            return self._invalid_response()
    
    def _approve_response(self):
        reasons = [
            "Payment Successful",
            "Transaction completed",
            "Order placed successfully",
            "Payment captured",
            "Success"
        ]
        return {
            "status": "captured",
            "response": random.choice(reasons)
        }
    
    def _decline_response(self):
        reasons = [
            "Insufficient funds",
            "Card declined by bank",
            "Transaction failed",
            "Bank unavailable",
            "3D Secure failed",
            "Invalid PIN",
            "Card restricted",
            "Do not honor",
            "Invalid card"
        ]
        return {
            "status": "failed",
            "response": random.choice(reasons)
        }
    
    def _invalid_response(self):
        return {
            "status": "failed",
            "response": "Invalid card details"
        }

# Initialize simulators
adyen_auth = AdyenAuthSimulator()
adyen_charge = AdyenChargeSimulator()
stripe = StripeChargeSimulator()
razorpay = RazorpayIndiaSimulator()

# User data storage
user_data = {}

class UserSession:
    def __init__(self, user_id, username, first_name):
        self.user_id = user_id
        self.username = username
        self.first_name = first_name
        self.joined_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.status = "Active"

# BIN Info API
def get_bin_info(bin_number):
    try:
        response = requests.get(f"https://lookup.binlist.net/{bin_number}", 
                                headers={'Accept-Version': '3'}, 
                                timeout=5)
        if response.status_code == 200:
            data = response.json()
            
            bank = data.get('bank', {})
            bank_name = bank.get('name', 'UNKNOWN')
            
            scheme = data.get('scheme', 'UNKNOWN').upper()
            card_type = data.get('type', 'UNKNOWN').upper()
            
            # Determine brand
            brand = "STANDARD"
            data_str = str(data).lower()
            if 'premium' in data_str:
                brand = "PREMIUM"
            elif 'platinum' in data_str:
                brand = "PLATINUM"
            elif 'gold' in data_str:
                brand = "GOLD"
            elif 'business' in data_str or 'corporate' in data_str:
                brand = "BUSINESS"
            elif 'classic' in data_str:
                brand = "CLASSIC"
            elif 'electron' in data_str:
                brand = "ELECTRON"
            elif 'signature' in data_str:
                brand = "SIGNATURE"
            elif 'infinite' in data_str:
                brand = "INFINITE"
            elif 'world' in data_str:
                brand = "WORLD"
            elif 'elite' in data_str:
                brand = "ELITE"
            elif 'black' in data_str:
                brand = "BLACK"
            
            country_data = data.get('country', {})
            country = country_data.get('name', 'UNKNOWN')
            country_code = country_data.get('alpha2', '')
            
            flag = ""
            if country_code:
                flag = ''.join(chr(127397 + ord(c)) for c in country_code.upper())
            
            return {
                'scheme': scheme,
                'type': card_type,
                'brand': brand,
                'bank': bank_name.upper(),
                'country': country.upper(),
                'flag': flag
            }
    except:
        pass
    
    # Random BIN info for fallback
    schemes = ['VISA', 'MASTERCARD', 'AMEX', 'DISCOVER', 'JCB', 'RUPAY', 'DINERS']
    types = ['CREDIT', 'DEBIT', 'PREPAID', 'CHARGE', 'BUSINESS']
    brands = ['STANDARD', 'PREMIUM', 'PLATINUM', 'GOLD', 'BUSINESS', 'CLASSIC', 'SIGNATURE', 'INFINITE', 'WORLD', 'ELITE', 'BLACK']
    banks = ['CHASE', 'BANK OF AMERICA', 'WELLS FARGO', 'CITIBANK', 'CAPITAL ONE', 'BARCLAYS', 'HSBC', 'TD BANK', 'PNC', 'US BANK']
    countries = ['UNITED STATES', 'UNITED KINGDOM', 'CANADA', 'AUSTRALIA', 'GERMANY', 'FRANCE', 'JAPAN', 'SINGAPORE', 'INDIA', 'UAE']
    
    return {
        'scheme': random.choice(schemes),
        'type': random.choice(types),
        'brand': random.choice(brands),
        'bank': random.choice(banks) + ' BANK',
        'country': random.choice(countries),
        'flag': '🌍'
    }

# ==================== BOT COMMANDS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.username or "unknown"
    first_name = user.first_name
    
    if user_id not in user_data:
        user_data[user_id] = UserSession(user_id, username, first_name)
    
    session = user_data[user_id]
    
    welcome_text = f"""⌬ 𝐎𝐱𝐲𝐱𝐄𝐧𝐯 | By @lost_yashika
『 𝐔𝐩𝐠𝐫𝐚𝐝𝐢𝐧𝐠... 』
━━━━━━━━━━━━━━━━━━━━━
『 𝐌𝐲 𝐏𝐫𝐨𝐟𝐢𝐥𝐞 』
👤 𝐍𝐚𝐦𝐞: {first_name}
🔰 𝐔𝐬𝐞𝐫𝐧𝐚𝐦𝐞: @{username}
🆔 𝐔𝐬𝐞𝐫𝐈𝐃: <code>{user_id}</code>
📅 𝐉𝐨𝐢𝐧𝐞𝐝: {session.joined_date}
⚡ 𝐒𝐭𝐚𝐭𝐮𝐬: {session.status}
━━━━━━━━━━━━━━━━━━━━━
『 𝐒𝐭𝐚𝐭𝐮𝐬 - 𝐋𝐢𝐯𝐞!!! 』"""

    keyboard = [
        [
            InlineKeyboardButton("『 𝐌𝐲 𝐏𝐫𝐨𝐟𝐢𝐥𝐞 』", callback_data='profile'),
            InlineKeyboardButton("『 𝐂𝐨𝐦𝐦𝐚𝐧𝐝𝐬 』", callback_data='commands')
        ]
    ]
    
    await update.message.reply_text(
        welcome_text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def check_rate_limit(user_id, gateway_name, check_count=1):
    now = datetime.now()
    user_limit = user_limits[user_id]
    
    if user_limit["reset_time"] and now > user_limit["reset_time"]:
        user_limit["total_used"] = 0
        user_limit["gateway_usage"] = {k: 0 for k in user_limit["gateway_usage"]}
        user_limit["reset_time"] = None
    
    if user_limit["reset_time"] is None:
        user_limit["reset_time"] = now + timedelta(minutes=LIMIT_MINUTES)
    
    if user_limit["total_used"] + check_count > TOTAL_LIMIT:
        time_left = user_limit["reset_time"] - now
        minutes_left = int(time_left.total_seconds() / 60)
        seconds_left = int(time_left.total_seconds() % 60)
        remaining = TOTAL_LIMIT - user_limit["total_used"]
        return False, remaining, f"{minutes_left}m {seconds_left}s"
    
    return True, TOTAL_LIMIT - user_limit["total_used"] - check_count, None

async def update_usage(user_id, gateway_name, check_count=1):
    user_limit = user_limits[user_id]
    user_limit["total_used"] += check_count
    user_limit["gateway_usage"][gateway_name] += check_count

async def reset_user_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Admin only command!")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Usage: /reset user_id")
        return
    
    try:
        target_user = int(context.args[0])
        if target_user in user_limits:
            user_limits[target_user]["total_used"] = 0
            user_limits[target_user]["gateway_usage"] = {k: 0 for k in user_limits[target_user]["gateway_usage"]}
            user_limits[target_user]["reset_time"] = None
            # Also clear card attempts for this user
            keys_to_delete = [k for k in card_attempts.keys() if k.endswith(f"_{target_user}")]
            for k in keys_to_delete:
                del card_attempts[k]
            await update.message.reply_text(f"✅ Limits reset for user: {target_user}")
        else:
            await update.message.reply_text(f"❌ User {target_user} not found")
    except:
        await update.message.reply_text("❌ Invalid user ID")

async def reset_everyone_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Admin only command!")
        return
    
    user_limits.clear()
    card_attempts.clear()
    await update.message.reply_text("✅ All user limits and card attempts have been reset")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    user_id = user.id
    
    if user_id not in user_data:
        user_data[user_id] = UserSession(user_id, user.username or "unknown", user.first_name)
    
    session = user_data[user_id]
    
    if query.data == 'profile':
        user_limit = user_limits.get(user_id, {"total_used": 0, "reset_time": None})
        remaining = TOTAL_LIMIT - user_limit.get("total_used", 0)
        reset_info = ""
        
        if user_limit.get("reset_time") and datetime.now() < user_limit["reset_time"]:
            time_left = user_limit["reset_time"] - datetime.now()
            minutes_left = int(time_left.total_seconds() / 60)
            reset_info = f"\n⏳ Reset in: {minutes_left}m"
        
        gateway_usage = user_limit.get('gateway_usage', {})
        
        text = f"""『 𝐌𝐲 𝐏𝐫𝐨𝐟𝐢𝐥𝐞 』
━━━━━━━━━━━━━━━━━━━━━
👤 𝐍𝐚𝐦𝐞: {session.first_name}
🔰 𝐔𝐬𝐞𝐫𝐧𝐚𝐦𝐞: @{session.username}
🆔 𝐔𝐬𝐞𝐫𝐈𝐃: <code>{session.user_id}</code>
📅 𝐉𝐨𝐢𝐧𝐞𝐝: {session.joined_date}
⚡ 𝐒𝐭𝐚𝐭𝐮𝐬: {session.status}
━━━━━━━━━━━━━━━━━━━━━
📊 𝐂𝐡𝐞𝐜𝐤𝐬 𝐋𝐞𝐟𝐭: {remaining}/{TOTAL_LIMIT}{reset_info}
📈 𝐔𝐬𝐞𝐝: 
• Adyen Auth: {gateway_usage.get('adyen_auth', 0)}
• Adyen Charge: {gateway_usage.get('adyen_charge', 0)}
• Stripe: {gateway_usage.get('stripe', 0)}
• Razorpay: {gateway_usage.get('razorpay', 0)}"""
        
        keyboard = [[InlineKeyboardButton("◀️ Back", callback_data='back_to_main')]]
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data == 'commands':
        text = f"""『 𝐂𝐨𝐦𝐦𝐚𝐧𝐝𝐬 』
━━━━━━━━━━━━━━━━━━━━━
『 𝐒𝐢𝐧𝐠𝐥𝐞 』
/ady - Adyen
