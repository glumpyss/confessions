import discord
from discord.ext import commands
from discord import app_commands # Required for slash commands
import os # Import the os module to access environment variables
from dotenv import load_dotenv # Import load_dotenv from python-dotenv

# Load environment variables from .env file (for local development)
# This line should be at the very top, before accessing any environment variables.
load_dotenv()

# --- Bot Configuration ---
# IMPORTANT: Get your Discord bot token from an environment variable.
# It will be read from your .env file locally, or directly from your
# hosting environment's configuration.
# CHANGED: Now looking for 'DISCORD_TOKEN' as per your setup.
DISCORD_BOT_TOKEN = os.getenv('DISCORD_TOKEN')

# Replace '1383002144352894990' with the actual ID of your confessions channel.
# To get a channel ID, enable Developer Mode in Discord (User Settings -> Advanced),
# then right-click the channel and select 'Copy ID'.
CONFESSIONS_CHANNEL_ID = 1383002144352894990 # Consider making this an environment variable too if it changes per deployment

# --- Bot Setup ---
# Define the bot's intents. Intents specify which events your bot wants to receive from Discord.
# discord.Intents.default() provides common intents.
# message_content intent is crucial for your bot to read message content (though less critical for slash commands).
intents = discord.Intents.default()
intents.message_content = True # Necessary for reading message content if you were using traditional commands.
                               # For slash commands, this intent is less directly used for command input,
                               # but good practice for general bot functionality.

# Create a bot instance with a command prefix (not used for slash commands, but required for the Bot class)
# and the defined intents.
bot = commands.Bot(command_prefix='!', intents=intents)

# --- Event: Bot is Ready ---
@bot.event
async def on_ready():
    """
    This event fires when the bot has successfully connected to Discord.
    It's a good place to synchronize slash commands.
    """
    print(f'Logged in as {bot.user.name} ({bot.user.id})')
    print('------')
    try:
        # Sync slash commands with Discord.
        # This can take a few seconds and might not be instant.
        # You can sync globally or to specific guilds. Global sync is usually fine for a few commands.
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s).")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

# --- Slash Command: /confession ---
@bot.tree.command(name="confession", description="Submit an anonymous confession.")
@app_commands.describe(
    text="The confession you want to submit anonymously."
)
async def confession(interaction: discord.Interaction, text: str):
    """
    Handles the '/confession' slash command.
    
    Args:
        interaction (discord.Interaction): The interaction object from Discord.
        text (str): The confession text provided by the user.
    """
    
    # 1. Send an ephemeral message to the user confirming their confession was sent.
    # ephemeral=True makes the message visible only to the user who invoked the command.
    await interaction.response.send_message(
        "Your confession has been sent!",
        ephemeral=True
    )

    # 2. Get the target channel for confessions.
    confessions_channel = bot.get_channel(CONFESSIONS_CHANNEL_ID)

    if confessions_channel:
        # 3. Create an embed for the confession.
        # Embeds are visually appealing message blocks in Discord.
        embed = discord.Embed(
            title="Anonymous Confession",
            description=f"\"**{text}**\"", # Format the confession text
            color=discord.Color.dark_red() # Choose a color for the embed
        )
        embed.set_footer(text="Confession submitted anonymously.") # A small note at the bottom

        # 4. Send the embed to the confessions channel.
        await confessions_channel.send(embed=embed)
        print(f"Confession sent to channel {confessions_channel.name} by {interaction.user.name}")
    else:
        # If the channel is not found (e.g., incorrect ID, bot not in server)
        print(f"Error: Confessions channel with ID {CONFESSIONS_CHANNEL_ID} not found or accessible.")
        # Optionally, inform the user if the bot couldn't find the channel.
        # This message would still be ephemeral.
        await interaction.followup.send(
            "An error occurred while sending your confession. The confessions channel might be misconfigured.",
            ephemeral=True
        )

# --- Run the Bot ---
if __name__ == "__main__":
    if DISCORD_BOT_TOKEN is None:
        print("ERROR: DISCORD_TOKEN environment variable not set.")
        print("Please set the 'DISCORD_TOKEN' environment variable.")
        print("For local development, create a .env file in the same directory as bot.py with: DISCORD_TOKEN='YOUR_ACTUAL_TOKEN_HERE'")
        print("For deployment, set the environment variable directly on your hosting platform (e.g., Heroku, Railway).")
    else:
        bot.run(DISCORD_BOT_TOKEN)
