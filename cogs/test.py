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
            title="Pong",
            description="Bot is online and responding",
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
                await interaction.followup.send("Database pool not initialized.")
                return

            async with self.bot.db.pool.acquire() as conn:
                await conn.fetchval('SELECT 1')

            async with self.bot.db.pool.acquire() as conn:
                tables = await conn.fetch("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                """)

            user_count = len(await self.bot.db.get_all_users())

            embed = discord.Embed(
                title="Database Connection Test",
                description="Database is working correctly.",
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
            embed.add_field(
                name="Tip",
                value="Check DATABASE_URL in the environment file.",
                inline=False
            )

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
                    value="Username does not exist\nLeetCode API unavailable\nNetwork connectivity issue",
                    inline=False
                )
                await interaction.followup.send(embed=embed)
                return

            total_solved = leetcode_api.get_total_solved(user_stats)
            submissions = await leetcode_api.get_recent_submissions(username, 5)

            embed = discord.Embed(
                title="LeetCode API Test Passed",
                description=f"Successfully fetched data for {username}",
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

async def setup(bot):
    await bot.add_cog(TestCommands(bot))
