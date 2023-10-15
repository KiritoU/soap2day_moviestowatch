import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path

import requests
from slugify import slugify

from _db import database
from helper import helper
from settings import CONFIG

logging.basicConfig(format="%(asctime)s %(levelname)s:%(message)s", level=logging.INFO)


class Moviestowatch:
    def __init__(self, film: dict, episodes: dict):
        self.film = film
        self.film["quality"] = self.film["extra_info"].get("Quality", "HD")
        self.film["origin_cover_src"] = self.film["cover_src"]
        self.episodes = episodes
        if CONFIG.IS_DOWNLOAD_COVER:
            self.download_cover()

    def get_header(self):
        header = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E150",  # noqa: E501
            "Accept-Encoding": "gzip, deflate",
            # "Cookie": CONFIG.COOKIE,
            "Cache-Control": "max-age=0",
            "Accept-Language": "vi-VN",
            # "Referer": "https://mangabuddy.com/",
        }
        return header

    def download_url(self, url):
        return requests.get(url, headers=self.get_header())

    def save_thumb(
        self,
        imageUrl: str,
        imageName: str = "0.jpg",
    ) -> str:
        Path(CONFIG.COVER_SAVE_PATH + "/covers").mkdir(parents=True, exist_ok=True)
        saveImage = f"{CONFIG.COVER_SAVE_PATH}/covers/{imageName}"

        isNotSaved = not Path(saveImage).is_file()
        if isNotSaved:
            image = self.download_url(imageUrl)
            with open(saveImage, "wb") as f:
                f.write(image.content)
            isNotSaved = True

        return f"{CONFIG.DOMAIN_NAME}/covers/{imageName}"

    def download_cover(self) -> None:
        cover_url = self.film["cover_src"]
        image_extension = cover_url.split("/")[-1].split(".")[-1]
        if image_extension:
            downloaded_cover_name = f"{self.film['slug']}.{image_extension}"
            downloaded_cover_url = self.save_thumb(cover_url, downloaded_cover_name)
            self.film["cover_src"] = downloaded_cover_url

    def get_season_number(self, season_str: str) -> str:
        season_str = season_str.replace("\n", " ").lower()
        regex = re.compile(r"season (\d+)")
        match = regex.search(season_str)
        if match:
            return match.group(1)
        else:
            return "1"

    def generate_film_data(
        self,
        title,
        slug,
        description,
        post_type,
        trailer_id,
        quality,
        fondo_player,
        poster_url,
        extra_info,
    ):
        post_data = {
            "description": description,
            "title": title,
            "slug": slug,
            "post_type": post_type,
            # "id": "202302",
            "youtube_id": trailer_id,
            "quality": quality,
            # "serie_vote_average": extra_info["IMDb"],
            # "episode_run_time": extra_info["Duration"],
            "fondo_player": fondo_player,
            "poster_url": poster_url,
            # "category": extra_info["Genre"],
            # "stars": extra_info["Actor"],
            # "director": extra_info["Director"],
            # "release-year": [extra_info["Release"]],
            # "country": extra_info["Country"],
        }

        key_mapping = {
            "TMDb": "imdb",
            "IMDb": "imdb",
            "Duration": "duration",
            "Genre": "genre",
            "Actors": "cast",
            "Starring": "cast",
            "Networks": "country",
            "Director": "director",
            "Studio": "director",
            "Country": "country",
            "Released": "year",
            "Release": "year",
            "Release Year": "year",
        }

        for info_key in key_mapping.keys():
            if info_key in extra_info.keys():
                post_data[key_mapping[info_key]] = extra_info[info_key]

        return post_data

    def get_timeupdate(self) -> datetime:
        timeupdate = datetime.now() - timedelta(hours=10)

        return timeupdate

    def get_slug_list_from(self, table: str, names: list) -> str:
        res = []
        for name in names:
            try:
                condition = f"slug='{slugify(name)}'"
                data = (name, slugify(name))
                be_data_with_slug = database.select_or_insert(
                    table=table, condition=condition, data=data
                )
                res.append(be_data_with_slug[0][-1])
            except:
                pass

        return json.dumps(res)

    def get_year_from(self, released: str) -> int:
        try:
            dt = datetime.strptime(released, "%Y-%m-%d")
            return int(dt.year)
        except:
            return CONFIG.DEFAULT_RELEASE_YEAR

    def get_imdb_from(self, imdb_str: str) -> float:
        try:
            return float(imdb_str)
        except:
            return 0

    def insert_movie(self, post_data: dict) -> int:
        try:
            timeupdate = self.get_timeupdate()
            genre_names = post_data.get("genre", "").split(",")
            country_names = post_data.get("country", "").split(",")
            cast_names = post_data.get("cast", "").split(",")
            for name in country_names:
                if name in genre_names:
                    genre_names = genre_names.remove(name)
                if name in cast_names:
                    cast_names.remove(name)
            duration = post_data.get("duration", "")
            director = post_data.get("director", [])
            if isinstance(director, str):
                director = director.split(",")

            movie = {
                "name": post_data.get("title", ""),
                "origin_name": post_data.get("title", ""),
                "thumb": post_data.get("poster_url", ""),
                "coverUrl": "",
                "genres": self.get_slug_list_from(table="genres", names=genre_names),
                # "year": self.get_year_from(post_data.get("year", 0)),
                "year": post_data.get("year", 0),
                "country": json.loads(
                    self.get_slug_list_from(table="country", names=country_names)
                )[0],
                "view": 0,
                "quality": post_data.get("quality", "HD"),
                "duration": f"{duration}" if duration else "",
                "trailerEmbed": ""
                if not post_data.get("youtube_id", "")
                else "https://www.youtube.com/embed/" + post_data.get("youtube_id", ""),
                "Casts": json.dumps(cast_names),
                "Production": json.dumps(director),
                "hot": 0,
                "votePoint": 0,
                "voteNum": 0,
                "imdb": self.get_imdb_from(post_data.get("imdb", "")),
                "content": post_data.get("description", ""),
                "type": post_data.get("post_type", CONFIG.TYPE_TV_SHOWS),
                "status": "ongoing"
                if post_data.get("post_type", CONFIG.TYPE_TV_SHOWS)
                == CONFIG.TYPE_TV_SHOWS
                else "completed",
                "public": 1,
                "slug": post_data.get("slug", slugify(post_data.get("title", ""))),
                "time": timeupdate.strftime("%Y-%m-%d %H:%M:%S"),
                "creater": timeupdate.strftime("%Y-%m-%d"),
            }
            post_id = database.insert_into(table="movie", data=list(movie.values()))

            return post_id
        except Exception as e:
            helper.error_log(
                f'Failed to insert film: {post_data.get("title", "")}\n{e}',
                "moviestowatch.insert_movie.log",
            )
            return 0

    def insert_root_film(self) -> list:
        condition = (
            f"""slug = '{self.film["slug"]}' AND type='{self.film["post_type"]}'"""
        )
        be_post = database.select_all_from(table=f"movie", condition=condition)
        if not be_post:
            logging.info(f'Inserting root film: {self.film["post_title"]}')
            post_data = self.generate_film_data(
                self.film["post_title"],
                self.film["slug"],
                self.film["description"],
                self.film["post_type"],
                self.film["trailer_id"],
                self.film["quality"],
                self.film["cover_src"],
                self.film["cover_src"],
                self.film["extra_info"],
            )

            return self.insert_movie(post_data)
        else:
            return be_post[0][0]

    def validate_movie_episodes(self) -> None:
        res = []
        for ep_num, episode in self.episodes.items():
            episode_name = episode.get("title")
            episode_links = episode.get("links")
            # episodeName = episodeName.replace("Episoden", "").strip()
            episode_name = (
                episode_name.strip()
                .replace("\n", "")
                .replace("\t", " ")
                .replace("\r", " ")
            )
            if episode_links:
                episode_links = [
                    link if link.startswith("https:") else "https:" + link
                    for link in episode_links
                ]
                res.append([episode_name, ep_num, episode_links])
        res.sort(key=lambda x: float(x[1]))
        self.movie_episodes = res

    def get_server_name_from(self, link: str) -> str:
        # return CONFIG.SERVER_NAME
        x = re.search(r"//[^/]*", link)
        if x:
            return x.group().replace("//", "")

        return "Default"

    def get_episode_server_from(self, links: list) -> list:
        CUSTOM_SERVERS = [
            "VidCloud",
            "MultiStream",
            "2embed",
            "VS Player",
            "MovPi",
            "Gdrive",
            "UpCloud",
        ]

        removeLinks = []
        for removeLink in removeLinks:
            if removeLink in links:
                links.remove(removeLink)

        pick_server = 0

        res = []
        for link in links:
            res.append(
                {
                    "server_name": CUSTOM_SERVERS[
                        pick_server
                    ],  # self.get_server_name_from(link),
                    "server_type": "embed",
                    "server_link": link,
                }
            )
            pick_server = (pick_server + 1) % len(CUSTOM_SERVERS)

        return res

    def get_ep_num_from(self, ep_name: str) -> str:
        ep_name = ep_name.replace("\n", " ").lower()
        regex = re.compile(r"episode (\d+)")
        match = regex.search(ep_name)
        if match:
            return match.group(1)
        else:
            return "1"

    def get_episode_data(self, season_episodes: dict) -> list:
        res = []
        episodes = season_episodes

        for ep_name, ep_links in episodes.items():
            ep_links = sorted(list(set(ep_links)))
            episodes[ep_name] = ep_links

        for ep_name, ep_links in episodes.items():
            if self.film["post_type"] == CONFIG.TYPE_MOVIE:
                episode_name = f""
                episode_number = "1"
            else:
                episode_name = ep_name
                episode_number = self.get_ep_num_from(ep_name)

            res.append(
                {
                    "episode_name": episode_name,
                    # "ep_num": episode_number,
                    # "ep_time": 0,
                    "episode_server": self.get_episode_server_from(ep_links),
                }
            )

        return res

    def insert_episodes(self, movie_id: int) -> None:
        logging.info(
            f"Updating episodes for movie {self.film['post_title']} with ID: {movie_id}"
        )

        # if self.film["post_type"] == CONFIG.TYPE_MOVIE:
        #     self.episodes["Season 1"] = {
        #         "1": "Episode 1",
        #     }

        self.film["season_number"] = self.get_season_number(self.season)

        data = [
            {
                "season_name": self.film["season_number"],
                "season_episode": self.get_episode_data(
                    season_episodes=self.season_episodes
                ),
            }
        ]

        data = json.dumps(data)

        be_episode_data = database.select_or_insert(
            table="episode", condition=f"movieId={movie_id}", data=(movie_id, data)
        )

        episode_data = be_episode_data[0][-1]
        episode_data = (
            episode_data.decode() if isinstance(episode_data, bytes) else episode_data
        )
        # with open("json/diff.txt", "w") as f:
        #     print(data, file=f)
        #     print(episode_data, file=f)

        if episode_data != data:
            print("Diff")
            escape_data = data.replace("'", "''")
            database.update_table(
                table="episode",
                set_cond=f"""data='{escape_data}'""",
                where_cond=f"movieId={movie_id}",
            )

    def insert_film(self):
        self.film["title"] = (
            self.film["title"].replace("Soap2Day", CONFIG.CUSTOM_SUFFIX).strip()
        )
        self.film["origin_slug"] = (
            self.film["slug"].replace("soap2day", slugify(CONFIG.CUSTOM_SUFFIX)).strip()
        )

        for season, season_episodes in self.episodes.items():
            self.film["post_title"] = self.film["title"]
            self.film["slug"] = self.film["origin_slug"]

            if self.film["post_type"] == CONFIG.TYPE_TV_SHOWS:
                self.film["post_title"] = self.film["title"] + f" - {season.strip()}"
                self.film["slug"] = slugify(
                    self.film["origin_slug"] + f" - {season.strip()}"
                )

            post_id = self.insert_root_film()
            if not post_id:
                return

            self.season = season
            self.season_episodes = season_episodes
            self.insert_episodes(post_id)
