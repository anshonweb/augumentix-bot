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
formatter = logging.Formatter('[{asctime}] [{levelname:<8}] {name}: {message}', dt_fmt, style='{')
handler.setFormatter(formatter)
logger.addHandler(handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
console_handler.setLevel(logging.DEBUG)
logger.addHandler(console_handler)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

load_dotenv()

class LeetCodeBot(commands.Bot):
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
            logger.info('[TASK] submission_checker started')
        if not weekly_reset.is_running():
            weekly_reset.start()
            logger.info('[TASK] weekly_reset started')
        if not ai_news_reminder.is_running():
            ai_news_reminder.start()
            logger.info('[TASK] ai_news_reminder started')
        if not post_daily_leetcode_question.is_running():
            post_daily_leetcode_question.start()
            logger.info('[TASK] post_daily_leetcode_question started')
        if not post_daily_leetcode_solution.is_running():
            post_daily_leetcode_solution.start()
            logger.info('[TASK] post_daily_leetcode_solution started')

        if not task_heartbeat.is_running():
            task_heartbeat.start()
            logger.info('[TASK] task_heartbeat started')
    
    async def load_cogs(self) -> None:
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py') and not filename.startswith('_'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    logger.info(f'Loaded cog: {filename[:-3]}')
                except Exception as e:
                    logger.error(f'Failed to load cog {filename}: {e}')
        
        try:
            await self.load_extension('jishaku')
            logger.info('Loaded jishaku')
        except:
            logger.warning('Jishaku not available')
    
    async def setup_hook(self) -> None:
        from utils.database import Database
        self.db = Database()
        await self.db.init_db()
        logger.info('Database initialized')
        
        await self.load_cogs()
        
        try:
            synced = await self.tree.sync()
            logger.info(f'Synced {len(synced)} command(s)')
        except Exception as e:
            logger.error(f'Failed to sync commands: {e}')


_task_last_run: dict[str, datetime] = {}
_task_error_counts: dict[str, int] = {}

def _task_status(task: tasks.Loop, name: str) -> str:
    running   = task.is_running()
    failed    = task.failed()
    count     = task.current_loop
    next_iter = task.next_iteration
    last_run  = _task_last_run.get(name, None)
    errors    = _task_error_counts.get(name, 0)

    next_str = next_iter.strftime('%H:%M:%S') if next_iter else 'N/A'
    last_str = last_run.strftime('%H:%M:%S')  if last_run  else 'never'

    status = 'RUNNING' if running else ('FAILED' if failed else 'STOPPED')
    return (
        f"{name:<35} | {status:<12} | loops={count:<5} | "
        f"last_ran={last_str} | next={next_str} | errors={errors}"
    )

@tasks.loop(seconds=10)
async def task_heartbeat():
    logger.debug('─' * 90)
    logger.debug('[HEARTBEAT] Background task status report')
    logger.debug(_task_status(submission_checker,            'submission_checker'))
    logger.debug(_task_status(weekly_reset,                  'weekly_reset'))
    logger.debug(_task_status(ai_news_reminder,              'ai_news_reminder'))
    logger.debug(_task_status(post_daily_leetcode_question,  'post_daily_leetcode_question'))
    logger.debug(_task_status(post_daily_leetcode_solution,  'post_daily_leetcode_solution'))
    logger.debug('─' * 90)

@task_heartbeat.before_loop
async def before_task_heartbeat():
    while True:
        try:
            if bot.is_ready():
                return
            await asyncio.sleep(1)
        except RuntimeError:
            await asyncio.sleep(1)


@tasks.loop(hours=1)
async def submission_checker():
    _task_name = 'submission_checker'
    logger.info(f'[TASK:{_task_name}] Starting iteration #{submission_checker.current_loop}')
    try:
        from utils.leetcode_api import LeetCodeAPI
        
        users = await bot.db.get_all_users()
        logger.debug(f'[TASK:{_task_name}] Found {len(users)} user(s) to check')
        leetcode_api = LeetCodeAPI()
        
        for idx, (user_id, leetcode_username) in enumerate(users, 1):
            try:
                logger.debug(f'[TASK:{_task_name}] Checking ({idx}/{len(users)}): {leetcode_username}')
                await leetcode_api.update_user(bot, user_id, leetcode_username)
                await asyncio.sleep(2)
            except Exception as e:
                _task_error_counts[_task_name] = _task_error_counts.get(_task_name, 0) + 1
                logger.error(f'[TASK:{_task_name}] Error updating {leetcode_username}: {e}')
        
        _task_last_run[_task_name] = datetime.now()
        logger.info(f'[TASK:{_task_name}] Iteration #{submission_checker.current_loop} complete')
    except Exception as e:
        _task_error_counts[_task_name] = _task_error_counts.get(_task_name, 0) + 1
        logger.error(f'[TASK:{_task_name}] Fatal error in iteration #{submission_checker.current_loop}: {e}')

@submission_checker.before_loop
async def before_submission_checker():
    while True:
        try:
            if bot.is_ready():
                logger.debug('[TASK:submission_checker] Bot ready — loop starting')
                return
            await asyncio.sleep(1)
        except RuntimeError:
            await asyncio.sleep(1)

@submission_checker.error
async def submission_checker_error(error):
    _task_error_counts['submission_checker'] = _task_error_counts.get('submission_checker', 0) + 1
    logger.error(f'[TASK:submission_checker] Unhandled loop error: {error}', exc_info=error)


@tasks.loop(time=time(hour=0, minute=0))
async def weekly_reset():
    _task_name = 'weekly_reset'
    logger.info(f'[TASK:{_task_name}] Starting iteration #{weekly_reset.current_loop}')
    try:
        if datetime.now().weekday() == 0:
            logger.info(f'[TASK:{_task_name}] It\'s Monday — running reset...')
            await bot.db.reset_weekly_stats()
            
            from utils.role_manager import RoleManager
            role_manager = RoleManager(bot.db)
            
            for guild in bot.guilds:
                users = await bot.db.get_all_users()
                logger.debug(f'[TASK:{_task_name}] Updating roles for {len(users)} user(s) in guild {guild.name}')
                for user_id, _ in users:
                    member = guild.get_member(user_id)
                    if member:
                        await role_manager.update_user_role(member, guild)
            
            _task_last_run[_task_name] = datetime.now()
            logger.info(f'[TASK:{_task_name}] Weekly reset complete')
        else:
            logger.debug(f'[TASK:{_task_name}] Not Monday (weekday={datetime.now().weekday()}) — skipping')
            _task_last_run[_task_name] = datetime.now()
    except Exception as e:
        _task_error_counts[_task_name] = _task_error_counts.get(_task_name, 0) + 1
        logger.error(f'[TASK:{_task_name}] Error: {e}')

@weekly_reset.before_loop
async def before_weekly_reset():
    while True:
        try:
            if bot.is_ready():
                logger.debug('[TASK:weekly_reset] Bot ready — loop starting')
                return
            await asyncio.sleep(1)
        except RuntimeError:
            await asyncio.sleep(1)

@weekly_reset.error
async def weekly_reset_error(error):
    _task_error_counts['weekly_reset'] = _task_error_counts.get('weekly_reset', 0) + 1
    logger.error(f'[TASK:weekly_reset] Unhandled loop error: {error}', exc_info=error)


@tasks.loop(time=time(hour=5, minute=0)) 
async def ai_news_reminder():
    _task_name = 'ai_news_reminder'
    logger.info(f'[TASK:{_task_name}] Starting iteration #{ai_news_reminder.current_loop}')
    try:
        if datetime.now().weekday() == 2:  
            logger.info(f'[TASK:{_task_name}] It\'s Wednesday — checking if reminder needed...')
            
            channel_id = int(os.getenv('AI_NEWS_CHANNEL_ID', 0))
            if not channel_id:
                logger.warning(f'[TASK:{_task_name}] AI_NEWS_CHANNEL_ID not set')
                return
            
            channel = bot.get_channel(channel_id)
            if not channel:
                logger.warning(f'[TASK:{_task_name}] Channel {channel_id} not found')
                return
            
            from utils.ai_news_picker import AINewsPicker
            picker = AINewsPicker(bot.db)
            
            should_send = await picker.should_send_reminder()
            logger.debug(f'[TASK:{_task_name}] should_send_reminder={should_send}')
            
            if should_send:
                member = await picker.pick_random_member(channel.guild, channel)
                
                if member:
                    logger.info(f'[TASK:{_task_name}] Selected member: {member.name} ({member.id})')
                    embed = discord.Embed(
                        title="Weekly AI News Time!",
                        description=f"{member.mention}, you've been selected to share this week's top AI news!\n\n"
                                    f"Please share the most interesting AI developments from this week. "
                                    f"The news will be posted on social media Thursday.",
                        color=discord.Color.blue()
                    )
                    embed.set_footer(text="Reply in this channel to mark as complete")
                    
                    await channel.send(member.mention)
                    message = await channel.send(embed=embed)
                    await picker.set_current_assignee(member.id)
                    logger.info(f'[TASK:{_task_name}] Reminder sent to {member.name}')
                else:
                    logger.warning(f'[TASK:{_task_name}] No eligible member found to assign')
            else:
                logger.info(f'[TASK:{_task_name}] Reminder not needed this week')
        else:
            logger.debug(f'[TASK:{_task_name}] Not Wednesday (weekday={datetime.now().weekday()}) — skipping')
        
        _task_last_run[_task_name] = datetime.now()
    except Exception as e:
        _task_error_counts[_task_name] = _task_error_counts.get(_task_name, 0) + 1
        logger.error(f'[TASK:{_task_name}] Error: {e}')

@ai_news_reminder.before_loop
async def before_ai_news_reminder():
    while True:
        try:
            if bot.is_ready():
                logger.debug('[TASK:ai_news_reminder] Bot ready — loop starting')
                return
            await asyncio.sleep(1)
        except RuntimeError:
            await asyncio.sleep(1)

@ai_news_reminder.error
async def ai_news_reminder_error(error):
    _task_error_counts['ai_news_reminder'] = _task_error_counts.get('ai_news_reminder', 0) + 1
    logger.error(f'[TASK:ai_news_reminder] Unhandled loop error: {error}', exc_info=error)


@tasks.loop(time=time(hour=9, minute=0))
async def post_daily_leetcode_question():
    _task_name = 'post_daily_leetcode_question'
    logger.info(f'[TASK:{_task_name}] Starting iteration #{post_daily_leetcode_question.current_loop}')
    try:
        today_challenge = await bot.db.get_todays_challenge()
        if today_challenge:
            logger.info(f'[TASK:{_task_name}] Question already posted today — skipping')
            _task_last_run[_task_name] = datetime.now()
            return
        
        dsa_channel_id = int(os.getenv('DSA_CHANNEL_ID', 0))
        if not dsa_channel_id:
            logger.warning(f'[TASK:{_task_name}] DSA_CHANNEL_ID not set')
            return
        
        channel = bot.get_channel(dsa_channel_id)
        if not channel:
            logger.warning(f'[TASK:{_task_name}] DSA channel {dsa_channel_id} not found')
            return

        import json
        with open('leetcode75_questions.json', 'r') as f:
            questions = json.load(f)
        
        logger.debug(f'[TASK:{_task_name}] Loaded {len(questions)} questions from file')
        
        posted_ids = await bot.db.get_posted_question_ids()
        logger.debug(f'[TASK:{_task_name}] {len(posted_ids)} questions already posted')
        
        next_question = None
        for q in questions:
            if q['id'] not in posted_ids:
                next_question = q
                break
        
        if not next_question:
            logger.warning(f'[TASK:{_task_name}] All questions posted — cycling back to first')
            next_question = questions[0]

        logger.info(f'[TASK:{_task_name}] Posting: #{next_question["id"]} {next_question["title"]} ({next_question["difficulty"]})')

        colors = {
            "Easy": discord.Color.green(),
            "Medium": discord.Color.orange(),
            "Hard": discord.Color.red()
        }
        
        embed = discord.Embed(
            title=f"Problem #{next_question['id']}: {next_question['title']}",
            description=next_question['description'],
            color=colors.get(next_question['difficulty'], discord.Color.blue()),
            url=next_question['leetcode_url']
        )
        embed.add_field(name="Difficulty", value=next_question['difficulty'], inline=True)
        embed.add_field(name="Category", value=next_question['category'], inline=True)
        
        if next_question.get('hints'):
            hints_text = "\n".join([f"{hint}" for hint in next_question['hints']])
            embed.add_field(name="Hints", value=hints_text, inline=False)
        
        embed.add_field(name="Link", value=f"[Solve on LeetCode]({next_question['leetcode_url']})", inline=False)
        embed.set_footer(text=f"Solution will be posted at 6 PM! • {datetime.now().strftime('%B %d, %Y')}")

        message = await channel.send(
            content="@everyone **Daily LeetCode Challenge!**",
            embed=embed
        )
        await bot.db.post_daily_challenge(next_question['id'], message.id)
        
        _task_last_run[_task_name] = datetime.now()
        logger.info(f'[TASK:{_task_name}] Posted question: {next_question["title"]}')
        
    except Exception as e:
        _task_error_counts[_task_name] = _task_error_counts.get(_task_name, 0) + 1
        logger.error(f'[TASK:{_task_name}] Error: {e}')

@post_daily_leetcode_question.before_loop
async def before_post_daily_leetcode_question():
    while True:
        try:
            if bot.is_ready():
                logger.debug('[TASK:post_daily_leetcode_question] Bot ready — loop starting')
                return
            await asyncio.sleep(1)
        except RuntimeError:
            await asyncio.sleep(1)

@post_daily_leetcode_question.error
async def post_daily_leetcode_question_error(error):
    _task_error_counts['post_daily_leetcode_question'] = _task_error_counts.get('post_daily_leetcode_question', 0) + 1
    logger.error(f'[TASK:post_daily_leetcode_question] Unhandled loop error: {error}', exc_info=error)


@tasks.loop(time=time(hour=18, minute=0))
async def post_daily_leetcode_solution():
    _task_name = 'post_daily_leetcode_solution'
    logger.info(f'[TASK:{_task_name}] Starting iteration #{post_daily_leetcode_solution.current_loop}')
    try:
        today_challenge = await bot.db.get_todays_challenge()
        
        if not today_challenge:
            logger.info(f'[TASK:{_task_name}] No question posted today — skipping solution')
            _task_last_run[_task_name] = datetime.now()
            return
        
        if today_challenge['solution_posted']:
            logger.info(f'[TASK:{_task_name}] Solution already posted today — skipping')
            _task_last_run[_task_name] = datetime.now()
            return
        
        dsa_channel_id = int(os.getenv('DSA_CHANNEL_ID', 0))
        if not dsa_channel_id:
            logger.warning(f'[TASK:{_task_name}] DSA_CHANNEL_ID not set')
            return
        
        channel = bot.get_channel(dsa_channel_id)
        if not channel:
            logger.warning(f'[TASK:{_task_name}] DSA channel {dsa_channel_id} not found')
            return

        import json
        with open('leetcode75_questions.json', 'r') as f:
            questions = json.load(f)
        
        question = None
        for q in questions:
            if q['id'] == today_challenge['question_id']:
                question = q
                break
        
        if not question:
            logger.error(f'[TASK:{_task_name}] Question ID {today_challenge["question_id"]} not found in JSON')
            return
        
        logger.info(f'[TASK:{_task_name}] Generating solutions for: {question["title"]}')
        
        from utils.groq_api import GroqAPI
        from cogs.leetcodedaily import LanguageSelectView
        
        groq = GroqAPI()
        solutions = await groq.generate_multi_language_solutions(
            question['title'],
            question['description'],
            question['difficulty'],
            question.get('hints', [])
        )
        logger.debug(f'[TASK:{_task_name}] Solutions generated for languages: {list(solutions.keys())}')
        
        view = LanguageSelectView(question, solutions)
        python_solution = solutions.get('python', {})
        embeds = view.children[0].create_solution_embeds(question, python_solution, 'python')
        message = await channel.send(
            content="**Solution for Today's Challenge** - Select your preferred language below:",
            embeds=embeds,
            view=view
        )
        await bot.db.post_challenge_solution(today_challenge['id'], message.id)
        
        _task_last_run[_task_name] = datetime.now()
        logger.info(f'[TASK:{_task_name}] Posted multi-language solution for: {question["title"]}')
        
    except Exception as e:
        _task_error_counts[_task_name] = _task_error_counts.get(_task_name, 0) + 1
        logger.error(f'[TASK:{_task_name}] Error: {e}')
        import traceback
        traceback.print_exc()

@post_daily_leetcode_solution.before_loop
async def before_post_daily_leetcode_solution():
    while True:
        try:
            if bot.is_ready():
                logger.debug('[TASK:post_daily_leetcode_solution] Bot ready loop starting')
                return
            await asyncio.sleep(1)
        except RuntimeError:
            await asyncio.sleep(1)

@post_daily_leetcode_solution.error
async def post_daily_leetcode_solution_error(error):
    _task_error_counts['post_daily_leetcode_solution'] = _task_error_counts.get('post_daily_leetcode_solution', 0) + 1
    logger.error(f'[TASK:post_daily_leetcode_solution] Unhandled loop error: {error}', exc_info=error)


bot = LeetCodeBot()

if __name__ == '__main__':
    bot.run(os.getenv('TOKEN'), log_handler=None)