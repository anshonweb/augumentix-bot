import aiohttp
from datetime import datetime, timedelta
import logging

logger = logging.getLogger('discord')

class LeetCodeAPI:
    def __init__(self):
        self.api_url = "https://leetcode.com/graphql"

    async def get_user_stats(self, username: str):
        query = """
        query getUserProfile($username: String!) {
            matchedUser(username: $username) {
                username
                submitStats {
                    acSubmissionNum {
                        difficulty
                        count
                    }
                }
            }
        }
        """
        variables = {"username": username}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    json={"query": query, "variables": variables},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("data") and data["data"].get("matchedUser"):
                            return data["data"]["matchedUser"]
            return None
        except Exception as e:
            logger.error(f"Error fetching user stats for {username}: {e}")
            return None

    async def get_recent_submissions(self, username: str, limit: int = 20):
        query = """
        query getRecentSubmissions($username: String!, $limit: Int!) {
            recentAcSubmissionList(username: $username, limit: $limit) {
                title
                titleSlug
                timestamp
            }
        }
        """

        variables = {"username": username, "limit": limit}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    json={"query": query, "variables": variables},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("data") and data["data"].get("recentAcSubmissionList"):
                            return data["data"]["recentAcSubmissionList"]
            return []
        except Exception as e:
            logger.error(f"Error fetching submissions for {username}: {e}")
            return []

    async def get_problem_difficulty(self, title_slug: str):
        query = """
        query getProblemDifficulty($titleSlug: String!) {
            question(titleSlug: $titleSlug) {
                difficulty
            }
        }
        """

        variables = {"titleSlug": title_slug}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    json={"query": query, "variables": variables},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("data") and data["data"].get("question"):
                            return data["data"]["question"]["difficulty"]
            return "Unknown"
        except Exception as e:
            logger.error(f"Error fetching difficulty for {title_slug}: {e}")
            return "Unknown"

    def get_total_solved(self, user_stats):
        if not user_stats or "submitStats" not in user_stats:
            return 0

        submit_stats = user_stats["submitStats"]["acSubmissionNum"]
        for stat in submit_stats:
            if stat["difficulty"] == "All":
                return stat["count"]
        return 0

    async def update_user(self, bot, discord_id: int, leetcode_username: str):
        try:
            user_stats = await self.get_user_stats(leetcode_username)

            if not user_stats:
                logger.warning(f"Could not fetch stats for {leetcode_username}")
                return False

            total_solved = self.get_total_solved(user_stats)
            recent_submissions = await self.get_recent_submissions(leetcode_username, 20)

            week_ago = datetime.now() - timedelta(days=7)
            weekly_count = 0

            for submission in recent_submissions:
                submission_time = datetime.fromtimestamp(int(submission["timestamp"]))

                if submission_time >= week_ago:
                    difficulty = await self.get_problem_difficulty(
                        submission["titleSlug"]
                    )

                    is_new = await bot.db.add_submission(
                        discord_id,
                        submission["title"],
                        submission["titleSlug"],
                        difficulty,
                        int(submission["timestamp"])
                    )

                    if is_new:
                        weekly_count += 1

            user = await bot.db.get_user(discord_id)

            if user:
                current_weekly = user["weekly_solved"]
                new_weekly = current_weekly + weekly_count
                await bot.db.update_user_stats(
                    discord_id,
                    total_solved,
                    new_weekly
                )
            else:
                await bot.db.update_user_stats(
                    discord_id,
                    total_solved,
                    weekly_count
                )

            logger.info(
                f"Updated {leetcode_username}: {total_solved} total, +{weekly_count} this week"
            )
            return True

        except Exception as e:
            logger.error(f"Error updating user {leetcode_username}: {e}")
            return False
