import discord
from discord.ext import commands
from discord import app_commands, FFmpegOpusAudio
import os
from dotenv import load_dotenv
import asyncio
import yt_dlp
import discord.utils # Import discord.utils for get()

# Load environment variables from .env file (for local development)
load_dotenv()

# --- Bot Configuration ---
DISCORD_BOT_TOKEN = os.getenv('DISCORD_TOKEN') # Using DISCORD_TOKEN as per your environment variable name
CONFESSIONS_CHANNEL_ID = 1383002144352894990

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

# --- Bot Setup ---
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True # Crucial for detecting voice channel changes

bot = commands.Bot(command_prefix='!', intents=intents)

# Dictionary to store song queues for each guild
guild_music_queues = {} # {guild_id: asyncio.Queue}

# --- Helper Function to Play Next Song ---
async def play_next_song(guild_id, error=None):
    """
    Called after a song finishes playing. Plays the next song in the queue.
    """
    if error:
        print(f"Player error in guild {guild_id}: {error}")
        # Consider sending an error message to the channel here

    # Corrected: Use discord.utils.get to find the voice client
    voice_client = discord.utils.get(bot.voice_clients, guild__id=guild_id)
    
    if voice_client and not voice_client.is_playing():
        if guild_id in guild_music_queues and not guild_music_queues[guild_id].empty():
            try:
                next_url = guild_music_queues[guild_id].get_nowait()
                player = await FFmpegOpusAudio.from_probe(next_url, **FFMPEG_OPTIONS)
                voice_client.play(player, after=lambda e: bot.loop.create_task(play_next_song(guild_id, e)))
                # You might want to send a message to the channel like "Now playing: [Song Title]"
            except asyncio.QueueEmpty:
                print(f"Queue empty for guild {guild_id}. Stopping playback.")
            except Exception as e:
                print(f"Error playing next song in guild {guild_id}: {e}")
        else:
            print(f"No more songs in queue or queue does not exist for guild {guild_id}.")


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
    """
    Handles the '/confession' slash command.
    """
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
    """
    Makes the bot join the voice channel of the user who invoked the command.
    """
    if not interaction.user.voice:
        return await interaction.response.send_message("You are not in a voice channel!", ephemeral=True)

    voice_channel = interaction.user.voice.channel
    
    # Corrected: Use discord.utils.get to find the voice client
    voice_client = discord.utils.get(bot.voice_clients, guild__id=interaction.guild.id)

    try:
        if voice_client: # If bot is already in a voice channel
            if voice_client.channel == voice_channel:
                await interaction.response.send_message("I am already in this voice channel!", ephemeral=True)
            else:
                await voice_client.move_to(voice_channel)
                await interaction.response.send_message(f"Moved to {voice_channel.name}!", ephemeral=True)
        else: # If bot is not in any voice channel in this guild
            voice_client = await voice_channel.connect()
            guild_music_queues[interaction.guild.id] = asyncio.Queue() # Initialize queue for guild
            await interaction.response.send_message(f"Joined {voice_channel.name}!", ephemeral=True)
    except discord.ClientException:
        await interaction.response.send_message("I am unable to join the voice channel. Check my permissions and ensure FFmpeg is installed.", ephemeral=True)
    except Exception as e:
        print(f"Error joining voice channel: {e}")
        await interaction.response.send_message("An unexpected error occurred while trying to join.", ephemeral=True)


@bot.tree.command(name="leave", description="Makes the bot leave the current voice channel.")
async def leave(interaction: discord.Interaction):
    """
    Makes the bot leave the voice channel it is currently in for the guild.
    """
    # Corrected: Use discord.utils.get to find the voice client
    voice_client = discord.utils.get(bot.voice_clients, guild__id=interaction.guild.id)

    if not voice_client:
        return await interaction.response.send_message("I am not in a voice channel!", ephemeral=True)

    if voice_client.is_playing():
        voice_client.stop()
    
    # Clear the queue for the guild
    if interaction.guild.id in guild_music_queues:
        while not guild_music_queues[interaction.guild.id].empty():
            try:
                guild_music_queues[interaction.guild.id].get_nowait()
            except asyncio.QueueEmpty:
                break
        del guild_music_queues[interaction.guild.id]

    await voice_client.disconnect()
    await interaction.response.send_message("Left the voice channel!", ephemeral=True)


