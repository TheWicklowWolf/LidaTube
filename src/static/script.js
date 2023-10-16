var lidarrButton = document.getElementById('lidarr_button');
var lidarrSpinner = document.getElementById('lidarr_spinner');
var lidarrStatus = document.getElementById('lidarr_status');
var metubeButton = document.getElementById('metube_button');
var metubeSpinner = document.getElementById('metube_spinner');
var metubeStatus = document.getElementById('metube_status');
var stopButton = document.getElementById('metube_button_stop');
var resetButton = document.getElementById('metube_button_reset');
var monitorButton = document.getElementById('metube_button_monitor');
var lidarrItemList = document.getElementById("lidarrItemList");
var selectAllCheckbox = document.getElementById("select-all");
var selectAllContainer = document.getElementById("select-all-container");
var metubeDataTable = document.getElementById('metube-data-table').getElementsByTagName('tbody')[0];
var configModal = document.getElementById('configModal');
var saveMessage = document.getElementById("saveMessage");
var saveChangesButton = document.getElementById("saveChangesBtn");
const lidarrMaxTags = document.getElementById("lidarrMaxTags");
const lidarrApiTimeout = document.getElementById("lidarrApiTimeout");
const youtubeSuffix = document.getElementById("youtubeSuffix");
const metubeSleepInterval = document.getElementById("metubeSleepInterval");
const runningLed = document.getElementById('running-led');
const sleepingLed = document.getElementById('sleeping-led');
const completeLed = document.getElementById('complete-led');
var lidarr_items = []
var socket = io();

function setLedStatus(ledElement, status) {
    if (status) {
        ledElement.classList.add('true');
        ledElement.classList.remove('false');
    } else {
        ledElement.classList.add('false');
        ledElement.classList.remove('true');
    }
}

setLedStatus(runningLed, false);
setLedStatus(sleepingLed, false);
setLedStatus(completeLed, false);

selectAllCheckbox.addEventListener("change", function () {
    var isChecked = this.checked;
    var checkboxes = document.querySelectorAll('input[name="lidarr_item"]');
    checkboxes.forEach(function (checkbox) {
        checkbox.checked = isChecked;
    });
});

lidarrButton.addEventListener('click', function () {
    lidarrButton.disabled = true;
    lidarrSpinner.style.display = "inline-flex";
    lidarrStatus.textContent = "Requesting Data from Lidarr API"
    socket.emit("lidarr");
});

metubeButton.addEventListener('click', function () {
    metubeButton.disabled = true;
    metubeSpinner.style.display = "inline-flex";
    var checkedItems = [];
    for (var i = 0; i < lidarr_items.length; i++) {
        var checkbox = document.getElementById("lidarr_" + i);

        if (checkbox.checked) {
            checkedItems.push(checkbox.value);
        }
    }
    socket.emit("metube", { "Data": checkedItems });
});

stopButton.addEventListener('click', function () {
    socket.emit("stopper");
    setLedStatus(runningLed, false);
    setLedStatus(sleepingLed, false);
});

configModal.addEventListener('show.bs.modal', function (event) {
    socket.emit("loadSettings");

    function handleSettingsLoaded(settings) {
        lidarrMaxTags.value = settings.lidarrMaxTags;
        lidarrApiTimeout.value = settings.lidarrApiTimeout;
        metubeSleepInterval.value = settings.metubeSleepInterval;
        youtubeSuffix.value = settings.youtubeSuffix;
        socket.off("settingsLoaded", handleSettingsLoaded);
    }
    socket.on("settingsLoaded", handleSettingsLoaded);
});

saveChangesButton.addEventListener("click", () => {
    socket.emit("updateSettings", {
        "lidarrMaxTags": lidarrMaxTags.value,
        "lidarrApiTimeout": lidarrApiTimeout.value,
        "metubeSleepInterval": metubeSleepInterval.value,
        "youtubeSuffix": youtubeSuffix.value
    });
    saveMessage.style.display = "block";
    setTimeout(function () {
        saveMessage.style.display = "none";
    }, 1000);
});

resetButton.addEventListener('click', function () {
    socket.emit("reset");
    metubeDataTable.innerHTML = '';
    metubeSpinner.style.display = "none";
    metubeStatus.textContent = "";
    setLedStatus(runningLed, false);
    setLedStatus(sleepingLed, false);
    setLedStatus(completeLed, false);
});

socket.on("lidarr_status", (response) => {
    if (response.Status == "Success") {
        lidarrButton.disabled = false;
        lidarrStatus.textContent = "Lidarr List Retrieved"
        lidarrSpinner.style.display = "none";
        lidarr_items = response.Data
        lidarrItemList.innerHTML = '';
        selectAllContainer.style.display = "block";
        selectAllCheckbox.checked = false;
        for (var i = 0; i < lidarr_items.length; i++) {
            var item = lidarr_items[i];

            var div = document.createElement("div");
            div.className = "form-check";

            var input = document.createElement("input");
            input.type = "checkbox";
            input.className = "form-check-input";
            input.id = "lidarr_" + i;
            input.name = "lidarr_item";
            input.value = item;

            var label = document.createElement("label");
            label.className = "form-check-label";
            label.htmlFor = "lidarr_" + i;
            label.textContent = item;

            div.appendChild(input);
            div.appendChild(label);

            lidarrItemList.appendChild(div);
        }
    }
    else {
        lidarrStatus.textContent = response.Code + " : " + response.Data;
    }
    lidarrSpinner.style.display = "none";
    lidarrButton.disabled = false;
});

socket.on("metube_status", (response) => {
    if (response.Status == "Success") {
        metubeSpinner.style.display = "none";
        metubeStatus.textContent = "";
    } else {
        metubeStatus.textContent = response.Data;
    }
    metubeButton.disabled = false;
});

socket.on("progress_status", (response) => {
    metubeDataTable.innerHTML = '';
    response.Data.forEach(function (item) {
        var row = metubeDataTable.insertRow();
        var cellItem = row.insertCell(0);
        var cellLinkFound = row.insertCell(1);
        var cellAddedToMetube = row.insertCell(2);

        cellItem.innerHTML = item.Item;
        cellLinkFound.innerHTML = item['Link Found'];
        cellAddedToMetube.innerHTML = item['Added to Metube'];

        setLedStatus(runningLed, response.Running);
        setLedStatus(sleepingLed, response.Sleeping);
        setLedStatus(completeLed, response.Complete);
    });
})