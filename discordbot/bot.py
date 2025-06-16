import discord
from discord.ext import commands
from discord import app_commands # Removed FFmpegPCMAudio
import os
from dotenv import load_dotenv
import asyncio # Keep asyncio for general async operations
import traceback
import aiohttp
import time

# Removed explicit Opus library loading as voice is no longer used

# Load environment variables from .env file (for local development)
load_dotenv()

# --- Bot Configuration ---
DISCORD_BOT_TOKEN = os.getenv('DISCORD_TOKEN')
CONFESSIONS_CHANNEL_ID = 1383079469958566038

# Removed YTDL_OPTIONS as yt_dlp is no longer used
# Removed FFMPEG_OPTIONS as ffmpeg is no longer used for playback

# --- API Configuration ---
GAG_STOCK_API_URL = "https://growagardenapi.vercel.app/api/stock/GetStock"

# --- Bot Setup ---
intents = discord.Intents.default()
intents.message_content = True
# Removed voice_states intent as music system is removed
# intents.voice_states = True 

bot = commands.Bot(command_prefix='!', intents=intents)

# Removed music-related global variables:
# guild_music_queues = {}
# now_playing_info = {}
# guild_loop_modes = {}
# guild_volumes = {}

# Removed play_next_song helper function as it's part of the music system

# --- Event: Bot is Ready ---
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} ({bot.user.id})')
    print('------')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s).")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

# Removed on_voice_state_update event as it's part of the music system


# --- Slash Command: /confession ---
@bot.tree.command(name="confession", description="Submit an anonymous confession.")
@app_commands.describe(
    text="The confession you want to submit.",
    visibility="Choose whether to submit publicly or anonymously."
)
@app_commands.choices(
    visibility=[
        app_commands.Choice(name="Anonymous", value="anonymous"),
        app_commands.Choice(name="Public", value="public"),
    ]
)
async def confession(interaction: discord.Interaction, text: str, visibility: str):
    confirmation_message = ""
    if visibility == "anonymous":
        confirmation_message = "Your anonymous confession has been sent!"
    else:
        confirmation_message = "Your public confession has been sent!"

    await interaction.response.send_message(
        confirmation_message,
        ephemeral=True
    )

    confessions_channel = bot.get_channel(CONFESSIONS_CHANNEL_ID)

    if confessions_channel:
        embed = discord.Embed(
            title="Confession",
            description=f"\"**{text}**\"",
            color=discord.Color.dark_grey()
        )
        
        if visibility == "anonymous":
            embed.set_footer(text="Submitted anonymously.")
        else:
            embed.set_author(name=interaction.user.display_name, 
                             icon_url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url)
        
        embed.timestamp = interaction.created_at

        await confessions_channel.send(embed=embed)
        print(f"Confession ({visibility}) sent to channel {confessions_channel.name} by {interaction.user.name}")
    else:
        print(f"Error: Confessions channel with ID {CONFESSIONS_CHANNEL_ID} not found or accessible.")
        await interaction.followup.send(
            "An error occurred while sending your confession. The confessions channel might be misconfigured.",
            ephemeral=True
        )

# Removed all music commands: /join, /leave, /play, /pause, /resume, /stop, /skip, /queue, /info, /loop, /volume


# --- Gag Stock Command ---
@bot.tree.command(name="gag-stock", description="Get the current stock levels for various gags.")
@app_commands.checks.cooldown(1, 10, key=lambda i: i.user.id)
async def gag_stock(interaction: discord.Interaction):
    try:
        await interaction.response.defer(ephemeral=True)
    except discord.errors.NotFound:
        print("Failed to defer interaction for /gag-stock. It might have expired or been responded to already.")
        return

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(GAG_STOCK_API_URL) as response:
                response.raise_for_status()
                data = await response.json()

        seeds_stock_data = data.get('seedsStock', [])
        egg_items = data.get('eggStock', [])         
        gear_items = data.get('gearStock', [])       
        
        print(f"Raw seedsStock from API: {seeds_stock_data}")

        def format_stock_list(items_data):
            if not isinstance(items_data, list):
                print(f"Warning: Expected a list for stock items, got {type(items_data)}")
                return "Data format error" 
            if not items_data:
                return "None in stock"
            
            formatted_items = []
            for item in items_data:
                if isinstance(item, dict) and 'name' in item and 'value' in item:
                    name = item['name']
                    value = item['value']
                    formatted_items.append(f"- {name} ({value})")
                else:
                    print(f"Skipping malformed item in stock list: {item}")
            
            if not formatted_items:
                return "None in stock (or all items malformed)" 
            
            return "\n".join(formatted_items)

        formatted_seeds_stock = format_stock_list(seeds_stock_data)
        formatted_egg_stock = format_stock_list(egg_items)
        formatted_gear_stock = format_stock_list(gear_items)

        embed = discord.Embed(
            title="Gag Stock Information",
            color=discord.Color.dark_grey(),
            timestamp=interaction.created_at
        )

        embed.add_field(name="Seed Stock", value=formatted_seeds_stock, inline=True)
        embed.add_field(name="Egg Stock", value=formatted_egg_stock, inline=True)
        embed.add_field(name="Gear Stock", value=formatted_gear_stock, inline=True)

        await interaction.followup.send(embed=embed, ephemeral=True)

    except aiohttp.ClientError as e:
        print(f"API request failed: {e}\n{traceback.format_exc()}")
        await interaction.followup.send(
            "Failed to retrieve stock information. The API might be down or unreachable. Please try again later.",
            ephemeral=True
        )
    except KeyError as e:
        print(f"Missing expected data in API response: {e}\n{traceback.format_exc()}")
        await interaction.followup.send(
            "Failed to parse stock information. The API response format might have changed. Please contact support.",
            ephemeral=True
        )
    except Exception as e:
        print(f"An unexpected error occurred in /gag-stock: {e}\n{traceback.format_exc()}")
        await interaction.followup.send(
            "An unexpected error occurred while fetching gag stock. Please try again later.",
            ephemeral=True
        )

# --- Cooldown Error Handling for all commands ---
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        remaining_time = round(error.retry_after, 1)
        if remaining_time < 1:
            cooldown_message = "Your command is on cooldown. Please try again in less than a second."
        else:
            cooldown_message = f"Your command is on cooldown. Please try again in **{remaining_time} seconds**."
        
        if interaction.response.is_done():
            await interaction.followup.send(cooldown_message, ephemeral=True)
        else:
            await interaction.response.send_message(cooldown_message, ephemeral=True)
    else:
        print(f"Unhandled application command error: {error}\n{traceback.format_exc()}")
        if interaction.response.is_done():
            await interaction.followup.send("An unexpected error occurred while processing your command. The bot developers have been notified.", ephemeral=True)
        else:
            await interaction.response.send_message("An unexpected error occurred while processing your command. The bot developers have been notified.", ephemeral=True)


# --- Run the Bot ---
if __name__ == "__main__":
    if DISCORD_BOT_TOKEN is None:
        print("ERROR: DISCORD_TOKEN environment variable not set.")
        print("Please set the 'DISCORD_TOKEN' environment variable.")
        print("For local development, create a .env file in the same directory as bot.py with: DISCORD_TOKEN='YOUR_ACTUAL_TOKEN_HERE'")
    else:
        bot.run(DISCORD_BOT_TOKEN)
