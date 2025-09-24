import asyncio
import aiohttp
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import json
from typing import List, Dict, Optional
import anthropic
import os
from urllib.parse import urljoin, quote_plus
import re

class RobustArticleScraper:
    def __init__(self, anthropic_api_key: str):
        # Try multiple methods to create Anthropic client
        self.client = None
        self.api_key = anthropic_api_key
        self.session = None
            
        # Multiple news sources with RSS feeds and APIs
        self.news_sources = {
            'hacker_news': {
                'rss': 'https://hnrss.org/newest',
                'search_rss': 'https://hnrss.org/newest?q={keywords}',
                'type': 'rss'
            },
            'reddit_tech': {
                'rss': 'https://www.reddit.com/r/technology/.rss',
                'search_url': 'https://www.reddit.com/search.json?q={keywords}&sort=new&limit={limit}',
                'type': 'reddit_api'
            },
            'arxiv': {
                'search_url': 'http://export.arxiv.org/api/query?search_query=all:{keywords}&start=0&max_results={limit}&sortBy=submittedDate&sortOrder=descending',
                'type': 'arxiv_api'
            },
            'newsapi_sources': [
                'https://feeds.bbci.co.uk/news/technology/rss.xml',
                'https://rss.cnn.com/rss/edition.rss',
                'https://feeds.reuters.com/reuters/technologyNews',
                'https://www.wired.com/feed/rss',
                'https://techcrunch.com/feed/',
                'https://www.theverge.com/rss/index.xml',
                'https://arstechnica.com/feed/',
                'https://www.engadget.com/rss.xml'
            ]
        }
        
        if anthropic_api_key and anthropic_api_key != 'dummy-key-for-testing':
            try:
                # Method 1: Standard creation
                self.client = anthropic.Anthropic(api_key=anthropic_api_key)
                print("✅ Anthropic client created successfully")
            except Exception as e:
                print(f"❌ Standard client creation failed: {e}")
                try:
                    # Method 2: With explicit parameters
                    self.client = anthropic.Anthropic(
                        api_key=anthropic_api_key,
                        base_url="https://api.anthropic.com",
                        max_retries=2
                    )
                    print("✅ Anthropic client created with explicit parameters")
                except Exception as e2:
                    print(f"❌ Alternative client creation failed: {e2}")
                    print("⚠️ AI filtering will be disabled - using simple keyword filtering")
                    self.client = None
        else:
            print("⚠️ No valid API key provided - AI filtering disabled")

    async def __aenter__(self):
        # Create session with minimal configuration to avoid proxy issues
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=30)
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def search_hacker_news(self, keywords: str, limit: int = 10) -> List[Dict]:
        """Search Hacker News using RSS"""
        try:
            search_url = self.news_sources['hacker_news']['search_rss'].format(keywords=quote_plus(keywords))
            print(f"Searching Hacker News: {search_url}")
            
            async with self.session.get(search_url) as response:
                if response.status == 200:
                    content = await response.text()
                    feed = feedparser.parse(content)
                    
                    articles = []
                    for entry in feed.entries[:limit]:
                        articles.append({
                            'title': entry.title,
                            'url': entry.link,
                            'source': 'Hacker News',
                            'timestamp': datetime.now().isoformat(),
                            'description': getattr(entry, 'summary', '')[:200]
                        })
                    return articles
        except Exception as e:
            print(f"Hacker News search failed: {e}")
        return []

    async def search_reddit(self, keywords: str, limit: int = 10) -> List[Dict]:
        """Search Reddit using their JSON API"""
        try:
            search_url = f"https://www.reddit.com/search.json?q={quote_plus(keywords)}&sort=new&limit={limit}"
            
            print(f"Searching Reddit: {search_url}")
            
            async with self.session.get(search_url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    articles = []
                    for post in data.get('data', {}).get('children', []):
                        post_data = post.get('data', {})
                        if post_data.get('url'):
                            articles.append({
                                'title': post_data.get('title', ''),
                                'url': post_data.get('url', ''),
                                'source': f"Reddit - r/{post_data.get('subreddit', 'unknown')}",
                                'timestamp': datetime.now().isoformat(),
                                'description': post_data.get('selftext', '')[:200]
                            })
                    return articles[:limit]
        except Exception as e:
            print(f"Reddit search failed: {e}")
        return []

    async def search_arxiv(self, keywords: str, limit: int = 5) -> List[Dict]:
        """Search arXiv for academic papers"""
        try:
            search_url = self.news_sources['arxiv']['search_url'].format(
                keywords=quote_plus(keywords), limit=limit
            )
            print(f"Searching arXiv: {search_url}")
            
            async with self.session.get(search_url) as response:
                if response.status == 200:
                    content = await response.text()
                    # Parse XML response
                    from xml.etree import ElementTree as ET
                    root = ET.fromstring(content)
                    
                    articles = []
                    for entry in root.findall('{http://www.w3.org/2005/Atom}entry'):
                        title = entry.find('{http://www.w3.org/2005/Atom}title')
                        link = entry.find('{http://www.w3.org/2005/Atom}id')
                        summary = entry.find('{http://www.w3.org/2005/Atom}summary')
                        
                        if title is not None and link is not None:
                            articles.append({
                                'title': title.text.strip(),
                                'url': link.text,
                                'source': 'arXiv',
                                'timestamp': datetime.now().isoformat(),
                                'description': summary.text[:200] if summary is not None else ''
                            })
                    return articles
        except Exception as e:
            print(f"arXiv search failed: {e}")
        return []

    async def search_rss_feeds(self, keywords: str, limit: int = 15) -> List[Dict]:
        """Search multiple RSS feeds for articles"""
        articles = []
        keywords_lower = keywords.lower().split()
        
        for feed_url in self.news_sources['newsapi_sources']:
            try:
                print(f"Checking RSS feed: {feed_url}")
                
                async with self.session.get(feed_url) as response:
                    if response.status == 200:
                        content = await response.text()
                        feed = feedparser.parse(content)
                        
                        for entry in feed.entries:
                            # Check if keywords match title or description
                            title = entry.title.lower() if hasattr(entry, 'title') else ''
                            description = getattr(entry, 'summary', '') or getattr(entry, 'description', '')
                            description = description.lower()
                            
                            # Simple keyword matching
                            if any(keyword in title or keyword in description for keyword in keywords_lower):
                                articles.append({
                                    'title': entry.title if hasattr(entry, 'title') else 'No Title',
                                    'url': entry.link if hasattr(entry, 'link') else '',
                                    'source': feed.feed.title if hasattr(feed.feed, 'title') else 'RSS Feed',
                                    'timestamp': datetime.now().isoformat(),
                                    'description': description[:200]
                                })
                        
                        if len(articles) >= limit:
                            break
                            
            except Exception as e:
                print(f"RSS feed {feed_url} failed: {e}")
                continue
        
        return articles[:limit]

    async def search_newsapi_fallback(self, keywords: str, limit: int = 10) -> List[Dict]:
        """Fallback: Try a simple news aggregator search"""
        try:
            # Try AllSides news search (has a simple API)
            search_url = f"https://www.allsides.com/search/node/{quote_plus(keywords)}"
            
            async with self.session.get(search_url) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    articles = []
                    # Look for article links
                    for link in soup.find_all('a', href=True)[:limit]:
                        title = link.get_text().strip()
                        if len(title) > 20 and 'http' in link['href']:
                            articles.append({
                                'title': title,
                                'url': link['href'],
                                'source': 'AllSides',
                                'timestamp': datetime.now().isoformat(),
                                'description': ''
                            })
                    
                    return articles[:limit]
        except Exception as e:
            print(f"NewsAPI fallback failed: {e}")
        return []

    async def scrape_article_content(self, url: str) -> str:
        """Enhanced article content scraping"""
        try:
            async with self.session.get(url, timeout=15) as response:
                if response.status != 200:
                    return ""
                    
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Remove unwanted elements
                for element in soup(['script', 'style', 'nav', 'header', 'footer', 'sidebar', 'aside', 'advertisement']):
                    element.decompose()
                
                # Try multiple content selectors (ordered by preference)
                content_selectors = [
                    'article',
                    '[role="main"]',
                    '.post-content',
                    '.article-content',
                    '.content',
                    '.entry-content',
                    '.post-body',
                    'main',
                    '.story-body',
                    '#content'
                ]
                
                content = None
                for selector in content_selectors:
                    content = soup.select_one(selector)
                    if content and len(content.get_text(strip=True)) > 200:
                        break
                
                if not content:
                    content = soup.body
                
                if content:
                    text = content.get_text(separator=' ', strip=True)
                    # Clean up the text
                    text = re.sub(r'\s+', ' ', text)  # Multiple whitespace to single space
                    return text[:5000]  # Limit to 5000 chars
                    
        except Exception as e:
            print(f"Error scraping {url}: {e}")
        return ""

    def filter_relevant_articles(self, articles: List[Dict], user_interests: str) -> List[Dict]:
        """Use Claude to filter articles based on user interests, with fallback to simple filtering"""
        if not articles:
            print("No articles to filter")
            return []
        
        # If we have a working Anthropic client, use AI filtering
        if self.client:
            print(f"🤖 Filtering {len(articles)} articles with AI...")
            
            # Create article summaries for AI
            article_summaries = []
            for i, art in enumerate(articles):
                summary = f"Article {i+1}:\nTitle: {art['title']}\nSource: {art['source']}"
                if art.get('description'):
                    summary += f"\nDescription: {art['description'][:150]}"
                article_summaries.append(summary)
            
            articles_text = "\n---\n".join(article_summaries)
            
            prompt = f"""Filter these articles based on user interests.

            User Interests: {user_interests}

            Articles:
            {articles_text}

            Instructions:
            1. Evaluate each article's relevance to the user's stated interests
            2. Consider both the title and description/summary when available
            3. Be somewhat generous - include articles that are tangentially related
            4. Return ONLY a JSON array of article numbers (1-indexed) that are relevant

            Return format: [1, 3, 5] or [] if none are relevant

            Do not include any explanation, just the JSON array."""

            try:
                message = self.client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=500,
                    messages=[{"role": "user", "content": prompt}]
                )
                
                response_text = message.content[0].text.strip()
                print(f"🤖 Claude response: {response_text}")
                
                # Extract JSON array
                start = response_text.find('[')
                end = response_text.find(']') + 1
                if start != -1 and end > start:
                    relevant_indices = json.loads(response_text[start:end])
                    relevant_articles = [articles[i-1] for i in relevant_indices if 0 < i <= len(articles)]
                    print(f"🎯 AI found {len(relevant_articles)} relevant articles")
                    return relevant_articles
            except Exception as e:
                print(f"❌ AI filtering failed: {e}")
        
        # Fallback to simple keyword filtering
        print(f"📝 Using simple keyword filtering for {len(articles)} articles")
        keywords = user_interests.lower().split()
        
        filtered_articles = []
        for article in articles:
            title_lower = article.get('title', '').lower()
            description_lower = article.get('description', '').lower()
            
            if any(keyword in title_lower or keyword in description_lower 
                for keyword in keywords if len(keyword) > 3):
                filtered_articles.append(article)
        
        if not filtered_articles:
            filtered_articles = articles[:10]
        
        print(f"📝 Simple filtering found {len(filtered_articles)} potentially relevant articles")
        return filtered_articles[:15]

    async def search_all_sources(self, keywords: str, interests: str, num_results: int = 20) -> List[Dict]:
        """Search all available sources and combine results"""
        print(f"🔍 Searching for: '{keywords}'")
        
        # Run all searches concurrently
        search_tasks = [
            self.search_hacker_news(keywords, num_results//4),
            self.search_reddit(keywords, num_results//4),
            self.search_arxiv(keywords, min(5, num_results//4)),
            self.search_rss_feeds(keywords, num_results//2),
            self.search_newsapi_fallback(keywords, num_results//4)
        ]
        
        results = await asyncio.gather(*search_tasks, return_exceptions=True)
        
        # Combine all articles
        all_articles = []
        source_counts = {}
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"Search {i} failed: {result}")
                continue
            if result:
                all_articles.extend(result)
                for article in result:
                    source = article['source']
                    source_counts[source] = source_counts.get(source, 0) + 1
        
        print(f"📊 Found articles from: {source_counts}")
        
        # Remove duplicates based on URL
        seen_urls = set()
        unique_articles = []
        for article in all_articles:
            if article['url'] not in seen_urls:
                seen_urls.add(article['url'])
                unique_articles.append(article)
        
        print(f"📝 {len(unique_articles)} unique articles before filtering")
        
        # Filter with AI
        relevant_articles = self.filter_relevant_articles(unique_articles, interests)
        
        # Scrape content for the top relevant articles
        print("🔍 Scraping content for relevant articles...")
        for i, article in enumerate(relevant_articles[:10]):  # Limit content scraping
            if article['url']:
                content = await self.scrape_article_content(article['url'])
                article['content_preview'] = content[:500] + "..." if len(content) > 500 else content
                print(f"  ✓ Scraped content for article {i+1}")
        
        return relevant_articles[:num_results]

# Keep the old class name for compatibility
ArticleScraper = RobustArticleScraper

# Example usage
async def main():
    API_KEY = os.getenv("ANTHROPIC_API_KEY", "your-api-key-here")
    
    user_interests = """
    I'm interested in:
    - AI and machine learning developments
    - Climate tech and renewable energy  
    - Space exploration and astronomy
    - Breakthrough scientific research
    """
    
    async with RobustArticleScraper(API_KEY) as scraper:
        articles = await scraper.search_all_sources(
            keywords="AI breakthroughs",
            interests=user_interests,
            num_results=15
        )
        
        print(f"\n🎯 Final Results: {len(articles)} articles")
        for i, article in enumerate(articles, 1):
            print(f"\n{i}. {article['title']}")
            print(f"   📰 Source: {article['source']}")
            print(f"   🔗 URL: {article['url'][:80]}...")
            if article.get('content_preview'):
                print(f"   📄 Preview: {article['content_preview'][:150]}...")

if __name__ == "__main__":
    asyncio.run(main())