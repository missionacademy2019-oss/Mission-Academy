import os
import logging
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# Enable logging so you can see errors in the Laplace console
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Load environment variables (Laplace provides these automatically)
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

# Configure Gemini API
genai.configure(api_key=GOOGLE_API_KEY)
# Using gemini-1.5-flash as it is fast and excellent for chat bots
model = genai.GenerativeModel('gemini-1.5-flash')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command."""
    welcome_text = (
        "Welcome to Mission Academy! 🎓\n\n"
        "Tap Start to continue or ask me a question about our courses, IGNOU, or daily study."
    )
    
    # Optional: Add a button to join your channel just like your screenshot
    keyboard = [[InlineKeyboardButton("📢 Join our channel", url="https://t.me/missionacademy_official")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text=welcome_text,
        reply_markup=reply_markup
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends user messages to Gemini and returns the response."""
    user_message = update.message.text
    chat_id = update.effective_chat.id

    # Show a "typing..." status in Telegram while Gemini generates the answer
    await context.bot.send_chat_action(chat_id=chat_id, action='typing')

    try:
        # Request a response from Gemini
        response = model.generate_content(user_message)
        
        # Send Gemini's answer back to the user
        await context.bot.send_message(chat_id=chat_id, text=response.text)

    except Exception as e:
        logging.error(f"Gemini API Error: {e}")
        
        # Your custom fallback message if the AI fails or hits a free limit
        fallback_text = (
            "The AI is at its free limit right now, so I can't answer that yet. "
            "Your question is saved, and Mission Academy will follow up on WhatsApp.\n"
            "Saved for the team.\n"
            "We will get back to you."
        )
        
        # Fallback button to WhatsApp
        keyboard = [[InlineKeyboardButton("💬 Chat with Mission Academy on WhatsApp", url="https://wa.me/918606688314")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=chat_id, 
            text=fallback_text,
            reply_markup=reply_markup
        )

if __name__ == '__main__':
    # Ensure tokens are present before starting
    if not TELEGRAM_TOKEN:
        raise ValueError("No TELEGRAM_BOT_TOKEN found in environment variables.")
    if not GOOGLE_API_KEY:
        raise ValueError("No GOOGLE_API_KEY found in environment variables.")

    # Build the bot application
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    # Run the bot (this uses long polling, which is standard for Laplace)
    logging.info("Bot is starting...")
    application.run_polling()
