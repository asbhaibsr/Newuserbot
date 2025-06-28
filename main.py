import os
import asyncio
import re
import random
from telethon.sync import TelegramClient, events
from telethon.tl.functions.messages import SetTypingRequest
from telethon.tl.types import SendMessageTypingAction
from telethon.sessions import StringSession
from pymongo import MongoClient
from datetime import datetime, timedelta

# --- Configuration (Koyeb Environment Variables se aayenge) ---
API_ID = int(os.environ.get('API_ID'))
API_HASH = os.environ.get('API_HASH')
STRING_SESSION = os.environ.get('STRING_SESSION')
MONGO_URI = os.environ.get('MONGO_URI')

# --- Private Message Reply Content (Girl-like, Fun & Engaging) ---
PRIVATE_REPLY_TEXT_FUNNY_GIRL_LIKE = [
    "Hii! 🤗 Mujhe private mein message kiya? Kitne cute ho! 🥰 Agar tum mujhe apne group mein add karoge na, toh main wahan itni masti karungi ki sabki hansi nahi rukegi! Aur haan, hamare movie group ko bhi join kar lena - @istreamX, updates ke liye @asbhai_bsr aur chat ke liye @aschat_group. Dekho, sab list mein hain! 😉",
    "Helloo! 💖 Surprise! Tumne mujhe private message kiya? Kya chal raha hai? Suno na, agar tum mujhe apne group mein shamil karte ho, toh wahan ki chat ko main super fun bana dungi! Promise! ✨ Aur haan, yeh rahe hamare special groups: Movie group - @istreamX, Updates - @asbhai_bsr, Chat group - @aschat_group. Jaldi se aa jao! 😉",
    "Arey wah! Tum akele yahan? 😊 Aao na, mere saath groups mein masti karte hain! Agar tum mujhe apne group mein add karoge, toh main wahan sabki messages ko yaad rakhti hu aur cute cute replies deti hu. Try karoge kya? 🙈 Aur hamare ye groups bhi dekhna: @istreamX (movies), @asbhai_bsr (updates), @aschat_group (chat). See you there! 👋",
    "Psst... Koi secret baat hai kya? 🤫 Haha! Main hu tumhari pyaari little helper. Agar tumhe group chat ko ekdum lively banana hai, toh mujhe apne group mein bulao! Main apni baaton se sabke dil jeet lungi! 💕 Aur haan, ye bhi join kar lena: Movie group - @istreamX, Updates - @asbhai_bsr, Chat group - @aschat_group. Bye! 😘",
    "Haaaiii! Meri pyaari friend ne mujhe message kiya! 🥰 Agar tum mujhe apne group mein add karte ho, toh main wahan itni mazedar baatein karungi ki tumko aur tumhare friends ko bahut mazaa aayega. Koi bore nahi hoga, I promise! 😉 Aur yeh bhi join karna mat bhoolna: @istreamX, @asbhai_bsr, @aschat_group. Milte hain group mein! 👋"
]

# --- MongoDB Setup ---
try:
    client_mongo = MongoClient(MONGO_URI)
    db = client_mongo['telegram_userbot_db']
    messages_collection = db['group_messages']
    print("MongoDB connection successful for main.py Userbot.") # Log message changed
except Exception as e:
    print(f"MongoDB connection failed for main.py Userbot: {e}")
    # exit() # <--- यह लाइन कमेंटेड या हटाई हुई होनी चाहिए!


# --- Telethon Client Setup ---
print("Attempting to initialize Telethon client in main.py.") # <-- डिबग लाइन
userbot = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)

# --- Global variables ---
last_processed_message_id = {}
last_reply_timestamp = {} 
REPLY_COOLDOWN_SECONDS = 3 # Aapki 3 second ki limit

