"""
Content Cleaner Agent using GAME X SDK
Cleans and generates titles for crypto news content using GAME's AI capabilities
"""

import re
from typing import Optional, Dict, Any
from game_sdk.game.worker import Worker
from game_sdk.game.custom_types import Function, Argument, FunctionResultStatus
from app.core.config import settings
from loguru import logger


class ContentCleanerAgent:
    """
    Content cleaning and title generation using GAME X SDK
    """

    def __init__(self, create_worker_now: bool = True):
        """Initialize GAME X SDK Worker for content cleaning"""
        self.api_key = settings.GAME_API_KEY
        self.worker: Optional[Worker] = None
        
        if create_worker_now:
            self._setup_worker()

    def _setup_worker(self):
        """Initialize GAME SDK Worker with content cleaning capabilities"""
        try:
            # Define action space for the worker
            action_space = [
                Function(
                    fn_name="generate_engaging_title",
                    fn_description="Generate a concise, engaging title from crypto news or tweet content",
                    args=[
                        Argument(
                            name="text",
                            type="string",
                            description="The full content text to generate a title from"
                        ),
                        Argument(
                            name="source",
                            type="string",
                            description="Source type: 'rss' or 'twitter'"
                        ), 
                        Argument(
                            name="category",
                            type="string",
                            description="Content category (rwa, defi, macro_events, virtuals, etc.)"
                        )
                    ],
                    executable=self._generate_title_executable
                )
            ]

            # Create GAME Worker with AI-powered content processing
            self.worker = Worker(
                api_key=self.api_key,
                description="AI-powered content cleaner and title generator for crypto news aggregation",
                instruction=self._get_instruction(),
                get_state_fn=lambda result, state: state or {},
                action_space=action_space
            )

            logger.info("✓ Content Cleaner Worker initialized with GAME X SDK")

        except Exception as e:
            logger.error(f"❌ Failed to initialize Content Cleaner Worker")
            self.worker = None

    def _get_instruction(self) -> str:
        """Get detailed instruction for the content cleaning agent"""
        return """You are an expert AI content editor specializing in cryptocurrency and blockchain news.

Your primary responsibilities:

🎯 **Title Generation**:
Generate professional, engaging titles (50-80 characters) that:
- Capture the main topic clearly and concisely
- Include key elements: token names, numbers, events, actions
- Use professional journalism style (Bloomberg Crypto, CoinDesk, The Block)
- Remove promotional language, excessive emojis, and clickbait
- Focus on factual information and key insights

Examples of good titles:
✅ "Bitcoin ETF Approval Drives BTC to $45K Milestone"
✅ "Ethereum L2 Activity Hits Record 2.3M Daily Transactions"
✅ "Circle Launches USDC on Solana Network"
✅ "SEC Charges DeFi Protocol Over Unregistered Securities"

Examples of bad titles:
❌ "🚨🔥 BREAKING: You won't BELIEVE what just happened!!!"
❌ "This could change EVERYTHING in crypto!"
❌ "RT @user: Big news coming soon..."

🔍 **Category-Specific Guidelines**:

**RWA (Real World Assets)**:
- Focus on: tokenization, securities, real estate, bonds, commodities
- Emphasize regulatory aspects and institutional adoption
- Example: "Ondo Finance Tokenizes $100M Treasury Bonds"

**DeFi**:
- Highlight: protocols, TVL, yields, liquidity pools, AMMs
- Include specific numbers and percentages
- Example: "Aave TVL Surges 40% to $8.2B After V3 Launch"

**Macro Events**:
- Emphasize: regulations, SEC, Fed, ETFs, institutional moves
- Focus on policy impact and market implications
- Example: "Fed Maintains Rates as Bitcoin Correlation Weakens"

**Virtuals/AI**:
- Focus on: AI agents, virtual protocols, automation, gaming
- Highlight innovation and technical developments
- Example: "Virtual Protocol Launches AI Trading Agent Platform"

**Memecoins**:
- Capture: viral momentum, community events, influencer activity
- Include specific metrics when available
- Example: "Dogecoin Jumps 25% Following Elon Musk Tweet"

📝 **Content Cleaning Principles**:
- Remove "RT @username:" prefixes
- Strip excessive emojis (keep max 1-2 if contextually relevant)
- Remove URLs and @mentions
- Eliminate spam indicators (click here, DM me, link in bio)
- Preserve critical information: numbers, percentages, token symbols
- Maintain factual accuracy

🎨 **Tone and Style**:
- Professional but accessible
- Factual and objective
- Avoid sensationalism
- Clear and direct
- Industry-standard terminology

When asked to generate a title, respond ONLY with the title text, nothing else. No explanations, no preambles."""

    async def _generate_title_executable(
        self,
        text: str,
        source: str,
        category: str
    ) -> tuple:
        """
        Executable function for GAME SDK to generate titles
        This is called by the Worker when processing requests
        
        Args:
            text: Content text to generate title from
            source: 'rss' or 'twitter'
            category: Content category
            
        Returns:
            Tuple of (status, message, result_dict)
        """
        try:
            if not text or len(text) < 20:
                return (
                    FunctionResultStatus.FAILED,
                    "Text too short for title generation",
                    {"title": "Crypto Update"}
                )

            # Clean the text first
            cleaned_text = self.clean_text(text)
            
            # For very short cleaned text, use fallback
            if len(cleaned_text) < 30:
                title = self._extract_title_fallback(cleaned_text)
                return (
                    FunctionResultStatus.DONE,
                    "Generated title using fallback",
                    {"title": title}
                )

            # Generate title using rule-based approach + context
            title = self._generate_smart_title(cleaned_text, category)
            
            logger.debug(f"✓ Generated title for {source}/{category}: {title}")
            
            return (
                FunctionResultStatus.DONE,
                "Title generated successfully",
                {"title": title}
            )

        except Exception as e:
            logger.error(f"Error in title generation: {e}")
            fallback_title = self._extract_title_fallback(text)
            return (
                FunctionResultStatus.FAILED,
                f"Error: {str(e)}",
                {"title": fallback_title}
            )

    def _generate_smart_title(self, text: str, category: str) -> str:
        """
        Generate smart title using context-aware rules
        
        Args:
            text: Cleaned text content
            category: Content category for context
            
        Returns:
            Generated title
        """
        # Category-specific keywords to prioritize
        category_focus = {
            "rwa": ["tokenize", "tokenization", "bonds", "treasury", "securities", "real estate"],
            "defi": ["tvl", "yield", "liquidity", "apy", "protocol", "dex", "lending"],
            "macro_events": ["sec", "fed", "etf", "regulation", "approval", "government"],
            "virtuals": ["ai", "virtual", "agent", "game", "protocol"],
            "memecoins": ["doge", "shib", "pepe", "bonk", "meme"]
        }

        # Extract key information
        title_parts = []
        
        # Look for token symbols
        tokens = re.findall(r'\$?[A-Z]{2,10}(?=\s|$|,)', text)
        if tokens:
            title_parts.append(tokens[0])
        
        # Look for numbers/percentages (often important)
        numbers = re.findall(r'\d+(?:\.\d+)?%|\$\d+(?:\.\d+)?[BMK]?', text)
        if numbers:
            title_parts.append(numbers[0])
        
        # Extract main action/event from first sentence
        first_sentence = text.split('.')[0].strip()
        
        # Find category-relevant terms
        relevant_terms = category_focus.get(category, [])
        found_terms = [term for term in relevant_terms if term.lower() in first_sentence.lower()]
        
        # Build title intelligently
        if title_parts:
            # Start with token/number
            base = ' '.join(title_parts[:2])
            
            # Add context from sentence
            words = first_sentence.split()[:15]  # First 15 words
            context = ' '.join(words)
            
            # Combine
            title = f"{base}: {context}"
        else:
            # Use first sentence directly
            words = first_sentence.split()[:12]
            title = ' '.join(words)
        
        # Clean up and truncate
        title = re.sub(r'\s+', ' ', title).strip()
        if len(title) > 80:
            title = title[:77] + "..."
        
        # Capitalize properly
        title = title[0].upper() + title[1:] if title else "Crypto Update"
        
        return title

    def _extract_title_fallback(self, text: str, max_length: int = 80) -> str:
        """
        Simple fallback title extraction without AI
        
        Args:
            text: Text to extract title from
            max_length: Maximum title length
            
        Returns:
            Extracted title
        """
        if not text:
            return "Crypto Update"

        # Remove emojis
        text = re.sub(r'[^\w\s$%.,!?-]', '', text)
        
        # Get first sentence
        sentences = re.split(r'[.!?]', text)
        if sentences and len(sentences[0]) > 15:
            title = sentences[0].strip()
        else:
            title = text[:max_length]

        # Clean and truncate
        title = title.strip()
        if len(title) > max_length:
            title = title[:max_length-3] + "..."

        return title or "Crypto Update"

    def clean_text(self, text: str) -> str:
        """
        Clean text content - removes noise and formatting issues
        
        Args:
            text: Raw text to clean
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""

        # Remove RT mentions
        text = re.sub(r'^RT\s+@\w+:\s*', '', text)
        
        # Remove @mentions but keep rest of content
        text = re.sub(r'@\w+', '', text)
        
        # Remove URLs
        text = re.sub(
            r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
            '',
            text
        )
        
        # Handle emojis - remove excessive ones but keep a few relevant ones
        emoji_pattern = re.compile("["
            u"\U0001F600-\U0001F64F"  # emoticons
            u"\U0001F300-\U0001F5FF"  # symbols & pictographs
            u"\U0001F680-\U0001F6FF"  # transport & map symbols
            u"\U0001F1E0-\U0001F1FF"  # flags
            u"\U00002702-\U000027B0"
            u"\U000024C2-\U0001F251"
            "]+", flags=re.UNICODE)
        
        # Extract emojis
        emojis = emoji_pattern.findall(text)
        text = emoji_pattern.sub(' ', text)
        
        # Add back max 1 emoji if relevant
        relevant_emojis = ['🚀', '📈', '💰', '🔥', '⚡', '🎯']
        if emojis:
            for emoji in emojis:
                if emoji in relevant_emojis:
                    text = emoji + ' ' + text
                    break
        
        # Clean whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Remove common spam patterns
        spam_patterns = [
            r'click here',
            r'follow for more',
            r'link in bio',
            r'dm for',
            r'check my profile',
            r'tap the link',
            r'join our telegram'
        ]
        for pattern in spam_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        return text.strip()

    def is_spam_content(self, text: str) -> bool:
        """
        Detect if content is spam/promotional
        
        Args:
            text: Content to check
            
        Returns:
            True if spam, False otherwise
        """
        if not text or len(text) < 10:
            return True

        text_lower = text.lower()
        spam_score = 0
        
        # High-confidence spam keywords
        spam_keywords = [
            'buy now', 'limited offer', 'guaranteed profit',
            'risk free', 'double your', 'free airdrop',
            'claim now', 'send to wallet', 'dm me',
            'private signal', '100x guaranteed', 'pump incoming'
        ]
        
        for keyword in spam_keywords:
            if keyword in text_lower:
                spam_score += 2
        
        # Medium-confidence indicators
        sus_keywords = [
            'click here', 'follow for', 'link in bio',
            'telegram', 'join our', 'exclusive'
        ]
        
        for keyword in sus_keywords:
            if keyword in text_lower:
                spam_score += 1
        
        # Check for excessive caps
        if len(text) > 20:
            caps_ratio = sum(1 for c in text if c.isupper()) / len(text)
            if caps_ratio > 0.5:
                spam_score += 2
        
        # Check for excessive emojis (more than 15% of text)
        emoji_count = len(re.findall(r'[^\w\s,.]', text))
        if len(text) > 0 and (emoji_count / len(text)) > 0.15:
            spam_score += 1
        
        # Check for excessive exclamation marks
        if text.count('!') > 3:
            spam_score += 1
        
        return spam_score >= 4

    async def generate_title_with_ai(
        self,
        text: str,
        source: str,
        category: str
    ) -> str:
        """
        Generate title using GAME X SDK AI agent
        
        Args:
            text: Content text
            source: 'rss' or 'twitter'
            category: Content category
            
        Returns:
            Generated title string
        """
        try:
            if not self.worker:
                logger.warning("GAME Worker not initialized, using smart fallback")
                cleaned = self.clean_text(text)
                return self._generate_smart_title(cleaned, category)

            # Use the worker's function
            status, message, result = await self._generate_title_executable(
                text, source, category
            )
            
            if status == FunctionResultStatus.DONE and result.get("title"):
                return result["title"]
            else:
                logger.warning(f"Title generation returned non-success: {message}")
                cleaned = self.clean_text(text)
                return self._generate_smart_title(cleaned, category)

        except Exception as e:
            logger.warning(f"AI title generation failed: {e}, using fallback")
            cleaned = self.clean_text(text)
            return self._generate_smart_title(cleaned, category)


# Lazy singleton initialization to avoid network calls at import time
_content_cleaner_agent: Optional[ContentCleanerAgent] = None


# app/agents/content_cleaner.py

def get_content_cleaner_agent(create_if_missing: bool = True) -> Optional[ContentCleanerAgent]:
    global _content_cleaner_agent

    if _content_cleaner_agent is None and create_if_missing:
        _content_cleaner_agent = ContentCleanerAgent(create_worker_now=True)

    return _content_cleaner_agent
