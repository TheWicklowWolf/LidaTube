var lidarrButton = document.getElementById('lidarr_button');
var lidarrSpinner = document.getElementById('lidarr_spinner');
var lidarrStatus = document.getElementById('lidarr_status');
var yt_dlpSpinner = document.getElementById('yt_dlp_spinner');
var yt_dlpStatus = document.getElementById('yt_dlp_status');
var addButton = document.getElementById('yt_dlp_button_add');
var stopButton = document.getElementById('yt_dlp_button_stop');
var resetButton = document.getElementById('yt_dlp_button_reset');
var lidarrItemList = document.getElementById("lidarrItemList");
var selectAllCheckbox = document.getElementById("select-all");
var selectAllContainer = document.getElementById("select-all-container");
var progress_bar = document.getElementById('progress-status-bar');
var yt_dlpDataTable = document.getElementById('yt_dlp-data-table').getElementsByTagName('tbody')[0];
var configModal = document.getElementById('configModal');
var saveMessage = document.getElementById("saveMessage");
var saveChangesButton = document.getElementById("saveChangesBtn");
const lidarrMaxTags = document.getElementById("lidarrMaxTags");
const lidarrApiTimeout = document.getElementById("lidarrApiTimeout");
const youtubeSuffix = document.getElementById("youtubeSuffix");
const sleepInterval = document.getElementById("sleepInterval");
var lidarr_items = []
var socket = io();

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
    lidarrStatus.textContent = "Accessing Lidarr API"
    lidarrItemList.innerHTML = '';
    socket.emit("lidarr");
});

addButton.addEventListener('click', function () {
    addButton.disabled = true;
    yt_dlpSpinner.style.display = "inline-flex";
    var checkedItems = [];
    for (var i = 0; i < lidarr_items.length; i++) {
        var checkbox = document.getElementById("lidarr_" + i);
        if (checkbox.checked) {
            checkedItems.push(checkbox.value);
        }
    }
    socket.emit("add_to_download_list", { "Data": checkedItems });
});

stopButton.addEventListener('click', function () {
    socket.emit("stopper");
});

configModal.addEventListener('show.bs.modal', function (event) {
    socket.emit("loadSettings");

    function handleSettingsLoaded(settings) {
        lidarrMaxTags.value = settings.lidarrMaxTags;
        lidarrApiTimeout.value = settings.lidarrApiTimeout;
        sleepInterval.value = settings.sleepInterval;
        youtubeSuffix.value = settings.youtubeSuffix;
        socket.off("settingsLoaded", handleSettingsLoaded);
    }
    socket.on("settingsLoaded", handleSettingsLoaded);
});

saveChangesButton.addEventListener("click", () => {
    socket.emit("updateSettings", {
        "lidarrMaxTags": lidarrMaxTags.value,
        "lidarrApiTimeout": lidarrApiTimeout.value,
        "sleepInterval": sleepInterval.value,
        "youtubeSuffix": youtubeSuffix.value
    });
    saveMessage.style.display = "block";
    setTimeout(function () {
        saveMessage.style.display = "none";
    }, 1000);
});

resetButton.addEventListener('click', function () {
    socket.emit("reset");
    yt_dlpDataTable.innerHTML = '';
    yt_dlpSpinner.style.display = "none";
    yt_dlpStatus.textContent = "";
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

            input.addEventListener("change", function () {
                selectAllCheckbox.checked = false;
            });

            div.appendChild(input);
            div.appendChild(label);

            lidarrItemList.appendChild(div);
        }
    }
    else {
        lidarrItemList.innerHTML = '';
        var errorDiv = document.createElement("div");
        errorDiv.textContent = response.Code + " : " + response.Data;
        errorDiv.style.wordBreak = "break-all";
        lidarrItemList.appendChild(errorDiv);
        lidarrStatus.textContent = "Error Accessing Lidarr"
    }
    lidarrSpinner.style.display = "none";
    lidarrButton.disabled = false;
});

socket.on("yt_dlp_status", (response) => {
    if (response.Status == "Success") {
        yt_dlpSpinner.style.display = "none";
        yt_dlpStatus.textContent = "";
    } else {
        yt_dlpStatus.textContent = response.Data;
    }
    addButton.disabled = false;
});

function updateProgressBar(percentage, status) {
    progress_bar.style.width = percentage + "%";
    progress_bar.ariaValueNow = percentage + "%";
    progress_bar.classList.remove("progress-bar-striped");
    progress_bar.classList.remove("progress-bar-animated");

    if (status === "Running") {
        progress_bar.classList.remove("bg-primary", "bg-danger", "bg-dark");
        progress_bar.classList.add("bg-success");
        progress_bar.classList.add("progress-bar-animated");

    } else if (status === "Stopped") {
        progress_bar.classList.remove("bg-primary", "bg-success", "bg-dark");
        progress_bar.classList.add("bg-danger");

    } else if (status === "Idle") {
        progress_bar.classList.remove("bg-success", "bg-danger", "bg-dark");
        progress_bar.classList.add("bg-primary");

    } else if (status === "Complete") {
        progress_bar.classList.remove("bg-primary", "bg-success", "bg-danger");
        progress_bar.classList.add("bg-dark");
    }
    progress_bar.classList.add("progress-bar-striped");
}

socket.on("progress_status", (response) => {
    yt_dlpDataTable.innerHTML = '';
    response.Data.forEach(function (item) {
        var row = yt_dlpDataTable.insertRow();
        var cellItem = row.insertCell(0);
        var cellLinkFound = row.insertCell(1);

        cellItem.innerHTML = item.Item;
        cellLinkFound.innerHTML = item['Status'];
    });
    var percent_completion = response.Percent_Completion;
    var actual_status = response.Status;
    updateProgressBar(percent_completion, actual_status);
})

const themeSwitch = document.getElementById('themeSwitch');
const savedTheme = localStorage.getItem('theme');
const savedSwitchPosition = localStorage.getItem('switchPosition');

if (savedSwitchPosition) {
    themeSwitch.checked = savedSwitchPosition === 'true';
}

if (savedTheme) {
    document.documentElement.setAttribute('data-bs-theme', savedTheme);
}

themeSwitch.addEventListener('click', () => {
    if (document.documentElement.getAttribute('data-bs-theme') === 'dark') {
        document.documentElement.setAttribute('data-bs-theme', 'light');
    } else {
        document.documentElement.setAttribute('data-bs-theme', 'dark');
    }
    localStorage.setItem('theme', document.documentElement.getAttribute('data-bs-theme'));
    localStorage.setItem('switchPosition', themeSwitch.checked);
});
