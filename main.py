import os
import asyncio
import re
import random
from telethon.sync import TelegramClient, events
from telethon.tl.types import SendMessageTypingAction
from telethon.sessions import StringSession # Yeh line zaroori hai StringSession ke liye
from pymongo import MongoClient
from datetime import datetime, timedelta
from flask import Flask, request, jsonify

# --- Configuration (Koyeb Environment Variables se aayenge) ---
# Yeh variables aap Koyeb par set karenge, code mein directly nahi likhenge.
API_ID = int(os.environ.get('API_ID'))
API_HASH = os.environ.get('API_HASH')
STRING_SESSION = os.environ.get('STRING_SESSION')
MONGO_URI = os.environ.get('MONGO_URI')

# --- Private Message Reply Content (Girl-like, Fun & Engaging) ---
# Ye replies random choose honge jab koi private message karega.
PRIVATE_REPLY_TEXT_FUNNY_GIRL_LIKE = [
    "Hii! 🤗 Mujhe private mein message kiya? Kitne cute ho! 🥰 Agar tum mujhe apne group mein add karoge na, toh main wahan itni masti karungi ki sabki hansi nahi rukegi! Aur haan, hamare movie group ko bhi join kar lena - @istreamX, updates ke liye @asbhai_bsr aur chat ke liye @aschat_group. Dekho, sab list mein hain! 😉",
    "Helloo! 💖 Surprise! Tumne mujhe private message kiya. Kya chal raha hai? Suno na, agar tum mujhe apne group mein shamil karte ho, toh wahan ki chat ko main super fun bana dungi! Promise! ✨ Aur haan, yeh rahe hamare special groups: Movie group - @istreamX, Updates - @asbhai_bsr, Chat group - @aschat_group. Jaldi se aa jao! 😉",
    "Arey wah! Tum akele yahan? 😊 Aao na, mere saath groups mein masti karte hain! Agar tum mujhe apne group mein add karoge, toh main wahan sabki messages ko yaad rakhti hu aur cute cute replies deti hu. Try karoge kya? 🙈 Aur hamare ye groups bhi dekhna: @istreamX (movies), @asbhai_bsr (updates), @aschat_group (chat). See you there! 👋",
    "Psst... Koi secret baat hai kya? 🤫 Haha! Main hu tumhari pyaari little helper. Agar tumhe group chat ko ekdum lively banana hai, toh mujhe apne group mein bulao! Main apni baaton se sabke dil jeet lungi! 💕 Aur haan, ye bhi join kar lena: Movie group - @istreamX, Updates - @asbhai_bsr, Chat group - @aschat_group. Bye! 😘",
    "Haaaiii! Meri pyaari friend ne mujhe message kiya! 🥰 Agar tum mujhe apne group mein add karte ho, toh main wahan itni mazedar baatein karungi ki tumko aur tumhare friends ko bahut mazaa aayega. Koi bore nahi hoga, I promise! 😉 Aur yeh bhi join karna mat bhoolna: @istreamX, @asbhai_bsr, @aschat_group. Milte hain group mein! 👋"
]

# --- MongoDB Setup ---
try:
    client_mongo = MongoClient(MONGO_URI)
    db = client_mongo['telegram_userbot_db'] # Aap database ka naam badal sakte hain
    messages_collection = db['group_messages'] # Collection jahan group messages store honge
    print("MongoDB connection successful.")
except Exception as e:
    print(f"MongoDB connection failed: {e}")
    # Agar MongoDB connect nahi hota, toh userbot ko exit kar sakte hain
    exit()

# --- Telethon Client Setup ---
# Yahan StringSession ka istemal kiya gaya hai takki Koyeb par file system error na aaye.
userbot = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)

# --- Global variable to store last message ID per chat to avoid double replies ---
last_processed_message_id = {}

# --- Flask App for Monitoring (Port 8080) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Userbot is running and monitoring on port 8080!"

@app.route('/health')
def health_check():
    # Simple health check, MongoDB connection bhi check kar sakte hain
    try:
        client_mongo.admin.command('ping')
        db_status = "Connected"
    except Exception:
        db_status = "Disconnected"
    return jsonify(status="ok", db=db_status, timestamp=datetime.utcnow().isoformat())

# --- MongoDB Data Management Task ---
async def manage_db_size():
    FULL_THRESHOLD = 10000 # Example: Max 10,000 messages. Aap ise adjust kar sakte hain.
    DELETE_PERCENTAGE = 0.50 # Purane 50% messages delete karein

    while True:
        await asyncio.sleep(3600) # Har ghante check karega (1 hour = 3600 seconds)
        try:
            total_messages = await messages_collection.count_documents({})
            print(f"Current DB size: {total_messages} messages.")

            if total_messages >= FULL_THRESHOLD:
                num_to_delete = int(total_messages * DELETE_PERCENTAGE)
                print(f"DB is getting full ({total_messages} messages), deleting {num_to_delete} oldest messages...")

                # Sabse purane documents ko dhoondein aur delete karein
                oldest_messages_cursor = messages_collection.find().sort("timestamp", 1).limit(num_to_delete)
                delete_ids = [msg['_id'] for msg in oldest_messages_cursor]

                if delete_ids:
                    delete_result = messages_collection.delete_many({"_id": {"$in": delete_ids}})
                    print(f"Deleted {delete_result.deleted_count} old messages successfully.")
                else:
                    print("No messages found to delete.")
            else:
                print(f"DB size is within limits ({total_messages}/{FULL_THRESHOLD}).")

        except Exception as e:
            print(f"Error managing DB size: {e}")

