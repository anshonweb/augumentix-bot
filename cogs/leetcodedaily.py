import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import random
from datetime import datetime
import logging

logger = logging.getLogger('discord')
from utils.leetcode_api import LeetCodeAPI

class LanguageSelectView(discord.ui.View):
    """View with dropdown to select programming language"""
    
    def __init__(self, question: dict, solutions: dict):
        super().__init__(timeout=None) 
        self.question = question
        self.solutions = solutions
        self.add_item(LanguageSelect(question, solutions))

class LanguageSelect(discord.ui.Select):
    """Dropdown menu for selecting programming language"""
    
    def __init__(self, question: dict, solutions: dict):
        self.question = question
        self.solutions = solutions
        
        options = [
            discord.SelectOption(
                label="Python",
                value="python",
                description="View solution in Python",
                default=True
            ),
            discord.SelectOption(
                label="JavaScript",
                value="javascript",
                description="View solution in JavaScript",
            ),
            discord.SelectOption(
                label="Java",
                value="java",
                description="View solution in Java",
            ),
            discord.SelectOption(
                label="C++",
                value="cpp",
                description="View solution in C++",

            ),
            discord.SelectOption(
                label="Go",
                value="go",
                description="View solution in Go",
            )
        ]
        
        super().__init__(
            placeholder="Choose a programming language...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle language selection"""
        selected_lang = self.values[0]

        for option in self.options:
            option.default = (option.value == selected_lang)

        solution_data = self.solutions.get(selected_lang, {})

        embeds = self.create_solution_embeds(self.question, solution_data, selected_lang)
        await interaction.response.edit_message(embeds=embeds, view=self.view)
    
    def create_solution_embeds(self, question: dict, solution_data: dict, language: str) -> list:
        lang_names = {
            "python": "Python ",
            "javascript": "JavaScript ",
            "java": "Java ",
            "cpp": "C++ ",
            "go": "Go "
        }
        
        syntax_map = {
            "python": "python",
            "javascript": "javascript",
            "java": "java",
            "cpp": "cpp",
            "go": "go"
        }
        
        embeds = []
        embed1 = discord.Embed(
            title=f"✅ Solution: {question['title']}",
            description=solution_data.get('explanation', 'No explanation available'),
            color=discord.Color.green(),
            url=question['leetcode_url']
        )
        
        embed1.add_field(
            name="⏱️ Time Complexity",
            value=solution_data.get('time_complexity', 'N/A'),
            inline=True
        )
        
        embed1.add_field(
            name="💾 Space Complexity",
            value=solution_data.get('space_complexity', 'N/A'),
            inline=True
        )
        
        embeds.append(embed1)
        code = solution_data.get('solution_code', '// No code available')
        syntax = syntax_map.get(language, 'python')
        
        if len(code) > 4000:
            code = code[:4000] + "\n// ... (truncated)"
        
        embed2 = discord.Embed(
            title=f"💻 {lang_names.get(language, language)} Solution",
            description=f"```{syntax}\n{code}\n```",
            color=discord.Color.blue()
        )
        
        embed2.set_footer(text=f"Generated with Groq AI • Select language above • {datetime.now().strftime('%B %d, %Y')}")
        
        embeds.append(embed2)
        
        return embeds

class LeetCodeDaily(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.questions = self.load_questions()
        self.dsa_channel_id = int(os.getenv('DSA_CHANNEL_ID', 0))
    
    def load_questions(self):
        """Load LeetCode 75 questions from JSON file"""
        try:
            json_path = 'leetcode75_questions.json'
            if not os.path.exists(json_path):
                logger.error(f"Questions file not found: {json_path}")
                return []
            
            with open(json_path, 'r') as f:
                questions = json.load(f)
                logger.info(f"Loaded {len(questions)} LeetCode questions")
                return questions
        except Exception as e:
            logger.error(f"Error loading questions: {e}")
            return []
    
    def get_question_by_id(self, question_id: int):
        """Get a specific question by ID"""
        for q in self.questions:
            if q['id'] == question_id:
                return q
        return None

    async def fetch_question(self, question_id: int):
        """Fetch question from local JSON or fall back to LeetCode API by number."""
        q = self.get_question_by_id(question_id)
        if q:
            return q
        try:
            api = LeetCodeAPI()
            problem = await api.get_problem_by_number(question_id)
            if not problem:
                return None
            return {
                'id': int(problem.get('id', question_id)),
                'title': problem.get('title', f'Problem {question_id}'),
                'description': problem.get('description', '') or 'Description not available.',
                'difficulty': problem.get('difficulty', '') or 'Unknown',
                'category': ', '.join(problem.get('topic_tags', [])) if problem.get('topic_tags') else 'General',
                'hints': [],
                'leetcode_url': problem.get('leetcode_url', f'https://leetcode.com/problems/{problem.get("title_slug", "")}/')
            }
        except Exception as e:
            logger.error(f'Error fetching question {question_id} from LeetCode API: {e}')
            return None
    
    def get_next_unposted_question(self, posted_ids: list):
        """Get the next question that hasn't been posted yet"""
        for q in self.questions:
            if q['id'] not in posted_ids:
                return q
        return None
    
    @app_commands.command(name="lc_question", description="Post today's LeetCode challenge")
    @app_commands.describe(question_id="Specific question ID (optional, picks next unposted if not provided)")
    async def post_question(self, interaction: discord.Interaction, question_id: int = None):
        """Post a LeetCode question"""
        await interaction.response.defer()
        
        try:
            today_challenge = await self.bot.db.get_todays_challenge()
            if today_challenge:
                await interaction.followup.send(
                    "❌ A question has already been posted today! Use `/lc_solution` to post the solution.",
                    ephemeral=True
                )
                return

            if question_id:
                question = self.get_question_by_id(question_id)
                if not question:

                    question = await self.fetch_question(question_id)
                    if not question:
                        await interaction.followup.send(
                            f"❌ Question ID {question_id} not found!",
                            ephemeral=True
                        )
                        return
            else:

                posted_ids = await self.bot.db.get_posted_question_ids()
                question = self.get_next_unposted_question(posted_ids)
                
                if not question:
                    question = self.questions[0] if self.questions else None
                
                if not question:
                    await interaction.followup.send(
                        "❌ No questions available!",
                        ephemeral=True
                    )
                    return
            channel_id = self.dsa_channel_id or interaction.channel_id
            channel = self.bot.get_channel(channel_id)
            
            if not channel:
                await interaction.followup.send(
                    "❌ DSA channel not found! Set DSA_CHANNEL_ID in .env",
                    ephemeral=True
                )
                return

            embed = self.create_question_embed(question)
            
            message = await channel.send(
                content="@everyon23 🚀 **Daily LeetCode Challenge!**",
                embed=embed
            )
            await self.bot.db.post_daily_challenge(question['id'], message.id)
            await interaction.followup.send(
                f"✅ Posted question #{question['id']}: **{question['title']}** to {channel.mention}",
                ephemeral=True
            )
            
            logger.info(f"Posted daily question: {question['title']}")
            
        except Exception as e:
            logger.error(f"Error posting question: {e}")
            await interaction.followup.send(
                f"❌ Error posting question: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(name="lc_solution", description="Post solution for today's challenge")
    async def post_solution(self, interaction: discord.Interaction):
        """Generate and post solution using Groq API with language selector"""
        await interaction.response.defer()
        
        try:
            today_challenge = await self.bot.db.get_todays_challenge()
            
            if not today_challenge:
                await interaction.followup.send(
                    "❌ No question posted today! Use `/lc_question` first.",
                    ephemeral=True
                )
                return
            
            if today_challenge['solution_posted']:
                await interaction.followup.send(
                    "❌ Solution already posted today!",
                    ephemeral=True
                )
                return
            question = await self.fetch_question(today_challenge['question_id'])

            if not question:
                await interaction.followup.send(
                    "❌ Question not found!",
                    ephemeral=True
                )
                return
            channel_id = self.dsa_channel_id or interaction.channel_id
            channel = self.bot.get_channel(channel_id)
            
            if not channel:
                await interaction.followup.send(
                    "❌ Channel not found!",
                    ephemeral=True
                )
                return
            await interaction.followup.send(
                "⏳ Generating solutions. This may take 30-60 seconds.\n",
                ephemeral=True
            )
            from utils.groq_api import GroqAPI
            groq = GroqAPI()
            
            solutions = await groq.generate_multi_language_solutions(
                question['title'],
                question['description'],
                question['difficulty'],
                question.get('hints', [])
            )
            
            view = LanguageSelectView(question, solutions)
            
            python_solution = solutions.get('python', {})
            embeds = view.children[0].create_solution_embeds(question, python_solution, 'python')
            
            message = await channel.send(
                content="✅ **Solution for Today's Challenge** - Select your preferred language below:",
                embeds=embeds,
                view=view
            )
            
            await self.bot.db.post_challenge_solution(
                today_challenge['id'],
                message.id
            )
            
            await interaction.edit_original_response(
                content=f"✅ Posted multi-language solution for **{question['title']}** to {channel.mention}\n"
                        f"Members can select from 5 languages!"
            )
            
            logger.info(f"Posted multi-language solution for: {question['title']}")
            
        except Exception as e:
            logger.error(f"Error posting solution: {e}")
            await interaction.edit_original_response(
                content=f"❌ Error posting solution: {str(e)}"
            )
    
    @app_commands.command(name="lc_stats", description="View LeetCode daily challenge statistics")
    async def challenge_stats(self, interaction: discord.Interaction):
        """Show statistics about posted challenges"""
        try:
            stats = await self.bot.db.get_challenge_stats()
            today_challenge = await self.bot.db.get_todays_challenge()
            
            embed = discord.Embed(
                title="📊 LeetCode Daily Challenge Stats",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="Total Questions Posted",
                value=f"{stats['total_posted']}/{len(self.questions)}",
                inline=True
            )
            
            embed.add_field(
                name="Solutions Posted",
                value=str(stats['solutions_posted']),
                inline=True
            )
            
            if today_challenge:
                question = await self.fetch_question(today_challenge['question_id'])
                status = "✅ Posted" if today_challenge['solution_posted'] else "⏳ Pending"
                title = question['title'] if question else f"Question #{today_challenge['question_id']}"
                embed.add_field(
                    name="Today's Challenge",
                    value=f"**{title}**\nSolution: {status}",
                    inline=False
                )
            else:
                embed.add_field(
                    name="Today's Challenge",
                    value="❌ Not posted yet",
                    inline=False
                )
            posted_ids = await self.bot.db.get_posted_question_ids()
            next_q = self.get_next_unposted_question(posted_ids)
            if next_q:
                embed.add_field(
                    name="Next Question",
                    value=f"#{next_q['id']}: {next_q['title']} ({next_q['difficulty']})",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(name="lc_list", description="List all LeetCode 75 questions")
    @app_commands.describe(
        category="Filter by category (optional)",
        difficulty="Filter by difficulty (optional)"
    )
    async def list_questions(
        self, 
        interaction: discord.Interaction,
        category: str = None,
        difficulty: str = None
    ):
        """List all available questions"""
        try:
            filtered = self.questions
            
            if category:
                filtered = [q for q in filtered if category.lower() in q['category'].lower()]
            
            if difficulty:
                filtered = [q for q in filtered if q['difficulty'].lower() == difficulty.lower()]
            
            if not filtered:
                await interaction.response.send_message(
                    "❌ No questions match your filters!",
                    ephemeral=True
                )
                return
            
            page_size = 10
            pages = [filtered[i:i + page_size] for i in range(0, len(filtered), page_size)]
            
            embed = self.create_question_list_embed(pages[0], 1, len(pages), category, difficulty)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error listing questions: {e}")
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )
    
    def create_question_embed(self, question: dict) -> discord.Embed:
        """Create embed for posting a question"""
        colors = {
            "Easy": discord.Color.green(),
            "Medium": discord.Color.orange(),
            "Hard": discord.Color.red()
        }
        
        embed = discord.Embed(
            title=f"Problem #{question['id']}: {question['title']}",
            description=question['description'],
            color=colors.get(question['difficulty'], discord.Color.blue()),
            url=question['leetcode_url']
        )
        
        embed.add_field(
            name="Difficulty",
            value=question['difficulty'],
            inline=True
        )
        
        embed.add_field(
            name="Category",
            value=question['category'],
            inline=True
        )
        
        if question.get('hints'):
            hints_text = "\n".join([f"💡 {hint}" for hint in question['hints']])
            embed.add_field(
                name="Hints",
                value=hints_text,
                inline=False
            )
        
        embed.add_field(
            name="Link",
            value=f"[Solve on LeetCode]({question['leetcode_url']})",
            inline=False
        )
        
        embed.set_footer(text=f"Solution will be posted later today! • {datetime.now().strftime('%B %d, %Y')}")
        
        return embed
    
    def create_question_list_embed(self, questions: list, page: int, total_pages: int,
                                   category: str = None, difficulty: str = None) -> discord.Embed:
        """Create embed for listing questions"""
        
        title = "📚 LeetCode 75 Questions"
        if category:
            title += f" - {category}"
        if difficulty:
            title += f" ({difficulty})"
        
        embed = discord.Embed(
            title=title,
            color=discord.Color.blue()
        )
        
        for q in questions:
            difficulty_emoji = {
                "Easy": "🟢",
                "Medium": "🟡",
                "Hard": "🔴"
            }
            
            embed.add_field(
                name=f"{difficulty_emoji.get(q['difficulty'], '⚪')} #{q['id']}: {q['title']}",
                value=f"*{q['category']}* | [Link]({q['leetcode_url']})",
                inline=False
            )
        
        embed.set_footer(text=f"Page {page}/{total_pages} • Total: {len(questions)} questions")
        
        return embed

async def setup(bot):
    await bot.add_cog(LeetCodeDaily(bot))