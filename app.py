from flask import Flask, render_template, jsonify
import sqlite3
import json
from datetime import datetime

app = Flask(__name__)


def get_db():
    conn = sqlite3.connect('feedback.db')
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Ensure tables exist (called on startup and before queries)."""
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
    conn.close()


# Create tables on startup
init_db()


@app.route('/')
def index():
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute('SELECT COUNT(*) as total FROM feedback')
        total = cur.fetchone()['total']

        cur.execute("SELECT COUNT(*) as count FROM feedback WHERE sentiment = 'pain'")
        pain = cur.fetchone()['count']

        cur.execute("SELECT COUNT(*) as count FROM feedback WHERE sentiment = 'gain'")
        gain = cur.fetchone()['count']

        cur.execute("SELECT COUNT(*) as count FROM feedback WHERE sentiment = 'neutral'")
        neutral = cur.fetchone()['count']

        cur.execute('SELECT * FROM feedback ORDER BY collected_at DESC LIMIT 200')
        feedbacks = [dict(row) for row in cur.fetchall()]

        conn.close()

        return render_template('dashboard.html',
                               feedbacks=feedbacks,
                               total=total, pain=pain, gain=gain, neutral=neutral)
    except Exception as e:
        return f"Error loading dashboard: {e}", 500


@app.route('/api/refresh', methods=['POST'])
def refresh():
    import subprocess
    import threading

    def run_scraper():
        subprocess.Popen(['python3', '-m', 'scraper'],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    threading.Thread(target=run_scraper, daemon=True).start()
    return jsonify({'status': 'triggered'})


@app.route('/api/stats')
def stats():
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute('''
            SELECT DATE(collected_at) as date, sentiment, COUNT(*) as count
            FROM feedback
            WHERE collected_at >= DATE('now', '-7 days')
            GROUP BY DATE(collected_at), sentiment
            ORDER BY date
        ''')
        trend = [dict(row) for row in cur.fetchall()]

        cur.execute('''
            SELECT source, sentiment, COUNT(*) as count
            FROM feedback
            GROUP BY source, sentiment
        ''')
        by_platform = [dict(row) for row in cur.fetchall()]

        cur.execute('''
            SELECT keyword, COUNT(*) as count
            FROM keywords
            GROUP BY keyword
            ORDER BY count DESC
            LIMIT 20
        ''')
        keywords = [dict(row) for row in cur.fetchall()]

        conn.close()
        return jsonify({'trend': trend, 'by_platform': by_platform, 'keywords': keywords})
    except Exception as e:
        return jsonify({'error': str(e), 'trend': [], 'by_platform': [], 'keywords': []}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
