import discord
from discord import app_commands
from discord.ext import commands
import logging
import os
from datetime import datetime
import asyncio

logger = logging.getLogger('discord')

class TestCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="ping", description="Test bot responsiveness")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        
        embed = discord.Embed(
            title="Pong!",
            description=f"Bot is online and responding",
            color=discord.Color.green()
        )
        embed.add_field(name="Latency", value=f"{latency}ms", inline=True)
        embed.add_field(name="Status", value="Operational", inline=True)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="test_db", description="Test database connection")
    async def test_db(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        try:
            if not self.bot.db or not self.bot.db.pool:
                await interaction.followup.send("Database pool not initialized!")
                return
            
            async with self.bot.db.pool.acquire() as conn:
                result = await conn.fetchval('SELECT 1')
            
            async with self.bot.db.pool.acquire() as conn:
                tables = await conn.fetch("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                """)
            
            user_count = len(await self.bot.db.get_all_users())
            
            embed = discord.Embed(
                title="Database Connection Test",
                description="Database is working correctly!",
                color=discord.Color.green()
            )
            embed.add_field(name="Connection", value="Connected", inline=True)
            embed.add_field(name="Tables Found", value=str(len(tables)), inline=True)
            embed.add_field(name="Linked Users", value=str(user_count), inline=True)
            
            table_list = "\n".join([f"- {t['table_name']}" for t in tables])
            embed.add_field(name="Tables", value=table_list or "None", inline=False)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Database test failed: {e}")
            
            embed = discord.Embed(
                title="Database Test Failed",
                description=f"Error: {str(e)}",
                color=discord.Color.red()
            )
            embed.add_field(name="Tip", value="Check DATABASE_URL in .env file", inline=False)
            
            await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="test_leetcode", description="Test LeetCode API")
    @app_commands.describe(username="LeetCode username to test")
    async def test_leetcode(self, interaction: discord.Interaction, username: str):
        await interaction.response.defer()
        
        try:
            from utils.leetcode_api import LeetCodeAPI
            
            leetcode_api = LeetCodeAPI()
            
            user_stats = await leetcode_api.get_user_stats(username)
            
            if not user_stats:
                embed = discord.Embed(
                    title="LeetCode API Test Failed",
                    description=f"Could not find user: `{username}`",
                    color=discord.Color.red()
                )
                embed.add_field(
                    name="Possible Issues",
                    value="- Username doesn't exist\n- LeetCode API is down\n- Network connectivity issue",
                    inline=False
                )
                await interaction.followup.send(embed=embed)
                return
            
            total_solved = leetcode_api.get_total_solved(user_stats)
            
            submissions = await leetcode_api.get_recent_submissions(username, 5)
            
            embed = discord.Embed(
                title="LeetCode API Test Passed",
                description=f"Successfully fetched data for: **{username}**",
                color=discord.Color.green()
            )
            
            embed.add_field(name="Username", value=username, inline=True)
            embed.add_field(name="Total Solved", value=str(total_solved), inline=True)
            embed.add_field(name="Recent Submissions", value=str(len(submissions)), inline=True)
            
            if submissions:
                recent = "\n".join([f"- {s['title']}" for s in submissions[:3]])
                embed.add_field(name="Last 3 Problems", value=recent, inline=False)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"LeetCode API test failed: {e}")
            
            embed = discord.Embed(
                title="LeetCode API Error",
                description=f"Error: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="test_roles", description="Check bot role permissions")
    async def test_roles(self, interaction: discord.Interaction):
        try:
            guild = interaction.guild
            bot_member = guild.get_member(self.bot.user.id)
            
            can_manage_roles = bot_member.guild_permissions.manage_roles
            
            gold_role = discord.utils.get(guild.roles, name="Gold")
            silver_role = discord.utils.get(guild.roles, name="Silver")
            bronze_role = discord.utils.get(guild.roles, name="Bronze")
            
            embed = discord.Embed(
                title="Role Permission Test",
                color=discord.Color.blue()
            )
            
            perm_status = "[YES]" if can_manage_roles else "[NO]"
            embed.add_field(
                name="Manage Roles Permission",
                value=f"{perm_status} {'Granted' if can_manage_roles else 'Missing'}",
                inline=False
            )
            
            roles_status = []
            for role_name, role in [("Gold", gold_role), ("Silver", silver_role), ("Bronze", bronze_role)]:
                if role:
                    can_manage = role < bot_member.top_role
                    status = "Can manage" if can_manage else "Bot role too low"
                    roles_status.append(f"**{role_name}**: {status}")
                else:
                    roles_status.append(f"**{role_name}**: Not created yet")
            
            embed.add_field(
                name="LeetCode Roles",
                value="\n".join(roles_status),
                inline=False
            )
            
            embed.add_field(
                name="Bot Role Position",
                value=f"#{bot_member.top_role.position} - {bot_member.top_role.name}",
                inline=False
            )
            
            if not can_manage_roles:
                embed.add_field(
                    name="Action Required",
                    value="Grant the bot 'Manage Roles' permission in Server Settings",
                    inline=False
                )
            
            if gold_role and gold_role >= bot_member.top_role:
                embed.add_field(
                    name="Role Hierarchy Issue",
                    value="Move the bot's role above Gold/Silver/Bronze roles in Server Settings -> Roles",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Role test failed: {e}")
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)
    
    @app_commands.command(name="test_channels", description="Verify channel IDs are correct")
    async def test_channels(self, interaction: discord.Interaction):
        try:
            ai_news_channel_id = int(os.getenv('AI_NEWS_CHANNEL_ID', 0))
            
            embed = discord.Embed(
                title="Channel Configuration Test",
                color=discord.Color.blue()
            )
            
            if ai_news_channel_id:
                channel = self.bot.get_channel(ai_news_channel_id)
                if channel:
                    embed.add_field(
                        name="AI News Channel",
                        value=f"Found: {channel.mention}\nID: `{ai_news_channel_id}`",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="AI News Channel",
                        value=f"Channel not found\nID: `{ai_news_channel_id}`\n"
                              f"Make sure the bot has access to this channel",
                        inline=False
                    )
            else:
                embed.add_field(
                    name="AI News Channel",
                    value="AI_NEWS_CHANNEL_ID not set in .env",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Channel test failed: {e}")
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)
    
    @app_commands.command(name="test_ai_news", description="Test AI news picker logic")
    @app_commands.checks.has_permissions(administrator=True)
    async def test_ai_news(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        try:
            from utils.ai_news_picker import AINewsPicker
            
            picker = AINewsPicker(self.bot.db)
            
            member = await picker.pick_random_member(interaction.guild, interaction.channel)
            
            if member:
                embed = discord.Embed(
                    title="AI News Picker Test",
                    description="Successfully selected a random member",
                    color=discord.Color.green()
                )
                embed.add_field(name="Selected User", value=member.mention, inline=True)
                embed.add_field(name="Is Admin", value="No" if not member.guild_permissions.administrator else "Yes (shouldn't happen!)", inline=True)
                
                recent = await self.bot.db.get_recent_ai_news_assignees(weeks=4)
                embed.add_field(
                    name="Recent Assignees (4 weeks)",
                    value=str(len(recent)),
                    inline=True
                )
                
                embed.set_footer(text="This is a test - no assignment was made")
                
            else:
                embed = discord.Embed(
                    title="AI News Picker Warning",
                    description="No eligible members found",
                    color=discord.Color.orange()
                )
                embed.add_field(
                    name="Possible Reasons",
                    value="- All members are admins\n- All members assigned recently\n- No members in server",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"AI news test failed: {e}")
            
            embed = discord.Embed(
                title="AI News Test Failed",
                description=f"Error: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="test_ai_news_2", description="Test AI news embed (sends actual assignment message)")
    @app_commands.checks.has_permissions(administrator=True)
    async def test_ai_news_2(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
        except:
            pass
        
        try:
            from utils.ai_news_picker import AINewsPicker
            picker = AINewsPicker(self.bot.db)
            await picker.set_current_assignee(interaction.user.id)
            
            embed = discord.Embed(
                title="📰 Weekly AI News Time!",
                description=f"{interaction.user.mention}, you've been selected to share this week's top AI news!\n\n"
                           f"Please share the most interesting AI developments from this week. "
                           f"The news will be posted on social media Thursday.",
                color=discord.Color.blue()
            )
            embed.set_footer(text="Reply in this channel or react with 👍 to mark as complete (Test)")
            
            await interaction.channel.send(interaction.user.mention)
            message = await interaction.channel.send(embed=embed)
            await message.add_reaction("👍")
            
            try:
                await interaction.followup.send("✅ Test embed sent! React with 👍 on the bot's reaction or send a message!", ephemeral=True)
            except:
                pass
            
        except Exception as e:
            logger.error(f"AI news test 2 failed: {e}")
            
            embed = discord.Embed(
                title="AI News Test 2 Failed",
                description=f"Error: {str(e)}",
                color=discord.Color.red()
            )
            try:
                await interaction.followup.send(embed=embed)
            except:
                try:
                    await interaction.response.send_message(embed=embed)
                except:
                    pass
    
    @app_commands.command(name="test_background_tasks", description="Check background task status")
    async def test_background_tasks(self, interaction: discord.Interaction):
        try:
            from main import submission_checker, weekly_reset, ai_news_reminder

            embed = discord.Embed(
                title="Background Tasks Diagnostics",
                color=discord.Color.blue()
            )

            def inspect_task(task_obj, pretty_name):
                try:
                    running = bool(task_obj.is_running())
                except Exception:
                    running = False

                # Attempt to read next_iteration if present
                next_it = None
                try:
                    next_it = getattr(task_obj, 'next_iteration', None)
                except Exception:
                    next_it = None

                lines = []
                lines.append(f"**{pretty_name}**")
                lines.append(f"- Running: `{running}`")

                if next_it:
                    try:
                        delta = next_it - discord.utils.utcnow()
                        secs = max(0, int(delta.total_seconds()))
                        lines.append(f"- Next iteration (UTC): `{next_it.isoformat()}`")
                        lines.append(f"- Time until next: `{secs}s`")
                    except Exception:
                        lines.append(f"- Next iteration: `{next_it}`")
                else:
                    lines.append(f"- Next iteration: `None`")

                # If not running, attempt to start the task (best-effort)
                start_attempt = None
                if not running:
                    try:
                        task_obj.start()
                        start_attempt = "started"
                        running = True
                    except RuntimeError:
                        start_attempt = "already started elsewhere"
                    except Exception as ex:
                        start_attempt = f"error: {ex}"

                if start_attempt is not None:
                    lines.append(f"- Start attempt: `{start_attempt}`")

                return "\n".join(lines)

            parts = [
                inspect_task(submission_checker, "Submission Checker"),
                inspect_task(weekly_reset, "Weekly Reset"),
                inspect_task(ai_news_reminder, "AI News Reminder"),
            ]

            embed.description = "\n\n".join(parts)
            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Background task test failed: {e}")
            try:
                await interaction.response.send_message(f"Error: {e}", ephemeral=True)
            except:
                pass
    
    @app_commands.command(name="test_env", description="Check environment variables")
    @app_commands.checks.has_permissions(administrator=True)
    async def test_env(self, interaction: discord.Interaction):
        try:
            embed = discord.Embed(
                title="Environment Variables Check",
                color=discord.Color.blue()
            )
            
            token = os.getenv('TOKEN')
            token_status = "Set" if token else "Missing"
            embed.add_field(name="TOKEN", value=token_status, inline=True)
            
            db_url = os.getenv('DATABASE_URL')
            if db_url:
                if '@' in db_url:
                    parts = db_url.split('@')
                    host = parts[1].split('/')[0]
                    db_status = f"Set\nHost: `{host}`"
                else:
                    db_status = "Set but malformed"
            else:
                db_status = "Missing"
            embed.add_field(name="DATABASE_URL", value=db_status, inline=True)
            
            channel_id = os.getenv('AI_NEWS_CHANNEL_ID')
            channel_status = f"Set: `{channel_id}`" if channel_id else "Missing"
            embed.add_field(name="AI_NEWS_CHANNEL_ID", value=channel_status, inline=True)
            
            all_set = token and db_url and channel_id
            overall = "All environment variables are set!" if all_set else "Some variables are missing"
            embed.add_field(name="Status", value=overall, inline=False)
            
            if not all_set:
                embed.add_field(
                    name="Fix",
                    value="Check your `.env` file and make sure all required variables are set",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Env test failed: {e}")
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)
    
    @app_commands.command(name="test_all", description="Run all tests at once")
    @app_commands.checks.has_permissions(administrator=True)
    async def test_all(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        embed = discord.Embed(
            title="Running Full Test Suite",
            description="Testing all bot functionality...",
            color=discord.Color.blue()
        )
        
        results = []
        
        try:
            latency = round(self.bot.latency * 1000)
            results.append(f"[OK] **Bot Online**: {latency}ms")
        except:
            results.append("[FAIL] **Bot Online**: Failed")
        
        try:
            if self.bot.db and self.bot.db.pool:
                async with self.bot.db.pool.acquire() as conn:
                    await conn.fetchval('SELECT 1')
                results.append("[OK] **Database**: Connected")
            else:
                results.append("[FAIL] **Database**: Not initialized")
        except Exception as e:
            results.append(f"[FAIL] **Database**: {str(e)[:50]}")
        
        try:
            from utils.leetcode_api import LeetCodeAPI
            api = LeetCodeAPI()
            test_user = await api.get_user_stats("testuser")
            results.append("[OK] **LeetCode API**: Accessible")
        except Exception as e:
            results.append(f"[WARN] **LeetCode API**: {str(e)[:50]}")
        
        try:
            guild = interaction.guild
            bot_member = guild.get_member(self.bot.user.id)
            can_manage = bot_member.guild_permissions.manage_roles
            if can_manage:
                results.append("[OK] **Role Permissions**: Granted")
            else:
                results.append("[FAIL] **Role Permissions**: Missing")
        except Exception as e:
            results.append(f"[FAIL] **Role Permissions**: {str(e)[:50]}")
        
        try:
            channel_id = int(os.getenv('AI_NEWS_CHANNEL_ID', 0))
            if channel_id and self.bot.get_channel(channel_id):
                results.append("[OK] **AI News Channel**: Found")
            else:
                results.append("[WARN] **AI News Channel**: Not configured")
        except:
            results.append("[FAIL] **AI News Channel**: Error")
        
        try:
            from main import submission_checker, weekly_reset, ai_news_reminder
            running = submission_checker.is_running() and weekly_reset.is_running() and ai_news_reminder.is_running()
            if running:
                results.append("[OK] **Background Tasks**: All running")
            else:
                results.append("[WARN] **Background Tasks**: Some not running")
        except:
            results.append("[FAIL] **Background Tasks**: Error")
        
        embed.description = "\n".join(results)
        
        failed = sum(1 for r in results if r.startswith("[FAIL]"))
        warnings = sum(1 for r in results if r.startswith("[WARN]"))
        
        if failed == 0 and warnings == 0:
            embed.color = discord.Color.green()
            embed.set_footer(text="All tests passed! Bot is fully operational.")
        elif failed == 0:
            embed.color = discord.Color.orange()
            embed.set_footer(text=f"{warnings} warning(s). Bot should work but check warnings.")
        else:
            embed.color = discord.Color.red()
            embed.set_footer(text=f"{failed} test(s) failed. Bot may not work correctly.")
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="bot_info", description="Show bot information and stats")
    async def info(self, interaction: discord.Interaction):
        try:
            guild_count = len(self.bot.guilds)
            user_count = len(await self.bot.db.get_all_users()) if self.bot.db else 0
            
            embed = discord.Embed(
                title="Bot Information",
                color=discord.Color.blue()
            )
            
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
            
            embed.add_field(name="Bot Name", value=self.bot.user.name, inline=True)
            embed.add_field(name="Bot ID", value=self.bot.user.id, inline=True)
            embed.add_field(name="Servers", value=str(guild_count), inline=True)
            
            embed.add_field(name="Linked Users", value=str(user_count), inline=True)
            embed.add_field(name="Discord.py", value=discord.__version__, inline=True)
            embed.add_field(name="Latency", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
            
            cog_count = len(self.bot.cogs)
            embed.add_field(name="Loaded Cogs", value=str(cog_count), inline=True)
            
            command_count = len(self.bot.tree.get_commands())
            embed.add_field(name="Slash Commands", value=str(command_count), inline=True)
            
            embed.set_footer(text=f"Made with discord.py")
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Bot info failed: {e}")
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(TestCommands(bot))