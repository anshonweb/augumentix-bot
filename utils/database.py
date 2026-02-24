import asyncpg
import os
from datetime import datetime
import logging

logger = logging.getLogger('discord')

class Database:
    def __init__(self):
        self.pool = None
        self.database_url = os.getenv('DATABASE_URL')
        
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable not set")
    
    async def init_db(self):
        try:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=1,
                max_size=10,
                command_timeout=60,
                statement_cache_size=0
            )
            
            logger.info('Database pool created')
            async with self.pool.acquire() as conn:
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        discord_id BIGINT PRIMARY KEY,
                        leetcode_username TEXT NOT NULL,
                        total_solved INTEGER DEFAULT 0,
                        weekly_solved INTEGER DEFAULT 0,
                        last_updated TIMESTAMP,
                        linked_at TIMESTAMP DEFAULT NOW()
                    )
                ''')
                
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS submissions (
                        id SERIAL PRIMARY KEY,
                        discord_id BIGINT REFERENCES users(discord_id) ON DELETE CASCADE,
                        problem_title TEXT,
                        problem_slug TEXT,
                        difficulty TEXT,
                        timestamp BIGINT,
                        week_number INTEGER
                    )
                ''')
                
                await conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_submissions_discord_id 
                    ON submissions(discord_id)
                ''')
                
                await conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_submissions_week 
                    ON submissions(week_number)
                ''')
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS ai_news_assignments (
                        id SERIAL PRIMARY KEY,
                        discord_id BIGINT,
                        assigned_date DATE DEFAULT CURRENT_DATE,
                        completed BOOLEAN DEFAULT FALSE,
                        completed_date TIMESTAMP
                    )
                ''')
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS daily_challenges (
                        id SERIAL PRIMARY KEY,
                        question_id INTEGER NOT NULL,
                        posted_date DATE DEFAULT CURRENT_DATE,
                        question_message_id BIGINT,
                        solution_message_id BIGINT,
                        solution_posted BOOLEAN DEFAULT FALSE
                    )
                ''')
                
                await conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_daily_challenges_date 
                    ON daily_challenges(posted_date)
                ''')
                
                logger.info('Database tables created/verified')
        
        except Exception as e:
            logger.error(f'Database initialization error: {e}')
            raise
    
    async def close(self):
        if self.pool:
            await self.pool.close()
            logger.info('Database pool closed')

    async def link_user(self, discord_id: int, leetcode_username: str):
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO users (discord_id, leetcode_username, last_updated)
                VALUES ($1, $2, $3)
                ON CONFLICT (discord_id) 
                DO UPDATE SET leetcode_username = $2, last_updated = $3
            ''', discord_id, leetcode_username, datetime.now())
    
    async def get_user(self, discord_id: int):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT * FROM users WHERE discord_id = $1',
                discord_id
            )
            return row
    
    async def get_all_users(self):
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                'SELECT discord_id, leetcode_username FROM users'
            )
            return [(row['discord_id'], row['leetcode_username']) for row in rows]
    
    async def update_user_stats(self, discord_id: int, total_solved: int, weekly_solved: int):
        async with self.pool.acquire() as conn:
            await conn.execute('''
                UPDATE users 
                SET total_solved = $1, weekly_solved = $2, last_updated = $3
                WHERE discord_id = $4
            ''', total_solved, weekly_solved, datetime.now(), discord_id)
    
    async def unlink_user(self, discord_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute('DELETE FROM users WHERE discord_id = $1', discord_id)
    
    async def add_submission(self, discord_id: int, problem_title: str, 
                           problem_slug: str, difficulty: str, timestamp: int):
        week_number = datetime.fromtimestamp(timestamp).isocalendar()[1]
        
        async with self.pool.acquire() as conn:
            existing = await conn.fetchrow('''
                SELECT id FROM submissions 
                WHERE discord_id = $1 AND problem_slug = $2 AND timestamp = $3
            ''', discord_id, problem_slug, timestamp)
            
            if not existing:
                await conn.execute('''
                    INSERT INTO submissions 
                    (discord_id, problem_title, problem_slug, difficulty, timestamp, week_number)
                    VALUES ($1, $2, $3, $4, $5, $6)
                ''', discord_id, problem_title, problem_slug, difficulty, timestamp, week_number)
                return True
            
            return False
    
    async def get_user_submissions_this_week(self, discord_id: int):
        current_week = datetime.now().isocalendar()[1]
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch('''
                SELECT problem_title, difficulty, timestamp
                FROM submissions
                WHERE discord_id = $1 AND week_number = $2
                ORDER BY timestamp DESC
            ''', discord_id, current_week)
            
            return [(row['problem_title'], row['difficulty'], row['timestamp']) for row in rows]
    
    async def get_weekly_leaderboard(self, limit: int = 10):
        async with self.pool.acquire() as conn:
            rows = await conn.fetch('''
                SELECT discord_id, leetcode_username, weekly_solved
                FROM users
                WHERE weekly_solved > 0
                ORDER BY weekly_solved DESC
                LIMIT $1
            ''', limit)
            
            return [(row['discord_id'], row['leetcode_username'], row['weekly_solved']) 
                    for row in rows]
    
    async def reset_weekly_stats(self):
        async with self.pool.acquire() as conn:
            await conn.execute('UPDATE users SET weekly_solved = 0')
    
    async def get_current_ai_news_assignee(self):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow('''
                SELECT discord_id, completed
                FROM ai_news_assignments
                WHERE assigned_date >= CURRENT_DATE - INTERVAL '7 days'
                AND completed = FALSE
                ORDER BY assigned_date DESC
                LIMIT 1
            ''')
            return row
    
    async def set_ai_news_assignee(self, discord_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO ai_news_assignments (discord_id, assigned_date)
                VALUES ($1, CURRENT_DATE)
            ''', discord_id)
    
    async def mark_ai_news_complete(self, discord_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute('''
                UPDATE ai_news_assignments
                SET completed = TRUE, completed_date = NOW()
                WHERE discord_id = $1 
                AND assigned_date >= CURRENT_DATE - INTERVAL '7 days'
            ''', discord_id)
    
    async def get_recent_ai_news_assignees(self, weeks: int = 4):
        async with self.pool.acquire() as conn:
            rows = await conn.fetch('''
                SELECT DISTINCT discord_id
                FROM ai_news_assignments
                WHERE assigned_date >= CURRENT_DATE - INTERVAL '%s weeks'
            ''' % weeks)
            
            return [row['discord_id'] for row in rows]
    
    async def get_todays_challenge(self):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow('''
                SELECT * FROM daily_challenges
                WHERE posted_date = CURRENT_DATE
            ''')
            return row
    
    async def post_daily_challenge(self, question_id: int, question_message_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO daily_challenges (question_id, posted_date, question_message_id)
                VALUES ($1, CURRENT_DATE, $2)
            ''', question_id, question_message_id)
    
    async def post_challenge_solution(self, challenge_id: int, solution_message_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute('''
                UPDATE daily_challenges
                SET solution_posted = TRUE, solution_message_id = $1
                WHERE id = $2
            ''', solution_message_id, challenge_id)
    
    async def get_posted_question_ids(self):
        async with self.pool.acquire() as conn:
            rows = await conn.fetch('''
                SELECT DISTINCT question_id FROM daily_challenges
            ''')
            return [row['question_id'] for row in rows]
    
    async def get_challenge_stats(self):
        async with self.pool.acquire() as conn:
            total = await conn.fetchval('''
                SELECT COUNT(*) FROM daily_challenges
            ''')
            
            with_solution = await conn.fetchval('''
                SELECT COUNT(*) FROM daily_challenges
                WHERE solution_posted = TRUE
            ''')
            
            return {
                'total_posted': total or 0,
                'solutions_posted': with_solution or 0
            }