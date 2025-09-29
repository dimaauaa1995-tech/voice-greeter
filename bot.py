import os
import asyncio
import threading
import http.server
import socketserver
import discord
from discord.ext import commands
from discord import FFmpegOpusAudio

# =========================
# Keepalive HTTP server (для безкоштовного Render)
# =========================
def run_keepalive():
    port = int(os.getenv("PORT", "10000"))
    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format, *args):
            # глушимо спам у логах
            pass
    with socketserver.TCPServer(("", port), Handler) as httpd:
        httpd.serve_forever()

threading.Thread(target=run_keepalive, daemon=True).start()

# =========================
# Налаштування з перемінних середовища
# =========================
TOKEN = os.getenv("DISCORD_TOKEN")                     # обов'язково
WELCOME_FILE = os.getenv("WELCOME_FILE", "greeting.mp3")
CHANNEL_WHITELIST = os.getenv("CHANNEL_WHITELIST")     # опційно: "123,456"

# =========================
# Discord client
# =========================
intents = discord.Intents.default()
intents.guilds = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)
recent_greeted: dict[tuple[int, int], float] = {}  # (user_id, channel_id) -> last_ts

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")

def should_greet(member: discord.Member, channel_id: int) -> bool:
    """Антиспам: не частіше ніж раз на 10с для пари користувач-канал, і не реагуємо на ботів."""
    if member.bot:
        return False
    key = (member.id, channel_id)
    now = asyncio.get_event_loop().time()
    last = recent_greeted.get(key)
    if last and now - last < 10:
        return False
    recent_greeted[key] = now
    return True

async def connect_or_move(guild: discord.Guild, channel: discord.VoiceChannel):
    """Підключитись або переміститись у потрібний канал з 3 спробами."""
    attempts = 3
    last_exc = None
    for i in range(1, attempts + 1):
        try:
            vc = discord.utils.get(bot.voice_clients, guild=guild)
            if vc and vc.is_connected():
                if vc.channel and vc.channel.id == channel.id:
                    return vc
                await vc.move_to(channel)
                return vc
            else:
                vc = await channel.connect(self_deaf=True)
                return vc
        except Exception as e:
            last_exc = e
            await asyncio.sleep(1.0 * i)  # невеликий бекоф
    raise last_exc if last_exc else RuntimeError("Unknown connect error")

@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    # Реагуємо тільки коли користувач ЗАЙШОВ у voice
    if before.channel is None and after.channel is not None:
        channel = after.channel

        # Якщо заданий whitelist каналів — ігноруємо інші
        if CHANNEL_WHITELIST:
            allowed = {int(x.strip()) for x in CHANNEL_WHITELIST.split(",") if x.strip().isdigit()}
            if channel.id not in allowed:
                return

        if not should_greet(member, channel.id):
            return

        try:
            # 1) Підключення / переміщення
            vc = await connect_or_move(member.guild, channel)

            # 2) Невелика пауза — допомагає на безкоштовних хостингах
            await asyncio.sleep(0.5)

            # 3) Граємо файл (через Opus — стабільніше)
            if not os.path.exists(WELCOME_FILE):
                print(f"⚠️ File not found: {WELCOME_FILE}")
                await asyncio.sleep(0.3)
                await vc.disconnect()
                return

            source = FFmpegOpusAudio(WELCOME_FILE, bitrate=128)
            vc.play(source)

            # 4) Чекаємо закінчення відтворення
            while vc.is_playing():
                await asyncio.sleep(0.2)

            # 5) Трошки зачекати і вийти
            await asyncio.sleep(0.3)
            await vc.disconnect()

        except Exception as e:
            print("❌ Error in voice greeting:", e)
            # Спробувати прибрати зависле з'єднання
            try:
                vc = discord.utils.get(bot.voice_clients, guild=member.guild)
                if vc and vc.is_connected():
                    await vc.disconnect()
            except Exception:
                pass

# Запуск
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is not set")
bot.run(TOKEN)
