import logging
import os
import threading
import unicodedata
import requests
from ytmusicapi import YTMusic
from flask import Flask, render_template
from flask_socketio import SocketIO
import yt_dlp
import concurrent.futures
import re
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TPE2, TYER, TDRC, TRCK


class Data_Handler:
    def __init__(self, lidarr_address, lidarr_api_key, thread_limit, fallback_to_top_result):
        self.thread_limit = thread_limit
        self.lidarrAddress = lidarr_address
        self.lidarrApiKey = lidarr_api_key
        self.lidarrMaxTags = 250
        self.lidarrApiTimeout = 120
        self.youtubeSuffix = ""
        self.sleepInterval = 0
        self.download_folder = "downloads"
        self.fallback_to_top_result = fallback_to_top_result
        self.reset()

    def reset(self):
        self.lidarr_items = []
        self.download_list = []
        self.futures = []
        self.stop_lidarr_event = threading.Event()
        self.stop_downloading_event = threading.Event()
        self.stop_monitoring_event = threading.Event()
        self.monitor_active_flag = False
        self.running_flag = False
        self.status = "Idle"
        self.index = 0
        self.percent_completion = 0

    def get_missing_from_lidarr(self):
        try:
            self.stop_lidarr_event.clear()
            self.lidarr_items = []
            endpoint = f"{self.lidarrAddress}/api/v1/wanted/missing?includeArtist=true"
            params = {"apikey": self.lidarrApiKey, "pageSize": self.lidarrMaxTags, "sortKey": "artists.sortname", "sortDir": "asc"}
            response = requests.get(endpoint, params=params, timeout=self.lidarrApiTimeout)
            if response.status_code == 200:
                wanted_missing_albums = response.json()
                for album in wanted_missing_albums["records"]:
                    self.lidarr_items.append(album["artist"]["artistName"] + " - " + album["title"])
                ret = {"Status": "Success", "Data": self.lidarr_items}
            else:
                ret = {"Status": "Error", "Code": response.status_code, "Data": response.text}

        except Exception as e:
            logger.error(str(e))
            ret = {"Status": "Error", "Code": 500, "Data": str(e)}

        finally:
            if not self.stop_lidarr_event.is_set():
                socketio.emit("lidarr_status", ret)
            else:
                ret = {"Status": "Error", "Code": "", "Data": ""}
                socketio.emit("lidarr_status", ret)

    def find_youtube_link_and_download(self, req_album):
        try:
            self.ytmusic = YTMusic()
            query_text = req_album["Item"]
            artist, album = query_text.split(" - ", maxsplit=1)

            cleaned_album = self.string_cleaner(album).lower()
            search_results = self.ytmusic.search(query=query_text, filter="albums", limit=10)

            found_browseId, year, album_found_name = self.matcher(artist, album, cleaned_album, search_results)

            folder = os.path.join(self.string_cleaner(artist), self.string_cleaner(album_found_name))
            folder_with_year = folder + year

            if found_browseId:
                req_album["Status"] = "Album Found"
                album_details = self.ytmusic.get_album(found_browseId)
                songs_info = []

                for i, track in enumerate(album_details["tracks"], start=1):
                    song_title = track["title"]
                    song_link = f"https://www.youtube.com/watch?v={track['videoId']}"
                    songs_info.append({"title": song_title, "link": song_link, "track_no": i})
            else:
                raise Exception("Nothing Found")

        except Exception as e:
            logger.error(f"Error downloading album: {req_album}. Error message: {e}")
            req_album["Status"] = "Search Failed"

        else:
            song_count = 0
            total = len(songs_info)
            artist_song_str = self.string_cleaner(artist)

            for song in songs_info:
                if self.stop_downloading_event.is_set():
                    break
                else:
                    title = song["title"]
                    link = song["link"]
                    title_str = self.string_cleaner(title)
                    track_no = str(song["track_no"]).zfill(2)
                    file_name = os.path.join(folder_with_year, artist_song_str + " - " + album_found_name + " - " + track_no + " - " + title_str)
                    full_file_path = os.path.join(self.download_folder, file_name)

                    if not os.path.exists(full_file_path + ".mp3"):
                        try:
                            ydl_opts = {
                                "ffmpeg_location": "/usr/bin/ffmpeg",
                                "format": "251/best",
                                "outtmpl": full_file_path,
                                "quiet": False,
                                "progress_hooks": [self.progress_callback],
                                "sleepInterval": self.sleepInterval,
                                "writethumbnail": True,
                                "postprocessors": [
                                    {
                                        "key": "FFmpegExtractAudio",
                                        "preferredcodec": "mp3",
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
                            yt_downloader = yt_dlp.YoutubeDL(ydl_opts)
                            yt_downloader.download([link])
                            logger.warning("yt_dl Complete : " + link)
                            self.add_metadata(song, album_details, full_file_path + ".mp3")

                        except Exception as e:
                            logger.error(f"Error downloading song: {link}. Error message: {e}")

                    else:
                        logger.warning("File Already Exists: " + artist + " " + title)
                song_count += 1
                req_album["Status"] = "Processed: " + str(song_count) + " of " + str(total)
            if self.stop_downloading_event.is_set():
                req_album["Status"] = "Download Stopped"
            else:
                req_album["Status"] = "Download Complete"
        finally:
            self.index += 1

    def progress_callback(self, d):
        if self.stop_downloading_event.is_set():
            raise Exception("Cancelled")
        if d["status"] == "finished":
            logger.warning("Download complete")

        elif d["status"] == "downloading":
            logger.warning(f'Downloaded {d["_percent_str"]} of {d["_total_bytes_str"]} at {d["_speed_str"]}')

    def add_metadata(self, song, album_details, full_file_path):
        try:
            metadata = ID3(full_file_path)
            metadata.add(TIT2(encoding=3, text=song["title"]))
            metadata.add(TRCK(encoding=3, text=str(song["track_no"])))
            metadata.add(TPE1(encoding=3, text=album_details["artists"][0]["name"]))
            metadata.add(TALB(encoding=3, text=album_details["title"]))
            metadata.add(TPE2(encoding=3, text=album_details["artists"][0]["name"]))
            metadata.add(TYER(encoding=3, text=album_details["year"]))
            metadata.add(TDRC(encoding=3, text=album_details["year"]))
            metadata.save()

            logger.warning(f"Metadata added for {full_file_path}")

        except Exception as e:
            logger.error(f"Error adding metadata for {full_file_path}: {e}")

    def matcher(self, artist, album, cleaned_album, search_results):
        year = ""
        folder_name = ""
        found_browseId = None
        if len(search_results):
            # Check for an exact match
            for item in search_results:
                cleaned_youtube_title = self.string_cleaner(item["title"]).lower()
                if cleaned_album == cleaned_youtube_title:
                    year = f" ({item['year']})"
                    found_browseId = item["browseId"]
                    folder_name = self.string_cleaner(item["title"])
                    logger.warning(f"Exact Match Found for: {artist} - {album} -> {item['artists'][0]['name']} - {item['title']}")
                    break
            else:
                # Try again but check for partial match, or reverse the check
                for item in search_results:
                    cleaned_youtube_title = self.string_cleaner(item["title"]).lower()
                    if cleaned_album in cleaned_youtube_title:
                        year = f" ({item['year']})"
                        found_browseId = item["browseId"]
                        folder_name = self.string_cleaner(item["title"])
                        logger.warning(f"Reverse Match Found for: {artist} - {album} -> {item['artists'][0]['name']} - {item['title']}")
                        break
                    if all(word in cleaned_album for word in cleaned_youtube_title.split()):
                        year = f" ({item['year']})"
                        found_browseId = item["browseId"]
                        folder_name = self.string_cleaner(item["title"])
                        logger.warning(f"Partial Match Found for: {artist} - {album} -> {item['artists'][0]['name']} - {item['title']}")
                        break
                else:
                    # Otherwise select top result if fallback_to_top_result is true
                    if self.fallback_to_top_result:
                        year = f" ({search_results[0]['year']})"
                        found_browseId = search_results[0]["browseId"]
                        folder_name = self.string_cleaner(search_results[0]["title"])
                        logger.warning(f"Using top result as no match found but fallback is enabled: {artist} - {album} -> {search_results[0]['title']} - {search_results[0]['artists'][0]['name']}")
                    else:
                        logger.error(f"No match found and fallback is turned off : {artist} - {album}")
        else:
            logger.error(f"Search for {artist} - {album} did not find anything!")
        return found_browseId, year, folder_name

    def master_queue(self):
        try:
            while not self.stop_downloading_event.is_set() and self.index < len(self.download_list):
                self.status = "Running"
                with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_limit) as executor:
                    self.futures = []
                    start_position = self.index
                    for album in self.download_list[start_position:]:
                        if self.stop_downloading_event.is_set():
                            break
                        logger.warning("Searching for Album: " + album["Item"])
                        self.futures.append(executor.submit(self.find_youtube_link_and_download, album))
                    concurrent.futures.wait(self.futures)

            if not self.stop_downloading_event.is_set():
                self.status = "Complete"
                logger.warning("Finished")
                self.running_flag = False

            else:
                self.status = "Stopped"
                logger.warning("Stopped")
                self.running_flag = False
                ret = {"Status": "Error", "Data": "Stopped"}
                socketio.emit("yt_dlp_status", ret)

        except Exception as e:
            logger.error(str(e))
            self.status = "Stopped"
            logger.warning("Stopped")
            ret = {"Status": "Error", "Data": str(e)}
            socketio.emit("yt_dlp_status", ret)

    def string_cleaner(self, input_string):
        if isinstance(input_string, str):
            raw_string = re.sub(r'[\/:*?"<>|]', " ", input_string)
            temp_string = re.sub(r"\s+", " ", raw_string)
            stripped_string = temp_string.strip()
            cleaned_string = re.sub(r"['‘’ʼ]", "'", stripped_string)
            normalised_string = unicodedata.normalize("NFKD", cleaned_string)
            return normalised_string

        elif isinstance(input_string, list):
            cleaned_strings = []
            for string in input_string:
                raw_string = re.sub(r'[\/:*?"<>|]', " ", string)
                temp_string = re.sub(r"\s+", " ", raw_string)
                stripped_string = temp_string.strip()
                cleaned_string = re.sub(r"['‘’ʼ]", "'", stripped_string)
                normalised_string = unicodedata.normalize("NFKD", cleaned_string)
                cleaned_strings.append(normalised_string)
            return cleaned_strings

    def monitor(self):
        while not self.stop_monitoring_event.is_set():
            self.percent_completion = 100 * (self.index / len(self.download_list)) if self.download_list else 0
            custom_data = {"Data": self.download_list, "Status": self.status, "Percent_Completion": self.percent_completion}
            socketio.emit("progress_status", custom_data)
            self.stop_monitoring_event.wait(1)


app = Flask(__name__)
app.secret_key = "secret_key"
socketio = SocketIO(app)

logging.basicConfig(level=logging.DEBUG, format="%(message)s")
logger = logging.getLogger()

lidarr_address = os.environ.get("lidarr_address", "http://192.168.1.2:8686")
lidarr_api_key = os.environ.get("lidarr_api_key", "0123456789")
thread_limit = int(os.environ.get("thread_limit", 1))
fallback_to_top_result = os.environ.get("fallback_to_top_result", False)  # if no match is found use top result
data_handler = Data_Handler(lidarr_address, lidarr_api_key, thread_limit, fallback_to_top_result)


@app.route("/")
def home():
    return render_template("base.html")


@socketio.on("lidarr")
def lidarr():
    thread = threading.Thread(target=data_handler.get_missing_from_lidarr, name="Lidarr_Thread")
    thread.daemon = True
    thread.start()


@socketio.on("add_to_download_list")
def add_to_download_list(data):
    try:
        data_handler.stop_downloading_event.clear()
        if data_handler.status == "Complete":
            data_handler.download_list = []
        for item in data["Data"]:
            full_item = {"Item": item, "Status": "Queued"}
            data_handler.download_list.append(full_item)

        if data_handler.running_flag == False:
            data_handler.index = 0
            data_handler.running_flag = True
            thread = threading.Thread(target=data_handler.master_queue, name="Queue_Thread")
            thread.daemon = True
            thread.start()

        ret = {"Status": "Success"}

    except Exception as e:
        logger.error(str(e))
        ret = {"Status": "Error", "Data": str(e)}

    finally:
        socketio.emit("yt_dlp_status", ret)


@socketio.on("connect")
def connection():
    if data_handler.monitor_active_flag == False:
        data_handler.stop_monitoring_event.clear()
        thread = threading.Thread(target=data_handler.monitor, name="Monitor_Thread")
        thread.daemon = True
        thread.start()
        data_handler.monitor_active_flag = True


@socketio.on("loadSettings")
def loadSettings():
    data = {
        "lidarrAddress": data_handler.lidarrAddress,
        "lidarrApiKey": data_handler.lidarrApiKey,
        "lidarrApiTimeout": data_handler.lidarrApiTimeout,
        "lidarrMaxTags": data_handler.lidarrMaxTags,
        "youtubeSuffix": data_handler.youtubeSuffix,
        "sleepInterval": data_handler.sleepInterval,
    }
    socketio.emit("settingsLoaded", data)


@socketio.on("updateSettings")
def updateSettings(data):
    data_handler.lidarrAddress = data["lidarrAddress"]
    data_handler.lidarrApiKey = data["lidarrApiKey"]
    data_handler.lidarrApiTimeout = int(data["lidarrApiTimeout"])
    data_handler.lidarrMaxTags = int(data["lidarrMaxTags"])
    data_handler.youtubeSuffix = data["youtubeSuffix"]
    data_handler.sleepInterval = int(data["sleepInterval"])


@socketio.on("disconnect")
def disconnect():
    data_handler.stop_monitoring_event.set()
    data_handler.monitor_active_flag = False


@socketio.on("stopper")
def stopper():
    data_handler.stop_lidarr_event.set()
    data_handler.stop_downloading_event.set()
    for album in data_handler.download_list[data_handler.index :]:
        album["Status"] = "Download Cancelled"
    for future in data_handler.futures:
        if not future.done():
            future.cancel()


@socketio.on("reset")
def reset():
    stopper()
    data_handler.reset()
    custom_data = {"Data": data_handler.download_list, "Status": data_handler.status, "Percent_Completion": data_handler.percent_completion}
    socketio.emit("progress_status", custom_data)


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
