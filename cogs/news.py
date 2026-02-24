import discord
from discord.ext import commands
import os
import logging

logger = logging.getLogger('discord')

class AINewsListener(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ai_news_channel_id = int(
            os.getenv('AI_NEWS_CHANNEL_ID', 0)
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if message.channel.id != self.ai_news_channel_id:
            return

        try:
            from utils.ai_news_picker import AINewsPicker
            picker = AINewsPicker(self.bot.db)
            await picker.check_for_response(message)

        except Exception as e:
            logger.error(f"Error in AI news listener: {e}")

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        if user.bot:
            return

        try:
            from utils.ai_news_picker import AINewsPicker
            picker = AINewsPicker(self.bot.db)
            await picker.check_for_reaction_response(reaction, user)

        except Exception as e:
            logger.error(f"Error in AI news reaction listener: {e}")

async def setup(bot):
    await bot.add_cog(AINewsListener(bot))
