import discord
from discord.ext import commands
from discord import app_commands, FFmpegPCMAudio # Changed from FFmpegOpusAudio to FFmpegPCMAudio
import os
from dotenv import load_dotenv
import asyncio
import yt_dlp
import discord.utils
import traceback
import aiohttp # Import aiohttp for making HTTP requests
import time # Import time module for performance logging

# Load environment variables from .env file (for local development)
load_dotenv()

# --- Bot Configuration ---
DISCORD_BOT_TOKEN = os.getenv('DISCORD_TOKEN') # Using DISCORD_TOKEN as per your environment variable name
CONFESSIONS_CHANNEL_ID = 1383079469958566038 # Updated to match discord-confession-bot immersive

# --- YTDLP Options for Music Playback ---
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    # Removed opus postprocessor as FFmpegPCMAudio expects PCM, not pre-encoded Opus
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
intents.voice_states = True # Crucial for detecting voice state changes

bot = commands.Bot(command_prefix='!', intents=intents)

# Dictionary to store song queues for each guild. Stores song_data dicts.
guild_music_queues = {}
# Dictionary to store information about the currently playing song for each guild
now_playing_info = {}
# Dictionary to store the loop mode for each guild: None, 'song', or 'queue'
guild_loop_modes = {}
# Dictionary to store the current volume for each guild (0.0 to 1.0)
guild_volumes = {}

# --- Helper Function to Play Next Song ---
async def play_next_song(guild_id, error=None):
    """
    Plays the next song in the queue for a given guild.
    This function is called recursively after each song finishes.
    """
    voice_client = discord.utils.get(bot.voice_clients, guild__id=guild_id)
    
    if error:
        print(f"Player error in guild {guild_id}: {error}")
        # If there was an error playing, clear current song info and try next in queue
        if guild_id in now_playing_info:
            del now_playing_info[guild_id]

    # Handle looping the current song
    loop_mode = guild_loop_modes.get(guild_id, None)
    if loop_mode == 'song' and guild_id in now_playing_info:
        # If looping current song, re-use the already stored now_playing_info
        song_to_play = now_playing_info[guild_id]
        print(f"DEBUG: Looping current song: {song_to_play.get('title')} in guild {guild_id}.")
    elif loop_mode == 'queue' and guild_id in guild_music_queues and guild_id in now_playing_info:
        # If looping queue, put the just finished song back at the end of the queue
        finished_song = now_playing_info[guild_id]
        await guild_music_queues[guild_id].put(finished_song)
        print(f"DEBUG: Looping queue, re-added {finished_song.get('title')} to end of queue for guild {guild_id}.")
        # Then get the next song from the regular queue logic below
        song_to_play = None # Will be fetched from queue
    else:
        song_to_play = None # Will be fetched from queue

    # Ensure the voice client still exists and is connected
    if voice_client and voice_client.is_connected():
        if song_to_play is None: # If not looping current song, get from queue
            if guild_id in guild_music_queues and not guild_music_queues[guild_id].empty():
                try:
                    # Get the next song data (url and info) from the queue
                    song_to_play = guild_music_queues[guild_id].get_nowait()
                except asyncio.QueueEmpty:
                    print(f"Queue empty for guild {guild_id}. Stopping playback.")
                    if guild_id in now_playing_info:
                        del now_playing_info[guild_id] # Clear now playing when queue is empty
                    return # No more songs to play
            else:
                print(f"No more songs in queue for guild {guild_id}. Stopping playback.")
                if guild_id in now_playing_info:
                    del now_playing_info[guild_id] # Clear now playing when queue is empty
                return # No more songs to play

        try:
            next_url = song_to_play['url']
            # Directly instantiate FFmpegPCMAudio with the URL
            player = FFmpegPCMAudio(next_url, **FFMPEG_OPTIONS) 
            
            # Wrap player with PCMVolumeTransformer for volume control
            current_volume = guild_volumes.get(guild_id, 1.0) # Default to 100%
            player = discord.PCMVolumeTransformer(player, volume=current_volume)
            
            voice_client.play(player, after=lambda e: bot.loop.create_task(play_next_song(guild_id, e)))
            now_playing_info[guild_id] = song_to_play # Update now_playing_info for this guild
            print(f"Playing next song: {song_to_play.get('title')} in guild {guild_id}.")
        except Exception as e:
            print(f"Error playing next song in guild {guild_id}: {e}\n{traceback.format_exc()}")
            if guild_id in now_playing_info:
                del now_playing_info[guild_id] # Clear if error occurs
            # If an error occurs, try to play the next song in case it was just a bad URL
            bot.loop.create_task(play_next_song(guild_id)) 
    else:
        print(f"Voice client not connected or found for guild {guild_id}. Cannot play next song.")
        if guild_id in guild_music_queues:
            # Clear the queue if bot unexpectedly left or disconnected
            while not guild_music_queues[guild_id].empty():
                try:
                    guild_music_queues[guild_id].get_nowait()
                except asyncio.QueueEmpty:
                    break
            del guild_music_queues[guild_id]
            print(f"Cleared queue for guild {guild_id} as bot is not connected.")
        if guild_id in now_playing_info:
            del now_playing_info[guild_id] # Clear now playing if not connected


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

