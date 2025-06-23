import threading
from flask import Flask
from waitress import serve

app = Flask(__name__)

@app.route('/')
def home():
    return "Grindelwald bot active."

def run_web():
    serve(app, host='0.0.0.0', port=8080)

threading.Thread(target=run_web).start()


import discord
from discord.ext import commands
from discord import app_commands
import os
import asyncio
from datetime import datetime, timedelta

TOKEN = os.getenv("DISCORD_TOKEN")

GUILD_ID = 1384588296222412851
FAMILY_ROLE_ID = 1324378367176212593
ALLY_ROLE_ID = 1328274975735549953
VERIFY_CHANNEL_ID = 1384588296222412851
LOG_CHANNEL_ID = 1386258700670472232
PANTEON_ROLE_ID = 1386249039473017022

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

user_data = {}  # user_id: {'os': 0, 'rank': 1}
contract_status = {}  # contract_name: {'cooldown_until': datetime, 'last_executor': user_id}

available_contracts = [
    "📦 Дары моря",
    "💣 Металлургия"
]

pending_confirmations = {}  # message_id: {'executor': id, 'helper': id, 'contract': str}

@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
        print("✅ Команды синхронизированы глобально")
    except Exception as e:
        print("❌ Ошибка синхронизации:", e)
    print(f"🤖 Бот запущен как {bot.user}")

@bot.tree.command(name="верификация", description="Пройти проверку и вступить в семью")
@app_commands.checks.has_permissions(send_messages=True)
async def verify(interaction: discord.Interaction):
    if interaction.channel.id != VERIFY_CHANNEL_ID:
        await interaction.response.send_message("❌ Команда доступна только в специальном канале.", ephemeral=True)
        return
    await interaction.response.send_message("📩 Проверь свои личные сообщения.", ephemeral=True)

    try:
        await interaction.user.send("❔ *Кодовое слово семьи, которое тебе назвали при инвайте?*")

        def check(m):
            return m.author == interaction.user and isinstance(m.channel, discord.DMChannel)

        msg = await bot.wait_for("message", check=check, timeout=120)

        guild = interaction.guild
        member = guild.get_member(interaction.user.id)
        if not member:
            return

        if msg.content.strip().lower() == "высшее благо":
            await member.add_roles(guild.get_role(FAMILY_ROLE_ID))
            await member.send("✅ Проверка пройдена. Добро пожаловать в семью.")
        else:
            await member.add_roles(guild.get_role(ALLY_ROLE_ID))
            await member.send("⚠️ Ответ неверен. Ты получаешь роль союзника.")
    except Exception as e:
        await interaction.user.send("❌ Ошибка при верификации.")
        print(e)

