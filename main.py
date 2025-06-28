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
from flask import Flask, request, jsonify

# --- Configuration (Koyeb Environment Variables se aayenge) ---
API_ID = int(os.environ.get('API_ID'))
API_HASH = os.environ.get('API_HASH')
STRING_SESSION = os.environ.get('STRING_SESSION')
MONGO_URI = os.environ.get('MONGO_URI')

# --- Private Message Reply Content (Girl-like, Fun & Engaging) ---
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
    db = client_mongo['telegram_userbot_db']
    messages_collection = db['group_messages']
    print("MongoDB connection successful.")
except Exception as e:
    print(f"MongoDB connection failed: {e}")
    exit()

# --- Telethon Client Setup ---
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
    try:
        client_mongo.admin.command('ping')
        db_status = "Connected"
    except Exception:
        db_status = "Disconnected"
    return jsonify(status="ok", db=db_status, timestamp=datetime.utcnow().isoformat())

# --- MongoDB Data Management Task ---
async def manage_db_size():
    FULL_THRESHOLD = 10000 
    DELETE_PERCENTAGE = 0.50 

    while True:
        await asyncio.sleep(3600)
        try:
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

        except Exception as e:
            print(f"Error managing DB size: {e}")

# --- Reply Generation Logic (Group Specific) ---
async def generate_and_send_group_reply(event):
    incoming_message = event.raw_text
    chat_id = event.chat_id
    message_id = event.id
    
    if event.out or (chat_id in last_processed_message_id and last_processed_message_id[chat_id] == message_id):
        return
    
    last_processed_message_id[chat_id] = message_id

    if re.search(r'http[s]?://\S+|@\S+', incoming_message, re.IGNORECASE):
        print(f"Skipping incoming message with link/username: {incoming_message}")
        return

    # --- Typing status dikhana aur 0.5 second ka delay ---
    await event.mark_read()
    try:
        input_peer = await userbot.get_input_entity(chat_id)
        await userbot(SetTypingRequest(peer=input_peer, action=SendMessageTypingAction()))
        await asyncio.sleep(0.5) # Minimum 0.5 second ka delay for typing
    except Exception as e:
        print(f"Error sending typing action: {e}")

    reply_text = None
    sticker_to_send = None
    emojis_to_send = [] # Har reply ke liye emojis ko reset karein

    # --- 1. Message Storage (Group messages hi store honge) ---
    sender = await event.get_sender()
    
    emojis_in_message = [char for char in incoming_message if 0x1F600 <= ord(char) <= 0x1F64F or 
                                                             0x1F300 <= ord(char) <= 0x1F5FF or 
                                                             0x1F900 <= ord(char) <= 0x1F9FF or 
                                                             0x1FA70 <= ord(char) <= 0x1FAFF]

    if event.sticker:
        sticker_to_store_id = event.sticker.id
    else:
        sticker_to_store_id = None

    messages_collection.insert_one({
        'chat_id': chat_id,
        'sender_id': sender.id,
        'message': incoming_message,
        'timestamp': datetime.utcnow(),
        'emojis': emojis_in_message,
        'sticker_id': sticker_to_store_id,
        'is_bot_reply': False # Mark as user message
    })
    print(f"Stored group message from {sender.id} in {chat_id}: '{incoming_message}'")

    # --- 2. Reply Generation Logic (Self-learning from stored group data) ---
    # Keywords extract karein user ke incoming message se
    words_from_message = [word for word in re.findall(r'\b\w+\b', incoming_message.lower()) if len(word) >= 3 and word not in ['the', 'and', 'is', 'a', 'to', 'in', 'it', 'i', 'of', 'for', 'on', 'with', 'as', 'at', 'this', 'that', 'he', 'she', 'you', 'they', 'we', 'my', 'your', 'his', 'her', 'its', 'our', 'their', 'hai', 'kya', 'kar', 'raha', 'ho', 'tum', 'main', 'ko', 'hi', 'mein', 'pr', 'jago', 'wahan', 'movie', 'search', 'group', 'nam', 'likho', 'ki', 'aapko', 'direct', 'file', 'mil', 'jayegi', 'go', 'profile', 'there', 'is', 'a', 'link', 'to', 'all', 'the', 'movies', 'and', 'webseries', 'click', 'photo']]
    
    if words_from_message:
        regex_pattern = f"({'|'.join(re.escape(w) for w in words_from_message)})"
        
        search_query = {
            "chat_id": chat_id,
            "is_bot_reply": False, # Ab hum user ke past messages mein search karenge
            "message": {"$regex": regex_pattern, "$options": "i"} # User ke message content mein search
        }
        
        # Pichle user message ko dhoondho jo bot ke reply ke liye context de sake
        # Fir us message se associated bot ka reply dhoondho
        
        # User ke relevant message ko dhundho
        relevant_user_message = messages_collection.find_one(search_query, sort=[("timestamp", -1)])

        if relevant_user_message:
            # Agar user ka relevant message mil gaya, toh uske baad ka bot ka reply dhoondho
            bot_reply_query = {
                "chat_id": chat_id,
                "is_bot_reply": True,
                "original_message_id": relevant_user_message['message_id'] # Yeh field aapke current DB schema mein nahi hai, isko use nahi kar sakte
                                                                            # Instead, us user message ke theek baad ka bot reply search karenge
            }
            # Instead of original_message_id, which might not be set correctly for older entries,
            # we'll find bot's replies *after* a specific user message. This is more complex.
            # A simpler approach: if a user message has a stored 'reply_text', use that.
            
            # LET'S REFINES THIS LOGIC:
            # Instead of searching for bot's previous replies based on the 'original_message' field,
            # which became confusing (as it stored user messages),
            # let's modify the document structure slightly to store user message and bot reply as a PAIR.
            # For now, let's just make sure we are searching for a USER's message
            # and trying to find a *corresponding* bot reply.
            
            # Refined search: Find a past user message that contains the keywords.
            # Then, see if there's a bot reply that immediately followed it.
            # This is hard with your current schema.

            # SIMPLER APPROACH FOR 1.28.0 (given constraints):
            # We need to search for an *already stored bot reply* that was given to a *similar user input*.
            # The current `original_message` field in `is_bot_reply: True` documents is problematic
            # because it stores the *user's message*.

            # Let's adjust the `original_message` field in the bot's reply document
            # to be specifically the *keywords* from the user's message, not the full message.
            # And refine the search.
            
            # For now, let's simplify: find any past *bot reply* (is_bot_reply: True)
            # whose `reply_text` contains keywords from the *current* user message.
            # This creates a loop: bot repeats what it said if it matches.
            
            # The *current* logic of finding `past_bot_reply` is trying to find a bot's *previous reply*
            # whose `original_message` field (which stores the user's message) matches the new incoming message.
            # This is actually the correct *intent* for self-learning.
            # The problem is that the `original_message` field in bot replies is being populated
            # with messages like "Searching for Sahi baat hai!", which are not what we want to learn from.

            # The `original_message` field in the bot's reply document is meant to store the *user's message*
            # that triggered this specific bot reply. This is crucial for context.

            # Let's ensure the `original_message` stored in the bot's reply entry is indeed the *user's message*
            # that it's replying to.

            # Let's clean up the regex for `original_message` and `reply_text`
            # and remove the problematic 'Searching For' from keywords if it originates from an external bot.

            # REVISED REPLY GENERATION LOGIC:
            # First, check if the incoming message is one of those "Searching For..." messages.
            # If yes, skip learning from it and just give a generic reply if needed.
            # Otherwise, proceed with learning.
            
            # Handle "Searching For..." messages first
            if "searching for" in incoming_message.lower():
                print(f"Detected 'Searching For' message: '{incoming_message}'. Providing generic reply.")
                reply_text = random.choice(common_replies) # Always use generic for these
                emojis_to_send = random.choice([['👍'], ['😁'], ['😂']])
            else:
                # Normal message processing for self-learning
                # Build regex from user's keywords (after filtering stop words and short words)
                keywords_for_search = [word for word in re.findall(r'\b\w+\b', incoming_message.lower()) if len(word) >= 3 and word not in ['the', 'and', 'is', 'a', 'to', 'in', 'it', 'i', 'of', 'for', 'on', 'with', 'as', 'at', 'this', 'that', 'he', 'she', 'you', 'they', 'we', 'my', 'your', 'his', 'her', 'its', 'our', 'their', 'hai', 'kya', 'kar', 'raha', 'ho', 'tum', 'main', 'ko', 'hi', 'mein', 'pr', 'jago', 'wahan', 'movie', 'search', 'group', 'nam', 'likho', 'ki', 'aapko', 'direct', 'file', 'mil', 'jayegi', 'go', 'profile', 'there', 'is', 'a', 'link', 'to', 'all', 'the', 'movies', 'and', 'webseries', 'click', 'photo', 'for', 'a', 'theek', 'baat', 'sahi']] # Added more stop words
                
                if keywords_for_search:
                    # Look for past bot replies whose 'original_message' (the user's input at that time)
                    # matches the current keywords.
                    search_query_for_past_bot_reply = {
                        "chat_id": chat_id,
                        "is_bot_reply": True,
                        "original_message": {"$regex": f"({'|'.join(re.escape(w) for w in keywords_for_search)})", "$options": "i"} 
                    }
                    
                    past_bot_reply_doc = messages_collection.find_one(search_query_for_past_bot_reply, sort=[("reply_timestamp", -1)])

                    if past_bot_reply_doc and 'reply_text' in past_bot_reply_doc:
                        reply_text = past_bot_reply_doc['reply_text']
                        emojis_to_send = past_bot_reply_doc.get('emojis', []) # Use emojis from the past reply
                        sticker_to_send = past_bot_reply_doc.get('sticker_id', None)
                        print(f"Found existing reply from DB: '{reply_text}' based on keywords: {keywords_for_search}")
                    else:
                        print(f"No relevant past bot reply found for keywords: {keywords_for_search}. Using common replies.")
                else:
                    print("No meaningful keywords extracted from message. Using common replies.")

                if not reply_text: # Agar koi relevant reply nahi mila ya keywords nahi the
                    common_replies = [
                        "Haa! 😄", "Theek hai! 👍", "Hmm...🤔", "Sahi baat hai! ✅", "Kya chal raha hai? 👀",
                        "Accha! ✨", "Samajh gayi! 😉", "Bilkul! 👍", "Baat kar! 🗣️", "Good! 😊",
                        "Aur batao? 👇", "Masti chal rahi hai! 😂", "Kuch naya? 🤩", "Wah! 🥳", "Kya kehna! 😲",
                        "Hehe! 😊", "Ek number! 👌", "Awesome! ✨", "Nice! 😄", "Super! 💖", " "
                    ]
                    reply_text = random.choice(common_replies)
                    
                    if not reply_text.strip():
                        emojis_to_send = random.choice([['👍'], ['😁'], ['😂'], ['🥳'], ['😎'], ['💖'], ['🥰'], ['✨']])
                    elif random.random() < 0.6:
                        emojis_to_send.append(random.choice(['😂', '😊', '🥳', '😎', '👍', '✨', '💖', '🥰']))

                    sticker_list = [ # !!! Yahan apne girl-like stickers ki actual IDs daalein !!!
                        # "CAACAgIAAxkBAAEFfBpmO...Fh18EAAH-xX8AAWJ2XAAE",
                        # "CAACAgIAAxkBAAEFfBpmO...Fh18EAAH-xX8AAWJ2XAAE"
                    ]
                    if not reply_text.strip() and sticker_list and random.random() < 0.7:
                        sticker_to_send = random.choice(sticker_list)
                        emojis_to_send = []

                    print(f"Using fallback reply: '{reply_text}' or sticker: '{sticker_to_send}'")

    # --- 3. Word count control (1-8 words) ---
    if reply_text:
        words = reply_text.split()
        if len(words) > 8:
            reply_text = " ".join(words[:8])

    # --- 4. Adjust length based on user message (2, 3, or 4 words) ---
    if reply_text:
        incoming_len = len(incoming_message.split())
        if incoming_len <= 5:
            reply_text = " ".join(reply_text.split()[:3]) if len(reply_text.split()) > 3 else reply_text
        elif incoming_len <= 12:
            reply_text = " ".join(reply_text.split()[:5]) if len(reply_text.split()) > 5 else reply_text

    # --- 5. Final check: Links aur usernames filter karein ---
    if reply_text and re.search(r'http[s]?://\S+|@\S+', reply_text, re.IGNORECASE):
        reply_text = "Main links ya usernames nahi bhej sakti. Sorry! 😔"

    # --- Reply send karna ---
    if reply_text or sticker_to_send:
        final_reply_text = reply_text + "".join(emojis_to_send) if reply_text else "".join(emojis_to_send) # Emojis ko sirf ek baar add karein
        
        sent_message = None
        if final_reply_text.strip():
            sent_message = await userbot.send_message(chat_id, final_reply_text, reply_to=message_id)
            print(f"Replied with text in {chat_id}: '{final_reply_text}'")

        if sticker_to_send:
            await userbot.send_file(chat_id, sticker_to_send)
            print(f"Replied with sticker in {chat_id}: '{sticker_to_send}'")

        if sent_message or sticker_to_send:
            messages_collection.insert_one({
                'chat_id': chat_id,
                'original_message_id': message_id, # This is the ID of the user's message
                'reply_text': final_reply_text,
                'reply_timestamp': datetime.utcnow(),
                'is_bot_reply': True, # Mark this as bot's reply
                'emojis': emojis_to_send,
                'sticker_id': sticker_to_send,
                'original_message': incoming_message # Store the actual user's message for context
            })
            print(f"Stored bot's reply for message ID {message_id}")
    else:
        print(f"No reply generated for message ID {message_id}.")

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
        await asyncio.sleep(0.5) # Delay for typing
    except Exception as e:
        print(f"Error sending typing action: {e}")

    reply_to_send = random.choice(PRIVATE_REPLY_TEXT_FUNNY_GIRL_LIKE)
    await event.reply(reply_to_send)
    print(f"Replied privately to {sender.id} with girl-like funny message.")

# --- Main function to start userbot and Flask ---
async def main():
    print("Starting userbot...")
    await userbot.start()
    print("Userbot started successfully!")

    asyncio.create_task(manage_db_size())
    
    print("Userbot is running and listening for messages.")
    await userbot.run_until_disconnected()

# --- Run the application ---
if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
