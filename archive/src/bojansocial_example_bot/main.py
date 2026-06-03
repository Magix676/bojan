import logging
import json
import os

from bojansocial_example_bot.client import BojanBotClient, MentionEvent, PostEvent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    force=True,
)

# check if config.json exists
if not os.path.exists("config.json"):
    print(f"error: config.json not found. copy config.example.json and fill in your token.")
    exit(1)

with open("config.json") as f:
    config = json.load(f)
    
    if "token" not in config:
        logging.error("token not found in config.json. please add your bot token from https://bojan.social/bots.")
        exit(1)        
    

def main():
    bot = BojanBotClient(
        token=config["token"],
    )

    @bot.on_connect
    def handle_connect():
        logging.info("connected!")

    @bot.on_disconnect
    def handle_disconnect():
        logging.warning("disconnected!")

    @bot.on_error
    def handle_error(e):
        logging.error(f"stream error: {e}", exc_info=e)

    @bot.on_mention
    def handle_mention(event: MentionEvent):
        logging.info(f"mentioned by {event.author_id}: {event.content}")
        try:
            bot.api.reply("peter griffen", event.post_id)
        except Exception as e:
            logging.error(f"failed to reply: {e}")

    @bot.on_post
    def handle_post(event: PostEvent):
        logging.info(f"new post from {event.author}: {event.content}")

    @bot.on_reply
    def handle_reply(event: PostEvent):
        logging.info(f"new reply from {event.author} on {event.reply_to}: {event.content}")

    print("starting bot...")
    bot.run()

if __name__ == "__main__":
    main()