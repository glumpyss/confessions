import discord
from discord.ext import commands
from discord import app_commands
import os
from dotenv import load_dotenv
import asyncio
import traceback
import aiohttp
import time
import random
from datetime import datetime, timedelta

# Load environment variables from .env file (for local development)
# This line should be present for local testing, but Railway handles environment variables directly.
load_dotenv()

# --- Bot Configuration ---
# All sensitive configurations MUST be loaded from environment variables.
# For Railway, these are set in your project's "Variables" tab.
DISCORD_BOT_TOKEN = os.getenv('DISCORD_TOKEN') # Ensure your Railway variable is named DISCORD_TOKEN
CONFESSIONS_CHANNEL_ID = int(os.getenv('CONFESSIONS_CHANNEL_ID', '1383079469958566038')) # Default if not set, but prefer explicit config

# --- API Configuration ---
GAG_STOCK_API_URL = "https://growagardenapi.vercel.app/api/stock/GetStock"

# --- API Keys for external services (ALL LOADED FROM ENVIRONMENT VARIABLES) ---
# You MUST set these environment variables in your Railway project settings.
# Do NOT hardcode actual keys here.
CURRENCY_API_KEY = os.getenv("CURRENCY_API_KEY") 
IMAGE_GEN_API_KEY = os.getenv("IMAGE_GEN_API_KEY") 
FORTNITE_API_KEY = os.getenv("FORTNITE_API_KEY")

# Example Stability AI (SDXL) endpoint - keep this as a string, no key needed in URL
IMAGE_GEN_API_URL = "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v0-9/text-to-image" 


# --- Bot Setup ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# --- Global Variables for Commands ---
bot_start_time = datetime.now() # To track bot uptime

# In-memory storage for bot-banned users (resets on bot restart)
bot_banned_users = set()
# In-memory storage for social links (resets on bot restart)
user_social_links = {} # {user_id: {platform: link}}

# Lists for fun commands - these can stay directly in code as they're not sensitive
TRUTHS = [
    "What's the most embarrassing thing you've ever worn?",
    "What's a secret talent you have?",
    "What's the weirdest food combination you secretly enjoy?",
    "What's one thing you're really bad at, but love doing?",
    "What's the funniest thing you've seen happen on Discord?",
    "What's the most scandalous thing you've ever witnessed in a public Discord call?",
    "What's a secret Discord server you're in that you'd never tell your real-life friends about?",
    "What's the riskiest lie you've ever told someone you met on Discord?",
    "Have you ever pretended to be busy in real life to spend more time on Discord? What were you doing instead?",
    "What's the most embarrassing Discord message you've ever accidentally sent to the wrong person/channel?",
    "What's a weird habit or ritual you have when you're heavily invested in a Discord game or event?",
    "What's the most inappropriate direct message exchange you've ever had on Discord?",
    "Have you ever snooped through someone else's Discord DMs or private channels (with or without permission)?",
    "What's a Discord crush you've had that no one knows about?",
    "What's the most time you've ever spent on Discord in a single day, and what were you avoiding in real life?",
    "What's one thing you've done in real life that was directly influenced by a dare or challenge from Discord?",
    "What's the most personal secret you've accidentally revealed in a Discord voice chat?",
    "What's one Discord server you joined purely out of FOMO (Fear Of Missing Out) and then immediately regretted?",
    "What's a Discord profile picture or bio you've had that you now deeply regret?",
    "Have you ever blocked someone on Discord in real life, or vice versa, because of something that happened online?",
    "What's the most outrageous lie you've ever told about yourself on a Discord profile or in a server?",
    "What's a Discord roleplay scenario you've been in that blurred the lines between online and real life too much?",
    "Have you ever tried to use Discord to find a romantic partner, and what was your most awkward experience?",
    "What's the most dramatic exit you've ever made from a Discord server, and why?",
    "What's a secret you keep from your real-life friends that you've told someone on Discord?",
]