# --- Reply Generation Logic (Group Specific) ---
async def generate_and_send_group_reply(event):
    incoming_message = event.raw_text
    chat_id = event.chat_id
    message_id = event.id
    
    # Apne hi messages ya pehle se processed messages ko ignore karein
    if event.out or (chat_id in last_processed_message_id and last_processed_message_id[chat_id] == message_id):
        return
    
    last_processed_message_id[chat_id] = message_id

    # Links aur usernames wale incoming messages ko skip karein (learning ke liye bhi)
    if re.search(r'http[s]?://\S+|@\S+', incoming_message, re.IGNORECASE):
        print(f"Skipping incoming message with link/username: {incoming_message}")
        return

    # --- Typing status dikhana aur 0.5 second ka delay ---
    # `send_read_acknowledge` ki jagah `iter_read_history` ka istemal
    await userbot.iter_read_history(chat_id, max_id=message_id)
    await userbot.send_action(chat_id, SendMessageTypingAction())
    await asyncio.sleep(0.5) # Minimum 0.5 second ka delay

    reply_text = None
    sticker_to_send = None
    emojis_to_send = []

    # --- 1. Message Storage (Group messages hi store honge) ---
    sender = await event.get_sender()
    
    # Store associated emojis (yahan common emojis ki list hai)
    emojis_in_message = [char for char in incoming_message if 0x1F600 <= ord(char) <= 0x1F64F or # Basic smileys
                                                             0x1F300 <= ord(char) <= 0x1F5FF or # Misc symbols
                                                             0x1F900 <= ord(char) <= 0x1F9FF or # Supplemental symbols
                                                             0x1FA70 <= ord(char) <= 0x1FAFF] # New emojis

    if event.sticker:
        sticker_to_store_id = event.sticker.id
    else:
        sticker_to_store_id = None

    await messages_collection.insert_one({
        'chat_id': chat_id,
        'sender_id': sender.id,
        'message': incoming_message,
        'timestamp': datetime.utcnow(),
        'emojis': emojis_in_message,
        'sticker_id': sticker_to_store_id,
        'is_bot_reply': False # Indicates it's an incoming user message
    })
    print(f"Stored group message from {sender.id} in {chat_id}: '{incoming_message}'")

    # --- 2. Reply Generation Logic (Self-learning from stored group data) ---
    # Database mein similar messages dhoondein aur unke replies dekhein
    # Yahan simple keyword-based search hai. Advanced NLP ke liye aap Word Embeddings, TF-IDF use kar sakte hain.
    keywords = incoming_message.lower().split()[:5] # Message ke pehle 5 shabdon ko keywords mana.
    
    search_query = {
        "chat_id": chat_id,
        "is_bot_reply": True, # Hum bot ke pehle ke replies search kar rahe hain
        # Search in 'original_message' field for keywords (jo bot ne pehle reply kiya tha)
        "original_message": {"$regex": f"({'|'.join(re.escape(k) for k in keywords if k)})", "$options": "i"} 
    }
    
    past_bot_reply = messages_collection.find_one(search_query, sort=[("timestamp", -1)]) # Sabse latest relevant reply

    if past_bot_reply and 'reply_text' in past_bot_reply:
        reply_text = past_bot_reply['reply_text']
        emojis_to_send = past_bot_reply.get('emojis', [])
        sticker_to_send = past_bot_reply.get('sticker_id', None)
        print(f"Found existing reply from DB: {reply_text}")
    else:
        # Fallback: Agar specific reply nahi mila, toh kuch random common reply choose karein (girl-like tone)
        common_replies = [
            "Haa! 😄", "Theek hai! 👍", "Hmm...🤔", "Sahi baat hai! ✅", "Kya chal raha hai? 👀",
            "Accha! ✨", "Samajh gayi! 😉", "Bilkul! 👍", "Baat kar! 🗣️", "Good! 😊",
            "Aur batao? 👇", "Masti chal rahi hai! 😂", "Kuch naya? 🤩", "Wah! 🥳", "Kya kehna! 😲",
            "Hehe! 😊", "Ek number! 👌", "Awesome! ✨", "Nice! 😄", "Super! 💖", " " # Khali reply for just sticker/emoji sometimes
        ]
        reply_text = random.choice(common_replies)
        
        if not reply_text.strip(): # Agar chosen reply sirf emojis ya empty string hai
            emojis_to_send = random.choice([['👍'], ['😁'], ['😂'], ['🥳'], ['😎'], ['💖'], ['🥰'], ['✨']]) # Send a random emoji
        elif random.random() < 0.6: # 60% chance to add a random emoji to text reply
            emojis_to_send.append(random.choice(['😂', '😊', '🥳', '😎', '👍', '✨', '💖', '🥰']))

        # Randomly decide to send a sticker if no specific reply was found and no text reply selected
        sticker_list = [ # !!! Yahan apne girl-like stickers ki actual IDs daalein !!!
            # Example (replace with your actual sticker IDs):
            # "CAACAgIAAxkBAAEFfBpmO...Fh18EAAH-xX8AAWJ2XAAE",
            # "CAACAgIAAxkBAAEFfBpmO...Fh18EAAH-xX8AAWJ2XAAE"
        ]
        if not reply_text.strip() and sticker_list and random.random() < 0.7: # 70% chance to send a random sticker if no text
            sticker_to_send = random.choice(sticker_list)
            emojis_to_send = [] # No emojis if sending sticker only

        print(f"Using fallback reply: '{reply_text}' or sticker: '{sticker_to_send}'")


    # --- 3. Word count control (1-8 words) ---
    if reply_text:
        words = reply_text.split()
        if len(words) > 8:
            reply_text = " ".join(words[:8]) # Truncate if too long

    # --- 4. Adjust length based on user message (2, 3, or 4 words) ---
    if reply_text:
        incoming_len = len(incoming_message.split())
        if incoming_len <= 5: # Chhota user message
            reply_text = " ".join(reply_text.split()[:3]) if len(reply_text.split()) > 3 else reply_text # Max 3 words
        elif incoming_len <= 12: # Medium user message
            reply_text = " ".join(reply_text.split()[:5]) if len(reply_text.split()) > 5 else reply_text # Max 5 words
        # Else (longer message), use up to 8 words as allowed by initial truncate

    # --- 5. Final check: Links aur usernames filter karein ---
    if reply_text and re.search(r'http[s]?://\S+|@\S+', reply_text, re.IGNORECASE):
        reply_text = "Main links ya usernames nahi bhej sakti. Sorry! 😔" # Fallback if filtered

    # --- Reply send karna ---
    if reply_text or sticker_to_send:
        # Full reply text includes emojis (if any)
        final_reply_text = reply_text + " ".join(emojis_to_send) if reply_text else "".join(emojis_to_send)

        sent_message = None
        if final_reply_text.strip(): # Only send text if it's not empty after adding emojis
            sent_message = await userbot.send_message(chat_id, final_reply_text, reply_to=message_id)
            print(f"Replied with text in {chat_id}: '{final_reply_text}'")

        if sticker_to_send:
            # Sticker always sent as a new message, not a reply to itself.
            await userbot.send_file(chat_id, sticker_to_send)
            print(f"Replied with sticker in {chat_id}: '{sticker_to_send}'")

        # Apne reply ko MongoDB mein store karein (conversation pair ke roop mein)
        if sent_message or sticker_to_send: # Store if anything was sent
            await messages_collection.insert_one({
                'chat_id': chat_id,
                'original_message_id': message_id,
                'reply_text': final_reply_text, # Will be empty if only sticker
                'reply_timestamp': datetime.utcnow(),
                'is_bot_reply': True, # Indicate this is a bot's reply
                'emojis': emojis_to_send,
                'sticker_id': sticker_to_send,
                'original_message': incoming_message # Store original message for context
            })
            print(f"Stored bot's reply for message ID {message_id}")