# --- Event: Voice State Update ---
@bot.event
async def on_voice_state_update(member, before, after):
    """
    Logs changes in voice state for members and the bot itself.
    Helpful for debugging unexpected disconnects or reconnections.
    """
    # If the bot itself changes voice state
    if member == bot.user:
        if before.channel is None and after.channel is not None:
            print(f"Bot joined voice channel: {after.channel.name} in guild {after.channel.guild.name}")
        elif before.channel is not None and after.channel is None:
            print(f"Bot left voice channel: {before.channel.name} in guild {before.channel.guild.name}")
            # If the bot was playing music and left, stop playback and clear queue
            guild_id = before.channel.guild.id
            voice_client = discord.utils.get(bot.voice_clients, guild__id=guild_id)
            if voice_client and voice_client.is_playing():
                voice_client.stop()
            if guild_id in guild_music_queues:
                while not guild_music_queues[guild_id].empty():
                    try:
                        guild_music_queues[guild_id].get_nowait()
                    except asyncio.QueueEmpty:
                        break
                del guild_music_queues[guild_id]
                print(f"Music queue cleared for guild {guild_id} as bot left voice channel.")
            if guild_id in now_playing_info:
                del now_playing_info[guild_id] # Clear now playing if bot leaves
            if guild_id in guild_loop_modes:
                del guild_loop_modes[guild_id] # Clear loop mode
            if guild_id in guild_volumes:
                del guild_volumes[guild_id] # Clear volume
        elif before.channel is not None and after.channel is not None and before.channel != after.channel:
            print(f"Bot moved from {before.channel.name} to {after.channel.name} in guild {after.channel.guild.name}")
        # Log other bot voice state changes (e.g., mute, deafen)
        if before.self_mute != after.self_mute:
            print(f"Bot self-muted: {after.self_mute}")
        if before.self_deaf != after.self_deaf:
            print(f"Bot self-deafened: {after.self_deaf}")
    
    # If a user disconnects from the bot's channel
    if before.channel and bot.user in before.channel.members and not after.channel:
        # If the bot is the only member left in the voice channel after a user leaves, disconnect
        if len(before.channel.members) == 1 and bot.user in before.channel.members:
            voice_client = discord.utils.get(bot.voice_clients, guild__id=before.channel.guild.id)
            if voice_client and voice_client.is_connected(): # Ensure it's still connected before trying to disconnect
                await voice_client.disconnect()
                if before.channel.guild.id in guild_music_queues:
                    del guild_music_queues[before.channel.guild.id]
                if before.channel.guild.id in now_playing_info:
                    del now_playing_info[before.channel.guild.id] # Clear now playing if no users left
                if before.channel.guild.id in guild_loop_modes:
                    del guild_loop_modes[before.channel.guild.id] # Clear loop mode
                if before.channel.guild.id in guild_volumes:
                    del guild_volumes[before.channel.guild.id] # Clear volume
                print(f"Bot left voice channel {before.channel.name} due to inactivity (no users left).")


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
            print(f"DEBUG: Attempting to connect to voice channel '{voice_channel.name}'...")
            start_time = time.time()
            voice_client = await voice_channel.connect()
            end_time = time.time()
            print(f"DEBUG: Connected to voice channel in {end_time - start_time:.2f} seconds.")
            guild_music_queues[interaction.guild.id] = asyncio.Queue()
            guild_volumes[interaction.guild.id] = 1.0 # Initialize volume to 100%
            guild_loop_modes[interaction.guild.id] = None # Initialize loop mode to off
            await interaction.followup.send(f"Joined {voice_channel.name}!")
    except discord.ClientException as e:
        print(f"ClientException during voice channel connection: {e}\n{traceback.format_exc()}")
        await interaction.followup.send(f"I encountered a permissions issue or other client error while trying to join the voice channel. Please check my permissions in '{voice_channel.name}' and the server. Detailed error: {e}", ephemeral=True)
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
    
    if interaction.guild.id in now_playing_info:
        del now_playing_info[interaction.guild.id] # Clear now playing when leaving
    if interaction.guild.id in guild_loop_modes:
        del guild_loop_modes[interaction.guild.id] # Clear loop mode
    if interaction.guild.id in guild_volumes:
        del guild_volumes[interaction.guild.id] # Clear volume

    try:
        await voice_client.disconnect()
        await interaction.followup.send("Left the voice channel!")
    except Exception as e:
        print(f"Error disconnecting from voice channel: {e}\n{traceback.format_exc()}")
        await interaction.followup.send("An error occurred while trying to leave the voice channel.")


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
            guild_volumes[interaction.guild.id] = 1.0 # Initialize volume to 100%
            guild_loop_modes[interaction.guild.id] = None # Initialize loop mode to off
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
             guild_volumes[interaction.guild.id] = 1.0 # Initialize volume to 100%
             guild_loop_modes[interaction.guild.id] = None # Initialize loop mode to off
    else:
        # Check if response was already sent by previous defer/followup for "Joined..."
        if not interaction.response.is_done():
            await interaction.followup.send(f"Searching for **{query}**...", ephemeral=False)

    try:
        print(f"DEBUG: Starting yt-dlp info extraction for '{query}'...")
        start_time_yt = time.time()
        with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
            info = await bot.loop.run_in_executor(None, lambda: ydl.extract_info(query, download=False))
        end_time_yt = time.time()
        print(f"DEBUG: yt-dlp info extraction finished in {end_time_yt - start_time_yt:.2f} seconds.")
            
        if not info:
            await interaction.followup.send("Could not find any results for that query. This might be due to an invalid URL/search term, region restrictions, or the source's bot detection blocking the request. Please try a different source or search term.", ephemeral=False)
            return

        if 'entries' in info and info['entries']:
            # If it's a playlist or search result, take the first entry
            info = info['entries'][0]
        elif 'webpage_url' in info: # If it's a direct video link, info is already the video.
            pass
        else:
            await interaction.followup.send("Could not extract video information from the provided query. Please try a different URL or search term.", ephemeral=False)
            return

        url = info['url']
        title = info.get('title', 'Unknown Title')
        uploader = info.get('uploader', 'Unknown Uploader')
        duration_seconds = info.get('duration')
        webpage_url = info.get('webpage_url', url) # Fallback to url if webpage_url is missing

        song_data = {
            'url': url,
            'title': title,
            'uploader': uploader,
            'duration': duration_seconds,
            'webpage_url': webpage_url
        }

        # --- Critical check for voice connection before attempting to play ---
        if voice_client and not voice_client.is_connected():
            await interaction.followup.send("I tried to play, but I'm no longer connected to the voice channel. Please try `/join` first.", ephemeral=False)
            print(f"DEBUG: Bot not connected to voice when attempting to play in guild {interaction.guild.id} (before starting playback).")
            return # Exit the command since we can't play if disconnected.

        if voice_client and (voice_client.is_playing() or (interaction.guild.id in guild_music_queues and not guild_music_queues[interaction.guild.id].empty())):
            await guild_music_queues[interaction.guild.id].put(song_data) # Store full song_data
            await interaction.followup.send(f"Added **{title}** to the queue!", ephemeral=False)
        elif voice_client: # Only attempt to play if voice_client is valid and connected
            try:
                print(f"DEBUG: Starting FFmpegPCMAudio for '{title}'...")
                start_time_ffmpeg = time.time()
                # Directly instantiate FFmpegPCMAudio with the URL
                player = FFmpegPCMAudio(url, **FFMPEG_OPTIONS) 
                
                # Wrap player with PCMVolumeTransformer for volume control
                current_volume = guild_volumes.get(interaction.guild.id, 1.0) # Default to 100%
                player = discord.PCMVolumeTransformer(player, volume=current_volume)

                end_time_ffmpeg = time.time()
                print(f"DEBUG: FFmpegPCMAudio instantiation finished in {end_time_ffmpeg - start_time_ffmpeg:.2f} seconds.")

                voice_client.play(player, after=lambda e: bot.loop.create_task(play_next_song(interaction.guild.id, e)))
                now_playing_info[interaction.guild.id] = song_data # Store current playing song info
                await interaction.followup.send(f"Now playing: **{title}**", ephemeral=False)
                print(f"DEBUG: Now playing initiated for guild {interaction.guild.id}: {title}")
            except discord.ClientException as ce:
                print(f"ClientException during voice_client.play: {ce}\n{traceback.format_exc()}")
                await interaction.followup.send(f"Failed to start playback. It seems I lost connection to voice. Please try `/join` again and then `/play`.", ephemeral=False)
            except Exception as e:
                print(f"General error during voice_client.play: {e}\n{traceback.format_exc()}")
                await interaction.followup.send(f"An unexpected error occurred while trying to play the song. Ensure PyNaCl and FFmpeg are installed and accessible, and try again. Detailed error: {e}", ephemeral=False)
        else:
            await interaction.followup.send("I'm not in a voice channel or there was an issue getting connected. Please try `/join` first.", ephemeral=False)


    except yt_dlp.utils.DownloadError as e:
        print(f"YTDL Download Error: {e}\n{traceback.format_exc()}")
        error_message = "Failed to retrieve song information."
        if "confirm you’re not a bot" in str(e).lower() or "too many requests" in str(e).lower() or "blocked by youtube" in str(e).lower():
            error_message += " The source's bot detection or rate limits blocked the request (e.g., YouTube). Please try a different URL or search term, or try again later."
        elif "private video" in str(e).lower() or "unavailable" in str(e).lower() or "not available in your country" in str(e).lower():
             error_message += " The video is private, unavailable, or restricted in your region."
        else:
            error_message += f" An unknown error occurred: {e}. Please ensure the URL is valid and publicly accessible."
        await interaction.followup.send(error_message, ephemeral=False)
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
        if interaction.guild.id in now_playing_info:
            del now_playing_info[interaction.guild.id] # Clear now playing when stopping
        if interaction.guild.id in guild_loop_modes:
            guild_loop_modes[interaction.guild.id] = None # Reset loop mode
        await interaction.followup.send("Playback stopped and queue cleared.")
    else:
        await interaction.followup.send("I am not currently playing anything.")