DARES = [
    "Send a random emoji to a random text channel in this server.",
    "Change your nickname to 'Daredevil' for 5 minutes.",
    "Say 'Boop boop beep' in a voice chat (if applicable).",
    "Post a picture of your pet (or a funny animal picture) in chat.",
    "Try to say your username backwards 3 times fast.",
    "Give a random user a compliment.",
    "Tell Summer hes a sexy young man", # This one is very specific, you might want to generalize it
    "Send a screenshot of your phone's home screen",
    "Tell us your go-to karaoke song.",
    "Post a picture of your shoes.",
    "Show us your best thinking pose",
    "What's one thing you can't live without?",
    "Type out your Discord ID backwards",
    "Share the last Discord sticker you used.",
    "Change your server profile picture to a random server emoji for 5 minutes.",
    "Do your best impression of a Discord notification sound.",
    "Send a message composed entirely of Discord bot command names.",
    "Share a screenshot of your current Discord activity status.",
    "Tell us a funny story about something that happened in a Discord call.",
    "What's one Discord Nitro feature you can't live without?",
    "Give a shoutout to a specific Discord server.",
    "Make a funny face during a Discord video call (if applicable).",
    "Write a 1-sentence synopsis of your favorite Discord bot's purpose.",
    "Ping the bot's developer in a public channel and tell them a random fact.",
    "Change your Discord bio to \"Powered by Lonelyy!\" for 30 minutes.", # Fixed string literal
    "Send a message that only contains Discord emoji reactions.",
    "List all the bots in the server in reverse alphabetical order.",
    "Say \"Latency is love, latency is life\" five times fast in a voice chat.", # Fixed string literal
    "Post a picture of your favorite Discord emote that isn't from this server.",
    "Share the first message you ever sent in this server.",
    "Send a screenshot of your Discord friend list (blurring names).",
    "Give a random user in the server a ping role (if you have permission).",
    "Invent a new Discord game mode for voice channels.",
    "Try to draw the Discord logo using only text characters.",
    "Describe what you'd do if Discord went down for 24 hours.",
    "Post a little-known Discord trick or tip.",
    "Write a mini-story (3 sentences) about a lost message in a Discord channel.",
    "Reveal your least favorite Discord server you've been in.",
    "Change your server nickname to a common Discord error message for 5 minutes.",
    "Send a message using only Discord system messages (e.g., \"User joined the call\").",
    "Tell us your favorite Discord custom status.",
    "Act out the \"connecting to voice\" sound in voice chat.", # Fixed string literal and made more specific
    "Describe your biggest Discord pet peeve in three words.",
    "Tell us your least favorite Discord feature.",
    "Post a picture of your longest active Discord thread.",
    "Recommend a Discord server you genuinely love.",
    "Invent a new Discord permission and describe its use.",
    "Try to say \"Slash commands are super swift\" with a mouthful of marshmallows (if you have them).", # Fixed string literal
    "Write a review for an imaginary Discord bot feature.",
    "Explain the difference between a guild and a server in Discord in 10 words or less.",
    "Show us your best typing... impression.",
    "Pretend to be a Discord moderator for your next 5 messages.",
    "Send a picture of your favorite Discord font.",
    "Tell us your dream Discord app command idea.",
    "Write a short poem about Discord DMs.",
    "What's the last Discord emoji you used? Tell us!",
    "Do your best impression of a Discord user leaving a voice channel.",
    "Describe your ideal Discord bot.",
    "What's your favorite Discord Easter egg?",
    "Send a message composed entirely of Discord invite links (to safe servers!).",
    "Share a screenshot of your oldest Discord message in a server.",
    "Tell us a funny story about a Discord bot going rogue.",
    "What's one Discord developer feature you can't live without?",
    "Give a shoutout to a specific Discord role.",
    "Make a funny sound in a Discord voice call (if applicable).",
    "Write a 1-sentence synopsis of why you love Discord.",
]

NEVER_HAVE_I_EVER = [
    "Never have I ever dyed my hair a crazy color.",
    "Never have I ever fallen asleep in a public place.",
    "Never have I ever accidentally sent a text to the wrong person.",
    "Never have I ever faked being sick to get out of something.",
    "Never have I ever cheated on a test.",
    "Never have I ever accidentally shared a highly embarrassing screenshot in a public Discord channel.",
    "Never have I ever ghosted someone in real life because I was too invested in a Discord roleplay.",
    "Never have I ever pretended to be someone else entirely during a Discord voice chat.",
    "Never have I ever gone on a date with someone I only knew from Discord, and it was nothing like I expected.",
    "Never have I ever been caught discussing something highly inappropriate in a Discord DM by someone looking over my shoulder.",
    "Never have I ever used a voice changer in Discord to prank someone and taken it too far.",
    "Never have I ever been secretly attracted to a Discord moderator or admin.",
    "Never have I ever joined a \"not safe for work\" Discord server just out of pure curiosity.", # Fixed string literal
    "Never have I ever stayed up all night on Discord and then had to pretend I got sleep in real life.",
    "Never have I ever sent a risky photo or video to someone I only knew from Discord.",
    "Never have I ever created a fake Discord account to snoop on someone.",
    "Never have I ever been involved in or witnessed serious drama unfold in a Discord voice channel.",
    "Never have I ever regretted a Discord username or profile picture so much that I considered quitting.",
    "Never have I ever had a dream about my Discord friends or a specific server.",
]

