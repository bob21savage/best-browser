# Multi-Platform Video Scraper

An advanced web application that searches and aggregates videos from multiple platforms including YouTube, Vimeo, and Dailymotion. Features browser rotation and anti-detection measures.

## Features

- Multi-platform video search (YouTube, Vimeo, Dailymotion)
- Asynchronous scraping for better performance
- Browser rotation to avoid detection
- Modern, responsive UI with dark mode support
- Platform filtering
- Embedded video players

## Installation

### Option 1: Basic Installation

1. Make sure you have Python 3.8+ installed

2. Clone this repository:
```bash
git clone <your-repo-url>
cd scrape
```

3. Create a virtual environment (recommended):
```bash
python -m venv venv
```

4. Activate the virtual environment:
- Windows:
```bash
venv\Scripts\activate
```
- Linux/Mac:
```bash
source venv/bin/activate
```

5. Install requirements:
```bash
pip install -r requirements.txt
```

### Option 2: Development Installation

For development or contributing to the project:

1. Follow steps 1-4 from Option 1

2. Install in development mode:
```bash
pip install -e .
```

3. Install with development dependencies (includes testing and linting tools):
```bash
pip install -e .[dev]
```

### Option 3: Package Installation

To install directly as a package:

```bash
pip install advanced-scraper
```

## Usage

1. Start the server:
```bash
python scrape_updated.py
```

2. Open your web browser and go to:
```
http://localhost:5000
```

3. Enter your search query and click "Search" or press Enter

## Troubleshooting

If you encounter SSL certificate errors while installing packages:
```bash

```

If you get browser driver errors:
1. Make sure you have Chrome, Firefox, or Edge installed
2. The webdriver-manager should automatically download the appropriate driver

## Requirements

- Python 3.8+
- Modern web browser (Chrome, Firefox, or Edge)
- Internet connection

## Dependencies

This project requires the following Python packages:

- Flask
- Flask-SQLAlchemy
- Flask-Login
- Flask-WTF
- Werkzeug
- aiohttp
- requests>=2.25.1
- beautifulsoup4  # For parsing HTML
- lxml  # For parsing HTML and XML
- matplotlib  # For data visualization
- seaborn  # For statistical data visualization
- yt-dlp  # For downloading videos
- schedule  # For scheduling tasks
- asyncio  # For asynchronous programming
- tweepy  # For Twitter API access
- python-dotenv
- httpx
- quart-auth
- quart
- hypercorn
- scrapy
- pandas
- numpy
- scikit-learn
- tensorflow

You can install all dependencies using the following command:

```bash
pip install -r requirements.txt
```

## Note

This scraper is for educational purposes only. Please respect the terms of service and robot.txt files of the platforms you're scraping.
