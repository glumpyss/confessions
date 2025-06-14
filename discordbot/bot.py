import discord
from discord.ext import commands
from discord import app_commands, FFmpegOpusAudio
import os
from dotenv import load_dotenv
import asyncio
import yt_dlp
import discord.utils
import traceback
import aiohttp # Import aiohttp for making HTTP requests

# Load environment variables from .env file (for local development)
load_dotenv()

# --- Bot Configuration ---
DISCORD_BOT_TOKEN = os.getenv('DISCORD_TOKEN') # Using DISCORD_TOKEN as per your environment variable name
CONFESSIONS_CHANNEL_ID = 1383079469958566038

# --- YTDLP Options for Music Playback ---
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'opus',
        'preferredquality': '192',
    }],
    'extract_flat': 'in_playlist',
    'nocheckcertificate': True,
    'ignoreerrors': True,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}

# FFmpeg options for discord.py. -vn means no video.
FFMPEG_OPTIONS = {
    'options': '-vn'
}

# --- API Configuration ---
GAG_STOCK_API_URL = "https://growagardenapi.vercel.app/api/stock/GetStock"

# --- Bot Setup ---
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Dictionary to store song queues for each guild
guild_music_queues = {}

# --- Helper Function to Play Next Song ---
async def play_next_song(guild_id, error=None):
    if error:
        print(f"Player error in guild {guild_id}: {error}")

    voice_client = discord.utils.get(bot.voice_clients, guild__id=guild_id)
    
    if voice_client and not voice_client.is_playing():
        if guild_id in guild_music_queues and not guild_music_queues[guild_id].empty():
            try:
                next_url = guild_music_queues[guild_id].get_nowait()
                player = await FFmpegOpusAudio.from_probe(next_url, **FFMPEG_OPTIONS)
                voice_client.play(player, after=lambda e: bot.loop.create_task(play_next_song(guild_id, e)))
            except asyncio.QueueEmpty:
                print(f"Queue empty for guild {guild_id}. Stopping playback.")
            except Exception as e:
                print(f"Error playing next song in guild {guild_id}: {e}\n{traceback.format_exc()}")
        else:
            print(f"No more songs in queue or queue does not exist for guild {guild_id}. Stopping playback if idle.")
            
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

# --- Music Commands ---

@bot.tree.command(name="join", description="Makes the bot join your current voice channel.")
async def join(interaction: discord.Interaction):
    if not interaction.user.voice:
        return await interaction.response.send_message("You are not in a voice channel!", ephemeral=True)

    voice_channel = interaction.user.voice.channel
    
    await interaction.response.defer(ephemeral=False)

    voice_client = discord.utils.get(bot.voice_clients, guild__id=interaction.guild.id)

    try:
        if voice_client:
            if voice_client.channel == voice_channel:
                await interaction.followup.send("I am already in this voice channel!")
            else:
                await voice_client.move_to(voice_channel)
                await interaction.followup.send(f"Moved to {voice_channel.name}!")
        else:
            voice_client = await voice_channel.connect()
            guild_music_queues[interaction.guild.id] = asyncio.Queue()
            await interaction.followup.send(f"Joined {voice_channel.name}!")
    except discord.ClientException:
        await interaction.followup.send("I am unable to join the voice channel. Check my permissions and ensure FFmpeg is installed.")
    except Exception as e:
        print(f"Error joining voice channel: {e}\n{traceback.format_exc()}")
        await interaction.followup.send("An unexpected error occurred while trying to join.")


@bot.tree.command(name="leave", description="Makes the bot leave the current voice channel.")
async def leave(interaction: discord.Interaction):
    voice_client = discord.utils.get(bot.voice_clients, guild__id=interaction.guild.id)

    if not voice_client:
        return await interaction.response.send_message("I am not in a voice channel!", ephemeral=True)

    await interaction.response.defer(ephemeral=False)

    if voice_client.is_playing():
        voice_client.stop()
    
    if interaction.guild.id in guild_music_queues:
        while not guild_music_queues[interaction.guild.id].empty():
            try:
                guild_music_queues[interaction.guild.id].get_nowait()
            except asyncio.QueueEmpty:
                break
        del guild_music_queues[interaction.guild.id]

    await voice_client.disconnect()
    await interaction.followup.send("Left the voice channel!")


