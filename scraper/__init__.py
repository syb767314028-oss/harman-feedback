from .googleplay_scraper import scrape_googleplay
from datetime import datetime
import sqlite3, os, subprocess, shutil


GITHUB_REPO = "https://github.com/syb767314028-oss/harman-feedback.git"
BACKUP_BRANCH = "data"
DB_FILE = "feedback.db"
BACKUP_MSG = "chore: backup feedback database"


def _git_run(*args, cwd=None):
    """Run a git command; return True if successful."""
    try:
        result = subprocess.run(
            ["git"] + list(args),
            cwd=cwd or os.getcwd(),
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            print(f"[git] {' '.join(args)} → {result.stderr.strip()}")
        return result.returncode == 0
    except Exception as e:
        print(f"[git] error: {e}")
        return False


def _git_config(cwd=None):
    """Configure git identity (needed on fresh Render instances)."""
    cwd = cwd or os.getcwd()
    _git_run("config", "user.email", "bot@harman-feedback.local", cwd=cwd)
    _git_run("config", "user.name", "Harman Feedback Bot", cwd=cwd)


def backup_to_github(project_dir):
    """
    Commit + push feedback.db to the 'data' branch.
    Called after each successful scrape.
    """
    project_dir = os.path.abspath(project_dir)
    cwd = project_dir
    _git_config(cwd)

    db_path = os.path.join(project_dir, DB_FILE)
    if not os.path.exists(db_path):
        print("[backup] feedback.db not found, skipping backup")
        return False

    # Check if there are actually records
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM feedback")
        count = cur.fetchone()[0]
        conn.close()
        if count == 0:
            print("[backup] DB is empty, skipping")
            return False
    except Exception as e:
        print(f"[backup] error reading DB: {e}")
        return False

    _git_config(cwd)

    # Check if data branch exists on remote
    check = subprocess.run(
        ["git", "ls-remote", "--heads", "origin", BACKUP_BRANCH],
        cwd=cwd, capture_output=True, text=True, timeout=10
    )
    has_branch = bool(check.stdout.strip())

    if has_branch:
        _git_run("checkout", BACKUP_BRANCH, cwd=cwd)
        _git_run("pull", "origin", BACKUP_BRANCH, cwd=cwd)
    else:
        _git_run("checkout", "--orphan", BACKUP_BRANCH, cwd=cwd)
        _git_run("rm", "-rf", ".", cwd=cwd)

    # Copy current db to project root and commit
    shutil.copy2(db_path, os.path.join(cwd, DB_FILE))

    _git_run("add", DB_FILE, cwd=cwd)
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=cwd, capture_output=True, text=True
    ).stdout.strip()
    if not status:
        print("[backup] no changes to commit")
        return True

    committed = _git_run("commit", "-m", BACKUP_MSG, cwd=cwd)
    if not committed:
        return False

    pushed = _git_run("push", "origin", BACKUP_BRANCH, cwd=cwd)
    if pushed:
        print(f"[backup] saved {count} records to GitHub (data branch)")
    return pushed


def restore_from_github(project_dir):
    """
    Pull feedback.db from the 'data' branch on startup.
    Returns True if a restore happened, False if no backup existed.
    """
    project_dir = os.path.abspath(project_dir)
    cwd = project_dir
    os.chdir(cwd)
    _git_config(cwd)

    # Check if data branch exists on remote using ls-remote
    check = subprocess.run(
        ["git", "ls-remote", "--heads", "origin", BACKUP_BRANCH],
        cwd=cwd, capture_output=True, text=True, timeout=10
    )
    if not check.stdout.strip():
        print("[restore] no data branch found, starting fresh")
        return False

    # Clone just the data branch into a temp subdir
    backup_dir = os.path.join(cwd, ".git_backup_temp")
    if os.path.exists(backup_dir):
        shutil.rmtree(backup_dir)
    os.makedirs(backup_dir)

    result = subprocess.run(
        ["git", "clone", "--branch", BACKUP_BRANCH, "--depth", "1",
         "https://github.com/syb767314028-oss/harman-feedback.git", backup_dir],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        print(f"[restore] clone failed: {result.stderr.strip()}")
        shutil.rmtree(backup_dir, ignore_errors=True)
        return False

    backup_db = os.path.join(backup_dir, DB_FILE)
    if not os.path.exists(backup_db):
        print("[restore] no feedback.db in data branch")
        shutil.rmtree(backup_dir, ignore_errors=True)
        return False

    # Merge: keep whichever is newer
    local_db = os.path.join(cwd, DB_FILE)
    restore_count = 0

    try:
        if os.path.exists(local_db):
            # Merge: import new rows from backup into existing db
            conn_local = sqlite3.connect(local_db)
            conn_backup = sqlite3.connect(backup_db)
            cur_local = conn_local.cursor()
            cur_backup = conn_backup.cursor()

            cur_backup.execute("SELECT * FROM feedback")
            rows = cur_backup.fetchall()
            imported = 0
            for row in rows:
                try:
                    cur_local.execute(
                        "INSERT OR IGNORE INTO feedback VALUES (?,?,?,?,?,?,?,?,?)", row
                    )
                    imported += 1
                except Exception:
                    pass
            conn_local.commit()

            cur_local.execute("SELECT COUNT(*) FROM feedback")
            restore_count = cur_local.fetchone()[0]
            conn_local.close()
            conn_backup.close()
            print(f"[restore] merged backup → {restore_count} total records")
        else:
            # No local DB, just copy the backup
            shutil.copy2(backup_db, local_db)
            conn = sqlite3.connect(local_db)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM feedback")
            restore_count = cur.fetchone()[0]
            conn.close()
            print(f"[restore] restored {restore_count} records from backup")
    except Exception as e:
        print(f"[restore] error: {e}")
        shutil.rmtree(backup_dir, ignore_errors=True)
        return False

    shutil.rmtree(backup_dir, ignore_errors=True)

    # Switch back to main branch for normal operation
    _git_run("checkout", "main", cwd=cwd)
    return restore_count > 0


def run_all():
    print(f"Starting scrape at {datetime.now().isoformat()}")
    g = scrape_googleplay()
    print(f"Total new items: {g}")
    return g


if __name__ == '__main__':
    run_all()