# --- MongoDB Data Management Task ---
async def manage_db_size():
    FULL_THRESHOLD = 10000 
    DELETE_PERCENTAGE = 0.50 

    while True:
        await asyncio.sleep(3600) # Har ghante check karega
        try:
            if client_mongo: 
                total_messages = messages_collection.count_documents({}) 
                print(f"Current DB size: {total_messages} messages.")

                if total_messages >= FULL_THRESHOLD:
                    num_to_delete = int(total_messages * DELETE_PERCENTAGE)
                    print(f"DB is getting full ({total_messages} messages), deleting {num_to_delete} oldest messages...")

                    oldest_messages_cursor = messages_collection.find().sort("timestamp", 1).limit(num_to_delete)
                    delete_ids = [msg['_id'] for msg in oldest_messages_cursor]

                    if delete_ids:
                        delete_result = messages_collection.delete_many({"_id": {"$in": delete_ids}})
                        print(f"Deleted {delete_result.deleted_count} old messages successfully.")
                    else:
                        print("No messages found to delete.")
                else:
                    print(f"DB size is within limits ({total_messages}/{FULL_THRESHOLD}).")
            else:
                print("MongoDB client not initialized, skipping DB size management.") 
        except Exception as e:
            print(f"Error managing DB size: {e}")