@bot.tree.command(name="skip", description="Skips the current song to the next in the queue.")
async def skip(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    voice_client = discord.utils.get(bot.voice_clients, guild__id=interaction.guild.id)
    
    # Reset loop mode to None when skipping to avoid unintended continuous looping
    if interaction.guild.id in guild_loop_modes:
        guild_loop_modes[interaction.guild.id] = None

    if voice_client and voice_client.is_playing():
        voice_client.stop() # This triggers the 'after' callback which calls play_next_song
        await interaction.followup.send("Skipping song...")
    elif voice_client and interaction.guild.id in guild_music_queues and not guild_music_queues[interaction.guild.id].empty():
        # If not playing but queue has items, just call play_next_song
        bot.loop.create_task(play_next_song(interaction.guild.id))
        await interaction.followup.send("Skipping to the next song in the queue.")
    else:
        await interaction.followup.send("No song is currently playing or in the queue to skip.")


@bot.tree.command(name="queue", description="Shows the current song queue.")
async def show_queue(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)

    if interaction.guild.id not in guild_music_queues or guild_music_queues[interaction.guild.id].empty():
        return await interaction.followup.send("The music queue is empty.")

    # Convert the async queue to a list for display
    # We now store song_data dictionaries in the queue
    queue_items_data = list(guild_music_queues[interaction.guild.id]._queue)

    if not queue_items_data:
        return await interaction.followup.send("The music queue is empty.")

    queue_description = "**Current Queue:**\n"
    for i, item_data in enumerate(queue_items_data):
        title = item_data.get('title', 'Unknown Title')
        queue_description += f"{i+1}. {title}\n" 

    embed = discord.Embed(
        title="Music Queue",
        description=queue_description,
        color=discord.Color.dark_grey(),
        timestamp=interaction.created_at # Set timestamp directly in constructor
    )
    await interaction.followup.send(embed=embed)

# --- Command: /info ---
@bot.tree.command(name="info", description="Shows information about the currently playing song.")
async def info(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)

    guild_id = interaction.guild.id
    current_song = now_playing_info.get(guild_id)
    voice_client = discord.utils.get(bot.voice_clients, guild__id=guild_id)

    if not voice_client or not voice_client.is_connected() or not current_song or not voice_client.is_playing():
        await interaction.followup.send("No song is currently playing.", ephemeral=False)
        return

    title = current_song.get('title', 'Unknown Title')
    uploader = current_song.get('uploader', 'Unknown Uploader')
    webpage_url = current_song.get('webpage_url', 'N/A')
    duration_seconds = current_song.get('duration')

    duration_str = "N/A"
    if duration_seconds is not None:
        minutes, seconds = divmod(duration_seconds, 60)
        duration_str = f"{int(minutes):02d}:{int(seconds):02d}"

    embed = discord.Embed(
        title="Currently Playing Song Information",
        color=discord.Color.blue(),
        timestamp=interaction.created_at # Set timestamp directly in constructor
    )
    embed.add_field(name="Title", value=title, inline=False)
    embed.add_field(name="Artist/Uploader", value=uploader, inline=False)
    if duration_seconds is not None:
        embed.add_field(name="Duration", value=duration_str, inline=True)
    embed.add_field(name="Source Link", value=f"[Click Here]({webpage_url})" if webpage_url != 'N/A' else 'N/A', inline=True)
    
    embed.set_footer(text=f"Requested by {interaction.user.display_name}")

    await interaction.followup.send(embed=embed, ephemeral=False)


# --- New Command: /ping ---
@bot.tree.command(name="ping", description="Checks the bot's latency (response time).")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"Pong! My latency is `{round(bot.latency * 1000)}ms`.", ephemeral=False)

