import praw
import os
from datetime import datetime, timedelta
import sqlite3
import re
from collections import Counter

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
    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_source ON feedback(source)
    ''')
    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_sentiment ON feedback(sentiment)
    ''')
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

def scrape_reddit():
    conn = init_db()
    
    client_id = os.environ.get('REDDIT_CLIENT_ID')
    client_secret = os.environ.get('REDDIT_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        print("Reddit credentials not set. Skipping Reddit scrape.")
        conn.close()
        return 0
    
    try:
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent="harman-feedback-bot/1.0"
        )
    except Exception as e:
        print(f"Reddit authentication error: {e}")
        conn.close()
        return 0
    
    # Search terms for Harman Kardon ONE
    search_terms = [
        'harman kardon one',
        'harman kardon one app',
        'HK One app',
        'harman kardon connect',
        'harman kardon speaker app'
    ]
    
    all_posts = []
    for term in search_terms:
        try:
            for post in reddit.subreddit('all').search(term, limit=50, time_filter='year'):
                if post not in all_posts:
                    all_posts.append(post)
        except Exception as e:
            print(f"Reddit search error for '{term}': {e}")
    
    # Also search specific relevant subreddits
    target_subs = ['harmankardon', 'AudioEngineering', 'turntables', 'smartspeakers', 'homeaudio']
    for sub_name in target_subs:
        try:
            subreddit = reddit.subreddit(sub_name)
            for post in subreddit.search('harman kardon one', limit=30, time_filter='year'):
                if post not in all_posts:
                    all_posts.append(post)
        except Exception as e:
            print(f"Subreddit '{sub_name}' error: {e}")
    
    seen = set()
    count = 0
    for post in all_posts:
        post_id = f"reddit_{post.id}"
        if post_id in seen:
            continue
        seen.add(post_id)
        
        # Check if already exists
        c = conn.cursor()
        c.execute('SELECT id FROM feedback WHERE id = ?', (post_id,))
        if c.fetchone():
            continue
        
        # Get top comments for richer context
        try:
            post.comments.replace_more(limit=3)
            comments = [c.body for c in list(post.comments)[:15]]
        except Exception:
            comments = []
        
        all_text = f"{post.title} {post.selftext} " + " ".join(comments)
        sentiment = classify(all_text)
        
        body_text = (post.selftext or '')[:2000]
        if comments:
            body_text += '\n\n---\nTop Comments:\n' + '\n'.join(comments[:5])
        
        c.execute('''
            INSERT INTO feedback (id, source, title, body, sentiment, rating, upvotes, collected_at, url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            post_id,
            'reddit',
            (post.title or '')[:200],
            body_text,
            sentiment,
            None,  # Reddit has no star rating
            getattr(post, 'score', 0),
            datetime.now().isoformat(),
            f"https://reddit.com{getattr(post, 'permalink', '')}"
        ))
        
        # Extract keywords
        for kw in extract_keywords(all_text):
            c.execute(
                'INSERT INTO keywords (keyword, sentiment, collected_at) VALUES (?, ?, ?)',
                (kw, sentiment, datetime.now().isoformat())
            )
        
        count += 1
    
    conn.commit()
    conn.close()
    print(f"Reddit: scraped {count} items (total searched: {len(all_posts)})")
    return count
