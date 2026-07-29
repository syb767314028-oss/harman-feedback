from .googleplay_scraper import scrape_googleplay
from datetime import datetime


def run_all():
    print(f"Starting scrape at {datetime.now().isoformat()}")
    g = scrape_googleplay()
    print(f"Total new items: {g}")
    return g


if __name__ == '__main__':
    run_all()
