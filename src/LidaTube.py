import logging
import os
import json
import threading
import requests
import time
from datetime import datetime
import youtubesearchpython
from ytmusicapi import YTMusic
from flask import Flask, render_template
from flask_socketio import SocketIO
import yt_dlp
import concurrent.futures
import re
from thefuzz import fuzz
import _matcher
import _general


class DataHandler:
    def __init__(self):
        logging.basicConfig(level=logging.WARNING, format="%(message)s")
        self.general_logger = logging.getLogger()

        app_name_text = os.path.basename(__file__).replace(".py", "")
        release_version = os.environ.get("RELEASE_VERSION", "unknown")
        self.general_logger.warning(f"{'*' * 50}\n")
        self.general_logger.warning(f"{app_name_text} Version: {release_version}\n")
        self.general_logger.warning(f"{'*' * 50}")

        self.lidarr_items = []
        self.lidarr_futures = []
        self.lidarr_status = "idle"
        self.lidarr_stop_event = threading.Event()

        self.ytdlp_items = []
        self.ytdlp_futures = []
        self.ytdlp_status = "idle"
        self.ytdlp_stop_event = threading.Event()

        self.ytdlp_in_progress_flag = False
        self.index = 0
        self.percent_completion = 0

        self.clients_connected_counter = 0
        self.config_folder = "config"
        self.download_folder = "downloads"

        if not os.path.exists(self.config_folder):
            os.makedirs(self.config_folder)

        full_cookies_path = os.path.join(self.config_folder, "cookies.txt")
        self.cookies_path = full_cookies_path if os.path.exists(full_cookies_path) else None

        self.load_environ_or_config_settings()

    def load_environ_or_config_settings(self):
        # Defaults
        default_settings = {
            "lidarr_address": "http://192.168.1.2:8686",
            "lidarr_api_key": "",
            "lidarr_api_timeout": 120.0,
            "thread_limit": 1,
            "sleep_interval": 0,
            "fallback_to_top_result": False,
            "library_scan_on_completion": True,
            "sync_schedule": [],
            "minimum_match_ratio": 90,
            "secondary_search": "YTS",
            "preferred_codec": "mp3",
            "attempt_lidarr_import": False,
        }

        # Load settings from environmental variables (which take precedence) over the configuration file.
        self.lidarr_address = os.environ.get("lidarr_address", "")
        self.lidarr_api_key = os.environ.get("lidarr_api_key", "")
        lidarr_api_timeout = os.environ.get("lidarr_api_timeout", "")
        self.lidarr_api_timeout = float(lidarr_api_timeout) if lidarr_api_timeout else ""
        thread_limit = os.environ.get("thread_limit", "")
        self.thread_limit = int(thread_limit) if thread_limit else ""
        sleep_interval = os.environ.get("sleep_interval", "")
        self.sleep_interval = float(sleep_interval) if sleep_interval else ""
        fallback_to_top_result = os.environ.get("fallback_to_top_result", "")
        self.fallback_to_top_result = fallback_to_top_result.lower() == "true" if fallback_to_top_result != "" else ""
        library_scan_on_completion = os.environ.get("library_scan_on_completion", "")
        self.library_scan_on_completion = library_scan_on_completion.lower() == "true" if library_scan_on_completion != "" else ""
        sync_schedule = os.environ.get("sync_schedule", "")
        self.sync_schedule = self.parse_sync_schedule(sync_schedule) if sync_schedule != "" else ""
        minimum_match_ratio = os.environ.get("minimum_match_ratio", "")
        self.minimum_match_ratio = float(minimum_match_ratio) if minimum_match_ratio else ""
        self.secondary_search = os.environ.get("secondary_search", "")
        self.preferred_codec = os.environ.get("preferred_codec", "")
        attempt_lidarr_import = os.environ.get("attempt_lidarr_import", "")
        self.attempt_lidarr_import = attempt_lidarr_import.lower() == "true" if attempt_lidarr_import != "" else ""

        # Load variables from the configuration file if not set by environmental variables.
        try:
            self.settings_config_file = os.path.join(self.config_folder, "settings_config.json")
            if os.path.exists(self.settings_config_file):
                self.general_logger.warning(f"Loading Settings via config file")
                with open(self.settings_config_file, "r") as json_file:
                    ret = json.load(json_file)
                    for key in ret:
                        if getattr(self, key) == "":
                            setattr(self, key, ret[key])
        except Exception as e:
            self.general_logger.error(f"Error Loading Config: {str(e)}")

        # Load defaults if not set by an environmental variable or configuration file.
        for key, value in default_settings.items():
            if getattr(self, key) == "":
                setattr(self, key, value)

        # Save config.
        self.save_config_to_file()

        # Start Scheduler
        thread = threading.Thread(target=self.schedule_checker, name="Schedule_Thread")
        thread.daemon = True
        thread.start()

    def save_config_to_file(self):
        try:
            with open(self.settings_config_file, "w") as json_file:
                json.dump(
                    {
                        "lidarr_address": self.lidarr_address,
                        "lidarr_api_key": self.lidarr_api_key,
                        "lidarr_api_timeout": self.lidarr_api_timeout,
                        "thread_limit": self.thread_limit,
                        "sleep_interval": self.sleep_interval,
                        "fallback_to_top_result": self.fallback_to_top_result,
                        "library_scan_on_completion": self.library_scan_on_completion,
                        "sync_schedule": self.sync_schedule,
                        "minimum_match_ratio": self.minimum_match_ratio,
                        "secondary_search": self.secondary_search,
                        "preferred_codec": self.preferred_codec,
                        "attempt_lidarr_import": self.attempt_lidarr_import,
                    },
                    json_file,
                    indent=4,
                )

        except Exception as e:
            self.general_logger.error(f"Error Saving Config: {str(e)}")

    def connect(self):
        socketio.emit("lidarr_update", {"status": self.lidarr_status, "data": self.lidarr_items})
        socketio.emit("ytdlp_update", {"status": self.ytdlp_status, "data": self.ytdlp_items, "percent_completion": self.percent_completion})
        self.clients_connected_counter += 1

    def disconnect(self):
        self.clients_connected_counter = max(0, self.clients_connected_counter - 1)

    def schedule_checker(self):
        try:
            while True:
                current_hour = time.localtime().tm_hour
                within_time_window = any(t == current_hour for t in self.sync_schedule)

                if within_time_window:
                    self.general_logger.warning(f"Time to Start - as in a time window: {self.sync_schedule}")
                    self.get_wanted_albums_from_lidarr()
                    if self.lidarr_items:
                        x = list(range(len(self.lidarr_items)))
                        self.add_items_to_download(x)
                    else:
                        self.general_logger.warning("No Missing Albums")

                    self.general_logger.warning("Big sleep for 1 Hour")
                    time.sleep(3600)
                    self.general_logger.warning(f"Checking every 10 minutes as not in a sync time window: {self.sync_schedule}")
                else:
                    time.sleep(600)

        except Exception as e:
            self.general_logger.error(f"Error in Scheduler: {str(e)}")
            self.general_logger.error(f"Scheduler Stopped")

    def get_wanted_albums_from_lidarr(self):
        try:
            self.general_logger.warning(f"Accessing Lidarr API")
            self.lidarr_status = "busy"
            self.lidarr_stop_event.clear()
            self.lidarr_items = []
            page = 1
            while True:
                if self.lidarr_stop_event.is_set():
                    return
                endpoint = f"{self.lidarr_address}/api/v1/wanted/missing?includeArtist=true"
                params = {"apikey": self.lidarr_api_key, "page": page}
                response = requests.get(endpoint, params=params, timeout=self.lidarr_api_timeout)
                if response.status_code == 200:
                    wanted_missing_albums = response.json()
                    if not wanted_missing_albums["records"]:
                        break
                    for album in wanted_missing_albums["records"]:
                        if self.lidarr_stop_event.is_set():
                            break
                        parsed_date = datetime.fromisoformat(album["releaseDate"].replace("Z", "+00:00"))
                        album_year = parsed_date.year
                        album_name = _general.convert_to_lidarr_format(album["title"])
                        album_folder = f"{album_name} ({album_year})"
                        album_full_path = os.path.join(album["artist"]["path"], album_folder)
                        album_release_id = album["releases"][0]["id"]
                        new_item = {
                            "artist_id": album["artistId"],
                            "artist_path": album["artist"]["path"],
                            "artist": album["artist"]["artistName"],
                            "album_name": album_name,
                            "album_folder": album_folder,
                            "album_full_path": album_full_path,
                            "album_year": album_year,
                            "album_id": album["id"],
                            "album_release_id": album_release_id,
                            "album_genres": ", ".join(album["genres"]),
                            "track_count": 0,
                            "missing_count": 0,
                            "missing_tracks": [],
                            "checked": True,
                            "status": "",
                        }
                        self.lidarr_items.append(new_item)

                    page += 1
                else:
                    self.general_logger.error(f"Lidarr Wanted API Error Code: {response.status_code}")
                    self.general_logger.error(f"Lidarr Wanted API Error Text: {response.text}")
                    socketio.emit("new_toast_msg", {"title": f"Lidarr API Error: {response.status_code}", "message": response.text})
                    break

            self.lidarr_items.sort(key=lambda x: (x["artist"], x["album_name"]))

            with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_limit) as executor:
                self.lidarr_futures = [executor.submit(self.get_missing_tracks_for_album, album) for album in self.lidarr_items]
                concurrent.futures.wait(self.lidarr_futures)

            self.lidarr_status = "stopped" if self.lidarr_stop_event.is_set() else "complete"

        except Exception as e:
            self.general_logger.error(f"Error Getting Missing Albums: {str(e)}")
            self.lidarr_status = "error"
            socketio.emit("new_toast_msg", {"title": "Error Getting Missing Albums", "message": str(e)})

        finally:
            socketio.emit("lidarr_update", {"status": self.lidarr_status, "data": self.lidarr_items})

    def get_missing_tracks_for_album(self, req_album):
        self.general_logger.warning(f'Reading Missing Track list of {req_album["artist"]} - {req_album["album_name"]} from Lidarr API')
        endpoint = f"{self.lidarr_address}/api/v1/track"
        params = {"apikey": self.lidarr_api_key, "albumId": req_album["album_id"]}
        try:
            response = requests.get(endpoint, params=params, timeout=self.lidarr_api_timeout)
            if response.status_code == 200:
                tracks = response.json()
                track_count = len(tracks)
                for track in tracks:
                    if self.lidarr_stop_event.is_set():
                        return
                    if not track.get("hasFile", False):
                        new_item = {
                            "artist": req_album["artist"],
                            "track_title": track["title"],
                            "track_number": track["trackNumber"],
                            "absolute_track_number": track["absoluteTrackNumber"],
                            "track_id": track["id"],
                            "link": "",
                            "title_of_link": "",
                        }
                        req_album["missing_tracks"].append(new_item)

                req_album["track_count"] = track_count
                req_album["missing_count"] = len(req_album["missing_tracks"])

            else:
                self.general_logger.error(req_album["album_name"])
                self.general_logger.error(f"Lidarr Track API Error Code: {response.status_code}")
                self.general_logger.error(f"Lidarr Track API Error Text: {response.text}")

        except Exception as e:
            self.general_logger.error(req_album["album_name"])
            self.general_logger.error(f"Error Getting Missing Tracks: {str(e)}")
            socketio.emit("new_toast_msg", {"title": "Error Getting Missing Tracks", "message": str(e)})

    def attempt_lidarr_song_import(self, req_album, song, filename):
        try:
            self.general_logger.warning(f"Attempting import of song via Lidarr API")
            endpoint = f"{self.lidarr_address}/api/v1/manualimport"
            headers = {"X-Api-Key": self.lidarr_api_key, "Content-Type": "application/json"}
            full_file_path = os.path.join(req_album["album_full_path"], filename)
            data = {
                "id": song["track_id"],
                "path": full_file_path,
                "name": song["track_title"],
                "artistId": req_album["artist_id"],
                "albumId": req_album["album_id"],
                "albumReleaseId": req_album["album_release_id"],
                "quality": {},
                "releaseGroup": "",
                "indexerFlags": 0,
                "downloadId": "",
                "additionalFile": False,
                "replaceExistingFiles": False,
                "disableReleaseSwitching": False,
                "rejections": [],
            }
            response = requests.post(endpoint, json=[data], headers=headers)
            if response.status_code == 202:
                self.general_logger.warning(f"Song import initiated")
            else:
                self.general_logger.error(f"Import Attempt - Failed to initiate song import: {response.status_code}")
                self.general_logger.error(f"Import Attempt - Error message: {response.text}")

        except Exception as e:
            self.general_logger.error(f"Error occurred while attempting import of song: {str(e)}")

    def trigger_lidarr_scan(self):
        try:
            endpoint = "/api/v1/rootfolder"
            headers = {"X-Api-Key": self.lidarr_api_key}
            root_folder_list = []
            response = requests.get(f"{self.lidarr_address}{endpoint}", headers=headers)
            endpoint = "/api/v1/command"
            if response.status_code == 200:
                root_folders = response.json()
                for folder in root_folders:
                    root_folder_list.append(folder["path"])
            else:
                self.general_logger.warning(f"No Lidarr root folders found")

            if root_folder_list:
                data = {"name": "RescanFolders", "folders": root_folder_list}
                headers = {"X-Api-Key": self.lidarr_api_key, "Content-Type": "application/json"}
                response = requests.post(f"{self.lidarr_address}{endpoint}", json=data, headers=headers)
                if response.status_code != 201:
                    self.general_logger.warning(f"Failed to start lidarr library scan")

        except Exception as e:
            self.general_logger.error(f"Lidarr library scan failed: {str(e)}")

        else:
            self.general_logger.warning(f"Lidarr library scan started")

    def add_items_to_download(self, data):
        try:
            self.ytdlp_stop_event.clear()
            if self.ytdlp_status == "complete" or self.ytdlp_status == "stopped":
                self.ytdlp_items = []
                self.percent_completion = 0
            for i in range(len(self.lidarr_items)):
                if i in data:
                    self.lidarr_items[i]["status"] = "Queued"
                    self.lidarr_items[i]["checked"] = True
                    self.ytdlp_items.append(self.lidarr_items[i])
                else:
                    self.lidarr_items[i]["checked"] = False

            if self.ytdlp_in_progress_flag == False:
                self.index = 0
                self.ytdlp_in_progress_flag = True
                thread = threading.Thread(target=self.master_queue, name="Queue_Thread")
                thread.daemon = True
                thread.start()

        except Exception as e:
            self.general_logger.error(str(e))
            socketio.emit("new_toast_msg", {"title": "Error adding new items", "message": str(e)})

        finally:
            socketio.emit("ytdlp_update", {"status": self.ytdlp_status, "data": self.ytdlp_items, "percent_completion": self.percent_completion})
            socketio.emit("new_toast_msg", {"title": "Download Queue Updated", "message": "New Items added to Queue"})

    def master_queue(self):
        try:
            while not self.ytdlp_stop_event.is_set() and self.index < len(self.ytdlp_items):
                self.ytdlp_status = "running"
                with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_limit) as executor:
                    self.ytdlp_futures = []
                    start_position = self.index
                    for req_album in self.ytdlp_items[start_position:]:
                        if self.ytdlp_stop_event.is_set():
                            break
                        self.ytdlp_futures.append(executor.submit(self.find_link_and_download, req_album))
                    concurrent.futures.wait(self.ytdlp_futures)

            if self.ytdlp_stop_event.is_set():
                self.ytdlp_status = "stopped"
                self.general_logger.warning("Downloading Stopped")
                self.ytdlp_in_progress_flag = False
            else:
                self.ytdlp_status = "complete"
                self.general_logger.warning("Downloading Finished")
                self.ytdlp_in_progress_flag = False
                if self.library_scan_on_completion:
                    self.trigger_lidarr_scan()

        except Exception as e:
            self.general_logger.error(f"Error in Master Queue: {str(e)}")
            self.ytdlp_status = "failed"
            socketio.emit("new_toast_msg", {"title": "Error in Master Queue", "message": str(e)})

        finally:
            socketio.emit("ytdlp_update", {"status": self.ytdlp_status, "data": self.ytdlp_items, "percent_completion": self.percent_completion})
            socketio.emit("new_toast_msg", {"title": "End of Session", "message": f"Downloading {self.ytdlp_status.capitalize()}"})

    def find_link_and_download(self, req_album):
        try:
            self._link_finder(req_album)
            if self.ytdlp_stop_event.is_set():
                return
            req_album["status"] = "Starting Download"
            artist_str = os.path.basename(req_album["artist_path"].rstrip("/"))
            album_name = req_album["album_name"]
            folder_with_year = req_album["album_folder"]
            grabbed_count = 0
            existing_count = 0
            error_count = 0
            song_links = [x for x in req_album["missing_tracks"] if x["link"] != ""]
            total_req = len(song_links)
            self.general_logger.warning(f"Valid link count of {total_req} for: {artist_str} - {album_name}")
            for song in song_links:
                if self.ytdlp_stop_event.is_set():
                    return
                else:
                    title = song["title_of_link"]
                    link = song["link"]
                    self.general_logger.warning(f"Starting Download of: {title}")
                    title_str = _general.convert_to_lidarr_format(title)
                    track_number = str(song["absolute_track_number"]).zfill(2)
                    file_name = os.path.join(artist_str, folder_with_year, f"{artist_str} - {album_name} - {track_number} - {title_str}")
                    full_file_path = os.path.join(self.download_folder, file_name)
                    full_file_path_with_ext = f"{full_file_path}.{self.preferred_codec}"

                    if not os.path.exists(full_file_path_with_ext):
                        try:
                            ydl_opts = {
                                "ffmpeg_location": "/usr/bin/ffmpeg",
                                "format": "251/best",
                                "outtmpl": full_file_path,
                                "quiet": False,
                                "progress_hooks": [self.progress_callback],
                                "writethumbnail": True,
                                "postprocessors": [
                                    {
                                        "key": "FFmpegExtractAudio",
                                        "preferredcodec": self.preferred_codec,
                                        "preferredquality": "0",
                                    },
                                    {
                                        "key": "EmbedThumbnail",
                                    },
                                    {
                                        "key": "FFmpegMetadata",
                                    },
                                ],
                            }
                            if self.cookies_path:
                                ydl_opts["cookiefile"] = self.cookies_path
                            yt_downloader = yt_dlp.YoutubeDL(ydl_opts)
                            yt_downloader.download([link])
                            self.general_logger.warning(f"DL Complete : {link}")
                            _general.add_metadata(self.general_logger, song, req_album, full_file_path_with_ext)
                            grabbed_count += 1
                            if self.attempt_lidarr_import:
                                self.attempt_lidarr_song_import(req_album, song, f"{artist_str} - {album_name} - {track_number} - {title_str}.{self.preferred_codec}")

                            self.ytdlp_stop_event.wait(self.sleep_interval)
                            if self.ytdlp_stop_event.is_set():
                                return

                        except Exception as e:
                            self.general_logger.error(f"Error downloading song: {link}. Error message: {e}")
                            error_count += 1

                    else:
                        existing_count += 1
                        self.general_logger.warning(f"File Already Exists: {artist_str} - {title_str}")

                song_processed_count = grabbed_count + error_count + existing_count
                req_album["status"] = f"Processed: {song_processed_count} of {total_req}"
                self.percent_completion = 100 * (self.index / len(self.ytdlp_items)) if self.ytdlp_items else 0
                socketio.emit("ytdlp_update", {"status": self.ytdlp_status, "data": self.ytdlp_items, "percent_completion": self.percent_completion})

            if self.ytdlp_stop_event.is_set():
                req_album["status"] = "Download Stopped"
            else:
                if total_req < req_album["missing_count"]:
                    req_album["status"] = "Album Incomplete"
                elif grabbed_count + existing_count == total_req:
                    req_album["status"] = "Download Complete"
                elif error_count == total_req:
                    req_album["status"] = "Download Failed"
                else:
                    req_album["status"] = "Partially Complete"

        except Exception as e:
            self.general_logger.error(f"Error Downloading: {str(e)}")
            req_album["status"] = "Download Error"

        finally:
            self.index += 1
            self.percent_completion = 100 * (self.index / len(self.ytdlp_items)) if self.ytdlp_items else 0
            socketio.emit("ytdlp_update", {"status": self.ytdlp_status, "data": self.ytdlp_items, "percent_completion": self.percent_completion})

    def progress_callback(self, d):
        if self.ytdlp_stop_event.is_set():
            raise Exception("Cancelled")
        if d["status"] == "finished":
            self.general_logger.warning("Download complete")

        elif d["status"] == "downloading":
            self.general_logger.warning(f'Downloaded {d["_percent_str"]} of {d["_total_bytes_str"]} at {d["_speed_str"]}')

    def _link_finder(self, req_album):
        try:
            self.general_logger.warning(f'Searching for: {req_album["artist"]} - {req_album["album_name"]}')
            artist = req_album["artist"]
            album_name = req_album["album_name"]
            number_tracks_in_album = req_album["track_count"]
            number_of_missing_tracks = req_album["missing_count"]
            query_text = f"{artist} - {album_name}"

            cleaned_artist = _general.string_cleaner(artist).lower()
            cleaned_album = _general.string_cleaner(album_name).lower()

            whole_album_required = number_tracks_in_album == number_of_missing_tracks
            if whole_album_required:
                self._get_album_links(req_album, artist, album_name, cleaned_artist, cleaned_album, query_text)

            # Check if there are links for each track
            number_of_links = len([x["link"] for x in req_album["missing_tracks"] if x["link"] != ""])
            all_tracks_found = number_of_links == len(req_album["missing_tracks"])
            if all_tracks_found:
                req_album["status"] = "All Tracks Found"
                socketio.emit("ytdlp_update", {"status": self.ytdlp_status, "data": self.ytdlp_items, "percent_completion": self.percent_completion})
                self.general_logger.warning(f'Links found for all tracks of: {req_album["artist"]} - {req_album["album_name"]}')
            else:
                req_album["status"] = "Searching"
                socketio.emit("ytdlp_update", {"status": self.ytdlp_status, "data": self.ytdlp_items, "percent_completion": self.percent_completion})
                self._get_song_links(req_album, artist, cleaned_artist)

                # Second Check
                number_of_links = len([x["link"] for x in req_album["missing_tracks"] if x["link"] != ""])
                all_tracks_found = number_of_links == len(req_album["missing_tracks"])
                if all_tracks_found:
                    req_album["status"] = "All Tracks Found"
                    socketio.emit("ytdlp_update", {"status": self.ytdlp_status, "data": self.ytdlp_items, "percent_completion": self.percent_completion})
                    self.general_logger.warning(f'Links found for all Tracks of: {req_album["artist"]} - {req_album["album_name"]}')
                else:
                    self.general_logger.warning(f'Not all tracks found, searching again: {req_album["artist"]} - {req_album["album_name"]}')
                    self._get_song_links_secondary(req_album, artist, cleaned_artist)

        except Exception as e:
            self.general_logger.error(f"Error in Link Finder: {str(e)}")

    def _get_song_links_secondary(self, req_album, artist, cleaned_artist):
        try:
            ytmusic = YTMusic()
            for missing_track in req_album["missing_tracks"]:
                if self.ytdlp_stop_event.is_set():
                    return
                if missing_track["link"] == "":
                    song_title = missing_track["track_title"]
                    cleaned_song_title = _general.string_cleaner(song_title).lower()
                    query_text = f'{missing_track["artist"]} - {missing_track["track_title"]}'
                    search_results = ytmusic.search(query=query_text, filter="songs", limit=20)
                    song_match = _matcher.song_matcher(self.minimum_match_ratio, artist, cleaned_artist, song_title, cleaned_song_title, search_results)
                    if song_match:
                        missing_track["link"] = f'https://www.youtube.com/watch?v={song_match["videoId"]}'
                        missing_track["title_of_link"] = song_match["title"]
                    elif self.fallback_to_top_result:
                        if search_results:
                            missing_track["link"] = f'https://www.youtube.com/watch?v={search_results[0]["videoId"]}'
                            missing_track["title_of_link"] = search_results[0]["title"]
                    else:
                        song_title = missing_track["track_title"]
                        search_results = self._yt_search(query_text)
                        song_match = _matcher.song_matcher_yt(self.minimum_match_ratio, query_text, search_results)
                        if song_match:
                            if self.secondary_search == "YTS":
                                missing_track["link"] = song_match["link"]
                                missing_track["title_of_link"] = song_match["title"]
                            elif self.secondary_search == "YTDLP":
                                missing_track["link"] = song_match["webpage_url"]
                                missing_track["title_of_link"] = song_match["title"]

            number_of_links = len([x["link"] for x in req_album["missing_tracks"] if x["link"] != ""])
            self.general_logger.warning(f'Found {number_of_links} of the missing {len(req_album["missing_tracks"])} tracks: {req_album["artist"]} - {req_album["album_name"]}')

        except Exception as e:
            self.general_logger.error(f"Error in Secondary Search: {str(e)}")

    def _get_song_links(self, req_album, artist, cleaned_artist):
        try:
            ytmusic = YTMusic()
            self.general_logger.warning(f'Searching for individual Tracks: {req_album["artist"]} - {req_album["album_name"]}')
            for missing_track in req_album["missing_tracks"]:
                if self.ytdlp_stop_event.is_set():
                    return
                if missing_track["link"] == "":
                    song_title = missing_track["track_title"]
                    cleaned_song_title = _general.string_cleaner(song_title).lower()

                    query_text = f'{missing_track["artist"]} - {missing_track["track_title"]}'
                    search_results = ytmusic.search(query=query_text, filter="songs", limit=5)
                    song_match = _matcher.song_matcher(self.minimum_match_ratio, artist, cleaned_artist, song_title, cleaned_song_title, search_results)
                    if song_match:
                        missing_track["link"] = f'https://www.youtube.com/watch?v={song_match["videoId"]}'
                        missing_track["title_of_link"] = song_match["title"]

                    elif self.fallback_to_top_result:
                        if search_results:
                            missing_track["link"] = f'https://www.youtube.com/watch?v={search_results[0]["videoId"]}'
                            missing_track["title_of_link"] = search_results[0]["title"]

        except Exception as e:
            self.general_logger.error(f"Error in Song Search: {str(e)}")

    def _get_album_links(self, req_album, artist, album_name, cleaned_artist, cleaned_album, query_text):
        try:
            ytmusic = YTMusic()
            search_results = ytmusic.search(query=query_text, filter="albums", limit=10)

            self.general_logger.warning(f'Searching for Whole Album: {req_album["artist"]} - {req_album["album_name"]}')
            album_match = _matcher.album_matcher(self.minimum_match_ratio, artist, album_name, cleaned_artist, cleaned_album, search_results)
            if album_match:
                req_album["status"] = "Album Found"
                album_details = ytmusic.get_album(album_match["browseId"])

                for track in album_details["tracks"]:
                    if self.ytdlp_stop_event.is_set():
                        return
                    for missing_track in req_album["missing_tracks"]:
                        missing_track_title = _general.string_cleaner(missing_track["track_title"])
                        song_title = _general.string_cleaner(track["title"])
                        if fuzz.ratio(song_title, missing_track_title) > 90:
                            missing_track["link"] = f'https://www.youtube.com/watch?v={track["videoId"]}'
                            missing_track["title_of_link"] = track["title"]
                            break

            elif self.fallback_to_top_result:
                if search_results:
                    req_album["status"] = "Album Found"
                    album_details = ytmusic.get_album(search_results[0]["browseId"])

                    for track in album_details["tracks"]:
                        if self.ytdlp_stop_event.is_set():
                            return
                        for missing_track in req_album["missing_tracks"]:
                            missing_track_title = _general.string_cleaner(missing_track["track_title"])
                            song_title = _general.string_cleaner(track["title"])
                            if fuzz.ratio(song_title, missing_track_title) > 90:
                                missing_track["link"] = f'https://www.youtube.com/watch?v={track["videoId"]}'
                                missing_track["title_of_link"] = track["title"]
                                break
                else:
                    self.general_logger.warning(f'No search results for album: {req_album["artist"]} - {req_album["album_name"]}')

            else:
                self.general_logger.warning(f'No matching album for: {req_album["artist"]} - {req_album["album_name"]}')

        except Exception as e:
            self.general_logger.error(f"Error in Album Search: {str(e)}")

    def _yt_search(self, query_text):
        try:
            if self.secondary_search == "YTDLP":
                ydl_opts = {
                    "default_search": "ytsearch10",
                    "quiet": True,
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    search = ydl.extract_info(query_text, download=False)
                    search_results = search.get("entries", [])

            elif self.secondary_search == "YTS":
                videos_search = youtubesearchpython.VideosSearch(query_text, limit=10)
                search_results = videos_search.result()["result"]

            if self.ytdlp_stop_event.is_set():
                return
            else:
                return search_results

        except Exception as e:
            self.general_logger.error(f"Error in YouTube Search: {str(e)}")

    def reset_lidarr(self):
        self.lidarr_stop_event.set()
        for future in self.lidarr_futures:
            if not future.done():
                future.cancel()
        self.lidarr_items = []

    def stop_ytdlp(self):
        try:
            self.ytdlp_stop_event.set()
            for future in self.ytdlp_futures:
                if not future.done():
                    future.cancel()
            for x in self.ytdlp_items[self.index :]:
                x["status"] = "Download Stopped"

        except Exception as e:
            self.general_logger.error(f"Error Stopping yt_dlp: {str(e)}")

        finally:
            self.ytdlp_status = "stopped"
            socketio.emit("ytdlp_update", {"status": self.ytdlp_status, "data": self.ytdlp_items, "percent_completion": self.percent_completion})

    def reset_ytdlp(self):
        try:
            self.ytdlp_stop_event.set()
            for future in self.ytdlp_futures:
                if not future.done():
                    future.cancel()
            self.ytdlp_items = []
            self.percent_completion = 0

        except Exception as e:
            self.general_logger.error(f"Error Stopping yt_dlp: {str(e)}")

        else:
            self.general_logger.warning("Reset Complete")

        finally:
            socketio.emit("ytdlp_update", {"status": self.ytdlp_status, "data": self.ytdlp_items, "percent_completion": self.percent_completion})

    def update_settings(self, data):
        try:
            self.lidarr_address = data["lidarr_address"]
            self.lidarr_api_key = data["lidarr_api_key"]
            self.sleep_interval = float(data["sleep_interval"])
            self.minimum_match_ratio = float(data["minimum_match_ratio"])
            self.sync_schedule = self.parse_sync_schedule(data["sync_schedule"])

        except Exception as e:
            self.general_logger.error(f"Failed to update settings: {str(e)}")

    def parse_sync_schedule(self, input_string):
        try:
            ret = []
            if input_string != "":
                raw_sync_schedule = [int(re.sub(r"\D", "", start_time.strip())) for start_time in input_string.split(",")]
                temp_sync_schedule = [0 if x < 0 or x > 23 else x for x in raw_sync_schedule]
                cleaned_sync_schedule = sorted(list(set(temp_sync_schedule)))
                ret = cleaned_sync_schedule

        except Exception as e:
            self.general_logger.error(f"Time not in correct format: {str(e)}")
            self.general_logger.error(f"Schedule Set to {ret}")

        finally:
            return ret

    def load_settings(self):
        data = {
            "lidarr_address": self.lidarr_address,
            "lidarr_api_key": self.lidarr_api_key,
            "sleep_interval": self.sleep_interval,
            "sync_schedule": self.sync_schedule,
            "minimum_match_ratio": self.minimum_match_ratio,
        }
        socketio.emit("settings_loaded", data)


app = Flask(__name__)
app.secret_key = "secret_key"
socketio = SocketIO(app)
data_handler = DataHandler()


@app.route("/")
def home():
    return render_template("base.html")


@socketio.on("lidarr_get_wanted")
def lidarr():
    thread = threading.Thread(target=data_handler.get_wanted_albums_from_lidarr, name="Lidarr_Thread")
    thread.daemon = True
    thread.start()


@socketio.on("stop_lidarr")
def stop_lidarr():
    data_handler.lidarr_stop_event.set()


@socketio.on("reset_lidarr")
def reset_lidarr():
    data_handler.reset_lidarr()


@socketio.on("stop_ytdlp")
def stop_ytdlp():
    data_handler.stop_ytdlp()


@socketio.on("reset_ytdlp")
def reset_ytdlp():
    data_handler.reset_ytdlp()


@socketio.on("add_to_download_list")
def add_to_download_list(data):
    data_handler.add_items_to_download(data)


@socketio.on("connect")
def connection():
    data_handler.connect()


@socketio.on("disconnect")
def disconnect():
    data_handler.disconnect()


@socketio.on("load_settings")
def load_settings():
    data_handler.load_settings()


@socketio.on("update_settings")
def update_settings(data):
    data_handler.update_settings(data)
    data_handler.save_config_to_file()


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
