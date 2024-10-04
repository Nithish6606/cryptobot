import os
import logging
from typing import Final, List, Dict, Any
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, filters

# Constants
BOT_USERNAME: Final = 'xyz'
BOT_TOKEN: Final = os.getenv("BOT_TOKEN")
COINGECKO_API_URL: Final = "https://api.coingecko.com/api/v3"
SUPPORTED_CURRENCIES: Final = ['usd', 'eur', 'gbp', 'jpy', 'aud', 'cad', 'chf', 'cny', 'inr']

# Conversation states
MAIN_MENU, CHOOSING_CRYPTO, CHOOSING_CURRENCY, TYPING_SEARCH = range(4)

# Logging configuration
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# API Functions
def get_top_cryptos(limit: int = 100) -> List[Dict[str, Any]]:
    try:
        response = requests.get(f"{COINGECKO_API_URL}/coins/markets", params={
            'vs_currency': 'usd',
            'order': 'market_cap_desc',
            'per_page': limit,
            'page': 1,
            'sparkline': False
        })
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Error fetching top cryptos: {e}")
        return []

def get_trending_cryptos() -> List[Dict[str, Any]]:
    try:
        response = requests.get(f"{COINGECKO_API_URL}/search/trending")
        response.raise_for_status()
        return response.json().get('coins', [])
    except requests.RequestException as e:
        logger.error(f"Error fetching trending cryptos: {e}")
        return []

def get_crypto_details(crypto_id: str, currency: str = 'usd') -> Dict[str, Any]:
    try:
        params = {'ids': crypto_id, 'vs_currencies': currency, 'include_24hr_change': 'true', 'include_market_cap': 'true'}
        response = requests.get(f"{COINGECKO_API_URL}/simple/price", params=params)
        response.raise_for_status()
        data = response.json()
        return data.get(crypto_id, {})
    except requests.RequestException as e:
        logger.error(f"Error fetching crypto details for {crypto_id}: {e}")
        return {}

# Command Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await show_main_menu(update, context)
    return MAIN_MENU

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = (
        "Welcome to the Crypto Price Bot!\n\n"
        "Commands:\n"
        "/start - Show main menu\n"
        "/help - Show this help message\n\n"
        "You can check prices of top cryptocurrencies, view trending coins, or search for a specific cryptocurrency."
    )
    await update.message.reply_text(help_text)

# Menu Functions
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [InlineKeyboardButton("Top 100 Cryptocurrencies", callback_data='top100')],
        [InlineKeyboardButton("Trending Cryptocurrencies", callback_data='trending')],
        [InlineKeyboardButton("Search Cryptocurrency", callback_data='search')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "Welcome to the Crypto Price Bot! What would you like to do?"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)

async def show_crypto_list(update: Update, context: ContextTypes.DEFAULT_TYPE, cryptos: List[Dict[str, Any]], title: str) -> None:
    keyboard = []
    for i in range(0, len(cryptos), 2):
        row = []
        for crypto in cryptos[i:i+2]:
            name = crypto.get('name', 'Unknown')
            symbol = crypto.get('symbol', 'Unknown')
            crypto_id = crypto.get('id', 'unknown')
            row.append(InlineKeyboardButton(f"{name} ({symbol.upper()})", callback_data=f"crypto:{crypto_id}"))
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("Back to Main Menu", callback_data='main_menu')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(title, reply_markup=reply_markup)
    else:
        await update.message.reply_text(title, reply_markup=reply_markup)

async def show_currency_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [InlineKeyboardButton(currency.upper(), callback_data=f"currency:{currency}")]
        for currency in SUPPORTED_CURRENCIES
    ]
    keyboard.append([InlineKeyboardButton("Back to Main Menu", callback_data='main_menu')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text('Choose a currency:', reply_markup=reply_markup)

# Callback Query Handler
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == 'main_menu':
        await show_main_menu(update, context)
        return MAIN_MENU
    elif query.data == 'top100':
        await query.edit_message_text("Fetching top cryptocurrencies, please wait...")
        cryptos = get_top_cryptos()
        await show_crypto_list(update, context, cryptos, "Top 100 Cryptocurrencies:")
        return CHOOSING_CRYPTO
    elif query.data == 'trending':
        await query.edit_message_text("Fetching trending cryptocurrencies, please wait...")
        cryptos = get_trending_cryptos()
        await show_crypto_list(update, context, cryptos, "Trending Cryptocurrencies:")
        return CHOOSING_CRYPTO
    elif query.data == 'search':
        await query.edit_message_text("Please enter the name of the cryptocurrency you want to check:")
        return TYPING_SEARCH
    elif query.data.startswith('crypto:'):
        context.user_data['crypto'] = query.data.split(':')[1]
        await show_currency_options(update, context)
        return CHOOSING_CURRENCY
    elif query.data.startswith('currency:'):
        currency = query.data.split(':')[1]
        crypto_id = context.user_data.get('crypto', 'bitcoin')
        await show_crypto_details(update, context, crypto_id, currency)
        return MAIN_MENU

async def show_crypto_details(update: Update, context: ContextTypes.DEFAULT_TYPE, crypto_id: str, currency: str) -> None:
    details = get_crypto_details(crypto_id, currency)
    if details:
        price = details.get(currency, 'N/A')
        change_24h = details.get(f'{currency}_24h_change', 'N/A')
        market_cap = details.get(f'{currency}_market_cap', 'N/A')
        
        change_symbol = '🔺' if change_24h > 0 else '🔻' if change_24h < 0 else '➖'
        message = (
            f"💰 {crypto_id.capitalize()} ({currency.upper()})\n"
            f"Price: {price:,.2f} {currency.upper()}\n"
            f"24h Change: {change_symbol} {abs(change_24h):.2f}%\n"
            f"Market Cap: {market_cap:,.0f} {currency.upper()}"
        )
    else:
        message = f"Sorry, I couldn't find the details for {crypto_id}."
    
    keyboard = [[InlineKeyboardButton("Back to Main Menu", callback_data='main_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(message, reply_markup=reply_markup)

# Message Handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_input = update.message.text.lower()
    try:
        search_results = requests.get(f"{COINGECKO_API_URL}/search", params={'query': user_input}).json()
        coins = search_results.get('coins', [])
        
        if coins:
            await show_crypto_list(update, context, coins[:10], "Search Results:")
            return CHOOSING_CRYPTO
        else:
            await update.message.reply_text("Sorry, I couldn't find any cryptocurrency matching your search.")
            await show_main_menu(update, context)
            return MAIN_MENU
    except requests.RequestException as e:
        logger.error(f"Error searching for cryptocurrency: {e}")
        await update.message.reply_text("An error occurred while searching for the cryptocurrency.")
        await show_main_menu(update, context)
        return MAIN_MENU

# Error Handler
async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")

def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MAIN_MENU: [CallbackQueryHandler(button_click)],
            CHOOSING_CRYPTO: [CallbackQueryHandler(button_click)],
            CHOOSING_CURRENCY: [CallbackQueryHandler(button_click)],
            TYPING_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
        },
        fallbacks=[CommandHandler("start", start)],
        per_message=False
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("help", help_command))
    app.add_error_handler(error)

    logger.info('Starting bot...')
    app.run_polling(poll_interval=3)

if __name__ == '__main__':
    main()