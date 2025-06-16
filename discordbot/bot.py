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
from datetime import datetime, timedelta # For uptime calculation

# Load environment variables from .env file (for local development)
load_dotenv()

# --- Bot Configuration ---
DISCORD_BOT_TOKEN = os.getenv('DISCORD_TOKEN')
CONFESSIONS_CHANNEL_ID = 1383002144352894990

# --- API Configuration ---
GAG_STOCK_API_URL = "https://growagardenapi.vercel.app/api/stock/GetStock"

# Placeholders for API Keys (Replace with your actual keys if you get them)
# For /lyrics (e.g., from an unofficial API or a service like Musixmatch, Genius)
LYRICS_API_URL = "https://api.lyrics.ovh/v1/{artist}/{title}" # Example
# For /currencyconvert (e.g., from ExchangeRate-API or Open Exchange Rates)
CURRENCY_API_KEY = "YOUR_CURRENCY_API_KEY" # Example: "YOUR_API_KEY"
CURRENCY_API_URL = f"https://v6.exchangerate-api.com/v6/{CURRENCY_API_KEY}/latest/USD" # Example
# For /imagegenerate (e.g., DALL-E, Stability AI)
IMAGE_GEN_API_KEY = "YOUR_IMAGE_GEN_API_KEY" # Example
IMAGE_GEN_API_URL = "https://api.example.com/image_generation" # Example

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

# Lists for fun commands
TRUTHS = [
    "What's the most embarrassing thing you've ever worn?",
    "What's a secret talent you have?",
    "What's the weirdest food combination you secretly enjoy?",
    "What's one thing you're really bad at, but love doing?",
    "What's the funniest thing you've seen happen on Discord?"
]

DARES = [
    "Send a random emoji to a random text channel in this server.",
    "Change your nickname to 'Daredevil' for 5 minutes.",
    "Say 'Boop boop beep' in a voice chat (if applicable).",
    "Post a picture of your pet (or a funny animal picture) in chat.",
    "Try to say your username backwards 3 times fast."
]

NEVER_HAVE_I_EVER = [
    "Never have I ever dyed my hair a crazy color.",
    "Never have I ever fallen asleep in a public place.",
    "Never have I ever accidentally sent a text to the wrong person.",
    "Never have I ever faked being sick to get out of something.",
    "Never have I ever cheated on a test."
]

# --- Check if user is bot-banned ---
async def is_bot_banned(interaction: discord.Interaction):
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
    if await is_bot_banned(interaction): return
    
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

# --- New Command: /uptime ---
@bot.tree.command(name="uptime", description="Shows how long the bot has been online.")
async def uptime(interaction: discord.Interaction):
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
        uptime_string.append(f"{seconds} second{'s' if seconds != 1 else ''}")
    
    await interaction.response.send_message(f"I've been online for **{' '.join(uptime_string)}**.", ephemeral=False)


# --- New Command: /ship ---
@bot.tree.command(name="ship", description="Calculate the compatibility between two users.")
@app_commands.describe(user1="The first user.", user2="The second user.")
async def ship(interaction: discord.Interaction, user1: discord.Member, user2: discord.Member):
    if await is_bot_banned(interaction): return

    # Ensure users are different
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
@bot.tree.command(name="simprate", description="Rate someone's 'simp' level.")
@app_commands.describe(user="The user to rate.")
async def simprate(interaction: discord.Interaction, user: discord.Member):
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
    if await is_bot_banned(interaction): return
    await interaction.response.send_message(f"**Truth:** {random.choice(TRUTHS)}", ephemeral=False)

# --- New Command: /dare ---
@bot.tree.command(name="dare", description="Get a random dare challenge.")
async def dare(interaction: discord.Interaction):
    if await is_bot_banned(interaction): return
    await interaction.response.send_message(f"**Dare:** {random.choice(DARES)}", ephemeral=False)

# --- New Command: /neverhaveiever ---
@bot.tree.command(name="neverhaveiever", description="Play a 'Never Have I Ever' statement.")
async def neverhaveiever(interaction: discord.Interaction):
    if await is_bot_banned(interaction): return
    await interaction.response.send_message(f"**Never Have I Ever:** {random.choice(NEVER_HAVE_I_EVER)}", ephemeral=False)

# --- New Command: /clickgame ---
@bot.tree.command(name="clickgame", description="A simple click-based mini-game.")
async def clickgame(interaction: discord.Interaction):
    if await is_bot_banned(interaction): return
    
    view = discord.ui.View()
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
    # The view will timeout after 180 seconds if no interaction occurs.

