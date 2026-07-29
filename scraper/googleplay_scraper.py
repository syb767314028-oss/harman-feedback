import time
import sqlite3
from datetime import datetime
from .reddit_scraper import classify, extract_keywords, init_db

def scrape_googleplay():
    conn = init_db()
    
    # Try multiple possible package names for Harman Kardon ONE App
    package_names = [
        'com.harman.kardon.one',
        'com.harmankardon.one',
        'com.harmankardon.hkone',
        'com.harman.kardon',
    ]
    
    APP_PACKAGE = None
    
    # Try to find the correct package by importing google_play_scraper
    try:
        from google_play_scraper import app, reviews
        
        # Test each package name
        for pkg in package_names:
            try:
                app_info = app(pkg, lang='en', country='us')
                APP_PACKAGE = pkg
                print(f"Found app: {app_info.get('title', 'Unknown')} (score: {app_info.get('score', 'N/A')})")
                break
            except Exception:
                continue
        
        if not APP_PACKAGE:
            print("Could not find Harman Kardon ONE App on Google Play.")
            print("Known package names were tested. Please update APP_PACKAGE manually.")
            conn.close()
            return 0
            
    except ImportError:
        print("google-play-scraper not installed. Run: pip install google-play-scraper")
        conn.close()
        return 0
    except Exception as e:
        print(f"Google Play setup error: {e}")
        conn.close()
        return 0
    
    count = 0
    
    # Scrape from multiple countries
    countries = ['us', 'gb', 'de', 'jp', 'au', 'ca', 'fr', 'it', 'es', 'in']
    
    for country in countries:
        try:
            result, _ = reviews(
                APP_PACKAGE,
                lang='en',
                country=country,
                count=100
            )
            
            if not result:
                print(f"Google Play {country}: no reviews found")
                time.sleep(1)
                continue
            
            c = conn.cursor()
            
            for review in result:
                review_id = f"gp_{review.get('reviewId', 'unknown')}"
                
                # Check if already exists
                c.execute('SELECT id FROM feedback WHERE id = ?', (review_id,))
                if c.fetchone():
                    continue
                
                # Build text for classification
                content = review.get('content', '') or ''
                version = review.get('reviewCreatedVersion', '') or ''
                text = f"{content} {version}".strip()
                
                sentiment = classify(text)
                
                # Get rating
                rating = None
                try:
                    # Try direct rating field first
                    if 'rating' in review:
                        rating = review['rating']
                    # Try nested reviewMetadata
                    elif 'reviewMetadata' in review:
                        rating = review['reviewMetadata'].get('overallRating')
                except Exception:
                    pass
                
                # Get thumbs up count
                thumbs_up = review.get('thumbsUpCount', 0) or 0
                
                # Get timestamp
                review_date = review.get('at') or review.get('reviewCreated', datetime.now())
                if hasattr(review_date, 'isoformat'):
                    date_str = review_date.isoformat()
                else:
                    date_str = str(review_date)
                
                c.execute('''
                    INSERT INTO feedback (id, source, title, body, sentiment, rating, upvotes, collected_at, url)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    review_id,
                    'googleplay',
                    None,
                    content[:2000],
                    sentiment,
                    rating,
                    thumbs_up,
                    date_str,
                    None
                ))
                
                # Extract keywords
                for kw in extract_keywords(text):
                    c.execute(
                        'INSERT INTO keywords (keyword, sentiment, collected_at) VALUES (?, ?, ?)',
                        (kw, sentiment, datetime.now().isoformat())
                    )
                
                count += 1
            
            print(f"Google Play {country}: {len(result)} reviews, {count} new total")
            
            # Be respectful - sleep between country requests
            time.sleep(2)
            
        except Exception as e:
            print(f"Google Play {country} error: {e}")
            time.sleep(1)
            continue
    
    conn.commit()
    conn.close()
    print(f"Google Play: scraped {count} new items")
    return count
