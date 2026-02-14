import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
import logging

logger = logging.getLogger('discord')

class LeetCodeCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="link", description="Link your LeetCode account")
    @app_commands.describe(username="Your LeetCode username")
    async def link(self, interaction: discord.Interaction, username: str):
        await interaction.response.defer()

        try:
            from utils.leetcode_api import LeetCodeAPI
            leetcode_api = LeetCodeAPI()

            user_stats = await leetcode_api.get_user_stats(username)

            if not user_stats:
                await interaction.followup.send(
                    f"❌ Could not find LeetCode user: `{username}`. Please check the spelling.",
                    ephemeral=True
                )
                return

            await self.bot.db.link_user(interaction.user.id, username)
            await leetcode_api.update_user(self.bot, interaction.user.id, username)

            from utils.role_manager import RoleManager
            role_manager = RoleManager(self.bot.db)
            await role_manager.update_user_role(interaction.user, interaction.guild)

            user = await self.bot.db.get_user(interaction.user.id)

            embed = discord.Embed(
                title="✅ Account Linked!",
                description=f"Your Discord account has been linked to: **{username}**",
                color=discord.Color.green()
            )

            if user:
                embed.add_field(
                    name="Total Solved",
                    value=f"🎯 {user['total_solved']}",
                    inline=True
                )
                embed.add_field(
                    name="This Week",
                    value=f"📅 {user['weekly_solved']}",
                    inline=True
                )

            embed.set_footer(text="Stats update automatically every hour")

            await interaction.followup.send(embed=embed)
            logger.info(f"{interaction.user.name} linked account: {username}")

        except Exception as e:
            logger.error(f"Error in link command: {e}")
            await interaction.followup.send(
                "❌ An error occurred. Please try again later.",
                ephemeral=True
            )

    @app_commands.command(name="profile", description="View LeetCode profile")
    @app_commands.describe(user="User to view (leave empty for yourself)")
    async def profile(self, interaction: discord.Interaction, user: discord.Member = None):
        target_user = user or interaction.user

        try:
            user_data = await self.bot.db.get_user(target_user.id)

            if not user_data:
                await interaction.response.send_message(
                    f"❌ {target_user.mention} hasn't linked their LeetCode account yet!\n"
                    f"Use `/link` to get started.",
                    ephemeral=True
                )
                return

            leetcode_username = user_data['leetcode_username']
            total_solved = user_data['total_solved']
            weekly_solved = user_data['weekly_solved']

            embed = discord.Embed(
                title="📊 LeetCode Profile",
                description=f"**LeetCode:** [{leetcode_username}](https://leetcode.com/{leetcode_username})",
                color=discord.Color.blue()
            )

            embed.set_author(
                name=target_user.display_name,
                icon_url=target_user.display_avatar.url
            )

            embed.add_field(
                name="Total Solved",
                value=f"🎯 {total_solved}",
                inline=True
            )
            embed.add_field(
                name="This Week",
                value=f"📅 {weekly_solved}",
                inline=True
            )

            submissions = await self.bot.db.get_user_submissions_this_week(target_user.id)

            if submissions:
                recent_text = ""
                for title, difficulty, timestamp in submissions[:5]:
                    date = datetime.fromtimestamp(timestamp).strftime("%m/%d")
                    emoji = {
                        "Easy": "🟢",
                        "Medium": "🟡",
                        "Hard": "🔴"
                    }.get(difficulty, "⚪")
                    recent_text += f"{emoji} {title} - {date}\n"

                embed.add_field(
                    name="Recent Submissions",
                    value=recent_text,
                    inline=False
                )

            last_updated = user_data['last_updated']
            if last_updated:
                embed.set_footer(
                    text=f"Last updated: {last_updated.strftime('%Y-%m-%d %H:%M')}"
                )

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error(f"Error in profile command: {e}")
            await interaction.response.send_message(
                "❌ An error occurred. Please try again later.",
                ephemeral=True
            )

    @app_commands.command(name="leaderboard", description="View the weekly leaderboard")
    async def leaderboard(self, interaction: discord.Interaction):
        try:
            leaderboard_data = await self.bot.db.get_weekly_leaderboard(10)

            if not leaderboard_data:
                await interaction.response.send_message(
                    "📊 No data available yet! Link your account with `/link`.",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title="🏆 Weekly Leaderboard",
                description="Top performers this week",
                color=discord.Color.gold()
            )

            medals = ["🥇", "🥈", "🥉"]
            leaderboard_text = ""

            for idx, (discord_id, leetcode_username, weekly_solved) in enumerate(leaderboard_data):
                medal = medals[idx] if idx < 3 else f"#{idx + 1}"

                member = interaction.guild.get_member(discord_id)
                display_name = member.display_name if member else leetcode_username

                leaderboard_text += f"{medal} **{display_name}** - {weekly_solved} problems\n"

            embed.description = leaderboard_text

            now = datetime.now()
            days_until_monday = (7 - now.weekday()) % 7

            if days_until_monday == 0:
                reset_text = "Resets tomorrow!"
            elif days_until_monday == 1:
                reset_text = "Resets in 1 day"
            else:
                reset_text = f"Resets in {days_until_monday} days"

            embed.set_footer(text=f"⏰ {reset_text}")

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error(f"Error in leaderboard command: {e}")
            await interaction.response.send_message(
                "❌ An error occurred. Please try again later.",
                ephemeral=True
            )

    @app_commands.command(name="update", description="Manually update your stats")
    async def update(self, interaction: discord.Interaction):
        await interaction.response.defer()

        try:
            user_data = await self.bot.db.get_user(interaction.user.id)

            if not user_data:
                await interaction.followup.send(
                    "❌ You haven't linked your account yet! Use `/link` first.",
                    ephemeral=True
                )
                return

            leetcode_username = user_data['leetcode_username']

            from utils.leetcode_api import LeetCodeAPI
            leetcode_api = LeetCodeAPI()

            success = await leetcode_api.update_user(
                self.bot,
                interaction.user.id,
                leetcode_username
            )

            if success:
                from utils.role_manager import RoleManager
                role_manager = RoleManager(self.bot.db)
                await role_manager.update_user_role(
                    interaction.user,
                    interaction.guild
                )

                user_data = await self.bot.db.get_user(interaction.user.id)

                embed = discord.Embed(
                    title="✅ Stats Updated!",
                    color=discord.Color.green()
                )

                embed.add_field(
                    name="Total Solved",
                    value=f"{user_data['total_solved']}",
                    inline=True
                )
                embed.add_field(
                    name="This Week",
                    value=f"{user_data['weekly_solved']}",
                    inline=True
                )

                await interaction.followup.send(embed=embed)

            else:
                await interaction.followup.send(
                    "❌ Failed to update stats. Please try again later.",
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error in update command: {e}")
            await interaction.followup.send(
                "❌ An error occurred. Please try again later.",
                ephemeral=True
            )

    @app_commands.command(name="unlink", description="Unlink your LeetCode account")
    async def unlink(self, interaction: discord.Interaction):
        try:
            user_data = await self.bot.db.get_user(interaction.user.id)

            if not user_data:
                await interaction.response.send_message(
                    "❌ You don't have a linked account.",
                    ephemeral=True
                )
                return

            await self.bot.db.unlink_user(interaction.user.id)

            await interaction.response.send_message(
                "✅ Your LeetCode account has been unlinked.",
                ephemeral=True
            )

            logger.info(f"{interaction.user.name} unlinked their account")

        except Exception as e:
            logger.error(f"Error in unlink command: {e}")
            await interaction.response.send_message(
                "❌ An error occurred. Please try again later.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(LeetCodeCommands(bot))
