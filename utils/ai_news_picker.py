import discord
import random
import logging
from datetime import datetime

logger = logging.getLogger('discord')

class AINewsPicker:
    def __init__(self, database):
        self.db = database

    async def should_send_reminder(self):
        assignee = await self.db.get_current_ai_news_assignee()

        if not assignee:
            return True

        if not assignee['completed']:
            return True

        return False

    async def pick_random_member(self, guild: discord.Guild, channel: discord.TextChannel):
        try:
            members = [m for m in guild.members if not m.bot]
            members = [m for m in members if not m.guild_permissions.administrator]

            recent_assignees = await self.db.get_recent_ai_news_assignees(weeks=4)
            members = [m for m in members if m.id not in recent_assignees]

            if not members:
                logger.warning("All members assigned recently, picking from full list")
                members = [
                    m for m in guild.members
                    if not m.bot and not m.guild_permissions.administrator
                ]

            if not members:
                logger.error("No eligible members found")
                return None

            selected = random.choice(members)
            logger.info(f"Selected {selected.name} for AI news")
            return selected

        except Exception as e:
            logger.error(f"Error picking random member: {e}")
            return None

    async def set_current_assignee(self, discord_id: int):
        try:
            await self.db.set_ai_news_assignee(discord_id)
            logger.info(f"Set AI news assignee: {discord_id}")
        except Exception as e:
            logger.error(f"Error setting assignee: {e}")

    async def mark_complete(self, discord_id: int):
        try:
            await self.db.mark_ai_news_complete(discord_id)
            logger.info(f"Marked AI news complete for: {discord_id}")
        except Exception as e:
            logger.error(f"Error marking complete: {e}")

    async def check_for_response(self, message: discord.Message):
        try:
            assignee = await self.db.get_current_ai_news_assignee()

            if not assignee or assignee['completed']:
                return False

            if message.author.id == assignee['discord_id']:
                await self.mark_complete(message.author.id)

                embed = discord.Embed(
                    title="✅ AI News Received!",
                    description=f"Thanks {message.author.mention}! Your AI news has been recorded.",
                    color=discord.Color.green()
                )

                embed.set_footer(
                    text="This will be shared on social media Thursday"
                )

                await message.channel.send(embed=embed)
                return True

            return False

        except Exception as e:
            logger.error(f"Error checking response: {e}")
            return False

    async def check_for_reaction_response(self, reaction: discord.Reaction, user: discord.User):
        try:
            assignee = await self.db.get_current_ai_news_assignee()

            if not assignee or assignee['completed']:
                return False

            if str(reaction.emoji) != "👍":
                return False

            if user.id == assignee['discord_id']:
                await self.mark_complete(user.id)

                embed = discord.Embed(
                    title="✅ AI News Received!",
                    description=f"Thanks <@{user.id}>! Your AI news has been recorded.",
                    color=discord.Color.green()
                )

                embed.set_footer(
                    text="This will be shared on social media Thursday"
                )

                await reaction.message.channel.send(embed=embed)
                return True

            return False

        except Exception as e:
            logger.error(f"Error checking reaction response: {e}")
            return False
