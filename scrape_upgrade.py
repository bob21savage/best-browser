import os
import re
import json
import logging
import asyncio
import aiohttp
import threading
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from threading import Thread
from urllib.parse import urlparse, parse_qs, quote, urljoin
from aiohttp.client_exceptions import ClientError
from dotenv import load_dotenv
import html2text
from quart import Quart, request, jsonify, render_template, render_template_string
from hypercorn.config import Config
from hypercorn.asyncio import serve
from typing import Dict, List, Optional, Any, Union
import webbrowser
import random

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Quart app
app = Quart(__name__)

# Define or import your Crawler class
class Crawler:
    async def collect_results(self):
        # Your logic to collect results
        pass

# Attach the crawler to the app
app.crawler = Crawler()

# Set to store unique links
links = set()

@app.route('/add_link', methods=['POST'])
async def add_link():
    data = await request.get_json()
    link = data.get('link')
    if link:
        links.add(link)  # Use a set to store unique links
        return jsonify({"message": "Link added", "link": link}), 201
    return jsonify({"message": "Link not provided"}), 400

@app.route('/search', methods=['POST'])
async def search() -> Dict[str, Any]:
    """Handle search requests"""
    try:
        data = await request.get_json()
        query = data.get('query', '')
        
        if not query:
            return jsonify({'error': 'No query provided'}), 400
        
        logger.info(f"Received search query: {query}")
        
        # Create crawler instance and store it in app context
        app.crawler = VideoSearchCrawler(query)
        app.crawler.last_result_count = 0  # Initialize result counter
        app.crawler.search_results = []  # Initialize results list
        
        # Start search in background task
        async def run_search():
            await app.crawler.collect_results()
            print("Search completed.")
            
            # Save results
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'search_results_{timestamp}.html'
            
            # Create HTML content with all results
            html_content = f'''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Search Results</title>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        margin: 0;
                        padding: 20px;
                        background-color: #f5f5f5;
                    }}
                    .container {{
                        max-width: 1200px;
                        margin: 0 auto;
                    }}
                    .result-card {{
                        background: white;
                        padding: 20px;
                        border-radius: 8px;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                        margin-bottom: 20px;
                    }}
                    .result-type {{
                        display: inline-block;
                        padding: 4px 8px;
                        background-color: #e8f0fe;
                        color: #1967d2;
                        border-radius: 4px;
                        font-size: 12px;
                        margin-bottom: 10px;
                    }}
                    .result-title {{
                        font-size: 18px;
                        color: #1a0dab;
                        margin: 0 0 10px 0;
                    }}
                    .result-link {{
                        color: #006621;
                        font-size: 14px;
                        margin-bottom: 10px;
                        word-break: break-all;
                    }}
                    .result-description {{
                        color: #545454;
                        font-size: 14px;
                        line-height: 1.4;
                    }}
                    .video-embed {{
                        margin-top: 15px;
                        width: 100%;
                        max-width: 560px;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>Search Results</h1>
                    <div class="results">
            '''
            
            for result in app.crawler.search_results:
                embed_html = ''
                if result.get('content_type') == 'video' and result.get('embed_code'):
                    embed_html = f'<div class="video-embed">{result["embed_code"]}</div>'
                
                html_content += f'''
                    <div class="result-card">
                        <div class="result-type">{result.get('content_type', 'unknown')}</div>
                        <h3 class="result-title">
                            <a href="{result.get('link', '#')}" target="_blank">{result.get('title', 'Untitled')}</a>
                        </h3>
                        <div class="result-link">
                            <a href="{result.get('link', '#')}" target="_blank">{result.get('link', '#')}</a>
                        </div>
                        <p class="result-description">{result.get('description', '')}</p>
                        {embed_html}
                    </div>
                '''
            
            html_content += '''
                    </div>
                </div>
            </body>
            </html>
            '''
            
            # Save the file
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            # Mark results as saved
            app.crawler.results_saved = True
            logger.info(f"Saved results to {filename}")
            
            # Start media display server
            await run_app(app, 5000)
            
            # Wait for media processing to complete
            await wait_for_media_processing()
            
            # After media processing is complete, save results
            print("All media processing completed. Saving results...")
        
        task = asyncio.create_task(run_search())
        
        return jsonify({'message': 'Search started'})
        
    except Exception as e:
        logger.error(f"Error in search route: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/progress')
async def get_progress() -> Dict[str, Any]:
    """Get current search progress and results"""
    try:
        if not hasattr(app, 'crawler') or app.crawler is None:
            return jsonify({'error': 'No search in progress'})
        
        # Get current results and progress
        results = getattr(app.crawler, 'search_results', [])
        completed = getattr(app.crawler, 'search_completed', False)
        progress = getattr(app.crawler, 'progress', {})
        
        current_engine = progress.get('current_engine', '')
        current_page = progress.get('current', 0)
        total_pages = progress.get('total', 0)
        
        # Get only new results since last check
        last_count = getattr(app.crawler, 'last_result_count', 0)
        new_results = results[last_count:]
        app.crawler.last_result_count = len(results)
        
        # Log progress for debugging
        logger.info(f"Progress - Total Results: {len(results)}, New Results: {len(new_results)}, Last Count: {last_count}")
        
        return jsonify({
            'completed': completed,
            'new_results': new_results,  # Only send new results
            'total_results': len(results),  # Total count of all results
            'current_engine': current_engine,
            'current_page': current_page,
            'total_pages': total_pages
        })
        
    except Exception as e:
        logger.error(f"Error in progress route: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/')
async def index():
    """Serve the main page"""
    return await render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>Video Search</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        .search-container {
            text-align: center;
            margin-bottom: 30px;
        }
        #searchInput {
            width: 70%;
            padding: 12px;
            font-size: 16px;
            border: 2px solid #ddd;
            border-radius: 4px;
            margin-right: 10px;
        }
        #searchButton {
            padding: 12px 24px;
            font-size: 16px;
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }
        #searchButton:hover {
            background-color: #45a049;
        }
        #results {
            display: flex;
            flex-direction: column;
            gap: 20px;
        }
        .result-card {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            transition: transform 0.2s;
        }
        .result-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.15);
        }
        .result-title {
            font-size: 18px;
            color: #1a0dab;
            margin: 0 0 10px 0;
        }
        .result-link {
            color: #006621;
            font-size: 14px;
            margin-bottom: 10px;
            word-break: break-all;
        }
        .result-description {
            color: #545454;
            font-size: 14px;
            line-height: 1.4;
        }
        .result-type {
            display: inline-block;
            padding: 4px 8px;
            background-color: #e8f0fe;
            color: #1967d2;
            border-radius: 4px;
            font-size: 12px;
            margin-bottom: 10px;
        }
        .video-embed {
            margin-top: 15px;
            width: 100%;
            max-width: 560px;
        }
        #progressContainer {
            display: none;
            margin: 20px 0;
            text-align: center;
        }
        .progress-bar {
            width: 100%;
            height: 20px;
            background-color: #f3f3f3;
            border-radius: 10px;
            overflow: hidden;
            margin-bottom: 10px;
        }
        .progress-fill {
            height: 100%;
            background-color: #4CAF50;
            width: 0%;
            transition: width 0.3s ease;
        }
        .progress-text {
            color: #666;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="search-container">
            <input type="text" id="searchInput" placeholder="Enter your search query...">
            <button id="searchButton">Search</button>
        </div>
        <div id="progressContainer">
            <div class="progress-bar">
                <div class="progress-fill" id="progressFill"></div>
            </div>
            <div class="progress-text" id="progressText">Starting search...</div>
        </div>
        <div id="results"></div>
    </div>

    <script>
        let progressInterval;
        let displayedResults = new Set();
        let totalResults = 0;

        async function startSearch() {
            const query = document.getElementById('searchInput').value.trim();
            if (!query) return;

            // Reset UI
            document.getElementById('results').innerHTML = '';
            document.getElementById('progressContainer').style.display = 'block';
            document.getElementById('progressFill').style.width = '0%';
            document.getElementById('progressText').textContent = 'Starting search...';
            displayedResults.clear();
            totalResults = 0;

            try {
                // Start search
                const response = await fetch('/search', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ query })
                });

                if (!response.ok) {
                    throw new Error('Failed to start search');
                }

                // Clear any existing interval and start new progress checking
                if (progressInterval) {
                    clearInterval(progressInterval);
                }
                progressInterval = setInterval(checkProgress, 1000);

            } catch (error) {
                console.error('Search error:', error);
                document.getElementById('progressContainer').style.display = 'none';
                document.getElementById('results').innerHTML = `
                    <div class="result-card">
                        <p style="color: red;">Error: ${error.message}</p>
                    </div>
                `;
            }
        }

        async function checkProgress() {
            try {
                const response = await fetch('/progress');
                if (!response.ok) {
                    throw new Error('Failed to fetch progress');
                }
                
                const data = await response.json();
                if (data.error) {
                    throw new Error(data.error);
                }

                // Update total results count
                totalResults = data.total_results;
                
                // Update progress bar and text
                const progress = Math.min((data.current_page / data.total_pages) * 100, 100);
                document.getElementById('progressFill').style.width = `${progress}%`;
                document.getElementById('progressText').textContent = 
                    `Searching ${data.current_engine || ''} (${totalResults} results found)`;

                // Log progress for debugging
                console.log('Progress update:', {
                    totalResults,
                    newResults: data.new_results?.length || 0,
                    completed: data.completed
                });

                // Display new results
                const resultsContainer = document.getElementById('results');
                
                if (data.new_results && data.new_results.length > 0) {
                    data.new_results.forEach(result => {
                        if (!displayedResults.has(result.link)) {
                            displayedResults.add(result.link);
                            
                            const resultCard = document.createElement('div');
                            resultCard.className = 'result-card';
                            
                            let embedHtml = '';
                            if (result.content_type === 'video' && result.embed_code) {
                                embedHtml = `
                                    <div class="video-embed">
                                        ${result.embed_code}
                                    </div>
                                `;
                            } else if (!result.link || result.link === 'unknown') {
                                embedHtml = `
                                    <p>No media available</p>
                                `;
                            }
                            
                            resultCard.innerHTML = `
                                <div class="result-type">${result.content_type || 'unknown'}</div>
                                <h3 class="result-title">
                                    <a href="${result.link || '#'}" target="_blank">${result.title || 'Untitled'}</a>
                                </h3>
                                <div class="result-link">
                                    <a href="${result.link || '#'}" target="_blank">${result.link || '#'}</a>
                                </div>
                                <p class="result-description">${result.description || ''}</p>
                                ${embedHtml}
                            `;
                            
                            resultsContainer.appendChild(resultCard);
                        }
                    });
                }

                // If search is completed
                if (data.completed) {
                    clearInterval(progressInterval);
                    document.getElementById('progressContainer').style.display = 'none';
                    document.getElementById('progressText').textContent = 
                        `Search completed. Found ${totalResults} results.`;
                    
                    // Show "No results" message if needed
                    if (totalResults === 0) {
                        resultsContainer.innerHTML = `
                            <div class="result-card">
                                <p>No results found.</p>
                            </div>
                        `;
                    }
                }

            } catch (error) {
                console.error('Progress check error:', error);
                clearInterval(progressInterval);
                document.getElementById('progressContainer').style.display = 'none';
                document.getElementById('progressText').textContent = 'Error: ' + error.message;
            }
        }

        // Add event listeners
        document.getElementById('searchButton').addEventListener('click', startSearch);
        document.getElementById('searchInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') startSearch();
        });
    </script>
