from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import asyncio
import os
from article_scraper import ArticleScraper
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

app = Flask(__name__)
CORS(app)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>AI Article Scraper</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        :root {
            --bg-color: #ffffff;
            --text-color: #333333;
            --card-bg: #f8f9fa;
            --border-color: #dee2e6;
            --primary-color: #007bff;
            --primary-hover: #0056b3;
            --input-bg: #ffffff;
            --shadow: 0 2px 4px rgba(0,0,0,0.1);
            --article-bg: #ffffff;
        }

        [data-theme="dark"] {
            --bg-color: #1a1a1a;
            --text-color: #e0e0e0;
            --card-bg: #2d2d2d;
            --border-color: #404040;
            --primary-color: #4a9eff;
            --primary-hover: #357abd;
            --input-bg: #383838;
            --shadow: 0 2px 4px rgba(0,0,0,0.3);
            --article-bg: #252525;
        }

        * {
            transition: background-color 0.3s ease, border-color 0.3s ease, color 0.3s ease;
        }

        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px; 
            margin: 0 auto; 
            padding: 20px;
            background-color: var(--bg-color);
            color: var(--text-color);
            line-height: 1.6;
        }

        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
        }

        h1 { 
            color: var(--text-color);
            margin: 0;
            font-size: 2.2em;
            font-weight: 600;
        }

        .theme-toggle {
            background: var(--card-bg);
            border: 2px solid var(--border-color);
            border-radius: 25px;
            padding: 8px 16px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 14px;
            font-weight: 500;
            color: var(--text-color);
        }

        .theme-toggle:hover {
            background: var(--primary-color);
            color: white;
            border-color: var(--primary-color);
        }

        .search-box { 
            background: var(--card-bg);
            padding: 30px; 
            border-radius: 12px; 
            margin-bottom: 30px;
            border: 1px solid var(--border-color);
            box-shadow: var(--shadow);
        }

        label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: var(--text-color);
        }

        input, textarea { 
            width: 100%; 
            padding: 12px 16px; 
            margin: 5px 0 20px 0; 
            box-sizing: border-box;
            border: 2px solid var(--border-color);
            border-radius: 8px;
            background-color: var(--input-bg);
            color: var(--text-color);
            font-size: 16px;
            font-family: inherit;
        }

        input:focus, textarea:focus {
            outline: none;
            border-color: var(--primary-color);
            box-shadow: 0 0 0 3px rgba(74, 158, 255, 0.1);
        }

        button { 
            background: var(--primary-color);
            color: white; 
            padding: 14px 28px; 
            border: none; 
            border-radius: 8px; 
            cursor: pointer; 
            font-size: 16px;
            font-weight: 600;
            transition: all 0.2s ease;
        }

        button:hover { 
            background: var(--primary-hover);
            transform: translateY(-1px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }

        button:active {
            transform: translateY(0);
        }

        .article { 
            background: var(--article-bg);
            border: 1px solid var(--border-color);
            padding: 24px; 
            margin: 16px 0; 
            border-radius: 12px;
            box-shadow: var(--shadow);
        }

        .article:hover {
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            transform: translateY(-2px);
        }

        .article h3 { 
            margin-top: 0; 
            color: var(--primary-color);
            font-size: 1.3em;
            line-height: 1.4;
            margin-bottom: 12px;
        }

        .source { 
            color: var(--text-color);
            opacity: 0.7;
            font-size: 14px;
            font-weight: 500;
            margin-bottom: 8px;
        }

        .article-url {
            color: var(--primary-color);
            text-decoration: none;
            font-size: 14px;
            word-break: break-all;
        }

        .article-url:hover {
            text-decoration: underline;
        }

        .preview { 
            color: var(--text-color);
            margin-top: 16px; 
            line-height: 1.6;
            font-size: 15px;
            opacity: 0.9;
        }

        .loading { 
            display: none; 
            color: var(--primary-color);
            font-weight: 500;
            margin-left: 12px;
        }

        .loading.show {
            display: inline;
        }

        .results-header {
            font-size: 1.5em;
            margin-bottom: 20px;
            color: var(--text-color);
            font-weight: 600;
        }

        .no-results {
            text-align: center;
            padding: 40px 20px;
            color: var(--text-color);
            opacity: 0.7;
            font-size: 16px;
        }

        @media (max-width: 768px) {
            body { padding: 15px; }
            .header { flex-direction: column; gap: 15px; }
            .search-box { padding: 20px; }
            .article { padding: 18px; }
        }
    </style>
</head>
<body data-theme="light">
    <div class="header">
        <h1>🔍 AI Article Scraper</h1>
        <button class="theme-toggle" onclick="toggleTheme()">
            <span id="theme-icon">🌙</span>
            <span id="theme-text">Dark Mode</span>
        </button>
    </div>
    
    <div class="search-box">
        <label><strong>Your Interests (helps AI filter relevant articles):</strong></label>
        <textarea id="interests" rows="4" placeholder="e.g., I'm interested in AI, climate tech, space exploration, scientific breakthroughs...">I'm interested in artificial intelligence, machine learning, and technology innovation.</textarea>
        
        <label><strong>Search Keywords:</strong></label>
        <input type="text" id="keywords" placeholder="e.g., AI breakthroughs, climate solutions, space discoveries">
        
        <label><strong>Number of Results:</strong></label>
        <input type="number" id="numResults" value="15" min="5" max="50">
        
        <button onclick="searchArticles()">
            Search Articles
            <span class="loading" id="loading">🔍 Searching and filtering...</span>
        </button>
    </div>
    
    <div id="results"></div>
    
    <script>
        // Theme management
        function toggleTheme() {
            const body = document.body;
            const currentTheme = body.getAttribute('data-theme');
            const newTheme = currentTheme === 'light' ? 'dark' : 'light';
            
            body.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            
            updateThemeButton(newTheme);
        }

        function updateThemeButton(theme) {
            const icon = document.getElementById('theme-icon');
            const text = document.getElementById('theme-text');
            
            if (theme === 'dark') {
                icon.textContent = '☀️';
                text.textContent = 'Light Mode';
            } else {
                icon.textContent = '🌙';
                text.textContent = 'Dark Mode';
            }
        }

        // Load saved theme
        document.addEventListener('DOMContentLoaded', function() {
            const savedTheme = localStorage.getItem('theme') || 'light';
            document.body.setAttribute('data-theme', savedTheme);
            updateThemeButton(savedTheme);
        });

        async function searchArticles() {
            const interests = document.getElementById('interests').value;
            const keywords = document.getElementById('keywords').value;
            const numResults = document.getElementById('numResults').value;
            
            if (!keywords.trim()) {
                alert('Please enter search keywords');
                return;
            }
            
            const loadingEl = document.getElementById('loading');
            const resultsEl = document.getElementById('results');
            
            loadingEl.classList.add('show');
            resultsEl.innerHTML = '';
            
            try {
                const response = await fetch('/api/search', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        interests, 
                        keywords, 
                        num_results: parseInt(numResults) 
                    })
                });
                
                const data = await response.json();
                
                if (data.error) {
                    resultsEl.innerHTML = `<div class="no-results">❌ Error: ${data.error}</div>`;
                } else if (data.articles && data.articles.length > 0) {
                    let html = `<div class="results-header">📰 Found ${data.articles.length} Relevant Articles</div>`;
                    
                    data.articles.forEach((article, i) => {
                        html += `
                            <div class="article">
                                <h3>${i + 1}. ${article.title}</h3>
                                <div class="source">📍 Source: ${article.source}</div>
                                <div><a href="${article.url}" target="_blank" class="article-url">${article.url}</a></div>
                                <div class="preview">${article.content_preview || article.description || 'No preview available'}</div>
                            </div>
                        `;
                    });
                    resultsEl.innerHTML = html;
                } else {
                    resultsEl.innerHTML = '<div class="no-results">🔍 No relevant articles found. Try different keywords or broader interests.</div>';
                }
            } catch (error) {
                resultsEl.innerHTML = `<div class="no-results">❌ Network error: ${error.message}</div>`;
            }
            
            loadingEl.classList.remove('show');
        }

        // Allow Enter key to trigger search
        document.getElementById('keywords').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                searchArticles();
            }
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/search', methods=['POST'])
def search_articles():
    data = request.json
    keywords = data.get('keywords', '')
    interests = data.get('interests', '')
    num_results = data.get('num_results', 10)
    
    print(f"🔍 Search request: keywords='{keywords}', interests='{interests[:50]}...', num_results={num_results}")
    
    if not keywords:
        return jsonify({'error': 'Keywords are required'}), 400
    
    # Temporarily bypass Anthropic API key requirement
    api_key = os.getenv('ANTHROPIC_API_KEY', 'dummy-key-for-testing')
    print(f"🔑 API key status: {'Found' if api_key else 'NOT FOUND'}")
    if api_key and api_key != 'dummy-key-for-testing':
        print(f"🔑 API Key starts with: {api_key[:15]}...")
    
    if not api_key:
        return jsonify({'error': 'ANTHROPIC_API_KEY not configured'}), 500
    
    # Run the async function in a new event loop
    async def run_scraper():
        async with ArticleScraper(api_key) as scraper:
            articles = await scraper.search_all_sources(keywords, interests, num_results)
            return articles
    
    try:
        print("🚀 Starting article search...")
        articles = asyncio.run(run_scraper())
        print(f"✅ Search completed: found {len(articles)} articles")
        return jsonify({'articles': articles})
    except Exception as e:
        print(f"❌ Search failed: {e}")
        return jsonify({'error': str(e)}), 500

def run_async_route(func):
    """Helper to run async routes"""
    return asyncio.run(func())

if __name__ == '__main__':
    app.run(debug=True, port=5000)