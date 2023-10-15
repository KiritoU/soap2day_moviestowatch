import json
import logging
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

from helper import helper
from moviestowatch import Moviestowatch
from settings import CONFIG

logging.basicConfig(format="%(asctime)s %(levelname)s:%(message)s", level=logging.INFO)
Path(CONFIG.COVER_SAVE_PATH).mkdir(parents=True, exist_ok=True)


class Crawler:
    def crawl_soup(self, url):
        logging.info(f"Crawling {url}")

        html = helper.download_url(url)
        soup = BeautifulSoup(html.content, "html.parser")

        return soup

    def get_episode_links(self, soup: BeautifulSoup) -> str:
        res = []
        player2 = soup.find("div", {"id": "player2"})
        if not player2:
            return res

        iframes = player2.find_all("iframe")
        if not iframes:
            return res

        for iframe in iframes:
            try:
                src = iframe.get("src", "")
                if src:
                    res.append(src)
            except Exception as e:
                print(e)

        return res

    def get_server_episodes_links(self, href, server_data_id) -> dict:
        res = {}
        soup = self.crawl_soup(href)
        list_episodes = soup.find("ul", class_="list-episodes")
        lis = list_episodes.find_all("li", class_="episode-item")
        for li in lis:
            episode_name = li.text.strip()
            episode_href = li.find("a").get("href")

            if not f"&server={int(server_data_id) + 1}" in episode_href:
                matches = re.search(r"&server=(\d+)&", episode_href)
                if matches:
                    episode_href = episode_href.replace(
                        matches.group(0), f"&server={int(server_data_id) + 1}&"
                    )
                # episode_href = episode_href.replace(
                #     f"&server={server_data_id}", f"&server={int(server_data_id) + 1}"
                # )
            episode_link = self.get_episode_link(href=episode_href)
            res[episode_name] = episode_link
        return res

    def get_episodes_data(
        self, href: str, post_type: str = CONFIG.TYPE_TV_SHOWS
    ) -> dict:
        soup = self.crawl_soup(href)
        res = {}

        try:
            if post_type == CONFIG.TYPE_TV_SHOWS:
                servers_list = soup.find("ul", {"id": "servers-list"})
                lis = servers_list.find_all("li")
                for li in lis:
                    a_element = li.find("a")
                    data_id = a_element.get("data-id")
                    server_href = a_element.get("href")
                    server_name = (
                        a_element.text.lower()
                        .replace("server", "")
                        .strip()
                        .capitalize()
                    )
                    res[data_id] = {
                        "name": server_name,
                        "episodes": self.get_server_episodes_links(
                            href=server_href, server_data_id=data_id
                        ),
                    }
            else:
                list_episodes = soup.find("ul", class_="list-episodes")
                lis = list_episodes.find_all("li", class_="episode-item")
                for li in lis:
                    server_name = (
                        li.text.lower().replace("server", "").strip().capitalize()
                    )
                    episode_link = self.get_episode_link(href=li.find("a").get("href"))
                    data_id = li.find("a").get("data-id")
                    res[data_id] = {
                        "name": server_name,
                        "episodes": {"movie_episode": episode_link},
                    }

        except Exception as e:
            helper.error_log(
                f"Failed to get_episodes_data. Href: {href}\n{e}",
                log_file="base.episodes.log",
            )

        return res

    def crawl_film(
        self,
        slug: str,
        href: str,
        post_type: str = CONFIG.TYPE_TV_SHOWS,
    ):
        soup = self.crawl_soup(href)
        mvi_content = soup.find("div", class_="mvi-content")

        title = helper.get_title(href=href, mvi_content=mvi_content)
        description = helper.get_description(href=href, mvi_content=mvi_content)

        cover_src = helper.get_cover_url(href=href, mvi_content=mvi_content)

        trailer_id = helper.get_trailer_id(soup)
        extra_info = helper.get_extra_info(mvi_content=mvi_content)

        if not title:
            helper.error_log(
                msg=f"No title was found. Href: {href}", log_file="base.no_title.log"
            )
            return

        film_data = {
            "title": title,
            "slug": slug,
            "description": description,
            "post_type": post_type,
            "trailer_id": trailer_id,
            "cover_src": cover_src,
            "extra_info": extra_info,
        }

        if post_type == CONFIG.TYPE_MOVIE:
            episodes_data = {
                "Season 1": {"Episode 1": self.get_episode_links(soup=soup)}
            }
        else:
            episodes_data = {}
            seasons = soup.find("div", {"id": "seasons"})
            if seasons:
                tvseasons = seasons.find_all("div", class_="tvseason")
                for tvseason in tvseasons:
                    les_title = tvseason.find("div", class_="les-title")
                    les_title = les_title.text.strip().strip("\n")
                    episodes_data.setdefault(les_title, {})

                    les_content = tvseason.find("div", class_="les-content")
                    episode_a_s = les_content.find_all("a")
                    for episode_a in episode_a_s:
                        episode_title = episode_a.text.strip().strip("\n")
                        episode_url = episode_a.get("href")
                        episode_soup = self.crawl_soup(url=episode_url)
                        episodes_data[les_title][
                            episode_title
                        ] = self.get_episode_links(episode_soup)
            # episodes_data = self.get_episodes_data(href=play_href, post_type=post_type)

        return film_data, episodes_data

    def crawl_ml_item(
        self, ml_item: BeautifulSoup, post_type: str = CONFIG.TYPE_TV_SHOWS
    ):
        try:
            href = ml_item.find("a").get("href")

            if not href.startswith("https://"):
                href = CONFIG.SOAP2DAY_HOMEPAGE + href

            slug = href.strip().strip("/").split("/")[-1]

            film_data, episodes_data = self.crawl_film(
                slug=slug,
                href=href,
                post_type=post_type,
            )

            # film_data["episodes_data"] = episodes_data

            # with open("json/crawled.json", "w") as f:
            #     f.write(json.dumps(film_data, indent=4, ensure_ascii=False))

            Moviestowatch(film=film_data, episodes=episodes_data).insert_film()
            # sys.exit(0)
        except Exception as e:
            helper.error_log(
                msg=f"Error crawl_flw_item\n{e}", log_file="base.crawl_flw_item.log"
            )

    def crawl_page(self, url, post_type: str = CONFIG.TYPE_TV_SHOWS):
        soup = self.crawl_soup(url)

        ml_items = soup.find_all("div", class_="ml-item")
        if not ml_items:
            return 0

        for ml_item in ml_items:
            self.crawl_ml_item(ml_item=ml_item, post_type=post_type)
            # break

        return 1

    def get_serie_link_from_episode(self, episode_url: str) -> str:
        try:
            soup = self.crawl_soup(episode_url)
            mvic_info = soup.find("div", class_="mvic-info")
            p_elements = mvic_info.find_all("p")
            for p in p_elements:
                key = p.find("strong").text
                if "serie" in key.lower():
                    serie_link = p.find("a").get("href")
                    return serie_link
        except Exception as e:
            print(e)
            return ""

    def update_episodes_page(self):
        soup = self.crawl_soup(f"{CONFIG.SOAP2DAY_HOMEPAGE}/episode/")
        ml_items = soup.find_all("div", class_="ml-item")
        if not ml_items:
            return 0

        links = [ml_item.find("a").get("href") for ml_item in ml_items]
        links = [self.get_serie_link_from_episode(link) for link in links]

        links = list(set(links))

        for link in links:
            try:
                if not link:
                    continue

                href = link
                if not href.startswith("https://"):
                    href = CONFIG.SOAP2DAY_HOMEPAGE + href

                slug = href.strip().strip("/").split("/")[-1]

                film_data, episodes_data = self.crawl_film(
                    slug=slug,
                    href=href,
                    post_type=CONFIG.TYPE_TV_SHOWS,
                )
                Moviestowatch(film=film_data, episodes=episodes_data).insert_film()
            except Exception as e:
                print(e)


if __name__ == "__main__":
    Crawler().update_episodes_page()
    # Crawler().crawl_page(url=CONFIG.SOAP2DAY_TVSHOWS_PAGE + "/page/1/")
    # Crawler().crawl_page(
    #     url=CONFIG.SOAP2DAY_MOVIES_PAGE + "/page/1/", post_type=CONFIG.TYPE_MOVIE
    # )
    # Crawler().crawl_page(url=CONFIG.TINYZONETV_MOVIES_PAGE, post_type=CONFIG.TYPE_MOVIE)
