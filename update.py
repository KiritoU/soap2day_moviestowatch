import logging
import time

from base import Crawler
from settings import CONFIG

logging.basicConfig(format="%(asctime)s %(levelname)s:%(message)s", level=logging.INFO)


crawler = Crawler()

if __name__ == "__main__":
    while True:
        try:
            crawler.update_episodes_page()
            crawler.crawl_page(f"{CONFIG.SOAP2DAY_TVSHOWS_PAGE}/")
            crawler.crawl_page(
                f"{CONFIG.SOAP2DAY_MOVIES_PAGE}/", post_type=CONFIG.TYPE_MOVIE
            )
        except Exception as e:
            pass
        time.sleep(CONFIG.WAIT_BETWEEN_LATEST)
