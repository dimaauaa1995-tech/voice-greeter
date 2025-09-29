import os, asyncio, threading, http.server, socketserver, discord
from discord.ext import commands
from discord import FFmpegPCMAudio

# ---- Keepalive HTTP server (для Render) ----
def run_keepalive():
    port = int(os.getenv("PORT", "10000"))
    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format, *args):  # тиша в логах
            pass
    with socketserver.TCPServer(("", port), Handler) as httpd:
        httpd.serve_forever()

threading.Thread(target=run_keepalive, daemon=True).start()
# --------------------------------------------

TOKEN = os.getenv("DISCORD_TOKEN")          # додамо на Render
WELCOME_FILE = os.getenv("WELCOME_FILE", "greeting.mp3")
CHANNEL_WHITELIST = os.getenv("CHANNEL_WHITELIST")  # опційно: ID voice-каналів через кому

intents = discord.Intents.default()
intents.guilds = True
intents.voice_states = True
bot = commands.Bot(command_prefix="!", intents=intents)

recent_greeted = {}

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")

def should_greet(member, channel_id):
    if member.bot:
        return False
    key = (member.id, channel_id)
    now = asyncio.get_event_loop().time()
    last = recent_greeted.get(key)
    if last and now - last < 10:
        return False
    recent_greeted[key] = now
    return True

@bot.event
async def on_voice_state_update(member, before, after):
    if before.channel is None and after.channel is not None:
        channel = after.channel
        if CHANNEL_WHITELIST:
            allowed = {int(x.strip()) for x in CHANNEL_WHITELIST.split(",") if x.strip().isdigit()}
            if channel.id not in allowed:
                return
        if not should_greet(member, channel.id):
            return
        try:
            vc = discord.utils.get(bot.voice_clients, guild=member.guild)
            if vc and vc.is_connected():
                await vc.move_to(channel)
            else:
                vc = await channel.connect()

            vc.play(FFmpegPCMAudio(WELCOME_FILE))
            while vc.is_playing():
                await asyncio.sleep(0.2)
            await asyncio.sleep(0.3)
            await vc.disconnect()
        except Exception as e:
            print("⚠️ Error playing greeting:", e)

bot.run(TOKEN)