</body>
</html>
    ''')

@app.route('/media_display', methods=['GET'])
async def media_display():
    logger.info("Fetching media display results...")
    
    if not hasattr(app, 'crawler') or app.crawler is None:
        logger.error("No crawler available.")
        return jsonify({'error': 'No search results available'}), 400

    search_results = app.crawler.search_results

    if not search_results:
        logger.warning("No search results found.")
        return jsonify({'error': 'No search results found'}), 404

    video_urls = []
    audio_urls = []
    image_urls = []

    try:
        for result in search_results:
            logger.info(f"Processing result: {result}")
            video_urls.extend(await extract_videos(result))
            audio_urls.extend(await extract_audio(result))
            image_urls.extend(await extract_images(result))
    except Exception as e:
        logger.error(f"Error extracting media: {e}")
        return jsonify({'error': 'Error extracting media'}), 500

    rendered_html = await render_template('media_display.html', videos=video_urls, audios=audio_urls, images=image_urls)

    with open('media_display_output.html', 'w', encoding='utf-8') as f:
        f.write(rendered_html)

    return rendered_html

@app.route('/media_display_output')
def media_display_output():
    return render_template('media_display_output.html')

@app.route('/fetch_media', methods=['GET'])
async def fetch_media():
    try:
        logger.info("Fetching media...")
        if not hasattr(app, 'crawler') or app.crawler is None:
            logger.error("No crawler available.")
            return jsonify({'error': 'No search results available'}), 400

        search_results = app.crawler.search_results
        logger.info(f"Search results: {search_results}")

        if not search_results:
            logger.warning("No search results found.")
            return jsonify({'error': 'No search results found'}), 404

        video_urls = []
        audio_urls = []
        image_urls = []

        for result in search_results:
            video_urls.extend(await extract_videos(result))
            audio_urls.extend(await extract_audio(result))
            image_urls.extend(await extract_images(result))

        logger.info(f"Returning media URLs: {video_urls}, {audio_urls}, {image_urls}")
        return jsonify({
            'videos': video_urls,
            'audios': audio_urls,
            'images': image_urls
        })
    except Exception as e:
        logger.error(f"Error fetching media: {e}")
        return jsonify({'error': 'Error fetching media'}), 500

@app.route('/save_media', methods=['POST'])
async def save_media():
    data = await request.get_json()
    try:
        with open('media_display_output.html', 'w') as f:
            f.write(render_template('media_display.html', videos=data['videos'], audios=data['audios'], images=data['images']))
        return jsonify({'success': True}), 200
    except Exception as e:
        logger.error(f"Error saving media content: {e}")
        return jsonify({'error': 'Error saving media content'}), 500

async def fetch_content(url):
    """Fetch the content of a URL."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.text()

async def extract_videos(result):
    logger.info(f"Extracting videos from result: {result}")
    try:
        url = result['link']  # Access the link from the result
        content = await fetch_content(url)
        soup = BeautifulSoup(content, 'html.parser')
        video_urls = [video['src'] for video in soup.find_all('video')]
        logger.info(f"Found video URLs: {video_urls}")
        return video_urls
    except Exception as e:
        logger.error(f"Error extracting videos: {e}")
        return []

async def extract_audio(result):
    logger.info(f"Extracting audio from result: {result}")
    try:
        url = result['link']  # Access the link from the result
        content = await fetch_content(url)
        soup = BeautifulSoup(content, 'html.parser')
        audio_urls = [audio['src'] for audio in soup.find_all('audio')]
        logger.info(f"Found audio URLs: {audio_urls}")
        return audio_urls
    except Exception as e:
        logger.error(f"Error extracting audio: {e}")
        return []

async def extract_images(result):
    logger.info(f"Extracting images from result: {result}")
    try:
        url = result['link']  # Access the link from the result
        content = await fetch_content(url)
        soup = BeautifulSoup(content, 'html.parser')
        image_urls = [img['src'] for img in soup.find_all('img')]
        logger.info(f"Found image URLs: {image_urls}")
        return image_urls
    except Exception as e:
        logger.error(f"Error extracting images: {e}")
        return []

class AdvancedContentScraper:
    def __init__(self) -> None:
        """Initialize the content scraper with SearX and enhanced media support."""
        # List of common user agents
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Safari/605.1.15'
        ]
        
        # Initialize HTML converter
        self.html_converter = html2text.HTML2Text()
        self.html_converter.ignore_links = False
        
        # Initialize cache
        self._cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache')
        os.makedirs(self._cache_dir, exist_ok=True)
        self._cache_durations = {
            'web': 7200,      # 2 hours for web results
            'images': 3600,   # 1 hour for images
            'news': 1800,     # 30 minutes for news
            'videos': 3600,   # 1 hour for videos
            'audio': 3600     # 1 hour for audio
        }
        self._default_cache_duration = 3600
        
        # SearX configuration
        self.searx_instances = [
            'https://searx.be',
            'https://search.ononoki.org',
            'https://searx.tiekoetter.com',
            'https://search.bus-hit.me',
            'https://search.leptons.xyz'
        ]
        
        # Proxy configuration
        self._proxy_list = self._load_proxies()
        self._proxy_failures = {}
        
        # Session management
        self._session = None
        
        # Rate limiting
        self._last_request_time = {}
        self._min_delay = {
            'searx': 1.0,  # 1 second between requests
            'general': 0.5  # 0.5 seconds for other requests
        }
        self._max_retries = 3
        self._max_requests_per_minute = 20  # SearX allows more requests
        
        self.spec = {
            'icon': 'cinema.ico',  # Add the icon file here
            'name': 'scrape_upgrade',
            'version': '1.0',
            'description': 'A scraper for video search',
        }
        
    async def search(self, query: str, content_types: List[str] = None) -> Dict[str, List[Dict]]:
        """
        Execute a search across multiple content types concurrently.
        
        Args:
            query (str): The search query
            content_types (List[str], optional): List of content types to search. 
                Defaults to ['web', 'images', 'videos', 'news']
        
        Returns:
            Dict[str, List[Dict]]: Dictionary mapping content types to their respective results
        """
        if not content_types:
            content_types = ['web', 'images', 'videos', 'news']
        
        logging.info(f"Starting search with query: {query}, content types: {content_types}")
        
        tasks = []
        for content_type in content_types:
            if content_type == 'web':
                tasks.append(self._search_web(query))
            elif content_type == 'images':
                tasks.append(self._search_images(query))
            elif content_type == 'videos':
                tasks.append(self._search_videos(query))
            elif content_type == 'news':
                tasks.append(self._search_news(query))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results and handle any exceptions
        processed_results = {}
        for content_type, result in zip(content_types, results):
            if isinstance(result, Exception):
                logging.error(f"Failed to execute {content_type} search: {str(result)}")
                processed_results[content_type] = []
            else:
                processed_results[content_type] = result
        
        # Extract embedded content
        for content_type, results in processed_results.items():
            if content_type in ['web', 'images', 'videos', 'news']:
                embedded_results = await self._extract_embedded_content(results, content_type)
                processed_results[content_type].extend(embedded_results)
        
        # Deduplicate results
        for content_type, results in processed_results.items():
            processed_results[content_type] = self._process_and_deduplicate(results)
        
        return processed_results

    def _load_proxies(self) -> List[str]:
        """Load proxy list from environment variables."""
        proxy_str = os.getenv('PROXIES', '')
        if proxy_str:
            return [p.strip() for p in proxy_str.split(',')]
        return []

    async def _search_web(self, query: str) -> List[Dict]:
        """Search for web pages using SearX instances."""
        results = []
        for instance in self.searx_instances:
            try:
                async with aiohttp.ClientSession() as session:
                    params = {
                        'q': query,
                        'format': 'json',
                        'engines': 'google,bing,brave',
                        'language': 'en-US',
                        'categories': 'general'
                    }
                    async with session.get(f"{instance}/search", params=params, ssl=False, headers={'User-Agent': random.choice(self.user_agents)}) as response:
                        if response.status == 200:
                            data = await response.json()
                            for result in data.get('results', []):
                                results.append({
                                    'title': result.get('title', ''),
                                    'link': result.get('url', ''),
                                    'snippet': result.get('content', ''),
                                    'source': result.get('engine', '')
                                })
                            if results:
                                break
            except Exception as e:
                logging.error(f"Error with SearX instance {instance}: {str(e)}")
                continue
        
        return results[:10]  # Limit to top 10 results

    async def _search_images(self, query: str) -> List[Dict]:
        """Search for images using SearX instances."""
        results = []
        for instance in self.searx_instances:
            try:
                async with aiohttp.ClientSession() as session:
                    params = {
                        'q': query,
                        'format': 'json',
                        'engines': 'google images,bing images',
                        'language': 'en-US',
                        'categories': 'images'
                    }
                    async with session.get(f"{instance}/search", params=params, ssl=False, headers={'User-Agent': random.choice(self.user_agents)}) as response:
                        if response.status == 200:
                            data = await response.json()
                            for result in data.get('results', []):
                                if 'img_src' in result:
                                    results.append({
                                        'title': result.get('title', ''),
                                        'link': result.get('url', ''),
                                        'thumbnail': result.get('img_src', ''),
                                        'source': result.get('engine', '')
                                    })
                            if results:
                                break
            except Exception as e:
                logging.error(f"Error with SearX instance {instance}: {str(e)}")
                continue
        
        return results[:10]  # Limit to top 10 results

    async def _search_videos(self, query: str) -> List[Dict]:
        """Search for videos using SearX instances."""
        results = []
        for instance in self.searx_instances:
            try:
                async with aiohttp.ClientSession() as session:
                    params = {
                        'q': query,
                        'format': 'json',
                        'engines': 'youtube',
                        'language': 'en-US',
                        'categories': 'videos'
                    }
                    async with session.get(f"{instance}/search", params=params, ssl=False, headers={'User-Agent': random.choice(self.user_agents)}) as response:
                        if response.status == 200:
                            data = await response.json()
                            for result in data.get('results', []):
                                results.append({
                                    'title': result.get('title', ''),
                                    'link': result.get('url', ''),
                                    'thumbnail': result.get('thumbnail', ''),
                                    'duration': result.get('length', ''),
                                    'platform': result.get('engine', 'YouTube'),
                                    'views': result.get('views', 'N/A'),
                                    'snippet': result.get('content', '')
                                })
                            if results:
                                break
            except Exception as e:
                logging.error(f"Error with SearX instance {instance}: {str(e)}")
                continue
        
        return results[:10]  # Limit to top 10 results

    async def _search_news(self, query: str) -> List[Dict]:
        """Search for news using SearX instances."""
        results = []
        for instance in self.searx_instances:
            try:
                async with aiohttp.ClientSession() as session:
                    params = {
                        'q': query,
                        'format': 'json',
                        'engines': 'google news,bing news',
                        'language': 'en-US',
                        'categories': 'news'
                    }
                    async with session.get(f"{instance}/search", params=params, ssl=False, headers={'User-Agent': random.choice(self.user_agents)}) as response:
                        if response.status == 200:
                            data = await response.json()
                            for result in data.get('results', []):
                                results.append({
                                    'title': result.get('title', ''),
                                    'link': result.get('url', ''),
                                    'snippet': result.get('content', ''),
                                    'source': result.get('engine', ''),
                                    'date': result.get('publishedDate', 'N/A')
                                })
                            if results:
                                break
            except Exception as e:
                logging.error(f"Error with SearX instance {instance}: {str(e)}")
                continue
        
        return results[:10]  # Limit to top 10 results

    async def _extract_embedded_content(self, results: List[Dict], content_type: str) -> List[Dict]:
        """
        Extract embedded content from search results.
        Handles videos, audio, and images embedded in web pages.
        """
        embedded_results = []
        
        for result in results:
            try:
                if content_type == 'videos':
                    video_results = await self._extract_embedded_videos(result)
                    embedded_results.extend(video_results)
                elif content_type == 'audio':
                    audio_results = await self._extract_embedded_audio(result)
                    embedded_results.extend(audio_results)
                elif content_type == 'images':
                    image_results = await self._extract_embedded_images(result)
                    embedded_results.extend(image_results)
                    
            except Exception as e:
                logging.warning(f"Failed to extract embedded content: {str(e)}")
                
        return embedded_results

    async def _extract_embedded_videos(self, result: Dict) -> List[Dict]:
        """Extract embedded videos from a search result."""
        logger.info(f"Extracting embedded videos from: {result}")
        try:
            url = result['link']  # Access the link from the result
            content = await fetch_content(url)
            soup = BeautifulSoup(content, 'html.parser')
            video_urls = [video['src'] for video in soup.find_all('video')]
            logger.info(f"Found video URLs: {video_urls}")
            return video_urls
        except Exception as e:
            logger.error(f"Error extracting videos from {result['link']}: {str(e)}")
            return []

    async def _extract_embedded_audio(self, result: Dict) -> List[Dict]:
        """Extract embedded audio from a search result."""
        logger.info(f"Extracting embedded audio from: {result}")
        try:
            url = result['link']  # Access the link from the result
            content = await fetch_content(url)
            soup = BeautifulSoup(content, 'html.parser')
            audio_urls = [audio['src'] for audio in soup.find_all('audio')]
            logger.info(f"Found audio URLs: {audio_urls}")
            return audio_urls
        except Exception as e:
            logger.error(f"Error extracting audio from {result['link']}: {str(e)}")
            return []

    async def _extract_embedded_images(self, result: Dict) -> List[Dict]:
        """Extract embedded images from a search result."""
        logger.info(f"Extracting embedded images from: {result}")
        try:
            url = result['link']  # Access the link from the result
            content = await fetch_content(url)
            soup = BeautifulSoup(content, 'html.parser')
            image_urls = [img['src'] for img in soup.find_all('img')]
            logger.info(f"Found image URLs: {image_urls}")
            return image_urls
        except Exception as e:
            logger.error(f"Error extracting images from {result['link']}: {str(e)}")
            return []

    async def _extract_media_links(self, result: Dict) -> List[str]:
        """Extract media links from a search result."""
        logger.info(f"Extracting media links from: {result}")
        media_urls = []
        try:
            # General regex pattern for capturing any media links
            pattern = r'https?:\/\/[^\/\s]+'  # Matches any HTTP or HTTPS URL
            matches = re.findall(pattern, result['content'])
            for media_url in matches:
                media_urls.append(media_url)
                logger.info(f"Found media URL: {media_url}")
        except Exception as e:
            logger.error(f"Error extracting media links from {result['link']}: {str(e)}")
            return []

        if not media_urls:
            logger.warning(f"No media links found for {result['link']}")
        return media_urls

    async def _is_valid_image_url(self, url: str) -> bool:
        """Validate if a URL points to an image."""
        image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')
        parsed_url = urlparse(url)
        return parsed_url.scheme in ['http', 'https'] and parsed_url.path.endswith(image_extensions)

    async def _get_image_dimensions(self, url: str) -> Optional[Dict[str, int]]:
        """
        Get image dimensions from URL.
        Returns None if dimensions cannot be determined.
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(url, allow_redirects=True) as response:
                    if 'content-length' in response.headers:
                        return {
                            'size': int(response.headers['content-length'])
                        }
        except:
            pass
        return None

    def _construct_video_url(self, platform: str, video_id: str) -> str:
        """Construct proper video URL based on platform and ID."""
        if platform == 'youtube':
            return f'https://www.youtube.com/watch?v={video_id}'
        elif platform == 'vimeo':
            return f'https://vimeo.com/{video_id}'
        elif platform == 'dailymotion':
            return f'https://www.dailymotion.com/video/{video_id}'
        elif platform == 'twitch':
            return f'https://www.twitch.tv/videos/{video_id}'
        elif platform == 'facebook':
            return f'https://www.facebook.com/watch/?v={video_id}'
        elif platform == 'tiktok':
            return f'https://www.tiktok.com/@user/video/{video_id}'
        # Add more platforms as needed
        return ''

    async def _construct_audio_url(self, platform: str, track_id: str) -> str:
        """Construct proper audio URL based on platform and ID."""
        if platform == 'soundcloud':
            return f'https://soundcloud.com/{track_id}'
        elif platform == 'spotify':
            return f'https://open.spotify.com/track/{track_id}'
        elif platform == 'bandcamp':
            return f'https://bandcamp.com/track/{track_id}'
        elif platform == 'apple_music':
            return f'https://music.apple.com/us/album/{track_id}'
        elif platform == 'tidal':
            return f'https://tidal.com/track/{track_id}'
        elif platform == 'deezer':
            return f'https://www.deezer.com/track/{track_id}'
        # Add more platforms as needed
        return ''

    def _get_video_thumbnail(self, platform: str, video_id: str) -> Optional[str]:
        """Get thumbnail URL for a video."""
        thumbnail_templates = {
            'youtube': f'https://img.youtube.com/vi/{video_id}/hqdefault.jpg',
            'vimeo': None,  # Vimeo requires API access for thumbnails
            'dailymotion': f'https://www.dailymotion.com/thumbnail/video/{video_id}',
            'twitch': None,  # Twitch requires API access for thumbnails
            'facebook': None  # Facebook requires API access for thumbnails
        }
        return thumbnail_templates.get(platform)

    def _process_and_deduplicate(self, results: List[Dict]) -> List[Dict]:
        """Process and deduplicate results while preserving order."""
        seen = set()
        unique_results = []
        
        for result in results:
            result_key = result['link']
            if result_key not in seen:
                seen.add(result_key)
                unique_results.append(result)
                
        return unique_results

class VideoSearchCrawler:
    def __init__(self, topic: str):
        self.main_topic = topic
        self.search_results = []
        self.seen_links = set()
        self.search_completed = False
        self.session = requests.Session()
        self.max_results = 1000  # Increased max results
        self.min_results = 50
        self.max_pages = 10
        self.delay = 3  # Increased delay between requests
        self.last_count = 0  # Initialize a variable to track the last count of results
        
        # Initialize headers
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Safari/605.1.15'
        ]
        self.headers = {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        # List of search engines to query
        self.search_engines = [
            'https://search.aol.com/aol/search?q=',
            'https://www.google.com/search?q=',
            'https://www.bing.com/search?q=',
            'https://search.yahoo.com/search?p=',
            'https://duckduckgo.com/?q=',
            'https://www.baidu.com/s?wd=',
            'https://www.yandex.com/search/?text=',
            'https://www.ask.com/web?q=',
            'https://www.aol.com/search?q=',
            'https://www.wolframalpha.com/input/?i=',
            'https://www.startpage.com/do/search?q=',
            'https://www.qwant.com/?q=',
            'https://www.searchencrypt.com/search?q=',
            'https://www.exalead.com/search/',
            'https://www.kiddle.co/',
            'https://www.yippy.com/search?query=',
            'https://www.dogpile.com/search/web?q=',
            'https://www.metacrawler.com/search/web?q=',
            'https://www.gigablast.com/search?q=',
            'https://www.lycos.com/search?q=',
            'https://www.webcrawler.com/search/web?q=',
            'https://www.info.com/search?q=',
            'https://www.teoma.com/search?q=',
            'https://www.bing.com/videos/search?q=',
            'https://www.vimeo.com/search?q=',
            'https://www.dailymotion.com/search?q=',
            'https://www.twitch.tv/search?term=',
            'https://www.tiktok.com/search?q=',
            'https://www.search.com/search?q=',
            'https://www.goo.gl/search?q=',
            'https://www.filehorse.com/search?q=',
            'https://www.searchenginewatch.com/?s=',
            'https://www.searchtempest.com/search?q=',
            'https://www.explore.com/search?q=',
            'https://www.searchresults.com/search?q=',
            'https://www.qwant.com/?q=',
            'https://www.find.com/search?q=',
            'https://www.searchenginejournal.com/search?q=',
            'https://vimeo.com/search?q=',
            'https://www.facebook.com/watch/search/?q=',
            'https://www.veoh.com/search/videos?q=',
            'https://www.metacafe.com/search/videos?q=',
            'https://www.bitchute.com/search/?query=',
            'https://rumble.com/search/?query=',
            'https://soundcloud.com/search?q=',
            'https://open.spotify.com/search?q=',
            'https://music.apple.com/us/search?term=',
            'https://tidal.com/search?q=',
            'https://www.amazon.com/music/search?q=',
            'https://www.pandora.com/search?q=',
            'https://www.iheart.com/search?q=',
            'https://www.mixcloud.com/search?q=',
            'https://www.last.fm/search?q=',
            'https://www.beatport.com/search?q=',
            'https://www.buzzfeed.com/search?q=',
            'https://www.huffpost.com/search?q=',
            'https://www.cnn.com/search?q=',
            'https://www.vice.com/search?q=',
        ]
        
    async def collect_results(self):
        logger.info(f"Starting search for: {self.main_topic}")
        self.search_completed = False
        self.search_results = []
        self.progress = {
            'current_engine': '',
            'current': 0,
            'total': len(self.search_engines)
        }
        for engine in self.search_engines:
            self.progress['current_engine'] = engine
            search_url = f'{engine}{self.main_topic}'
            logger.info(f"Searching URL: {search_url}")
            try:
                html_content = await self.fetch_search_results(search_url)
            except requests.exceptions.ConnectionError as e:
                logger.error(f"Connection error with {engine}: {e}. Trying next engine.")
                continue  # Skip to the next engine if there's a connection error
            if html_content:
                # Extract URLs from the HTML content
                results = self.extract_page_urls(html_content, search_url)
                
                # Log the extracted URLs
                if results:
                    logger.info(f"Extracted URLs from {search_url}:")
                    for result in results:
                        logger.info(f"- {result['link']} (Title: {result['title']})")  # Assuming your results include a title
                
                # Add extracted results to the main results list
                self.search_results.extend(results)
                logger.info(f"Total results after {engine}: {len(self.search_results)}")
            self.progress['current'] += 1
            await asyncio.sleep(3)  # Increased delay between requests
        self.search_completed = True

        # Save results
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'search_results_{timestamp}.html'
        
        # Create HTML content with all results
        html_content = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Search Results</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 0;
                    padding: 20px;
                    background-color: #f5f5f5;
                }}
                .container {{
                    max-width: 1200px;
                    margin: 0 auto;
                }}
                .result-card {{
                    background: white;
                    padding: 20px;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    margin-bottom: 20px;
                }}
                .result-type {{
                    display: inline-block;
                    padding: 4px 8px;
                    background-color: #e8f0fe;
                    color: #1967d2;
                    border-radius: 4px;
                    font-size: 12px;
                    margin-bottom: 10px;
                }}
                .result-title {{
                    font-size: 18px;
                    color: #1a0dab;
                    margin: 0 0 10px 0;
                }}
                .result-link {{
                    color: #006621;
                    font-size: 14px;
                    margin-bottom: 10px;
                    word-break: break-all;
                }}
                .result-description {{
                    color: #545454;
                    font-size: 14px;
                    line-height: 1.4;
                }}
                .video-embed {{
                    margin-top: 15px;
                    width: 100%;
                    max-width: 560px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Search Results</h1>
                <div class="results">
        '''
        
        for result in self.search_results:
            embed_html = ''
            if result.get('content_type') == 'video' and result.get('embed_code'):
                embed_html = f'<div class="video-embed">{result["embed_code"]}</div>'
            
            html_content += f'''
                <div class="result-card">
                    <div class="result-type">{result.get('content_type', 'unknown')}</div>
                    <h3 class="result-title">
                        <a href="{result.get('link', '#')}" target="_blank">{result.get('title', 'Untitled')}</a>
                    </h3>
                    <div class="result-link">
                        <a href="{result.get('link', '#')}" target="_blank">{result.get('link', '#')}</a>
                    </div>
                    <p class="result-description">{result.get('description', '')}</p>
                    {embed_html}
                </div>
            '''
        
        html_content += '''
                </div>
            </div>
        </body>
        </html>
        '''
        
        # Save the file
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        # Mark results as saved
        self.results_saved = True
        logger.info(f"Saved results to {filename}")
        
        # Start media display server
        await run_app(app, 5000)
        
        # Wait for media processing to complete
        await wait_for_media_processing()
        
        # After media processing is complete, save results
        print("All media processing completed. Saving results...")

async def run_app(app, port):
    config = Config()
    config.bind = [f"0.0.0.0:{port}"]  # Bind to 0.0.0.0 to allow external access
    await serve(app, config)  # Await the serve function directly

async def wait_for_media_processing():
    """Wait for media processing to complete."""
    while not app.crawler.search_completed:
        await asyncio.sleep(1)  # Check every second
    logger.info("Media processing completed.")

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    async def run_search():
        await app.crawler.collect_results()
        print("Search completed.")

    # Run the search function in the event loop
    asyncio.run(run_search())

    # Start the Flask app on port 5001 for fetching media
    asyncio.run(run_app(app, 5001))

    # Start the Flask app on port 5002 for media display output
    asyncio.run(run_app(app, 5002))