# --- Reply Generation Logic (Group Specific) ---
async def generate_and_send_group_reply(event):
    incoming_message = event.raw_text
    chat_id = event.chat_id
    message_id = event.id # Current message ID
    
    # Ignore outgoing messages or already processed messages
    if event.out or (chat_id in last_processed_message_id and last_processed_message_id[chat_id] == message_id):
        return
    
    # --- Cooldown Check ---
    current_time = datetime.utcnow()
    if chat_id in last_reply_timestamp:
        time_since_last_reply = (current_time - last_reply_timestamp[chat_id]).total_seconds()
        if time_since_last_reply < REPLY_COOLDOWN_SECONDS:
            print(f"Cooldown active for chat {chat_id}. Skipping reply. Time since last reply: {time_since_last_reply:.2f}s")
            return 
    
    last_processed_message_id[chat_id] = message_id # Ab message ko processed mark karo

    # Links aur usernames skip karein
    if re.search(r'http[s]?://\S+|@\S+', incoming_message, re.IGNORECASE):
        print(f"Skipping incoming message with link/username: {incoming_message}")
        return

    # Typing status dikhana aur 0.5 second ka delay
    await event.mark_read()
    try:
        input_peer = await userbot.get_input_entity(chat_id)
        await userbot(SetTypingRequest(peer=input_peer, action=SendMessageTypingAction()))
        await asyncio.sleep(0.5) # Minimum 0.5 second ka delay for typing
    except Exception as e:
        print(f"Error sending typing action: {e}")

    reply_text = None
    sticker_to_send = None
    
    # --- 1. Message Storage (Sirf User ke Group messages store honge) ---
    sender = await event.get_sender()
    
    emojis_in_message = [char for char in incoming_message if 0x1F600 <= ord(char) <= 0x1F64F or 
                                                             0x1F300 <= ord(char) <= 0x1F5FF or 
                                                             0x1F900 <= ord(char) <= 0x1F9FF or 
                                                             0x1FA70 <= ord(char) <= 0x1FAFF]

    if event.sticker:
        sticker_to_store_id = event.sticker.id
    else:
        sticker_to_store_id = None

    if client_mongo:
        messages_collection.insert_one({
            'chat_id': chat_id,
            'sender_id': sender.id,
            'message': incoming_message,
            'timestamp': datetime.utcnow(),
            'emojis': emojis_in_message,
            'sticker_id': sticker_to_store_id,
            'is_bot_reply': False, # Mark as user message
            'message_id': message_id 
        })
        print(f"Stored group message from {sender.id} in {chat_id}: '{incoming_message}'")
    else:
        print("MongoDB not connected, skipping message storage.") 

    # --- 2. Reply Generation Logic (Ab bot apne replies store nahi karega) ---
    if "searching for" in incoming_message.lower():
        print(f"Detected 'Searching For' message: '{incoming_message}'. Providing generic reply.")
        common_replies_for_generic = [
            "Hmm... theek hai!", "Samajh gayi!", "Okay!", "Dekhti hu!"
        ]
        reply_text = random.choice(common_replies_for_generic)
    else:
        stop_words_hindi = [
            'the', 'and', 'is', 'a', 'to', 'in', 'it', 'i', 'of', 'for', 'on', 'with', 'as', 'at', 'this', 'that', 'he', 'she', 'you', 'they', 'we', 'my', 'your', 'his', 'her', 'its', 'our', 'their', # English stop words
            'hai', 'kya', 'kar', 'raha', 'ho', 'tum', 'main', 'ko', 'hi', 'mein', 'pr', 'jago', 'wahan', 'movie', 'search', 'group', 'nam', 'likho', 'ki', 'aapko', 'direct', 'file', 'mil', 'jayegi', # Hindi specific
            'go', 'profile', 'there', 'link', 'all', 'movies', 'webseries', 'click', 'photo', # From previous logs, possibly external bot related
            'bhi', 'hum', 'us', 'yeh', 'woh', 'haan', 'nahi', 'kuch', 'aur', 'kaise', 'kab', 'kyun', 'kaha', 'kon', 'ka', 'bata', 'de', 'bhai', 'be', 'teri', 'to', 'losu', 'chutiya', 'pagal', 'kon', 'aap', 'ka', 'name', 'pta', 'na', 'kiya', 'chak', 'rah', 'chutiya', 'sach', 'bhag', 'are', 'abe', 'yaar', 'oye', 'tum', 'main', 'kya', 'kaise', 'mujhe', 'tera', 'mere', 'sab', 'sirf', 'ek', 'fir', 'hota', 'hoga', 'karoge', 'apna', 'apni', 'apne', 'usse', 'isme', 'kabhi', 'har', 'roz', 'fir', 'kahi'
        ]

        keywords_for_search = [
            word for word in re.findall(r'\b\w+\b', incoming_message.lower()) 
            if len(word) >= 2 and word not in stop_words_hindi
        ]
        
        print("Bot will now only use common replies or stickers, not learn from its own past replies.")

        common_replies = [
            "Haa!", "Theek hai!", "Hmm...", "Sahi baat hai!", "Kya chal raha hai?",
            "Accha!", "Samajh gayi!", "Bilkul!", "Baat kar!", "Good!",
            "Aur batao?", "Masti chal rahi hai!", "Kuch naya?", "Wah!", "Kya kehna!",
            "Hehe!", "Ek number!", "Awesome!", "Nice!", "Super!",
            "Hellooo!", "Kaisi ho?", "Sab theek hai?", "Bolo na!", "Arey wah!",
            "Kya planning hai?", "Maza aa raha hai!", "Aur batao kya chal raha hai?",
            "Din kaisa raha?", "Kuch khaas?", "Main toh bas yahi hu!", "Aur kya kar rahe ho?",
            "Mausam kaisa hai?", "Hansi nahi ruk rahi!", "Bahut mazaa aa raha hai!"
        ]
        reply_text = random.choice(common_replies)

    # --- Sticker Logic ---
    sticker_list = [ 
        "CAACAgIAAxkBAAEF_1lmW36q2G3AASU76C_W_u6mG30bO_wAAmV1AAKqFMFZ7dYv-89yE9M0BA", 
        "CAACAgIAAxkBAAEF_1tmW36q2G3AASU76C_W_u6mG30bO_wAAmV1AAKqFMFZ7dYv-89yE9M0BA", 
        "CAACAgIAAxkBAAEF_11mW36q2G3AASU76C_W_u6mG30bO_wAAmV1AAKqFMFZ7dYv-89yE9M0BA", 
    ]
    
    if sticker_list and random.random() < 0.4: 
        sticker_to_send = random.choice(sticker_list)
        reply_text = "" 
        print(f"Selecting sticker: {sticker_to_send}")
    else:
        emojis_for_text = [
            '😂', '😊', '🥳', '😎', '👍', '✨', '💖', '🥰', '🤣', '😅', '🤗', '🌟', '🌈', '🔥'
        ]
        if not reply_text.strip():
            reply_text = random.choice(emojis_for_text)
        else:
            reply_text += " " + random.choice(emojis_for_text) 

        if reply_text:
            words = reply_text.split()
            if len(words) > 8:
                if words and words[-1] in emojis_for_text:
                    reply_text = " ".join(words[:random.randint(4, 7)]) + " " + words[-1]
                else:
                    reply_text = " ".join(words[:random.randint(4, 8)])

        if reply_text:
            incoming_len = len(incoming_message.split())
            if incoming_len <= 5 and len(reply_text.split()) > 3:
                last_word = reply_text.split()[-1] if reply_text.split() else ''
                if last_word in emojis_for_text:
                    reply_text = " ".join(reply_text.split()[:random.randint(2, 3)]) + " " + last_word
                else:
                    reply_text = " ".join(reply_text.split()[:random.randint(2, 4)])
            elif incoming_len <= 12 and len(reply_text.split()) > 5:
                last_word = reply_text.split()[-1] if reply_text.split() else ''
                if last_word in emojis_for_text:
                    reply_text = " ".join(reply_text.split()[:random.randint(4, 5)]) + " " + last_word
                else:
                    reply_text = " ".join(reply_text.split()[:random.randint(4, 6)])

        if reply_text and re.search(r'http[s]?://\S+|@\S+', reply_text, re.IGNORECASE):
            reply_text = "Main links ya usernames nahi bhej sakti. Sorry! 😔"

    sent_message_successfully = False
    if reply_text.strip(): 
        sent_message = await userbot.send_message(chat_id, reply_text, reply_to=message_id)
        print(f"Replied with text in {chat_id}: '{reply_text}'")
        sent_message_successfully = True
    elif sticker_to_send: 
        try:
            await userbot.send_file(chat_id, sticker_to_send, reply_to=message_id)
            print(f"Replied with sticker in {chat_id}: '{sticker_to_send}'")
            sent_message_successfully = True
        except ValueError as ve:
            print(f"Error sending sticker '{sticker_to_send}': {ve}. Falling back to text reply.")
            fallback_text = "Sorry, main abhi sticker nahi bhej pa rahi. 😊"
            await userbot.send_message(chat_id, fallback_text, reply_to=message_id)
            sent_message_successfully = True 
    else:
        print(f"No reply generated for message ID {message_id}.")

    if sent_message_successfully:
        last_reply_timestamp[chat_id] = datetime.utcnow() 