@bot.tree.command(name="взять_контракт", description="Выбрать контракт из списка")
@app_commands.describe(название="Контракт для выполнения")
async def взять_контракт(interaction: discord.Interaction, название: str):
    cooldown = contract_status.get(название, {}).get("cooldown_until")
    now = datetime.utcnow()

    if cooldown and now < cooldown:
        left = cooldown - now
        mins = int(left.total_seconds() // 60)
        await interaction.response.send_message(f"❌ Контракт '{название}' на кулдауне. Подожди {mins} мин.", ephemeral=True)
        return

    contract_status[название] = {"cooldown_until": None, "last_executor": None}
    await interaction.response.send_message(f"📝 Контракт **{название}** закреплён за тобой. Не забудь сдать его после выполнения.")

    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(f"📌 {interaction.user.mention} взял контракт: **{название}**")

@взять_контракт.autocomplete("название")
async def контракт_autocomplete(interaction: discord.Interaction, current: str):
    now = datetime.utcnow()
    return [
        app_commands.Choice(name=c, value=c)
        for c in available_contracts
        if c.lower().startswith(current.lower())
        and (c not in contract_status or not contract_status[c].get("cooldown_until") or contract_status[c]["cooldown_until"] < now)
    ]

@bot.tree.command(name="сдать_контракт", description="Заполнить форму сдачи контракта")
@app_commands.describe(контракт="Контракт", помощник1="Кто помогал (1)", помощник2="Кто помогал (2)", помощник3="Кто помогал (3)")
async def сдать_контракт(interaction: discord.Interaction, контракт: str, помощник1: discord.Member = None, помощник2: discord.Member = None, помощник3: discord.Member = None):
    await interaction.response.send_message("📨 Заявка отправлена на рассмотрение Пантеона.", ephemeral=True)

    embed = discord.Embed(title="📜 Заявка на подтверждение контракта", color=0x888888)
    embed.add_field(name="Контракт", value=контракт, inline=False)
    embed.add_field(name="Исполнитель", value=interaction.user.mention, inline=False)

    helpers = [помощник1, помощник2, помощник3]
    helper_mentions = [m.mention for m in helpers if m]
    helper_ids = [m.id for m in helpers if m]

    embed.add_field(name="Помощники", value="
".join(helper_mentions) if helper_mentions else "—", inline=False)
    embed.set_footer(text="Ожидает подтверждения Пантеоном")

    view = ConfirmView(interaction.user.id, helper_ids, контракт)
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        msg = await log_channel.send(content=f"<@&{PANTEON_ROLE_ID}> требуется подтверждение контракта!", embed=embed, view=view)
        pending_confirmations[msg.id] = {
            "executor": interaction.user.id,
            "helpers": helper_ids,
            "contract": контракт
        }

class ConfirmView(discord.ui.View):
    def __init__(self, executor_id, helper_ids, contract_name):
        super().__init__(timeout=None)
        self.executor_id = executor_id
        self.helper_ids = helper_ids
        self.contract_name = contract_name

    @discord.ui.button(label="✅ Подтвердить", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        info = pending_confirmations.pop(interaction.message.id, None)
        if not info:
            await interaction.response.send_message("❌ Данные не найдены.", ephemeral=True)
            return

        now = datetime.utcnow()
        contract_status[info["contract"]] = {
            "cooldown_until": now + timedelta(hours=24),
            "last_executor": info["executor"]
        }

        user_data.setdefault(info["executor"], {'os': 0, 'rank': 1})
        user_data[info["executor"]]['os'] += 15

        for helper_id in info["helpers"]:
            user_data.setdefault(helper_id, {'os': 0, 'rank': 1})
            user_data[helper_id]['os'] += 10
            user_data.setdefault(info["helpers"], {'os': 0, 'rank': 1})
            user_data[info["helpers"]]['os'] += 10

        await interaction.response.send_message("✅ Контракт подтверждён. ОС начислены.")
        await interaction.message.edit(content="Контракт подтверждён Пантеоном.", view=None)

        # Проверка на повышение
        executor = bot.get_user(info["executor"])
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if user_data[info["executor"]]['os'] >= user_data[info["executor"]]['rank'] * 100:
            await log_channel.send(
                f"🧬 {executor.mention} достиг лимита для повышения (Ранг {rank_now} → {rank_next}).\n"
    f"<@&{PANTEON_ROLE_ID}>, подтвердите вручную повышение."
            )

    @discord.ui.button(label="❌ Отклонить", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        pending_confirmations.pop(interaction.message.id, None)
        await interaction.message.edit(content="🚫 Контракт отклонён Пантеоном.", view=None)
        await interaction.response.send_message("Отклонено.")


@bot.event
async def on_member_join(member):
    channel = bot.get_channel(1324369135466975287)
    if not channel:
        return

    import random
    phrases = [
        "Мир меняется. Прислушайся к тишине.",
        "Сила не просит позволения. Она просто берёт.",
        "Они боятся правды. А ты?",
        "Выбор сделан. Назад пути нет.",
        "Те, кто видят дальше, идут первыми.",
        "Не задавай вопросов — знай своё место.",
        "Молчи. Наблюдай. Воздействуй.",
        "Вера — оружие сильных.",
        "Тот, кто жаждет порядка, должен быть готов к хаосу.",
        "Ты вступил туда, где служат без слов."
    ]
    phrase = random.choice(phrases)
    embed = discord.Embed(
        description=f"{member.mention}\n**{phrase}**",
        color=discord.Color.dark_gray()
    )
    embed.set_image(url="attachment://welcome.gif")
    await channel.send(file=discord.File("welcome.gif", filename="welcome.gif"), embed=embed)


bot.run(TOKEN)
