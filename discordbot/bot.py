import discord
from discord.ext import commands
from discord import app_commands # Required for slash commands

# --- Bot Configuration ---
# IMPORTANT: Replace 'YOUR_BOT_TOKEN_HERE' with your actual Discord bot token.
# Get this from the Discord Developer Portal -> Your Application -> Bot -> Token.
DISCORD_BOT_TOKEN = 'YOUR_BOT_TOKEN_HERE' 

# Replace '1383002144352894990' with the actual ID of your confessions channel.
# To get a channel ID, enable Developer Mode in Discord (User Settings -> Advanced),
# then right-click the channel and select 'Copy ID'.
CONFESSIONS_CHANNEL_ID = 1383002144352894990

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
# Ensure your bot token is set before running.
if __name__ == "__main__":
    if DISCORD_BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
        print("ERROR: Please replace 'YOUR_BOT_TOKEN_HERE' with your actual Discord bot token.")
        print("The bot will not start without a valid token.")
    else:
        bot.run(DISCORD_BOT_TOKEN)
