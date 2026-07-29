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


init_db()


# ============================================================
# Issue taxonomy + Chinese translations
# ============================================================

ISSUE_CATEGORIES = {
    "连接稳定性": {
        "keywords": ["connect", "disconnect", "connection", "wifi", "bluetooth", "network",
                     "drop", "drops", "lost", "unstable", "reconnect", "signal"],
        "description": "音箱无法稳定连接 Wi-Fi 或蓝牙，反复断开重连",
        "zh": "设备连接不稳定，Wi-Fi/蓝牙频繁断连或无法配对",
        "severity": "high",
    },
    "设备发现失败": {
        "keywords": ["find", "detect", "discover", "search", "find my", "find device",
                     "device not found", "cant find", "doesnt find"],
        "description": "App 无法发现/找到已配对的音箱，用户无法完成初始设置",
        "zh": "App 搜不到音箱设备，无法完成配对或初始设置",
        "severity": "high",
    },
    "软件卡顿/崩溃": {
        "keywords": ["crash", "freeze", "lag", "slow", "laggy", "glitch", "hang",
                     "responsive", "loading", "stuck", "overheat"],
        "description": "App 反应迟钝、卡死、闪退或长时间加载无响应",
        "zh": "App 响应缓慢、频繁卡顿或闪退崩溃",
        "severity": "high",
    },
    "更新后功能退化": {
        "keywords": ["update", "after update", "since update", "new version",
                     "after update broke", "update broke", "latest version"],
        "description": "App 更新后出现原本正常功能失效或体验下降",
        "zh": "更新版本后原本可用的功能变差或直接失效",
        "severity": "high",
    },
    "音频播放异常": {
        "keywords": ["sound", "audio", "play", "music", "speaker", "volume",
                     "no sound", "quiet", "distort", "skip", "cut out", "static"],
        "description": "音频播放出现杂音、跳帧、静音或音质异常",
        "zh": "播放音乐时出现杂音、跳音、音量异常或无声",
        "severity": "medium",
    },
    "多房间/分组问题": {
        "keywords": ["multi-room", "multi room", "group", "zone", "speaker group",
                     "onyx", "stereo", "left right", "sync", "delay"],
        "description": "多设备分组或多房间播放时出现同步、延迟或设置失败",
        "zh": "多房间分组或立体声配对时同步失败、延迟或无法设置",
        "severity": "medium",
    },
    "设置/配置复杂": {
        "keywords": ["setup", "configure", "config", "difficult", "confusing",
                     "complicate", "hard", "struggle", "cant figure", "not clear"],
        "description": "初次设置或高级配置流程不直观，用户花费大量时间仍无法完成",
        "zh": "设备设置流程不清晰，初次使用配置复杂、门槛高",
        "severity": "medium",
    },
    "流媒体服务兼容": {
        "keywords": ["spotify", "tidal", "chromecast", "airplay", "qobuz", "deezer",
                     "streaming", "service", "cast", "link", "preset"],
        "description": "主流流媒体服务（Spotify Connect、AirPlay、Chromecast）无法正常使用",
        "zh": "Spotify Connect、AirPlay、Chromecast 等投屏/串流功能无法使用",
        "severity": "medium",
    },
    "固件/版本兼容": {
        "keywords": ["firmware", "version", "android", "ios", "phone", "model",
                     "compatible", "os", "system requirement"],
        "description": "与特定手机系统、Android/iOS 版本或设备型号存在兼容问题",
        "zh": "与某些手机型号或系统版本不兼容",
        "severity": "low",
    },
    "续航/耗电": {
        "keywords": ["battery", "drain", "charge", "power", "dead", "sleep",
                     "standby", "energy", "consumption"],
        "description": "音箱待机耗电异常快，或 App 长时间后台导致手机耗电增加",
        "zh": "设备待机耗电异常或 App 后台耗电量大",
        "severity": "low",
    },
}

GAIN_CATEGORIES = {
    "音质体验优秀": {
        "keywords": ["sound", "audio", "quality", "bass", "clarity", "rich",
                     "deep", "clear", "beautiful sound", "amazing sound"],
        "description": "音质表现出色，低音深沉、高音清晰、整体听感令人满意",
        "zh": "音色饱满、低音有力、高音清晰，整体听感出色",
    },
    "设置体验流畅": {
        "keywords": ["easy", "simple", "intuitive", "setup", "quick", "fast setup",
                     "seamless", "smooth", "straightforward", "easy to use"],
        "description": "配对和设置过程快速简单，用户无需查阅说明即可完成",
        "zh": "配对设置简单快捷，无需复杂操作即可完成",
    },
    "连接稳定可靠": {
        "keywords": ["stable", "reliable", "works great", "consistent", "perfect",
                     "never", "without issue", "flawless", "seamless"],
        "description": "Wi-Fi/蓝牙连接稳定可靠，长时间使用不断连",
        "zh": "连接稳定流畅，长时间使用不出现断连问题",
    },
    "多房间体验出色": {
        "keywords": ["multi-room", "multi room", "group", "zone", "onyx",
                     "stereo", "whole house", "whole-home", "throughout"],
        "description": "多房间音乐同步体验完美，分组控制响应迅速",
        "zh": "多房间分组体验优秀，同步流畅、控制响应快",
    },
    "App 体验良好": {
        "keywords": ["app", "design", "interface", "ui", "ux", "beautiful",
                     "clean", "well design", "nice ui", "modern"],
        "description": "App 界面设计美观，操作逻辑清晰，功能布局合理",
        "zh": "App 界面设计美观，操作直观，功能逻辑清晰",
    },
}


