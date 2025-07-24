from dotenv import load_dotenv
import os

# Load the .env file
load_dotenv()

# Print all environment variables that start with DISCORD
print("Environment variables:")
for key, value in os.environ.items():
    if 'DISCORD' in key:
        print(f"{key}: {value}")

# Specifically check for the token
token = os.getenv('DISCORD_BOT_TOKEN')
print(f"\nDISCORD_BOT_TOKEN value: '{token}'")
print(f"Token is None: {token is None}")
print(f"Token is empty: {token == ''}")