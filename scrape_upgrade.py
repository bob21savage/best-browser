import os
import re
import json
import random
import asyncio
import logging
import aiohttp
import requests
import html2text
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin, quote, urlparse
from typing import List, Dict, Any
from flask_socketio import emit

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class VideoSearchCrawler:
    def __init__(self, topic: str):
        self.main_topic = topic
        self.search_results = []
        self.seen_links = set()
        
        # Initialize HTML converter
        self.html_converter = html2text.HTML2Text()
        self.html_converter.ignore_links = False
        
        # Initialize headers
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0'
        }

    async def collect_results(self):
        """Collect video results from multiple sources"""
        try:
            logger.info(f"Starting search for: {self.main_topic}")
            all_results = []
            
            # Create tasks for all search engines
            tasks = [
                self._search_youtube(self.main_topic),
                self._search_youtube_mobile(self.main_topic),
                self._search_bing_videos(self.main_topic),
                self._search_bing_videos_uk(self.main_topic)
            ]
            
            # Run all searches in parallel
            results = await asyncio.gather(*tasks)
            
            # Combine results
            for engine_results in results:
                if engine_results:
                    all_results.extend(engine_results)
                    logger.info(f"Found {len(engine_results)} results from {engine_results[0]['platform'] if engine_results else 'Unknown'}")
            
            # Shuffle results to mix platforms
            random.shuffle(all_results)
            return all_results
            
        except Exception as e:
            logger.error(f"Error in collect_results: {str(e)}")
            raise

    async def _search_youtube(self, query: str) -> List[Dict]:
        """Search for videos on YouTube."""
        results = []
        try:
            # Try different sorting options to get more results
            sort_params = ['', '&sp=CAI%253D', '&sp=CAM%253D']  # Default, Date, Rating
            
            for sort_param in sort_params:
                if len(results) >= 75:  
                    break
                    
                # YouTube search URL with sort parameter
                search_url = f"https://www.youtube.com/results?search_query={quote(query)}{sort_param}"
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(search_url, headers=self.headers) as response:
                        if response.status == 200:
                            html = await response.text()
                            
                            # Extract video IDs using regex
                            video_ids = re.findall(r'"videoId":"([^"]+)"', html)
                            video_titles = re.findall(r'"title":{"runs":\[{"text":"([^"]+)"}]}', html)
                            video_durations = re.findall(r'"simpleText":"([0-9:]+)"', html)
                            video_views = re.findall(r'"viewCountText":{"simpleText":"([^"]+)"}', html)
                            
                            # Process unique video IDs
                            seen_ids = set()
                            for i, video_id in enumerate(video_ids):
                                if video_id in seen_ids or len(results) >= 75:  
                                    continue
                                    
                                seen_ids.add(video_id)
                                title = video_titles[i] if i < len(video_titles) else "Untitled Video"
                                duration = video_durations[i] if i < len(video_durations) else "Unknown"
                                views = video_views[i] if i < len(video_views) else "Unknown views"
                                
                                video_url = f"https://www.youtube.com/watch?v={video_id}"
                                thumbnail_url = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
                                
                                results.append({
                                    'title': title,
                                    'url': video_url,
                                    'thumbnail': thumbnail_url,
                                    'duration': duration,
                                    'views': views,
                                    'platform': 'YouTube',
                                    'description': f"Watch this video on YouTube: {title}",
                                    'source': 'YouTube'
                                })
                                
        except Exception as e:
            logger.error(f"Error searching YouTube: {str(e)}")
        
        return results[:75]  

    async def _search_youtube_mobile(self, query: str) -> List[Dict]:
        """Search for videos on YouTube mobile site"""
        results = []
        try:
            # Search multiple pages
            for page in range(1, 4):  # Get up to 3 pages of results
                if len(results) >= 75:
                    break
                
                search_url = f"https://m.youtube.com/results?search_query={quote(query)}&page={page}"
                logger.info(f"Searching YouTube Mobile page {page}: {search_url}")
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(search_url, headers=self.headers) as response:
                        if response.status == 200:
                            html = await response.text()
                            soup = BeautifulSoup(html, 'html.parser')
                            
                            # Find video elements
                            video_elements = soup.find_all('div', class_='compact-media-item')
                            logger.info(f"Found {len(video_elements)} video elements on YouTube Mobile page {page}")
                            
                            for element in video_elements:
                                try:
                                    if len(results) >= 75:
                                        break
                                    
                                    # Get video ID and title
                                    link = element.find('a', href=True)
                                    if not link:
                                        continue
                                        
                                    href = link.get('href', '')
                                    if not href or '/watch?v=' not in href:
                                        continue
                                        
                                    video_id = href.split('watch?v=')[-1].split('&')[0]
                                    if not video_id:
                                        continue
                                    
                                    # Get title
                                    title_elem = element.find(['h4', 'h3', 'span'], class_=['compact-media-item-headline', 'title'])
                                    title = title_elem.text.strip() if title_elem else ''
                                    if not title:
                                        continue
                                    
                                    # Get thumbnail
                                    thumbnail = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
                                    
                                    # Get duration
                                    duration = 'Unknown'
                                    duration_elem = element.find('span', class_='compact-media-item-metadata')
                                    if duration_elem:
                                        duration = duration_elem.text.strip()
                                    
                                    results.append({
                                        'title': title,
                                        'url': f"https://www.youtube.com/watch?v={video_id}",
                                        'thumbnail': thumbnail,
                                        'duration': duration,
                                        'platform': 'YouTube Mobile',
                                        'description': title,
                                        'source': 'YouTube'
                                    })
                                    logger.debug(f"Added YouTube Mobile result: {title}")
                                    
                                except Exception as e:
                                    logger.error(f"Error processing YouTube Mobile result: {str(e)}")
                                    continue
                
                await asyncio.sleep(1)  # Respect rate limits
                
        except Exception as e:
            logger.error(f"Error searching YouTube Mobile: {str(e)}")
        
        logger.info(f"Found {len(results)} results from YouTube Mobile")
        return results[:75]

    async def _search_bing_videos(self, query: str) -> List[Dict]:
        """Search for videos using Bing Video Search."""
        results = []
        try:
            # Search multiple pages
            for offset in range(0, 100, 25):  # Get up to 100 results
                if len(results) >= 75:
                    break
                
                search_url = f"https://www.bing.com/videos/search?q={quote(query)}&first={offset}"
                logger.info(f"Searching Bing videos offset {offset}: {search_url}")
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(search_url, headers=self.headers) as response:
                        if response.status == 200:
                            html = await response.text()
                            soup = BeautifulSoup(html, 'html.parser')
                            
                            # Try multiple selectors for video elements
                            video_elements = soup.find_all('div', class_='dg_u')
                            if not video_elements:
                                video_elements = soup.find_all('div', class_='mc_vtvc')
                            if not video_elements:
                                video_elements = soup.find_all('div', class_='mc_vtvc_meta')
                                
                            logger.info(f"Found {len(video_elements)} video elements on Bing offset {offset}")
                            
                            for element in video_elements:
                                try:
                                    if len(results) >= 75:
                                        break
                                    
                                    # Try multiple ways to get title
                                    title = None
                                    title_elem = element.find(['div', 'span'], class_=['mc_vtvc_title', 'title'])
                                    if title_elem:
                                        title = title_elem.text.strip()
                                    
                                    # Try finding URL
                                    video_url = None
                                    link = element.find('a', href=True)
                                    if link:
                                        video_url = link.get('href', '')
                                    
                                    # Skip if we couldn't find essential info
                                    if not title or not video_url:
                                        logger.debug(f"Skipping Bing result - missing title or URL")
                                        continue
                                    
                                    # Ensure URL is absolute
                                    if video_url and not video_url.startswith('http'):
                                        video_url = f"https://www.bing.com{video_url}"
                                    
                                    # Get thumbnail
                                    thumbnail = None
                                    img = element.find('img')
                                    if img:
                                        thumbnail = img.get('src') or img.get('data-src')
                                    
                                    # Get duration if available
                                    duration = 'Unknown'
                                    duration_elem = element.find(['div', 'span'], class_=['mc_vtvc_duration', 'duration'])
                                    if duration_elem:
                                        duration = duration_elem.text.strip()
                                    
                                    results.append({
                                        'title': title,
                                        'url': video_url,
                                        'thumbnail': thumbnail,
                                        'duration': duration,
                                        'platform': 'Bing',
                                        'description': title,
                                        'source': 'Bing'
                                    })
                                    logger.debug(f"Added Bing result: {title}")
                                    
                                except Exception as e:
                                    logger.error(f"Error processing Bing result: {str(e)}")
                                    continue
                
                await asyncio.sleep(1)  # Respect rate limits
                
        except Exception as e:
            logger.error(f"Error searching Bing: {str(e)}")
        
        logger.info(f"Found {len(results)} results from Bing")
        return results[:75]

    async def _search_bing_videos_uk(self, query: str) -> List[Dict]:
        """Search for videos using Bing UK Video Search."""
        results = []
        try:
            # Search multiple pages
            for offset in range(0, 100, 25):  # Get up to 100 results
                if len(results) >= 75:
                    break
                
                search_url = f"https://www.bing.co.uk/videos/search?q={quote(query)}&first={offset}"
                logger.info(f"Searching Bing UK videos offset {offset}: {search_url}")
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(search_url, headers=self.headers) as response:
                        if response.status == 200:
                            html = await response.text()
                            soup = BeautifulSoup(html, 'html.parser')
                            
                            # Try multiple selectors for video elements
                            video_elements = soup.find_all('div', class_='dg_u')
                            if not video_elements:
                                video_elements = soup.find_all('div', class_='mc_vtvc')
                                
                            logger.info(f"Found {len(video_elements)} video elements on Bing UK offset {offset}")
                            
                            for element in video_elements:
                                try:
                                    if len(results) >= 75:
                                        break
                                    
                                    # Try multiple ways to get title
                                    title = None
                                    title_elem = element.find(['div', 'span'], class_=['mc_vtvc_title', 'title'])
                                    if title_elem:
                                        title = title_elem.text.strip()
                                    
                                    # Try finding URL
                                    video_url = None
                                    link = element.find('a', href=True)
                                    if link:
                                        video_url = link.get('href', '')
                                    
                                    # Skip if we couldn't find essential info
                                    if not title or not video_url:
                                        logger.debug(f"Skipping Bing UK result - missing title or URL")
                                        continue
                                    
                                    # Ensure URL is absolute
                                    if video_url and not video_url.startswith('http'):
                                        video_url = f"https://www.bing.co.uk{video_url}"
                                    
                                    # Get thumbnail
                                    thumbnail = None
                                    img = element.find('img')
                                    if img:
                                        thumbnail = img.get('src') or img.get('data-src')
                                    
                                    # Get duration if available
                                    duration = 'Unknown'
                                    duration_elem = element.find(['div', 'span'], class_=['mc_vtvc_duration', 'duration'])
                                    if duration_elem:
                                        duration = duration_elem.text.strip()
                                    
                                    results.append({
                                        'title': title,
                                        'url': video_url,
                                        'thumbnail': thumbnail,
                                        'duration': duration,
                                        'platform': 'Bing UK',
                                        'description': title,
                                        'source': 'Bing'
                                    })
                                    logger.debug(f"Added Bing UK result: {title}")
                                    
                                except Exception as e:
                                    logger.error(f"Error processing Bing UK result: {str(e)}")
                                    continue
                
                await asyncio.sleep(1)  # Respect rate limits
                
        except Exception as e:
            logger.error(f"Error searching Bing UK: {str(e)}")
        
        logger.info(f"Found {len(results)} results from Bing UK")
        return results[:75]

