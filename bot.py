import os, asyncio, discord
from discord.ext import commands
from discord import FFmpegPCMAudio

TOKEN = os.getenv("DISCORD_TOKEN")  # вставимо в хостингу як змінну середовища
WELCOME_FILE = os.getenv("WELCOME_FILE", "greeting.mp3")
CHANNEL_WHITELIST = os.getenv("CHANNEL_WHITELIST")  # необов'язково: список ID каналів через кому

intents = discord.Intents.default()
intents.guilds = True
intents.voice_states = True
bot = commands.Bot(command_prefix="!", intents=intents)

recent_greeted = {}  # антиспам

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")

def should_greet(member, channel_id):
    if member.bot:
        return False
    key = (member.id, channel_id)
    now = asyncio.get_event_loop().time()
    last = recent_greeted.get(key)
    if last and now - last < 10:  # не частіше ніж раз на 10 сек для однієї пари користувач-канал
        return False
    recent_greeted[key] = now
    return True

@bot.event
async def on_voice_state_update(member, before, after):
    # реагуємо лише коли користувач ЗАЙШОВ у voice
    if before.channel is None and after.channel is not None:
        channel = after.channel
        if CHANNEL_WHITELIST:
            allowed = {int(x.strip()) for x in CHANNEL_WHITELIST.split(",") if x.strip().isdigit()}
            if channel.id not in allowed:
                return
        if not should_greet(member, channel.id):
            return
        try:
            # підключаємось або пересуваємось у потрібний канал
            vc = discord.utils.get(bot.voice_clients, guild=member.guild)
            if vc and vc.is_connected():
                await vc.move_to(channel)
            else:
                vc = await channel.connect()

            # граємо файл
            source = FFmpegPCMAudio(WELCOME_FILE)
            vc.play(source)

            # чекаємо завершення
            while vc.is_playing():
                await asyncio.sleep(0.2)
            await asyncio.sleep(0.3)
            await vc.disconnect()
        except Exception as e:
            print("⚠️ Error playing greeting:", e)

bot.run(TOKEN)