# --- Check if user is bot-banned ---
async def is_bot_banned(interaction: discord.Interaction):
    """
    Checks if a user is banned from using bot commands.
    Sends an ephemeral message if banned.
    """
    if interaction.user.id in bot_banned_users:
        await interaction.response.send_message("You are banned from using bot commands.", ephemeral=True)
        return True
    return False

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
    Submits an anonymous confession to a predefined channel.
    """
    if await is_bot_banned(interaction): return
    
    await interaction.response.send_message(
        "Your confession has been sent!",
        ephemeral=True
    )

    confessions_channel = bot.get_channel(CONFESSIONS_CHANNEL_ID)

    if confessions_channel:
        embed = discord.Embed(
            title="Anonymous Confession",
            description=f"\"**{text}**\"",
            color=discord.Color.dark_red()
        )
        embed.set_footer(text="Confession submitted anonymously.")
        embed.timestamp = interaction.created_at

        await confessions_channel.send(embed=embed)
        print(f"Confession sent to channel {confessions_channel.name} by {interaction.user.name}")
    else:
        print(f"Error: Confessions channel with ID {CONFESSIONS_CHANNEL_ID} not found or accessible.")
        await interaction.followup.send(
            "An error occurred while sending your confession. The confessions channel might be misconfigured.",
            ephemeral=True
        )

# --- Slash Command: /gag-stock ---
@bot.tree.command(name="gag-stock", description="Get the current stock levels for various gags.")
@app_commands.checks.cooldown(1, 10, key=lambda i: i.user.id)
async def gag_stock(interaction: discord.Interaction):
    """
    Fetches and displays current stock levels from the Grow A Garden API.
    """
    if await is_bot_banned(interaction): return
    
    try:
        await interaction.response.defer(ephemeral=True)
    except discord.errors.NotFound:
        print("Failed to defer interaction for /gag-stock. It might have expired or been responded to already.")
        return

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(GAG_STOCK_API_URL) as response:
                response.raise_for_status() # Raises an exception for HTTP errors (4xx or 5xx)
                data = await response.json()

        seeds_stock_data = data.get('seedsStock', [])
        egg_items = data.get('eggStock', [])         
        gear_items = data.get('gearStock', [])       
        
        print(f"Raw seedsStock from API: {seeds_stock_data}")

        def format_stock_list(items_data):
            """Helper to format stock items into a readable string."""
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

# --- New Command: /uptime ---
@bot.tree.command(name="uptime", description="Shows how long the bot has been online.")
async def uptime(interaction: discord.Interaction):
    """
    Displays the bot's current uptime.
    """
    if await is_bot_banned(interaction): return

    current_time = datetime.now()
    delta = current_time - bot_start_time
    
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    uptime_string = []
    if days > 0:
        uptime_string.append(f"{days} day{'s' if days != 1 else ''}")
    if hours > 0:
        uptime_string.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes > 0:
        uptime_string.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if seconds > 0 or not uptime_string: # Include seconds if no other unit, or if it's less than a minute
        uptime_string.append(f"{int(seconds)} second{'s' if seconds != 1 else ''}") # Cast to int for display
    
    await interaction.response.send_message(f"I've been online for **{' '.join(uptime_string)}**.", ephemeral=False)


# --- New Command: /ship ---
@bot.tree.command(name="ship", description="Calculate the compatibility between two users.")
@app_commands.describe(user1="The first user.", user2="The second user.")
async def ship(interaction: discord.Interaction, user1: discord.Member, user2: discord.Member):
    """
    Calculates and displays a "compatibility percentage" between two users.
    """
    if await is_bot_banned(interaction): return

    if user1.id == user2.id:
        return await interaction.response.send_message("Please pick two different users!", ephemeral=True)

    # Combine user IDs in a consistent way to ensure same result regardless of order
    user_ids = sorted([user1.id, user2.id])
    seed_value = sum(user_ids) # Simple numeric sum as a seed

    random.seed(seed_value)
    compatibility_percentage = random.randint(0, 100)
    random.seed() # Reset seed for other random operations

    response_messages = [
        "Hmm, interesting combo...",
        "Let's see what the stars say...",
        "Calculating connection...",
        "A bond is forming...",
        "Chemistry check..."
    ]
    random_response = random.choice(response_messages)

    if compatibility_percentage < 30:
        phrase = "not a great match."
    elif 30 <= compatibility_percentage < 60:
        phrase = "an okay match."
    elif 60 <= compatibility_percentage < 85:
        phrase = "a good match!"
    else:
        phrase = "a perfect match! ❤️"

    await interaction.response.send_message(
        f"{random_response}\n"
        f"**{user1.display_name}** and **{user2.display_name}** are **{compatibility_percentage}%** {phrase}",
        ephemeral=False
    )

# --- New Command: /simprate ---
@bot.tree.command(name="simprate", description="Rate someone's 'simp' level (for playful use).")
@app_commands.describe(user="The user to rate.")
async def simprate(interaction: discord.Interaction, user: discord.Member):
    """
    Playfully rates a user's 'simp' level.
    """
    if await is_bot_banned(interaction): return

    # Use user ID as a seed for consistent results for the same user
    random.seed(user.id)
    simp_percentage = random.randint(0, 100)
    random.seed() # Reset seed

    if simp_percentage < 25:
        tier = "just a friend."
    elif 25 <= simp_percentage < 50:
        tier = "a bit caring."
    elif 50 <= simp_percentage < 75:
        tier = "quite devoted."
    else:
        tier = "a true simp! ❤️"

    await interaction.response.send_message(f"**{user.display_name}** is **{simp_percentage}%** {tier}", ephemeral=False)

# --- New Command: /howgay ---
@bot.tree.command(name="howgay", description="Playfully rate someone's 'gayness'.")
@app_commands.describe(user="The user to rate.")
async def howgay(interaction: discord.Interaction, user: discord.Member):
    """
    Playfully rates a user's 'gayness'.
    """
    if await is_bot_banned(interaction): return

    random.seed(user.id)
    gay_percentage = random.randint(0, 100)
    random.seed()

    phrases = [
        "just vibing.",
        "got some rainbow flair.",
        "pretty fabulous.",
        "shining bright like a diamond!",
        "the gayest of them all! 🌈"
    ]
    
    if gay_percentage < 20:
        phrase_index = 0
    elif gay_percentage < 40:
        phrase_index = 1
    elif gay_percentage < 60:
        phrase_index = 2
    elif gay_percentage < 80:
        phrase_index = 3
    else:
        phrase_index = 4

    await interaction.response.send_message(f"**{user.display_name}** is **{gay_percentage}%** {phrases[phrase_index]}", ephemeral=False)


# --- New Command: /truth ---
@bot.tree.command(name="truth", description="Get a random truth question.")
async def truth(interaction: discord.Interaction):
    """
    Sends a random 'truth' question.
    """
    if await is_bot_banned(interaction): return
    await interaction.response.send_message(f"**Truth:** {random.choice(TRUTHS)}", ephemeral=False)

# --- New Command: /dare ---
@bot.tree.command(name="dare", description="Get a random dare challenge.")
async def dare(interaction: discord.Interaction):
    """
    Sends a random 'dare' challenge.
    """
    if await is_bot_banned(interaction): return
    await interaction.response.send_message(f"**Dare:** {random.choice(DARES)}", ephemeral=False)

# --- New Command: /neverhaveiever ---
@bot.tree.command(name="neverhaveiever", description="Play a 'Never Have I Ever' statement.")
async def neverhaveiever(interaction: discord.Interaction):
    """
    Sends a random 'Never Have I Ever' statement.
    """
    if await is_bot_banned(interaction): return
    await interaction.response.send_message(f"**Never Have I Ever:** {random.choice(NEVER_HAVE_I_EVER)}", ephemeral=False)

# --- New Command: /clickgame ---
@bot.tree.command(name="clickgame", description="A simple click-based mini-game.")
async def clickgame(interaction: discord.Interaction):
    """
    Starts a simple mini-game where the user clicks a button.
    """
    if await is_bot_banned(interaction): return
    
    view = discord.ui.View(timeout=30) # Set a timeout for the view (e.g., 30 seconds)
    button = discord.ui.Button(label="Click Me!", style=discord.ButtonStyle.primary)

    async def button_callback(button_interaction: discord.Interaction):
        if button_interaction.user.id == interaction.user.id:
            await button_interaction.response.send_message(f"You clicked it! Good job!", ephemeral=True)
            view.stop() # Stop listening after one click
        else:
            await button_interaction.response.send_message("This isn't your game!", ephemeral=True)

    button.callback = button_callback
    view.add_item(button)

    await interaction.response.send_message("Test your reflexes! Click the button!", view=view, ephemeral=False)
    # The view will timeout after 180 seconds by default if no interaction occurs.

# --- New Command: /lyrics ---
@bot.tree.command(name="lyrics", description="Get lyrics for a song.")
@app_commands.describe(artist="The artist's name.", title="The song title.")
async def lyrics(interaction: discord.Interaction, artist: str, title: str):
    """
    Fetches and displays lyrics for a given song and artist using Lyrics.ovh API.
    """
    if await is_bot_banned(interaction): return

    await interaction.response.defer(ephemeral=False)
    
    try:
        lyrics_url = f"https://api.lyrics.ovh/v1/{artist}/{title}"
        async with aiohttp.ClientSession() as session:
            async with session.get(lyrics_url) as response:
                if response.status == 200:
                    data = await response.json()
                    lyrics_text = data.get('lyrics')
                    if lyrics_text:
                        # Discord embed description has a limit of 4096 characters
                        if len(lyrics_text) > 4000:
                            lyrics_text = lyrics_text[:4000] + "\n\n... (lyrics too long, truncated)"

                        embed = discord.Embed(
                            title=f"Lyrics for {title} by {artist}",
                            description=lyrics_text,
                            color=discord.Color.blue()
                        )
                        await interaction.followup.send(embed=embed, ephemeral=False)
                    else:
                        await interaction.followup.send(f"Couldn't find lyrics for **{title}** by **{artist}**. No lyrics data available.", ephemeral=False)
                elif response.status == 404:
                    await interaction.followup.send(f"Lyrics not found for **{title}** by **{artist}**. Please check the spelling.", ephemeral=False)
                else:
                    await interaction.followup.send(f"An error occurred while fetching lyrics. Status code: {response.status}", ephemeral=False)
    except Exception as e:
        print(f"Error fetching lyrics: {e}\n{traceback.format_exc()}")
        await interaction.followup.send("An unexpected error occurred while trying to get lyrics. The lyrics API might be down or unreachable.", ephemeral=False)


# --- New Command: /currencyconvert ---
@bot.tree.command(name="currencyconvert", description="Convert currencies.")
@app_commands.describe(amount="The amount to convert.", from_currency="The currency code to convert from (e.g., USD, EUR).", to_currency="The currency code to convert to (e.g., JPY, GBP).")
async def currencyconvert(interaction: discord.Interaction, amount: float, from_currency: str, to_currency: str):
    """
    Converts a given amount from one currency to another using an external API.
    """
    if await is_bot_banned(interaction): return

    await interaction.response.defer(ephemeral=False)

    # Check if API key is properly configured
    if not CURRENCY_API_KEY:
        return await interaction.followup.send("Currency conversion API key is not configured. Please contact the bot owner.", ephemeral=True)

    try:
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()

        # The API URL uses the from_currency as the base for rates
        # Construct the URL with the API key loaded from environment variable
        api_url = f"https://v6.exchangerate-api.com/v6/{CURRENCY_API_KEY}/latest/{from_currency}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as response:
                response.raise_for_status()
                data = await response.json()
                
                if data.get('result') == 'success':
                    rates = data.get('conversion_rates')
                    if rates and to_currency in rates:
                        exchange_rate = rates[to_currency]
                        converted_amount = amount * exchange_rate
                        await interaction.followup.send(
                            f"{amount:,.2f} {from_currency} is **{converted_amount:,.2f} {to_currency}**.",
                            ephemeral=False
                        )
                    else:
                        await interaction.followup.send(f"Could not find exchange rate for `{to_currency}`. Please check the currency codes (e.g., USD, EUR).", ephemeral=False)
                else:
                    error_type = data.get('error-type', 'Unknown error')
                    await interaction.followup.send(f"Currency conversion failed: {error_type}. Please check your currency codes and API key.", ephemeral=False)
    except aiohttp.ClientError as e:
        print(f"API request failed for currency conversion: {e}\n{traceback.format_exc()}")
        await interaction.followup.send("Failed to retrieve currency rates. The API might be down or unreachable or your API key is invalid.", ephemeral=False)
    except Exception as e:
        print(f"An unexpected error occurred in /currencyconvert: {e}\n{traceback.format_exc()}")
        await interaction.followup.send("An unexpected error occurred during currency conversion.", ephemeral=False)

# --- New Command: /imagegenerate ---
@bot.tree.command(name="imagegenerate", description="Generate an image based on a text prompt.")
@app_commands.describe(prompt="The text description for the image to generate.")
async def imagegenerate(interaction: discord.Interaction, prompt: str):
    """
    Generates an image from a text prompt using an external AI image generation API.
    """
    if await is_bot_banned(interaction): return

    await interaction.response.defer(ephemeral=False)

    # Check if API key and URL are properly configured
    if not IMAGE_GEN_API_KEY:
        return await interaction.followup.send("Image generation API key is not configured. Please contact the bot owner.", ephemeral=True)
    if not IMAGE_GEN_API_URL.startswith("http"):
         return await interaction.followup.send("Image generation API URL is not properly set. Please contact the bot owner.", ephemeral=True)

    try:
        # Headers and payload need to match your chosen Image Generation API's documentation
        headers = {
            "Authorization": f"Bearer {IMAGE_GEN_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json" # Typically application/json for response, or image/png/jpeg for direct image
        }
        
        # Example payload for Stability AI's SDXL (check docs for exact parameters)
        payload = {
            "text_prompts": [{"text": prompt}],
            "cfg_scale": 7, # Controls how much the prompt is adhered to
            "height": 512,  # Image height
            "width": 512,   # Image width
            "samples": 1,   # Number of images to generate (keep to 1 for free tier/simplicity)
            "steps": 30,    # Number of steps for generation
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(IMAGE_GEN_API_URL, json=payload, headers=headers) as response:
                response.raise_for_status() # Raise exception for bad responses
                data = await response.json()
                
                # --- IMPORTANT: Parsing the response depends on your chosen API ---
                # Example for Stability AI, which often returns base64 encoded images:
                image_url = None
                if data and 'artifacts' in data and len(data['artifacts']) > 0:
                    # Check if the image is base64 encoded
                    if 'base64' in data['artifacts'][0]:
                        image_data_base64 = data['artifacts'][0]['base64']
                        image_url = f"data:image/png;base64,{image_data_base64}"
                    # Or if a direct URL is provided by the API (less common for direct generation)
                    elif 'url' in data['artifacts'][0]:
                        image_url = data['artifacts'][0]['url']

                if image_url:
                    embed = discord.Embed(
                        title="Generated Image",
                        description=f"Prompt: \"{prompt}\"",
                        color=discord.Color.green(),
                        timestamp=interaction.created_at
                    )
                    embed.set_image(url=image_url)
                    embed.set_footer(text="Generated by AI")
                    await interaction.followup.send(embed=embed, ephemeral=False)
                else:
                    await interaction.followup.send("Could not generate image. The AI response was unexpected or empty.", ephemeral=False)

    except aiohttp.ClientError as e:
        print(f"Image generation API request failed: {e}\n{traceback.format_exc()}")
        await interaction.followup.send(f"Failed to generate image. The AI service might be down, unreachable, or your API key is invalid. Error: `{e}`", ephemeral=False)
    except Exception as e:
        print(f"An unexpected error occurred in /imagegenerate: {e}\n{traceback.followup()}")
        await interaction.followup.send("An unexpected error occurred during image generation. Please ensure your prompt is appropriate.", ephemeral=False)


# --- New Command: /socials ---
@bot.tree.command(name="socials", description="Add your social media links to your profile.")
@app_commands.describe(platform="The social media platform (e.g., YouTube, Reddit).", link="Your profile link on that platform.")
async def socials(interaction: discord.Interaction, platform: str, link: str):
    """
    Allows users to save their social media links. (Data is in-memory)
    """
    if await is_bot_banned(interaction): return

    user_id = interaction.user.id
    if user_id not in user_social_links:
        user_social_links[user_id] = {}
    
    # Store platform in lowercase for consistency
    user_social_links[user_id][platform.lower()] = link
    
    await interaction.response.send_message(f"Your **{platform.capitalize()}** link has been saved!", ephemeral=True)

# --- New Command: /getsocials ---
@bot.tree.command(name="getsocials", description="View a user's linked social media.")
@app_commands.describe(user="The user whose social links you want to view.")
async def getsocials(interaction: discord.Interaction, user: discord.Member):
    """
    Displays a user's saved social media links.
    """
    if await is_bot_banned(interaction): return

    user_id = user.id
    if user_id not in user_social_links or not user_social_links[user_id]:
        return await interaction.response.send_message(f"**{user.display_name}** hasn't added any social media links yet.", ephemeral=False)

    embed = discord.Embed(
        title=f"{user.display_name}'s Social Links",
        color=discord.Color.purple(),
        timestamp=interaction.created_at
    )
    embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)

    description_parts = []
    for platform, link in user_social_links[user_id].items():
        description_parts.append(f"**{platform.capitalize()}:** <{link}>")
    
    embed.description = "\n".join(description_parts)

    await interaction.response.send_message(embed=embed, ephemeral=False)

# --- New Command: /botban (Admin Only) ---
@bot.tree.command(name="botban", description="Prevent a user from using any bot commands.")
@app_commands.checks.has_permissions(ban_members=True) # Requires Ban Members permission
@app_commands.describe(user="The user to ban from bot commands.", reason="The reason for the bot ban.")
async def botban(interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided."):
    """
    Bans a user from using any bot commands. Requires 'Ban Members' permission.
    """
    if user.id == bot.user.id:
        return await interaction.response.send_message("I cannot ban myself from using commands.", ephemeral=True)
    if user.id == interaction.user.id:
        return await interaction.response.send_message("You cannot ban yourself from using commands.", ephemeral=True)
    # Prevent non-admin from banning admin, unless they are also admin
    if user.guild_permissions.administrator and not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("You cannot ban an administrator from using bot commands unless you are also an administrator.", ephemeral=True)

    if user.id in bot_banned_users:
        return await interaction.response.send_message(f"**{user.display_name}** is already banned from using bot commands.", ephemeral=True)

    bot_banned_users.add(user.id)
    await interaction.response.send_message(f"**{user.display_name}** has been banned from using bot commands. Reason: {reason}", ephemeral=False)
    # Optionally, notify the banned user via DM
    try:
        await user.send(f"You have been banned from using commands in **{interaction.guild.name}** by **{interaction.user.display_name}**. Reason: {reason}")
    except discord.Forbidden:
        print(f"Could not DM {user.display_name} about bot ban.")

# --- New Command: /botunban (Admin Only) ---
@bot.tree.command(name="botunban", description="Allow a user to use bot commands again.")
@app_commands.checks.has_permissions(ban_members=True) # Requires Ban Members permission
@app_commands.describe(user="The user to unban from bot commands.")
async def botunban(interaction: discord.Interaction, user: discord.Member):
    """
    Unbans a user, allowing them to use bot commands again. Requires 'Ban Members' permission.
    """
    if user.id not in bot_banned_users:
        return await interaction.response.send_message(f"**{user.display_name}** is not currently banned from using bot commands.", ephemeral=True)

    bot_banned_users.remove(user.id)
    await interaction.response.send_message(f"**{user.display_name}** has been unbanned from using bot commands.", ephemeral=False)
    try:
        await user.send(f"You have been unbanned from using commands in **{interaction.guild.name}** by **{interaction.user.display_name}**.")
    except discord.Forbidden:
        print(f"Could not DM {user.display_name} about bot unban.")


# --- New Command: /roblox ---
@bot.tree.command(name="roblox", description="Shows a Roblox user's profile and stats.")
@app_commands.describe(username="The Roblox username.")
async def roblox(interaction: discord.Interaction, username: str):
    """
    Fetches and displays a Roblox user's profile information.
    Performs two API calls: username-to-ID, then ID-to-profile.
    """
    if await is_bot_banned(interaction): return
    await interaction.response.defer(ephemeral=False)

    try:
        # Step 1: Get UserID from username (POST request)
        username_to_id_url = "https://users.roblox.com/v1/usernames/users"
        payload = {"usernames": [username], "excludeBannedUsers": False}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(username_to_id_url, json=payload) as response:
                response.raise_for_status()
                user_id_data = await response.json()
                
                if not user_id_data or not user_id_data.get('data'):
                    return await interaction.followup.send(f"Could not find Roblox user **{username}**.", ephemeral=False)
                
                roblox_user_id = user_id_data['data'][0]['id']
                roblox_display_name = user_id_data['data'][0].get('displayName', username)


            # Step 2: Get User Profile Details using UserID (GET request)
            profile_url = f"https://users.roblox.com/v1/users/{roblox_user_id}"
            async with session.get(profile_url) as response:
                response.raise_for_status()
                profile_data = await response.json()

                # Extract relevant data
                name = profile_data.get('name', 'N/A')
                display_name = profile_data.get('displayName', name)
                description = profile_data.get('description', 'No description set.').strip()
                created_date_str = profile_data.get('created', 'N/A')
                is_banned = profile_data.get('isBanned', False)

                # Format join date
                join_date = "N/A"
                if created_date_str != 'N/A':
                    try:
                        # Parse ISO format (e.g., '2020-01-01T00:00:00.000Z')
                        created_dt = datetime.fromisoformat(created_date_str.replace('Z', '+00:00'))
                        join_date = created_dt.strftime("%Y-%m-%d %H:%M UTC")
                    except ValueError:
                        pass # Keep N/A if parsing fails
                
                embed = discord.Embed(
                    title=f"Roblox Profile: {display_name}",
                    description=f"Username: `{name}`",
                    color=discord.Color.blue(),
                    timestamp=interaction.created_at
                )
                embed.set_thumbnail(url=f"https://www.roblox.com/Thumbs/Avatar.ashx?x=150&y=150&username={name}") # Basic avatar thumbnail
                
                embed.add_field(name="User ID", value=roblox_user_id, inline=True)
                embed.add_field(name="Join Date", value=join_date, inline=True)
                embed.add_field(name="Banned", value="Yes" if is_banned else "No", inline=True)
                
                if description:
                    embed.add_field(name="About Me", value=description if len(description) <= 1024 else description[:1021] + "...", inline=False) # Discord field value limit

                await interaction.followup.send(embed=embed, ephemeral=False)

    except aiohttp.ClientResponseError as e:
        if e.status == 404:
            await interaction.followup.send(f"Roblox user **{username}** not found.", ephemeral=False)
        else:
            print(f"Roblox API error (status {e.status}): {e}\n{traceback.format_exc()}")
            await interaction.followup.send(f"An error occurred while fetching Roblox profile: HTTP Status {e.status}.", ephemeral=False)
    except aiohttp.ClientError as e:
        print(f"Roblox API request failed: {e}\n{traceback.format_exc()}")
        await interaction.followup.send("Failed to connect to Roblox API. It might be down or unreachable.", ephemeral=False)
    except Exception as e:
        print(f"An unexpected error occurred in /roblox: {e}\n{traceback.format_exc()}")
        await interaction.followup.send("An unexpected error occurred while fetching Roblox profile.", ephemeral=False)


# --- New Command: /fortnite ---
@bot.tree.command(name="fortnite", description="Shows Fortnite stats for a given username.")
@app_commands.describe(username="The Fortnite username (Epic Games Display Name).")
async def fortnite(interaction: discord.Interaction, username: str):
    """
    Fetches and displays Fortnite Battle Royale player statistics using Fortnite-API.com.
    """
    if await is_bot_banned(interaction): return
    await interaction.response.defer(ephemeral=False)

    # Check if API key is properly configured
    if not FORTNITE_API_KEY:
        return await interaction.followup.send("Fortnite API key is not configured. Please contact the bot owner.", ephemeral=True)

    try:
        api_url = f"https://fortnite-api.com/v2/stats/br/v2?name={username}"
        headers = {"Authorization": FORTNITE_API_KEY}

        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, headers=headers) as response:
                response.raise_for_status()
                data = await response.json()

                if data.get('status') == 200 and data.get('data'):
                    player_data = data['data']
                    
                    # Extract general stats
                    account_name = player_data['account']['name']
                    account_level = player_data['account']['level']
                    battle_pass_level = player_data['battlePass']['level']
                    
                    # Extract overall stats (for all game modes combined)
                    overall_stats = player_data['stats']['all']['overall']
                    wins = overall_stats.get('wins', 0)
                    kills = overall_stats.get('kills', 0)
                    kd = overall_stats.get('kd', 0.0)
                    matches = overall_stats.get('matches', 0)
                    win_rate = overall_stats.get('winRate', 0.0)

                    # Extract image for player icon (if available)
                    avatar_icon = player_data.get('image') # Fortnite-API might provide a generated image

                    embed = discord.Embed(
                        title=f"Fortnite Stats for {account_name}",
                        color=discord.Color.dark_green(),
                        timestamp=interaction.created_at
                    )
                    
                    if avatar_icon:
                        embed.set_thumbnail(url=avatar_icon)

                    embed.add_field(name="Account Level", value=account_level, inline=True)
                    embed.add_field(name="Battle Pass Level", value=battle_pass_level, inline=True)
                    embed.add_field(name="Total Matches", value=matches, inline=True)
                    
                    embed.add_field(name="Wins", value=wins, inline=True)
                    embed.add_field(name="Kills", value=kills, inline=True)
                    embed.add_field(name="K/D", value=f"{kd:.2f}", inline=True)
                    embed.add_field(name="Win Rate", value=f"{win_rate:.2f}%", inline=True)

                    embed.set_footer(text="Data from Fortnite-API.com")
                    await interaction.followup.send(embed=embed, ephemeral=False)

                elif data.get('status') == 404:
                    await interaction.followup.send(f"Fortnite player **{username}** not found. Please ensure it's an exact Epic Games Display Name.", ephemeral=False)
                else:
                    error_message = data.get('error', 'Unknown API error.')
                    await interaction.followup.send(f"An error occurred while fetching Fortnite stats: {error_message}", ephemeral=False)

    except aiohttp.ClientResponseError as e:
        if e.status == 400: # Bad Request, often due to invalid username format or missing API key
            await interaction.followup.send(f"Invalid request for Fortnite stats (HTTP 400). Please check the username and ensure your API key is correctly configured.", ephemeral=False)
        elif e.status == 403: # Forbidden, often due to invalid API key
            await interaction.followup.send(f"Access to Fortnite API forbidden (HTTP 403). Please check if your Fortnite-API.com key is valid.", ephemeral=False)
        elif e.status == 404: # Not found, specifically handled above
            await interaction.followup.send(f"Fortnite player **{username}** not found (HTTP 404).", ephemeral=False)
        else:
            print(f"Fortnite API error (status {e.status}): {e}\n{traceback.format_exc()}")
            await interaction.followup.send(f"An error occurred while fetching Fortnite stats: HTTP Status {e.status}.", ephemeral=False)
    except aiohttp.ClientError as e:
        print(f"Fortnite API request failed: {e}\n{traceback.format_exc()}")
        await interaction.followup.send("Failed to connect to Fortnite API. It might be down or unreachable.", ephemeral=False)
    except Exception as e:
        print(f"An unexpected error occurred in /fortnite: {e}\n{traceback.format_exc()}")
        await interaction.followup.send("An unexpected error occurred while fetching Fortnite stats.", ephemeral=False)


# --- Cooldown Error Handling for all commands ---
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """
    Global error handler for application commands.
    Handles cooldowns and missing permissions specifically.
    """
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
    elif isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("You don't have the necessary permissions to use this command.", ephemeral=True)
    else:
        print(f"Unhandled application command error: {error}\n{traceback.format_exc()}")
        if interaction.response.is_done():
            await interaction.followup.send("An unexpected error occurred while processing your command. The bot developers have been notified.", ephemeral=True)
        else:
            await interaction.response.send_message("An unexpected error occurred while processing your command. The bot developers have been notified.", ephemeral=True)


# --- Run the Bot ---
if __name__ == "__main__":
    # Check if the Discord bot token is set as an environment variable
    if DISCORD_BOT_TOKEN is None:
        print("ERROR: DISCORD_TOKEN environment variable not set.")
        print("Please set the 'DISCORD_TOKEN' environment variable in your deployment environment (e.g., Railway).")
        print("For local development, ensure you have a .env file with DISCORD_TOKEN='YOUR_ACTUAL_TOKEN_HERE'")
    else:
        # This is the correct way to call bot.run():
        bot.run(DISCORD_BOT_TOKEN)
