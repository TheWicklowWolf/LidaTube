import logging
import os
import sys
import threading
import googlesearch
import requests
from flask import Flask, render_template
from flask_socketio import SocketIO


class Data_Handler:
    def __init__(self, lidarrAddress, lidarrAPIKey, metubeAddress):
        self.full_metube_address = metubeAddress + "/add"
        self.lidarrAddress = lidarrAddress
        self.lidarrAPIKey = lidarrAPIKey
        self.lidarrMaxTags = 250
        self.lidarrApiTimeout = 120
        self.youtubeSuffix = "full album YouTube playlist"
        self.metubeSleepInterval = 450
        self.reset()

    def reset(self):
        self.lidarr_items = []
        self.metube_items = []
        self.stop_lidarr_event = threading.Event()
        self.stop_metube_event = threading.Event()
        self.stop_monitoring_event = threading.Event()
        self.monitor_active_flag = False
        self.in_progress_flag = False
        self.sleeping_flag = False
        self.complete_flag = False
        self.index = 0

    def get_missing_from_lidarr(self):
        try:
            self.stop_lidarr_event.clear()
            self.lidarr_items = []
            endpoint = f"{self.lidarrAddress}/api/v1/wanted/missing?includeArtist=true"
            params = {"apikey": self.lidarrAPIKey, "pageSize": self.lidarrMaxTags, "sortKey": "artists.sortname", "sortDir": "asc"}
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

    def add_items(self):
        try:
            while not self.stop_metube_event.is_set() and self.index < len(self.metube_items):
                item = self.metube_items[self.index]["Item"]
                search_results = googlesearch.search(item + self.youtubeSuffix, stop=10)
                first_result = next((x for x in search_results if "playlist" in x), None)
                if first_result:
                    self.metube_items[self.index]["Link Found"] = True
                    ret = self.add_to_metube(first_result, item)
                    if ret == "Success":
                        self.metube_items[self.index]["Added to Metube"] = True
                    else:
                        socketio.emit("metube_status", {"Status": "Error", "Data": ret + " Error Adding to metube"})
                else:
                    socketio.emit("metube_status", {"Status": "Error", "Data": item + " No Playlist Found"})
                    self.index += 1
                    continue

                self.sleeping_flag = True
                if self.stop_metube_event.wait(timeout=self.metubeSleepInterval):
                    break
                self.sleeping_flag = False
                self.index += 1

            if not self.stop_metube_event.is_set():
                self.complete_flag = True
                self.in_progress_flag = False
                self.sleeping_flag = False
            else:
                self.complete_flag = False
                self.in_progress_flag = False
                self.sleeping_flag = False
                ret = {"Status": "Error", "Data": "Stopped"}
                socketio.emit("metube_status", ret)

        except Exception as e:
            logger.error(str(e))
            ret = {"Status": "Error", "Data": str(e)}
            socketio.emit("metube_status", ret)

    def add_to_metube(self, link, folder):
        payload = {"url": link, "quality": "best", "format": "mp3", "folder": folder}
        response = requests.post(self.full_metube_address, json=payload)
        if response.status_code == 200:
            return "Success"
        else:
            return str(response.status_code) + " : " + response.text

    def monitor(self):
        while not self.stop_monitoring_event.is_set():
            custom_data = {"Data": self.metube_items, "Sleeping": self.sleeping_flag, "Running": self.in_progress_flag, "Complete": self.complete_flag}
            socketio.emit("progress_status", custom_data)
            socketio.sleep(1)


app = Flask(__name__)
app.secret_key = "secret_key"
socketio = SocketIO(app)

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(message)s", datefmt="%d/%m/%Y %H:%M:%S", handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger()

try:
    lidarrAddress = os.environ["lidarr_address"]
    lidarrAPIKey = os.environ["lidarr_api_key"]
    metubeAddress = os.environ["metube_address"]
except:
    lidarrAddress = "http://192.168.1.2:8686"
    lidarrAPIKey = "1234567890"
    metubeAddress = "http://192.168.1.2:8080"

data_handler = Data_Handler(lidarrAddress, lidarrAPIKey, metubeAddress)


@app.route("/")
def home():
    return render_template("base.html")


@socketio.on("lidarr")
def lidarr():
    thread = threading.Thread(target=data_handler.get_missing_from_lidarr)
    thread.start()


@socketio.on("metube")
def metube(data):
    try:
        data_handler.stop_metube_event.clear()
        data_handler.complete_flag = False
        for item in data["Data"]:
            full_item = {"Item": item, "Link Found": False, "Added to Metube": False}
            data_handler.metube_items.append(full_item)

        if data_handler.in_progress_flag == False:
            data_handler.index = 0
            data_handler.in_progress_flag = True
            thread = threading.Thread(target=data_handler.add_items)
            thread.start()

        ret = {"Status": "Success"}

    except Exception as e:
        logger.error(str(e))
        ret = {"Status": "Error", "Data": str(e)}

    finally:
        socketio.emit("metube_status", ret)


@socketio.on("connect")
def connection():
    if data_handler.monitor_active_flag == False:
        data_handler.stop_monitoring_event.clear()
        thread = threading.Thread(target=data_handler.monitor)
        thread.start()
        data_handler.monitor_active_flag = True


@socketio.on("loadSettings")
def loadSettings():
    data = {"lidarrMaxTags": data_handler.lidarrMaxTags, "lidarrApiTimeout": data_handler.lidarrApiTimeout, "youtubeSuffix": data_handler.youtubeSuffix, "metubeSleepInterval": data_handler.metubeSleepInterval}
    socketio.emit("settingsLoaded", data)


@socketio.on("updateSettings")
def updateSettings(data):
    data_handler.lidarrMaxTags = int(data["lidarrMaxTags"])
    data_handler.lidarrApiTimeout = int(data["lidarrApiTimeout"])
    data_handler.youtubeSuffix = data["youtubeSuffix"]
    data_handler.metubeSleepInterval = int(data["metubeSleepInterval"])


@socketio.on("disconnect")
def disconnect():
    data_handler.stop_monitoring_event.set()
    data_handler.monitor_active_flag = False


@socketio.on("stopper")
def stopper():
    data_handler.stop_lidarr_event.set()
    data_handler.stop_metube_event.set()
    data_handler.sleeping_flag = False


@socketio.on("reset")
def reset():
    stopper()
    data_handler.reset()
    custom_data = {"Data": data_handler.metube_items, "Sleeping": data_handler.sleeping_flag, "Running": data_handler.in_progress_flag, "Complete": data_handler.complete_flag}
    socketio.emit("progress_status", custom_data)


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