# --- New Command: /loop ---
@bot.tree.command(name="loop", description="Sets the looping mode for the current song or queue.")
@app_commands.describe(mode="Choose the loop mode: off, song, or queue.")
@app_commands.choices(
    mode=[
        app_commands.Choice(name="Off", value="off"),
        app_commands.Choice(name="Song", value="song"),
        app_commands.Choice(name="Queue", value="queue"),
    ]
)
async def loop(interaction: discord.Interaction, mode: app_commands.Choice[str]):
    await interaction.response.defer(ephemeral=False)
    
    guild_id = interaction.guild.id
    voice_client = discord.utils.get(bot.voice_clients, guild__id=guild_id)

    if not voice_client or not voice_client.is_connected():
        await interaction.followup.send("I am not currently in a voice channel.", ephemeral=False)
        return

    current_song = now_playing_info.get(guild_id)
    
    if mode.value == 'off':
        guild_loop_modes[guild_id] = None
        await interaction.followup.send("Looping is now **off**.")
    elif mode.value == 'song':
        if not voice_client.is_playing() and not current_song:
            await interaction.followup.send("No song is currently playing to loop. Start playing a song first.", ephemeral=False)
            return
        guild_loop_modes[guild_id] = 'song'
        await interaction.followup.send("Looping current **song**.")
    elif mode.value == 'queue':
        if not voice_client.is_playing() and guild_music_queues[guild_id].empty() and not current_song:
            await interaction.followup.send("The queue is empty. Add songs to the queue first to loop it.", ephemeral=False)
            return
        guild_loop_modes[guild_id] = 'queue'
        await interaction.followup.send("Looping current **queue**.")
    else:
        await interaction.followup.send("Invalid loop mode. Choose 'off', 'song', or 'queue'.", ephemeral=False)