@bot.tree.command(name="play", description="Plays a song from a URL or search query.")
@app_commands.describe(query="The URL of the song (e.g., YouTube) or search query.")
async def play(interaction: discord.Interaction, query: str):
    if not interaction.user.voice:
        return await interaction.response.send_message("You need to be in a voice channel to use this command!", ephemeral=True)

    voice_channel = interaction.user.voice.channel
    voice_client = discord.utils.get(bot.voice_clients, guild__id=interaction.guild.id)

    await interaction.response.defer(ephemeral=False) 

    if not voice_client:
        try:
            voice_client = await voice_channel.connect()
            guild_music_queues[interaction.guild.id] = asyncio.Queue()
            await interaction.followup.send(f"Joined {voice_channel.name} to play the song.", ephemeral=False)
        except discord.ClientException:
            await interaction.followup.send("I am unable to join your voice channel. Check my permissions and ensure FFmpeg is installed.")
            return
        except Exception as e:
            print(f"Error connecting to voice channel for play command: {e}\n{traceback.format_exc()}")
            await interaction.followup.send("An unexpected error occurred while trying to join for playback.")
            return
    elif voice_client.channel != voice_channel:
        await voice_client.move_to(voice_channel)
        await interaction.followup.send(f"Moved to {voice_channel.name} to play the song.", ephemeral=False)
        if interaction.guild.id not in guild_music_queues:
             guild_music_queues[interaction.guild.id] = asyncio.Queue()
    else:
        if not interaction.response.is_done():
            await interaction.followup.send(f"Searching for **{query}**...", ephemeral=False)

    try:
        with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
            info = await bot.loop.run_in_executor(None, lambda: ydl.extract_info(query, download=False))
            
            if not info:
                await interaction.followup.send("Could not find any results for that query. This might be due to an invalid URL/search term, region restrictions, or the source's bot detection blocking the request. Please try a different source or search term.", ephemeral=False)
                return

            if 'entries' in info and info['entries']:
                info = info['entries'][0]

            url = info['url']
            title = info.get('title', 'Unknown Title')

            if voice_client.is_playing() or not guild_music_queues[interaction.guild.id].empty():
                await guild_music_queues[interaction.guild.id].put(url)
                await interaction.followup.send(f"Added **{title}** to the queue!", ephemeral=False)
            else:
                player = await FFmpegOpusAudio.from_probe(url, **FFMPEG_OPTIONS)
                voice_client.play(player, after=lambda e: bot.loop.create_task(play_next_song(interaction.guild.id, e)))
                await interaction.followup.send(f"Now playing: **{title}**", ephemeral=False)

    except yt_dlp.utils.DownloadError as e:
        print(f"YTDL Download Error: {e}\n{traceback.format_exc()}")
        if "confirm you’re not a bot" in str(e).lower() or "too many requests" in str(e).lower() or "blocked by youtube" in str(e).lower():
            await interaction.followup.send("Failed to retrieve song information: The source's bot detection or rate limits blocked the request (e.g., YouTube). Please try a different URL or search term, or try again later.", ephemeral=False)
        elif "private video" in str(e).lower() or "unavailable" in str(e).lower() or "not available in your country" in str(e).lower():
             await interaction.followup.send("Failed to retrieve song information: The video is private, unavailable, or restricted.", ephemeral=False)
        else:
            await interaction.followup.send(f"Could not download or process audio from the provided query/URL due to an error: {e}. Please ensure the URL is valid and publicly accessible.", ephemeral=False)
    except Exception as e:
        print(f"General error in play command: {e}\n{traceback.format_exc()}")
        await interaction.followup.send(f"An unexpected error occurred while trying to play the song. Ensure PyNaCl and FFmpeg are installed and accessible, and try again. Detailed error: {e}", ephemeral=False)