# --- New Command: /lyrics ---
@bot.tree.command(name="lyrics", description="Get lyrics for a song.")
@app_commands.describe(artist="The artist's name.", title="The song title.")
async def lyrics(interaction: discord.Interaction, artist: str, title: str):
    if await is_bot_banned(interaction): return

    await interaction.response.defer(ephemeral=False)
    
    # Placeholder for actual lyrics API integration
    # You would replace this with a real API call (e.g., to Lyrics.ovh, Genius, Musixmatch)
    try:
        # Example using Lyrics.ovh (rate-limited, might not always work)
        lyrics_url = f"https://api.lyrics.ovh/v1/{artist}/{title}"
        async with aiohttp.ClientSession() as session:
            async with session.get(lyrics_url) as response:
                if response.status == 200:
                    data = await response.json()
                    lyrics_text = data.get('lyrics')
                    if lyrics_text:
                        # Discord embed description has a limit of 4096 characters
                        if len(lyrics_text) > 4000:
                            lyrics_text = lyrics_text[:4000] + "\n... (lyrics too long, truncated)"

                        embed = discord.Embed(
                            title=f"Lyrics for {title} by {artist}",
                            description=lyrics_text,
                            color=discord.Color.blue()
                        )
                        await interaction.followup.send(embed=embed, ephemeral=False)
                    else:
                        await interaction.followup.send(f"Couldn't find lyrics for **{title}** by **{artist}**.", ephemeral=False)
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
    if await is_bot_banned(interaction): return

    await interaction.response.defer(ephemeral=False)

    if not CURRENCY_API_KEY or CURRENCY_API_KEY == "YOUR_CURRENCY_API_KEY":
        return await interaction.followup.send("Currency conversion API key is not configured. Please contact the bot owner.", ephemeral=True)

    try:
        # Ensure currency codes are uppercase for API consistency
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()

        api_url = f"https://v6.exchangerate-api.com/v6/{CURRENCY_API_KEY}/latest/{from_currency}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as response:
                response.raise_for_status() # Raise an exception for HTTP errors
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
                        await interaction.followup.send(f"Could not find exchange rate for {to_currency}. Please check the currency codes.", ephemeral=False)
                else:
                    error_type = data.get('error-type', 'Unknown error')
                    await interaction.followup.send(f"Currency conversion failed: {error_type}. Please check your currency codes and API key.", ephemeral=False)
    except aiohttp.ClientError as e:
        print(f"API request failed for currency conversion: {e}\n{traceback.format_exc()}")
        await interaction.followup.send("Failed to retrieve currency rates. The API might be down or unreachable.", ephemeral=False)
    except Exception as e:
        print(f"An unexpected error occurred in /currencyconvert: {e}\n{traceback.format_exc()}")
        await interaction.followup.send("An unexpected error occurred during currency conversion.", ephemeral=False)

# --- New Command: /imagegenerate ---
@bot.tree.command(name="imagegenerate", description="Generate an image based on a text prompt.")
@app_commands.describe(prompt="The text description for the image to generate.")
async def imagegenerate(interaction: discord.Interaction, prompt: str):
    if await is_bot_banned(interaction): return

    await interaction.response.defer(ephemeral=False)

    if not IMAGE_GEN_API_KEY or IMAGE_GEN_API_KEY == "YOUR_IMAGE_GEN_API_KEY" or not IMAGE_GEN_API_URL.startswith("http"):
        return await interaction.followup.send("Image generation API is not configured. Please contact the bot owner.", ephemeral=True)

    try:
        # Placeholder for actual image generation API call
        # This assumes an API that returns a direct image URL or base64 data
        headers = {"Authorization": f"Bearer {IMAGE_GEN_API_KEY}", "Content-Type": "application/json"}
        payload = {"prompt": prompt, "size": "512x512"} # Example payload

        async with aiohttp.ClientSession() as session:
            async with session.post(IMAGE_GEN_API_URL, json=payload, headers=headers) as response:
                response.raise_for_status()
                data = await response.json()
                
                # Assuming the API returns a direct image URL
                image_url = data.get('url') or data.get('data', [{}])[0].get('url') # Common formats

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
                    await interaction.followup.send("Could not generate image. The API response was unexpected.", ephemeral=False)

    except aiohttp.ClientError as e:
        print(f"Image generation API request failed: {e}\n{traceback.format_exc()}")
        await interaction.followup.send("Failed to generate image. The AI service might be down or unreachable.", ephemeral=False)
    except Exception as e:
        print(f"An unexpected error occurred in /imagegenerate: {e}\n{traceback.format_exc()}")
        await interaction.followup.send("An unexpected error occurred during image generation.", ephemeral=False)