# --- Event Handlers ---
@userbot.on(events.NewMessage(incoming=True))
async def handle_all_messages(event):
    if event.is_private:
        await handle_private_message(event)
    elif event.is_group or event.is_channel: # Channels ke messages bhi process karein (group learning logic use hogi)
        await generate_and_send_group_reply(event)

async def handle_private_message(event):
    if event.out: # Agar message userbot ne khud bheja hai
        return
    
    sender = await event.get_sender()
    print(f"Received private message from {sender.id}: {event.raw_text}")
    
    # Typing status
    # `send_read_acknowledge` ki jagah `iter_read_history` ka istemal
    await userbot.iter_read_history(event.chat_id, max_id=event.id)
    await userbot.send_action(event.chat_id, SendMessageTypingAction())
    await asyncio.sleep(0.5) # Delay

    # Send a random funny/engaging girl-like private reply
    reply_to_send = random.choice(PRIVATE_REPLY_TEXT_FUNNY_GIRL_LIKE)
    await event.reply(reply_to_send)
    print(f"Replied privately to {sender.id} with girl-like funny message.")

# --- Main function to start userbot and Flask ---
async def main():
    print("Starting userbot...")
    await userbot.start()
    print("Userbot started successfully!")

    # Background tasks chalayein
    asyncio.create_task(manage_db_size()) # DB cleaning task
    
    print("Userbot is running and listening for messages.")
    await userbot.run_until_disconnected() # Yeh Telethon loop ko chalta rakhega

# --- Run the application ---
if __name__ == '__main__':
    # Telethon loop ke liye
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
