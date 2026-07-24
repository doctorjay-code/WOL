import os, logging
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.DEBUG)

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

@app.event("message")
def handle_message_events(body, logger):
    print("=== MESSAGE EVENT RECEIVED ===")
    print(body)

if __name__ == "__main__":
    handler = SocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN"))
    handler.start()
