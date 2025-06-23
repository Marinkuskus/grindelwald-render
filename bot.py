import discord
from discord.ext import commands
import os

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
        print("✅ Команды синхронизированы глобально")
    except Exception as e:
        print("❌ Ошибка синхронизации:", e)
    print(f"🤖 Бот запущен как {bot.user}")

bot.run(os.getenv("DISCORD_TOKEN"))
