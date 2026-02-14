import discord
import os
from discord.ext import commands, tasks
from dotenv import load_dotenv
import logging
import logging.handlers
from datetime import datetime, time
import asyncio

logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
logging.getLogger('discord.http').setLevel(logging.INFO)

handler = logging.handlers.RotatingFileHandler(
    filename='discord.log',
    encoding='utf-8',
    maxBytes=32 * 1024 * 1024,
    backupCount=5,
)

dt_fmt = '%Y-%m-%d %H:%M:%S'
formatter = logging.Formatter(
    '[{asctime}] [{levelname:<8}] {name}: {message}',
    dt_fmt,
    style='{'
)
handler.setFormatter(formatter)
logger.addHandler(handler)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

load_dotenv()

class AugumentixBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None,
            owner_ids={744729824400244758, 708231383688019999},
        )
        self.db = None

    async def on_ready(self):
        logger.info(f'Logged in as {self.user} (ID: {self.user.id})')
        print(f'Bot is ready! Logged in as {self.user}')
        print(f'Connected to {len(self.guilds)} guild(s)')

        if not submission_checker.is_running():
            submission_checker.start()
        if not weekly_reset.is_running():
            weekly_reset.start()
        if not ai_news_reminder.is_running():
            ai_news_reminder.start()

    async def load_cogs(self) -> None:
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py') and not filename.startswith('_'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    logger.info(f'Loaded cog: {filename[:-3]}')
                    print(f'Loaded cog: {filename[:-3]}')
                except Exception as e:
                    logger.error(f'Failed to load cog {filename}: {e}')
                    print(f'Failed to load cog: {filename[:-3]}')

        try:
            await self.load_extension('jishaku')
            logger.info('Loaded jishaku')
            print('Loaded cog: jishaku')
        except:
            logger.warning('Jishaku not available')
            print('Jishaku not available')

    async def setup_hook(self) -> None:
        from utils.database import Database
        self.db = Database()
        await self.db.init_db()
        logger.info('Database initialized')
        print('Database initialized')

        await self.load_cogs()

        try:
            synced = await self.tree.sync()
            logger.info(f'Synced {len(synced)} command(s)')
            print(f'Synced {len(synced)} slash command(s)')
        except Exception as e:
            logger.error(f'Failed to sync commands: {e}')
            print(f'Failed to sync commands: {e}')

@tasks.loop(hours=1)
async def submission_checker():
    try:
        logger.info('Running submission checker...')
        from utils.leetcode_api import LeetCodeAPI

        users = await bot.db.get_all_users()
        leetcode_api = LeetCodeAPI()

        for user_id, leetcode_username in users:
            try:
                await leetcode_api.update_user(bot, user_id, leetcode_username)
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f'Error updating {leetcode_username}: {e}')

        logger.info('Submission checker completed')
    except Exception as e:
        logger.error(f'Error in submission_checker: {e}')

@submission_checker.before_loop
async def before_submission_checker():
    await bot.wait_until_ready()

@tasks.loop(time=time(hour=0, minute=0))
async def weekly_reset():
    try:
        if datetime.now().weekday() == 0:
            logger.info('Running weekly reset...')
            await bot.db.reset_weekly_stats()

            from utils.role_manager import RoleManager
            role_manager = RoleManager(bot.db)

            for guild in bot.guilds:
                users = await bot.db.get_all_users()
                for user_id, _ in users:
                    member = guild.get_member(user_id)
                    if member:
                        await role_manager.update_user_role(member, guild)

            logger.info('Weekly reset completed')
    except Exception as e:
        logger.error(f'Error in weekly_reset: {e}')

@weekly_reset.before_loop
async def before_weekly_reset():
    await bot.wait_until_ready()

@tasks.loop(time=time(hour=10, minute=0))
async def ai_news_reminder():
    try:
        if datetime.now().weekday() == 2:
            logger.info('Running AI news reminder...')

            channel_id = int(os.getenv('AI_NEWS_CHANNEL_ID', 0))
            if not channel_id:
                logger.warning('AI_NEWS_CHANNEL_ID not set')
                return

            channel = bot.get_channel(channel_id)
            if not channel:
                logger.warning(f'Channel {channel_id} not found')
                return

            from utils.ai_news_picker import AINewsPicker
            picker = AINewsPicker(bot.db)
            should_send = await picker.should_send_reminder()

            if should_send:
                member = await picker.pick_random_member(channel.guild, channel)

                if member:
                    embed = discord.Embed(
                        title="📰 Weekly AI News Time!",
                        description=f"{member.mention}, you've been selected to share this week's AI news!\n\n"
                                    f"Please share the most interesting AI developments from this week. "
                                    f"The news will be posted on social media Thursday.",
                        color=discord.Color.blue()
                    )
                    embed.set_footer(text="Reply in this channel to mark as complete")

                    await channel.send(embed=embed)
                    await picker.set_current_assignee(member.id)
                    logger.info(f'Sent AI news reminder to {member.name}')

    except Exception as e:
        logger.error(f'Error in ai_news_reminder: {e}')

@ai_news_reminder.before_loop
async def before_ai_news_reminder():
    await bot.wait_until_ready()

bot = AugumentixBot()

if __name__ == '__main__':
    bot.run(os.getenv('TOKEN'), log_handler=None)