def setup_routes(app, socketio):
    """Set up Flask routes and Socket.IO event handlers"""
    
    # Track search status
    search_in_progress = False
    
    @socketio.on('connect')
    def handle_connect():
        logger.info("Client connected")
        emit('connected', {'status': 'Connected to server'})

    @socketio.on('disconnect')
    def handle_disconnect():
        logger.info("Client disconnected")

    @socketio.on('search_query')
    def handle_search_query(data):
        """Handle incoming search queries"""
        nonlocal search_in_progress
        
        try:
            logger.info(f"Received search query: {json.dumps(data, indent=2)}")
            
            if search_in_progress:
                logger.warning("Search already in progress")
                emit('search_error', {'error': 'A search is already in progress'})
                return
            
            query = data.get('query', '').strip()
            if not query:
                logger.warning("Empty query received")
                emit('search_error', {'error': 'Please enter a search query'})
                return

            search_in_progress = True
            logger.info(f"Starting search for: {query}")
            
            # Notify client
            emit('search_started', {
                'query': query,
                'message': f'Starting search for: {query}'
            })
            
            # Create crawler and run search
            try:
                crawler = VideoSearchCrawler(query)
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                all_results = loop.run_until_complete(crawler.collect_results())
                loop.close()
                
                # Process and emit results incrementally
                for result in all_results:
                    processed_result = {
                        'url': result.get('url', ''),
                        'title': result.get('title', 'Untitled Video'),
                        'description': result.get('description', ''),
                        'thumbnail': result.get('thumbnail', ''),
                        'source': result.get('source', 'Unknown'),
                        'duration': result.get('duration', 'Unknown'),
                        'type': 'video'
                    }
                    emit('link_found', processed_result)
                
                logger.info(f"Search completed with {len(all_results)} results")
                emit('search_complete', {
                    'total_links': len(all_results),
                    'duration': 'unknown',  # Add actual duration if available
                    'query': query
                })
                
            except Exception as e:
                logger.error(f"Search error: {str(e)}")
                emit('search_error', {'error': str(e)})
                
            finally:
                search_in_progress = False
                
        except Exception as e:
            logger.error(f"Error handling search query: {str(e)}")
            emit('search_error', {'error': str(e)})