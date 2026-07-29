import time
import sqlite3
import re
from datetime import datetime
from collections import Counter


# ============ Shared utilities (moved from reddit_scraper) ============

def init_db():
    conn = sqlite3.connect('feedback.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS feedback (
            id TEXT PRIMARY KEY,
            source TEXT,
            title TEXT,
            body TEXT,
            sentiment TEXT,
            rating INTEGER,
            upvotes INTEGER,
            collected_at TEXT,
            url TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS keywords (
            keyword TEXT,
            sentiment TEXT,
            collected_at TEXT
        )
    ''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_source ON feedback(source)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_sentiment ON feedback(sentiment)')
    conn.commit()
    return conn


def classify(text):
    """Simple keyword-based sentiment classifier"""
    text_lower = text.lower()

    pain_words = [
        'bug', 'crash', 'slow', 'disconnect', 'fail', 'terrible', 'awful',
        'unstable', 'lag', 'freeze', 'not work', 'broken', 'worst',
        'horrible', 'frustrat', 'annoying', 'disappoint', 'problem',
        'issue', 'error', 'refuse', 'cannot', "can't", "won't", 'laggy',
        'unresponsive', 'drops', 'connection lost', 'update broke', 'hate',
        'uninstall', 'worst app', 'garbage', 'useless', 'waste', 'terrible',
        'poor', 'bad', 'wrong', 'stuck', 'never', 'cant', 'wont', 'doesnt work',
        'keeps crashing', 'randomly', 'constantly', 'every time', 'no response',
        'dead', 'battery drain', 'glitch', 'overheat', 'fails to', 'unable to'
    ]

    gain_words = [
        'love', 'amazing', 'perfect', 'great', 'excellent', 'awesome',
        'fantastic', 'wonderful', 'best', 'easy', 'smooth', 'beautiful',
        'intuitive', 'seamless', 'reliable', 'stable', 'works great',
        'love it', 'highly recommend', 'best app', 'perfect', 'brilliant',
        'nice', 'good', 'helpful', 'works well', 'solid', 'fast', 'simple',
        'clean', 'powerful', 'convenient', 'enjoy', 'satisfied', 'happy'
    ]

    pain_score = sum(1 for w in pain_words if w in text_lower)
    gain_score = sum(1 for w in gain_words if w in text_lower)

    if pain_score > gain_score:
        return 'pain'
    elif gain_score > pain_score:
        return 'gain'
    else:
        return 'neutral'


def extract_keywords(text, top_n=5):
    """Extract frequent keywords excluding stopwords"""
    stopwords = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'is', 'it', 'that', 'this', 'be', 'are',
        'was', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
        'could', 'should', 'may', 'might', 'must', 'shall', 'can', 'need',
        'i', 'you', 'he', 'she', 'we', 'they', 'my', 'your', 'his', 'our',
        'their', 'its', 'me', 'him', 'her', 'us', 'them', 'what', 'which',
        'who', 'when', 'where', 'why', 'how', 'all', 'each', 'every', 'both',
        'few', 'more', 'most', 'other', 'some', 'such', 'no', 'not', 'only',
        'same', 'so', 'than', 'too', 'very', 'just', 'as', 'if', 'then', 'because',
        'while', 'although', 'though', 'after', 'before', 'about', 'into',
        'through', 'during', 'above', 'below', 'between', 'under', 'again',
        'further', 'once', 'here', 'there', 'any', 'up', 'down', 'out', 'off',
        'over', 'get', 'got', 'one', 'two', 'also', 'im', 'ive', 'dont', 'doesnt',
        'would', 'could', 'should', 'really', 'even', 'much', 'like', 'make',
        'made', 'use', 'using', 'used', 'app', 'apps', 'phone', 'speaker',
        'sound', 'audio', 'music', 'time', 'times', 'thing', 'things', 'way',
        'work', 'working', 'works', 'goes', 'going', 'want', 'needed', 'need',
        'still', 'yet', 'now', 'new', 'old', 'first', 'last', 'see', 'looking'
    }

    words = re.findall(r'[a-zA-Z]{3,}', text.lower())
    words = [w for w in words if w not in stopwords]
    counter = Counter(words)
    return [w for w, _ in counter.most_common(top_n)]


# ============ Google Play scraper ============

def scrape_googleplay():
    conn = init_db()

    # Try multiple possible package names for Harman Kardon ONE App
    package_names = [
        'com.harmankardon.oneapp',
        'com.harman.kardon.one',
        'com.harmankardon.one',
        'com.harmankardon.hkone',
        'com.harman.kardon',
    ]

    APP_PACKAGE = None

    try:
        from google_play_scraper import app, reviews

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

                c.execute('SELECT id FROM feedback WHERE id = ?', (review_id,))
                if c.fetchone():
                    continue

                content = review.get('content', '') or ''
                version = review.get('reviewCreatedVersion', '') or ''
                text = f"{content} {version}".strip()

                sentiment = classify(text)

                rating = None
                try:
                    if 'rating' in review:
                        rating = review['rating']
                    elif 'reviewMetadata' in review:
                        rating = review['reviewMetadata'].get('overallRating')
                except Exception:
                    pass

                thumbs_up = review.get('thumbsUpCount', 0) or 0

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

                for kw in extract_keywords(text):
                    c.execute(
                        'INSERT INTO keywords (keyword, sentiment, collected_at) VALUES (?, ?, ?)',
                        (kw, sentiment, datetime.now().isoformat())
                    )

                count += 1

            print(f"Google Play {country}: {len(result)} reviews, {count} new total")

            time.sleep(2)

        except Exception as e:
            print(f"Google Play {country} error: {e}")
            time.sleep(1)
            continue

    conn.commit()
    conn.close()
    print(f"Google Play: scraped {count} new items")
    return count
