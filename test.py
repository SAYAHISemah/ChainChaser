from dotenv import load_dotenv
import os

load_dotenv()  # This loads the .env file

discord_token = os.getenv('DISCORD_BOT_TOKEN')