# --- New Command: /socials ---
@bot.tree.command(name="socials", description="Add your social media links to your profile.")
@app_commands.describe(platform="The social media platform (e.g., Twitter, Instagram).", link="Your profile link on that platform.")
async def socials(interaction: discord.Interaction, platform: str, link: str):
    if await is_bot_banned(interaction): return

    user_id = interaction.user.id
    if user_id not in user_social_links:
        user_social_links[user_id] = {}
    
    # Store platform in lowercase for consistency
    user_social_links[user_id][platform.lower()] = link
    
    await interaction.response.send_message(f"Your **{platform}** link has been saved!", ephemeral=True)

# --- New Command: /getsocials ---
@bot.tree.command(name="getsocials", description="View a user's linked social media.")
@app_commands.describe(user="The user whose social links you want to view.")
async def getsocials(interaction: discord.Interaction, user: discord.Member):
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
    if user.id == bot.user.id:
        return await interaction.response.send_message("I cannot ban myself from using commands.", ephemeral=True)
    if user.id == interaction.user.id:
        return await interaction.response.send_message("You cannot ban yourself from using commands.", ephemeral=True)
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
    if user.id not in bot_banned_users:
        return await interaction.response.send_message(f"**{user.display_name}** is not currently banned from using bot commands.", ephemeral=True)

    bot_banned_users.remove(user.id)
    await interaction.response.send_message(f"**{user.display_name}** has been unbanned from using bot commands.", ephemeral=False)
    try:
        await user.send(f"You have been unbanned from using commands in **{interaction.guild.name}** by **{interaction.user.display_name}**.")
    except discord.Forbidden:
        print(f"Could not DM {user.display_name} about bot unban.")


# --- Social Profile Placeholders (Requires external APIs, many are difficult to access) ---

async def fetch_social_profile(platform: str, username: str, interaction: discord.Interaction):
    """Placeholder for fetching social media profiles."""
    await interaction.response.defer(ephemeral=False)
    
    # In a real bot, you'd integrate with APIs like:
    # - Instagram: Very difficult for public bots due to strict API access.
    # - Twitter: Requires Developer Account and API keys, subject to rate limits.
    # - Roblox: Has public APIs for user info.
    # - Fortnite: Has various third-party APIs for stats.

    embed = discord.Embed(
        title=f"{platform.capitalize()} Profile: {username}",
        description="This command requires integration with external APIs.\n"
                    "Many social media platforms have strict API access rules (e.g., Instagram, Twitter).\n"
                    "For gaming platforms like Roblox/Fortnite, you might find third-party APIs.",
        color=discord.Color.orange(),
        timestamp=interaction.created_at
    )
    embed.add_field(name="Status", value="API Integration Pending", inline=False)
    embed.set_footer(text="Contact the bot owner to set up API keys.")

    await interaction.followup.send(embed=embed, ephemeral=False)

@bot.tree.command(name="instagram", description="Shows an Instagram profile/stats (API integration needed).")
@app_commands.describe(username="The Instagram username.")
async def instagram(interaction: discord.Interaction, username: str):
    if await is_bot_banned(interaction): return
    await fetch_social_profile("Instagram", username, interaction)

@bot.tree.command(name="twitter", description="Shows a Twitter profile/stats (API integration needed).")
@app_commands.describe(username="The Twitter username.")
async def twitter(interaction: discord.Interaction, username: str):
    if await is_bot_banned(interaction): return
    await fetch_social_profile("Twitter", username, interaction)

@bot.tree.command(name="roblox", description="Shows a Roblox profile/stats (API integration needed).")
@app_commands.describe(username="The Roblox username.")
async def roblox(interaction: discord.Interaction, username: str):
    if await is_bot_banned(interaction): return
    await fetch_social_profile("Roblox", username, interaction)

@bot.tree.command(name="fortnite", description="Shows Fortnite stats (API integration needed).")
@app_commands.describe(username="The Fortnite username.")
async def fortnite(interaction: discord.Interaction, username: str):
    if await is_bot_banned(interaction): return
    await fetch_social_profile("Fortnite", username, interaction)


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
    if DISCORD_BOT_TOKEN is None or DISCORD_BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
        print("ERROR: DISCORD_TOKEN environment variable not set or is default. Please replace 'YOUR_BOT_TOKEN_HERE' with your actual Discord bot token.")
        print("For local development, create a .env file in the same directory as bot.py with: DISCORD_TOKEN='YOUR_ACTUAL_TOKEN_HERE'")
    else:
        bot.run(DISCORD_BOT_TOKEN)
