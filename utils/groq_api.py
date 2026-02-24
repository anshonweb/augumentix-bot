import aiohttp
import os
import logging

logger = logging.getLogger('discord')

class GroqAPI:
    """Groq API integration for generating LeetCode solutions and explanations"""
    
    def __init__(self):
        self.api_key = os.getenv('GROQ_API_KEY')
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
        self.model = "llama-3.3-70b-versatile"
        
        if not self.api_key:
            logger.warning("GROQ_API_KEY not set in environment variables")
    
    async def generate_solution(self, problem_title: str, problem_description: str, 
                               difficulty: str, hints: list = None, language: str = "python") -> dict:
        """
        Generate a complete solution with explanation for a LeetCode problem in specified language
        
        Args:
            language: "python", "javascript", "java", "cpp", or "go"
        
        Returns:
            dict with keys: solution_code, explanation, time_complexity, space_complexity, language
        """
        
        if not self.api_key:
            return {
                "error": "Groq API key not configured",
                "solution_code": "# API key not set",
                "explanation": "Please set GROQ_API_KEY in .env file",
                "time_complexity": "N/A",
                "space_complexity": "N/A",
                "language": language
            }
        lang_config = {
            "python": {"name": "Python", "syntax": "python", "comment": "#"},
            "javascript": {"name": "JavaScript", "syntax": "javascript", "comment": "//"},
            "java": {"name": "Java", "syntax": "java", "comment": "//"},
            "cpp": {"name": "C++", "syntax": "cpp", "comment": "//"},
            "go": {"name": "Go", "syntax": "go", "comment": "//"}
        }
        
        lang_info = lang_config.get(language, lang_config["python"])
        hints_text = "\n".join([f"- {hint}" for hint in hints]) if hints else "No hints provided"
        
        prompt = f"""You are a LeetCode expert. Provide a complete solution for this problem in {lang_info['name']}.

**Problem:** {problem_title}
**Difficulty:** {difficulty}
**Description:** {problem_description}
**Hints:** 
{hints_text}

Please provide:
1. A clean, working {lang_info['name']} solution with comments
2. A clear explanation of the approach (language-agnostic)
3. Time complexity analysis
4. Space complexity analysis

Format your response EXACTLY like this:

```{lang_info['syntax']}
{lang_info['comment']} Your solution code here with comments
```

**Explanation:**
[Your detailed explanation here]

**Time Complexity:** O(...)
**Space Complexity:** O(...)

Be concise but thorough. Focus on the optimal solution. Use proper {lang_info['name']} syntax and conventions."""

        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a helpful coding assistant specializing in LeetCode problems. Provide clean, optimal solutions with clear explanations."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.3, 
                    "max_tokens": 2000
                }
                
                async with session.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Groq API error: {response.status} - {error_text}")
                        return {
                            "error": f"API error: {response.status}",
                            "solution_code": "# Error generating solution",
                            "explanation": error_text,
                            "time_complexity": "N/A",
                            "space_complexity": "N/A"
                        }
                    
                    data = await response.json()
                    content = data['choices'][0]['message']['content']
                    result = self._parse_solution_response(content)
                    result['language'] = language
                    return result
                    
        except Exception as e:
            logger.error(f"Error generating solution: {e}")
            return {
                "error": str(e),
                "solution_code": f"{lang_info['comment']} Error generating solution",
                "explanation": f"Failed to generate solution: {str(e)}",
                "time_complexity": "N/A",
                "space_complexity": "N/A",
                "language": language
            }
    
    async def generate_multi_language_solutions(self, problem_title: str, problem_description: str,
                                               difficulty: str, hints: list = None) -> dict:
        """
        Generate solutions in multiple languages
        
        Returns:
            dict with keys for each language: python, javascript, java, cpp, go
            Each containing: solution_code, explanation, time_complexity, space_complexity, language
        """
        
        languages = ["python", "javascript", "java", "cpp", "go"]
        solutions = {}
        
        for lang in languages:
            logger.info(f"Generating {lang} solution for {problem_title}")
            solution = await self.generate_solution(
                problem_title,
                problem_description,
                difficulty,
                hints,
                language=lang
            )
            solutions[lang] = solution
        
        return solutions
    
    def _parse_solution_response(self, content: str) -> dict:
        """Parse Groq's response into structured format"""
        
        result = {
            "solution_code": "",
            "explanation": "",
            "time_complexity": "N/A",
            "space_complexity": "N/A"
        }
        
        try:
            code_patterns = ["```python", "```javascript", "```java", "```cpp", "```go", "```"]
            
            for pattern in code_patterns:
                if pattern in content:
                    code_start = content.find(pattern) + len(pattern)
                    code_end = content.find("```", code_start)
                    if code_end != -1:
                        result["solution_code"] = content[code_start:code_end].strip()
                        break
            
            if "**Explanation:**" in content:
                exp_start = content.find("**Explanation:**") + 16
                exp_end = content.find("**Time Complexity:**", exp_start)
                if exp_end == -1:
                    exp_end = len(content)
                result["explanation"] = content[exp_start:exp_end].strip()
            if "**Time Complexity:**" in content:
                tc_start = content.find("**Time Complexity:**") + 20
                tc_end = content.find("\n", tc_start)
                if tc_end == -1:
                    tc_end = content.find("**Space Complexity:**", tc_start)
                if tc_end == -1:
                    tc_end = len(content)
                result["time_complexity"] = content[tc_start:tc_end].strip()
            if "**Space Complexity:**" in content:
                sc_start = content.find("**Space Complexity:**") + 21
                result["space_complexity"] = content[sc_start:].strip()
            
        except Exception as e:
            logger.error(f"Error parsing solution response: {e}")
            result["explanation"] = content
        
        return result
    
    async def get_hints(self, problem_title: str, problem_description: str, 
                       num_hints: int = 3) -> list:
        """Generate helpful hints for a problem without giving away the solution"""
        
        if not self.api_key:
            return ["Groq API key not configured"]
        
        prompt = f"""Generate {num_hints} helpful hints for solving this LeetCode problem. 
The hints should guide thinking without revealing the complete solution.

**Problem:** {problem_title}
**Description:** {problem_description}

Provide exactly {num_hints} hints, each on a new line starting with a number.
Focus on:
1. Data structures to consider
2. Algorithm patterns
3. Edge cases to think about

Format:
1. [First hint]
2. [Second hint]
3. [Third hint]"""

        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "model": self.model,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.7,
                    "max_tokens": 500
                }
                async with session.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        content = data['choices'][0]['message']['content']
                        hints = []
                        for line in content.split('\n'):
                            line = line.strip()
                            if line and (line[0].isdigit() or line.startswith('-')):
                                hint = line.split('.', 1)[-1].strip()
                                if hint:
                                    hints.append(hint)
                        
                        return hints[:num_hints]
                    else:
                        logger.error(f"Error generating hints: {response.status}")
                        return ["Unable to generate hints"]
                        
        except Exception as e:
            logger.error(f"Error generating hints: {e}")
            return ["Unable to generate hints"]