# --- Event Handlers ---
@userbot.on(events.NewMessage(incoming=True))
async def handle_all_messages(event):
    if event.is_private:
        await handle_private_message(event)
    elif event.is_group or event.is_channel:
        await generate_and_send_group_reply(event)

async def handle_private_message(event):
    if event.out:
        return
    
    sender = await event.get_sender()
    print(f"Received private message from {sender.id}: {event.raw_text}")
    
    await event.mark_read()
    try:
        input_peer = await userbot.get_input_entity(event.chat_id)
        await userbot(SetTypingRequest(peer=input_peer, action=SendMessageTypingAction()))
        await asyncio.sleep(0.5) 
    except Exception as e:
        print(f"Error sending typing action: {e}")

    reply_to_send = random.choice(PRIVATE_REPLY_TEXT_FUNNY_GIRL_LIKE) 
    await event.reply(reply_to_send)
    print(f"Replied privately to {sender.id} with girl-like funny message.")

# --- Main function to start userbot ---
async def start_userbot():
    print("Starting Userbot function in main.py...")
    # debug prints for environment variables - temporarily add these
    print(f"DEBUG: API_ID: {API_ID}, API_HASH length: {len(API_HASH) if API_HASH else 0}, STRING_SESSION length: {len(STRING_SESSION) if STRING_SESSION else 0}, MONGO_URI starts with: {MONGO_URI[:20] if MONGO_URI else 'N/A'}")
    
    await userbot.start()
    print("Userbot started successfully in main.py!")

    # Manage DB size task for the worker
    asyncio.create_task(manage_db_size())
    
    print("Userbot is running and listening for messages in main.py.")
    await userbot.run_until_disconnected()

# --- Run the Userbot ---
if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_userbot())