def categorize_feedback(text):
    """Return matching categories for a piece of feedback text."""
    text_lower = text.lower()
    matched = []
    for cat, info in {**ISSUE_CATEGORIES, **GAIN_CATEGORIES}.items():
        for kw in info["keywords"]:
            if kw in text_lower:
                matched.append(cat)
                break
    return matched


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
                               feedbacks=feedbacks, total=total, pain=pain, gain=gain, neutral=neutral)
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
            ORDER BY count DESC LIMIT 20
        ''')
        keywords = [dict(row) for row in cur.fetchall()]
        conn.close()
        return jsonify({'trend': trend, 'by_platform': by_platform, 'keywords': keywords})
    except Exception as e:
        return jsonify({'error': str(e), 'trend': [], 'by_platform': [], 'keywords': []}), 200


@app.route('/api/issues')
def issues():
    """Cluster feedback into problem categories with percentages and Chinese translations."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id, body, sentiment, rating, upvotes, collected_at, source FROM feedback ORDER BY collected_at DESC")
        rows = cur.fetchall()
        conn.close()

        total = len(rows)
        if total == 0:
            return jsonify({'pain_categories': [], 'gain_categories': [], 'total': 0, 'unclassified_pain': 0, 'unclassified_gain': 0})

        # Count per category
        pain_counts = {cat: 0 for cat in ISSUE_CATEGORIES}
        pain_examples = {cat: [] for cat in ISSUE_CATEGORIES}
        gain_counts = {cat: 0 for cat in GAIN_CATEGORIES}
        gain_examples = {cat: [] for cat in GAIN_CATEGORIES}
        unclassified_pain = 0
        unclassified_gain = 0

        for row in rows:
            body = (row['body'] or '')[:500]
            sentiment = row['sentiment']
            item = {
                'body': body,
                'rating': row['rating'],
                'upvotes': row['upvotes'],
                'source': row['source'],
                'date': row['collected_at'][:10] if row['collected_at'] else '',
            }

            if sentiment == 'pain':
                cats = categorize_feedback(body)
                if cats:
                    for cat in cats:
                        if cat in pain_counts:
                            pain_counts[cat] += 1
                            if len(pain_examples[cat]) < 3:
                                pain_examples[cat].append(item)
                else:
                    unclassified_pain += 1

            elif sentiment == 'gain':
                cats = categorize_feedback(body)
                if cats:
                    for cat in cats:
                        if cat in gain_counts:
                            gain_counts[cat] += 1
                            if len(gain_examples[cat]) < 3:
                                gain_examples[cat].append(item)
                else:
                    unclassified_gain += 1

        # Sort pain categories by count descending
        pain_result = []
        for cat, count in sorted(pain_counts.items(), key=lambda x: -x[1]):
            if count > 0:
                pct = round(count / total * 100, 1)
                pain_result.append({
                    'category': cat,
                    'count': count,
                    'pct': pct,
                    'description': ISSUE_CATEGORIES[cat]['description'],
                    'zh': ISSUE_CATEGORIES[cat]['zh'],
                    'severity': ISSUE_CATEGORIES[cat]['severity'],
                    'examples': pain_examples[cat],
                })

        gain_result = []
        for cat, count in sorted(gain_counts.items(), key=lambda x: -x[1]):
            if count > 0:
                pct = round(count / total * 100, 1)
                gain_result.append({
                    'category': cat,
                    'count': count,
                    'pct': pct,
                    'description': GAIN_CATEGORIES[cat]['description'],
                    'zh': GAIN_CATEGORIES[cat]['zh'],
                    'examples': gain_examples[cat],
                })

        return jsonify({
            'pain_categories': pain_result,
            'gain_categories': gain_result,
            'total': total,
            'unclassified_pain': unclassified_pain,
            'unclassified_gain': unclassified_gain,
        })

    except Exception as e:
        return jsonify({'error': str(e), 'pain_categories': [], 'gain_categories': [], 'total': 0}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