@bot.tree.command(name="pause", description="Pauses the currently playing song.")
async def pause(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    voice_client = discord.utils.get(bot.voice_clients, guild__id=interaction.guild.id)
    if voice_client and voice_client.is_playing():
        voice_client.pause()
        await interaction.followup.send("Song paused.")
    else:
        await interaction.followup.send("No song is currently playing or paused.")


@bot.tree.command(name="resume", description="Resumes a paused song.")
async def resume(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    voice_client = discord.utils.get(bot.voice_clients, guild__id=interaction.guild.id)
    if voice_client and voice_client.is_paused():
        voice_client.resume()
        await interaction.followup.send("Song resumed.")
    else:
        await interaction.followup.send("No song is currently paused.")


@bot.tree.command(name="stop", description="Stops the current song and clears the queue.")
async def stop(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    voice_client = discord.utils.get(bot.voice_clients, guild__id=interaction.guild.id)
    if voice_client:
        voice_client.stop()
        if interaction.guild.id in guild_music_queues:
            while not guild_music_queues[interaction.guild.id].empty():
                try:
                    guild_music_queues[interaction.guild.id].get_nowait()
                except asyncio.QueueEmpty:
                    break
            del guild_music_queues[interaction.guild.id]
        await interaction.followup.send("Playback stopped and queue cleared.")
    else:
        await interaction.followup.send("I am not currently playing anything.")


@bot.tree.command(name="skip", description="Skips the current song to the next in the queue.")
async def skip(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    voice_client = discord.utils.get(bot.voice_clients, guild__id=interaction.guild.id)
    if voice_client and voice_client.is_playing():
        voice_client.stop()
        await interaction.followup.send("Skipping song...")
    else:
        await interaction.followup.send("No song is currently playing to skip.")


@bot.tree.command(name="queue", description="Shows the current song queue.")
async def show_queue(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)

    if interaction.guild.id not in guild_music_queues or guild_music_queues[interaction.guild.id].empty():
        return await interaction.followup.send("The music queue is empty.")

    queue_items = list(guild_music_queues[interaction.guild.id]._queue)

    if not queue_items:
        return await interaction.followup.send("The music queue is empty.")

    queue_description = "**Current Queue:**\n"
    for i, item_url in enumerate(queue_items):
        queue_description += f"{i+1}. Song from URL\n" 

    embed = discord.Embed(
        title="Music Queue",
        description=queue_description,
        color=discord.Color.dark_grey()
    )
    embed.set_timestamp(interaction.created_at)
    await interaction.followup.send(embed=embed)

# --- New Gag Stock Command ---
@bot.tree.command(name="gag-stock", description="Get the current stock levels for various gags.")
# Apply a 10-second cooldown per user
@app_commands.checks.cooldown(1, 10, key=lambda i: i.user.id)
async def gag_stock(interaction: discord.Interaction):
    # Ensure deferral happens immediately.
    try:
        await interaction.response.defer(ephemeral=True)
    except discord.errors.NotFound:
        print("Failed to defer interaction for /gag-stock. It might have expired or been responded to already.")
        return # Exit the command if we can't defer.

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(GAG_STOCK_API_URL) as response:
                response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
                data = await response.json()

        seed_items = data.get('seedStock', [])
        egg_items = data.get('eggStock', [])         
        gear_items = data.get('gearStock', [])       
        
        # --- DEBUG PRINT STATEMENT for Raw Seed Stock ---
        print(f"Raw seedStock from API: {seed_items}")
        # --- END DEBUG PRINT STATEMENT ---

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

        formatted_seed_stock = format_stock_list(seed_items)
        formatted_egg_stock = format_stock_list(egg_items)
        formatted_gear_stock = format_stock_list(gear_items)

        embed = discord.Embed(
            title="Gag Stock Information",
            color=discord.Color.dark_grey(),
            timestamp=interaction.created_at
        )

        embed.add_field(name="Seed Stock", value=formatted_seed_stock, inline=True)
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
        
        # Always try to send the cooldown message, using followup if interaction.response.is_done()
        if interaction.response.is_done():
            await interaction.followup.send(cooldown_message, ephemeral=True)
        else:
            await interaction.response.send_message(cooldown_message, ephemeral=True)
    else:
        # For any other unhandled errors, log them and send a generic message
        print(f"Unhandled application command error: {error}\n{traceback.format_exc()}")
        if interaction.response.is_done():
            # If a response has already been sent (e.g., initial deferral), use followup
            await interaction.followup.send("An unexpected error occurred while processing your command. The bot developers have been notified.", ephemeral=True)
        else:
            # Otherwise, send initial response
            await interaction.response.send_message("An unexpected error occurred while processing your command. The bot developers have been notified.", ephemeral=True)


# --- Run the Bot ---
if __name__ == "__main__":
    if DISCORD_BOT_TOKEN is None:
        print("ERROR: DISCORD_TOKEN environment variable not set.")
        print("Please set the 'DISCORD_TOKEN' environment variable.")
        print("For local development, create a .env file in the same directory as bot.py with: DISCORD_TOKEN='YOUR_ACTUAL_TOKEN_HERE'")
    else:
        bot.run(DISCORD_BOT_TOKEN)