@bot.tree.command(name="play", description="Plays a song from a URL or search query.")
@app_commands.describe(query="The URL of the song (e.g., YouTube) or search query.")
async def play(interaction: discord.Interaction, query: str):
    """
    Plays a song from a given URL or search query. Joins if not already in VC.
    """
    if not interaction.user.voice:
        return await interaction.response.send_message("You need to be in a voice channel to use this command!", ephemeral=True)

    voice_channel = interaction.user.voice.channel
    # Corrected: Use discord.utils.get to find the voice client
    voice_client = discord.utils.get(bot.voice_clients, guild__id=interaction.guild.id)

    if not voice_client:
        try:
            voice_client = await voice_channel.connect()
            guild_music_queues[interaction.guild.id] = asyncio.Queue()
        except discord.ClientException:
            return await interaction.response.send_message("I am unable to join your voice channel. Check my permissions and ensure FFmpeg is installed.", ephemeral=True)
        except Exception as e:
            print(f"Error connecting to voice channel for play command: {e}")
            await interaction.response.send_message("An unexpected error occurred while trying to join for playback.", ephemeral=True)
            return # Exit function if connection failed
    elif voice_client.channel != voice_channel:
        await voice_client.move_to(voice_channel)
        await interaction.followup.send(f"Moved to {voice_channel.name} to play the song.", ephemeral=False)
        # Ensure queue is initialized if moving to a new channel within the same guild,
        # though it should ideally persist across moves within the same guild.

    await interaction.response.send_message(f"Searching for **{query}**...", ephemeral=True)

    try:
        with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
            info = ydl.extract_info(query, download=False)
            
            if 'entries' in info and info['entries']:
                info = info['entries'][0]

            if not info:
                return await interaction.followup.send("Could not find any results for that query.", ephemeral=False)

            url = info['url']
            title = info.get('title', 'Unknown Title')

            if voice_client.is_playing() or (interaction.guild.id in guild_music_queues and not guild_music_queues[interaction.guild.id].empty()):
                await guild_music_queues[interaction.guild.id].put(url)
                await interaction.followup.send(f"Added **{title}** to the queue!", ephemeral=False)
            else:
                player = await FFmpegOpusAudio.from_probe(url, **FFMPEG_OPTIONS)
                voice_client.play(player, after=lambda e: bot.loop.create_task(play_next_song(interaction.guild.id, e)))
                await interaction.followup.send(f"Now playing: **{title}**", ephemeral=False)

    except yt_dlp.utils.DownloadError as e:
        print(f"YTDL Download Error: {e}")
        await interaction.followup.send(f"Could not download or process audio from the provided query/URL. Error: {e}", ephemeral=False)
    except Exception as e:
        print(f"General error in play command: {e}")
        await interaction.followup.send(f"An unexpected error occurred while trying to play the song. Ensure PyNaCl and FFmpeg are installed and accessible.", ephemeral=False)


@bot.tree.command(name="pause", description="Pauses the currently playing song.")
async def pause(interaction: discord.Interaction):
    """
    Pauses the currently playing song.
    """
    # Corrected: Use discord.utils.get to find the voice client
    voice_client = discord.utils.get(bot.voice_clients, guild__id=interaction.guild.id)
    if voice_client and voice_client.is_playing():
        voice_client.pause()
        await interaction.response.send_message("Song paused.", ephemeral=False)
    else:
        await interaction.response.send_message("No song is currently playing or paused.", ephemeral=True)


@bot.tree.command(name="resume", description="Resumes a paused song.")
async def resume(interaction: discord.Interaction):
    """
    Resumes a paused song.
    """
    # Corrected: Use discord.utils.get to find the voice client
    voice_client = discord.utils.get(bot.voice_clients, guild__id=interaction.guild.id)
    if voice_client and voice_client.is_paused():
        voice_client.resume()
        await interaction.response.send_message("Song resumed.", ephemeral=False)
    else:
        await interaction.response.send_message("No song is currently paused.", ephemeral=True)


@bot.tree.command(name="stop", description="Stops the current song and clears the queue.")
async def stop(interaction: discord.Interaction):
    """
    Stops the current song and clears the queue for the guild.
    """
    # Corrected: Use discord.utils.get to find the voice client
    voice_client = discord.utils.get(bot.voice_clients, guild__id=interaction.guild.id)
    if voice_client:
        voice_client.stop()
        if interaction.guild.id in guild_music_queues:
            while not guild_music_queues[interaction.guild.id].empty():
                try:
                    guild_music_queues[interaction.guild.id].get_nowait()
                except asyncio.QueueEmpty:
                    break
            del guild_music_queues[interaction.guild.id] # Delete queue after clearing
        await interaction.response.send_message("Playback stopped and queue cleared.", ephemeral=False)
    else:
        await interaction.response.send_message("I am not currently playing anything.", ephemeral=True)


@bot.tree.command(name="skip", description="Skips the current song to the next in the queue.")
async def skip(interaction: discord.Interaction):
    """
    Skips the current song to the next in the queue.
    """
    # Corrected: Use discord.utils.get to find the voice client
    voice_client = discord.utils.get(bot.voice_clients, guild__id=interaction.guild.id)
    if voice_client and voice_client.is_playing():
        voice_client.stop() # Stopping the current song triggers the 'after' callback to play next
        await interaction.response.send_message("Skipping song...", ephemeral=False)
    else:
        await interaction.response.send_message("No song is currently playing to skip.", ephemeral=True)


@bot.tree.command(name="queue", description="Shows the current song queue.")
async def show_queue(interaction: discord.Interaction):
    """
    Shows the current song queue for the guild.
    """
    if interaction.guild.id not in guild_music_queues or guild_music_queues[interaction.guild.id].empty():
        return await interaction.response.send_message("The music queue is empty.", ephemeral=False)

    # Convert the asyncio.Queue to a list for iteration and display
    queue_items = list(guild_music_queues[interaction.guild.id]._queue)

    if not queue_items:
        return await interaction.response.send_message("The music queue is empty.", ephemeral=False)

    queue_description = "**Current Queue:**\n"
    for i, item_url in enumerate(queue_items):
        # For simplicity, just show as "Song [number]". Enhancing to show actual titles
        # would require storing titles in the queue along with URLs.
        queue_description += f"{i+1}. Song from URL\n" 

    embed = discord.Embed(
        title="Music Queue",
        description=queue_description,
        color=discord.Color.dark_grey()
    )
    embed.set_timestamp(interaction.created_at)
    await interaction.response.send_message(embed=embed, ephemeral=False)


# --- Run the Bot ---
if __name__ == "__main__":
    if DISCORD_BOT_TOKEN is None:
        print("ERROR: DISCORD_TOKEN environment variable not set.")
        print("Please set the 'DISCORD_TOKEN' environment variable.")
        print("For local development, create a .env file in the same directory as bot.py with: DISCORD_TOKEN='YOUR_ACTUAL_TOKEN_HERE'")
        print("For deployment, set the environment variable directly on your hosting platform (e.g., Heroku, Railway).")
    else:
        bot.run(DISCORD_BOT_TOKEN)