# --- New Command: /volume ---
@bot.tree.command(name="volume", description="Sets the bot's playback volume (0-100%).")
@app_commands.describe(percentage="The desired volume percentage (0 to 100).")
async def volume(interaction: discord.Interaction, percentage: int):
    await interaction.response.defer(ephemeral=False)

    guild_id = interaction.guild.id
    voice_client = discord.utils.get(bot.voice_clients, guild__id=guild_id)

    if not voice_client or not voice_client.is_connected():
        await interaction.followup.send("I am not currently in a voice channel.", ephemeral=False)
        return

    if not (0 <= percentage <= 100):
        await interaction.followup.send("Please provide a volume percentage between 0 and 100.", ephemeral=False)
        return

    # Convert percentage to a 0.0-1.0 scale
    new_volume = percentage / 100.0
    guild_volumes[guild_id] = new_volume # Store the new volume

    if voice_client.source: # Check if a song is currently playing and has a source
        voice_client.source.volume = new_volume
        await interaction.followup.send(f"Volume set to **{percentage}%**.")
    else:
        await interaction.followup.send(f"Volume preference set to **{percentage}%**. This will apply to the next song played.")


# --- Gag Stock Command ---
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

        # --- FIX: Using 'seedsStock' key for seeds data ---
        seeds_stock_data = data.get('seedsStock', []) # Use 'seedsStock' here
        egg_items = data.get('eggStock', [])         
        gear_items = data.get('gearStock', [])       
        
        # --- DEBUG PRINT STATEMENT for Raw Seed Stock ---
        print(f"Raw seedsStock from API: {seeds_stock_data}")
        # --- END DEBUG STATEMENT ---

        def format_stock_list(items_data):
            """Helper function to format a list of stock items into a readable string."""
            if not isinstance(items_data, list):
                print(f"Warning: Expected a list for stock items, got {type(items_data)}")
                return "Data format error" 
            if not items_data:
                return "None in stock"
            
            formatted_items = []
            for item in items_data:
                # Ensure each item is a dictionary and has 'name' and 'value' keys
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

        # Create a clean, modern embed with inline fields
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
        
        # Always try to send the cooldown message, using followup if interaction.response.is_done():
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
