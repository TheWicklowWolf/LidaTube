var get_wanted_lidarr = document.getElementById('get-lidarr-wanted-btn');
var stop_lidarr = document.getElementById('stop-lidarr-btn');
var reset_lidarr = document.getElementById('reset-lidarr-btn');
var lidarr_spinner = document.getElementById('lidarr-spinner');
var lidarr_progress_bar = document.getElementById('lidarr-progress-status-bar');
var lidarr_table = document.getElementById('lidarr-table').getElementsByTagName('tbody')[0];
var select_all_checkbox = document.getElementById("select-all-checkbox");

var start_ytdlp = document.getElementById('start-ytdlp-btn');
var stop_ytdlp = document.getElementById('stop-ytdlp-btn');
var reset_ytdlp = document.getElementById('reset-ytdlp-btn');
var ytdlp_progress_bar = document.getElementById('ytdlp-progress-status-bar');
var ytdlp_table = document.getElementById('ytdlp-table').getElementsByTagName('tbody')[0];

var config_modal = document.getElementById('config-modal');
var save_message = document.getElementById("save-message");
var save_changes_button = document.getElementById("save-changes-btn");
const lidarr_address = document.getElementById("lidarr-address");
const lidarr_api_key = document.getElementById("lidarr-api-key");
const sleep_interval = document.getElementById("sleep-interval");
const sync_schedule = document.getElementById("sync-schedule");
const minimum_match_ratio = document.getElementById("minimum-match-ratio");
var socket = io();

// Track which album rows are expanded
var expanded_albums = new Set();

lidarr_progress_bar.style.width = "0%";
lidarr_progress_bar.setAttribute("aria-valuenow", 0);

function check_if_all_true() {
    var all_checked = true;
    var checkboxes = document.querySelectorAll('input[name="lidarr_item"]');
    checkboxes.forEach(function (checkbox) {
        if (!checkbox.checked) {
            all_checked = false;
        }
    });
    select_all_checkbox.checked = all_checked;
}

function update_progress_bar(percentage, status) {
    ytdlp_progress_bar.style.width = percentage + "%";
    ytdlp_progress_bar.setAttribute("aria-valuenow", percentage);
    ytdlp_progress_bar.classList.remove("progress-bar-striped");
    ytdlp_progress_bar.classList.remove("progress-bar-animated");

    if (status === "running") {
        ytdlp_progress_bar.classList.remove("bg-primary", "bg-danger", "bg-dark", "bg-warning");
        ytdlp_progress_bar.classList.add("bg-success");
        ytdlp_progress_bar.classList.add("progress-bar-animated");

    } else if (status === "stopped") {
        ytdlp_progress_bar.classList.remove("bg-primary", "bg-danger", "bg-success", "bg-dark");
        ytdlp_progress_bar.classList.add("bg-warning");

    } else if (status === "idle") {
        ytdlp_progress_bar.classList.remove("bg-danger", "bg-success", "bg-primary", "bg-dark");
        ytdlp_progress_bar.classList.add("bg-primary");

    } else if (status === "complete") {
        ytdlp_progress_bar.classList.remove("bg-primary", "bg-warning", "bg-success", "bg-danger");
        ytdlp_progress_bar.classList.add("bg-dark");

    } else if (status === "failed") {
        ytdlp_progress_bar.classList.remove("bg-primary", "bg-success", "bg-warning", "bg-dark");
        ytdlp_progress_bar.classList.add("bg-danger");
    }
    ytdlp_progress_bar.classList.add("progress-bar-striped");
}

function get_track_status_html(track) {
    if (track.link) {
        var icon = "&#128279;";
        var status_class = "text-info";
        if (track.download_status === "done") {
            icon = "&#10003;";
            status_class = "text-success";
        } else if (track.download_status === "exists") {
            icon = "&#10003;";
            status_class = "text-success";
        } else if (track.download_status === "error") {
            icon = "&#10007;";
            status_class = "text-danger";
        } else if (track.download_status === "downloading") {
            icon = "&#8635;";
            status_class = "text-warning";
        }
        var safe_title = track.title_of_link.replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
        var safe_link = track.link.replace(/"/g, '&quot;');
        return `<small class="${status_class}">${icon}</small> <small><a href="${safe_link}" target="_blank" rel="noopener" title="${safe_link}">${safe_title}</a></small>`;
    } else {
        if (track.download_status === "not_found") {
            return `<small class="text-muted">&#10007; No match found</small>`;
        }
        return `<small class="text-muted">Pending</small>`;
    }
}

function toggle_album_expand(album_key, idx) {
    if (expanded_albums.has(album_key)) {
        expanded_albums.delete(album_key);
    } else {
        expanded_albums.add(album_key);
    }
    var detail_rows = document.querySelectorAll('.detail-' + idx);
    detail_rows.forEach(function (dr) {
        dr.classList.toggle("d-none");
    });
    var arrow_span = document.querySelector('.arrow-' + idx);
    if (arrow_span) {
        arrow_span.textContent = expanded_albums.has(album_key) ? "\u25BC " : "\u25B6 ";
    }
}

select_all_checkbox.addEventListener("change", function () {
    var is_checked = this.checked;
    var checkboxes = document.querySelectorAll('input[name="lidarr_item"]');
    checkboxes.forEach(function (checkbox) {
        checkbox.checked = is_checked;
    });
});

get_wanted_lidarr.addEventListener('click', function () {
    get_wanted_lidarr.disabled = true;
    lidarr_spinner.classList.remove('d-none');
    lidarr_table.innerHTML = '';
    socket.emit("lidarr_get_wanted");
});

stop_lidarr.addEventListener('click', function () {
    socket.emit("stop_lidarr");
    lidarr_spinner.classList.add('d-none');
    get_wanted_lidarr.disabled = false;
});

reset_lidarr.addEventListener('click', function () {
    socket.emit("reset_lidarr");
    lidarr_table.innerHTML = '';
    lidarr_spinner.classList.add('d-none');
    get_wanted_lidarr.disabled = false;
});

config_modal.addEventListener('show.bs.modal', function (event) {
    socket.emit("load_settings");
    function handle_settings_loaded(settings) {
        lidarr_address.value = settings.lidarr_address;
        lidarr_api_key.value = settings.lidarr_api_key;
        sleep_interval.value = settings.sleep_interval;
        sync_schedule.value = settings.sync_schedule.join(', ');
        minimum_match_ratio.value = settings.minimum_match_ratio;
        socket.off("settings_loaded", handle_settings_loaded);
    }
    socket.on("settings_loaded", handle_settings_loaded);
});

save_changes_button.addEventListener("click", () => {
    socket.emit("update_settings", {
        "lidarr_address": lidarr_address.value,
        "lidarr_api_key": lidarr_api_key.value,
        "sleep_interval": sleep_interval.value,
        "sync_schedule": sync_schedule.value,
        "minimum_match_ratio": minimum_match_ratio.value
    });
    save_message.style.display = "block";
    setTimeout(function () {
        save_message.style.display = "none";
    }, 1000);
});

start_ytdlp.addEventListener('click', function () {
    start_ytdlp.disabled = true;
    var checked_indices = [];
    var checkboxes = document.getElementsByName("lidarr_item");

    checkboxes.forEach(function (checkbox, index) {
        if (checkbox.checked) {
            checked_indices.push(index);
        }
    });
    socket.emit("add_to_download_list", checked_indices);
    start_ytdlp.disabled = false;
});

stop_ytdlp.addEventListener('click', function () {
    socket.emit("stop_ytdlp");
});

reset_ytdlp.addEventListener('click', function () {
    socket.emit("reset_ytdlp");
    ytdlp_table.innerHTML = '';
});

// Manual download submit handler
document.getElementById("manual-download-submit-btn").addEventListener("click", function () {
    var artist = document.getElementById("manual-artist").value.trim();
    var album = document.getElementById("manual-album").value.trim();
    var year = document.getElementById("manual-year").value.trim();
    var tracks = document.getElementById("manual-tracks").value.trim();
    var url = document.getElementById("manual-url").value.trim();

    if (!artist) {
        show_toast("Error", "Artist name is required");
        return;
    }
    if (!tracks && !url) {
        show_toast("Error", "Please provide track names or a YouTube URL");
        return;
    }

    socket.emit("manual_download", {
        artist: artist,
        album_name: album,
        year: year || new Date().getFullYear(),
        tracks: tracks,
        youtube_url: url
    });

    // Close modal and clear fields
    var modal = bootstrap.Modal.getInstance(document.getElementById("manual-download-modal"));
    modal.hide();
    document.getElementById("manual-artist").value = "";
    document.getElementById("manual-album").value = "";
    document.getElementById("manual-year").value = "";
    document.getElementById("manual-tracks").value = "";
    document.getElementById("manual-url").value = "";
});

socket.on("lidarr_update", (response) => {
    lidarr_table.innerHTML = '';
    var all_checked = true;
    if (response.status == "busy") {
        get_wanted_lidarr.disabled = true;
        lidarr_spinner.classList.remove('d-none');
    }
    else {
        get_wanted_lidarr.disabled = false;
        lidarr_spinner.classList.add('d-none');
    }

    select_all_checkbox.style.display = "block";
    select_all_checkbox.checked = false;

    response.data.forEach((item, i) => {
        if (!item.checked) {
            all_checked = false;
        }
        var row = lidarr_table.insertRow();

        var cell1 = row.insertCell(0);
        var cell2 = row.insertCell(1);
        var cell3 = row.insertCell(2);

        var checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.className = "form-check-input";
        checkbox.id = "lidarr_" + i;
        checkbox.name = "lidarr_item";
        checkbox.checked = item.checked;
        checkbox.addEventListener("change", function () {
            check_if_all_true();
        });

        var label = document.createElement("label");
        label.className = "form-check-label";
        label.htmlFor = "lidarr_" + i;

        label.textContent = item.artist + " - " + item.album_name;

        cell1.appendChild(checkbox);
        cell2.appendChild(label);
        cell3.textContent = `${item.missing_count}/${item.track_count}`;
        cell3.classList.add("text-center");
    });
    select_all_checkbox.checked = all_checked;
});

socket.on("ytdlp_update", (response) => {
    ytdlp_table.innerHTML = '';
    response.data.forEach(function (entry, idx) {
        var album_key = entry.artist + "|" + entry.album_name;
        var is_expanded = expanded_albums.has(album_key);

        // Main album row
        var row = ytdlp_table.insertRow();
        row.className = "album-row";
        row.style.cursor = "pointer";
        row.dataset.artist = entry.artist;
        row.dataset.album = entry.album_name;

        var cell_item = row.insertCell(0);
        var cell_item_status = row.insertCell(1);

        var arrow = is_expanded ? "\u25BC " : "\u25B6 ";
        var manual_badge = entry.is_manual ? ' <span class="badge bg-info">Manual</span>' : '';
        cell_item.innerHTML = `<span class="expand-arrow arrow-${idx}">${arrow}</span>${entry.artist} - ${entry.album_name}${manual_badge}`;
        cell_item_status.innerHTML = entry.status;
        cell_item_status.classList.add("text-center");

        (function (ak, i) {
            row.addEventListener("click", function () {
                toggle_album_expand(ak, i);
            });
        })(album_key, idx);

        // Track detail rows
        if (entry.missing_tracks) {
            entry.missing_tracks.forEach(function (track) {
                var detail_row = ytdlp_table.insertRow();
                detail_row.className = "detail-" + idx + " track-detail-row";
                if (!is_expanded) {
                    detail_row.classList.add("d-none");
                }

                var cell_track = detail_row.insertCell(0);
                var cell_source = detail_row.insertCell(1);

                var track_num = String(track.absolute_track_number).padStart(2, '0');
                cell_track.innerHTML = `<small class="text-muted ms-3">${track_num}. ${track.track_title}</small>`;
                cell_source.innerHTML = get_track_status_html(track);
                cell_source.classList.add("text-center");
            });
        }
    });
    var percent_completion = response.percent_completion;
    var actual_status = response.status;
    update_progress_bar(percent_completion, actual_status);
});

// Lightweight per-track download progress updates
socket.on("download_progress", function (data) {
    var rows = ytdlp_table.querySelectorAll(".album-row");
    rows.forEach(function (row) {
        if (row.dataset.artist === data.artist && row.dataset.album === data.album_name) {
            row.cells[1].innerHTML = data.status;
        }
    });
});

socket.on("new_toast_msg", function (data) {
    show_toast(data.title, data.message);
});

function show_toast(header, message) {
    var toast_container = document.querySelector('.toast-container');
    var toast_template = document.getElementById('toast-template').cloneNode(true);
    toast_template.classList.remove('d-none');

    toast_template.querySelector('.toast-header strong').textContent = header;
    toast_template.querySelector('.toast-body').textContent = message;
    toast_template.querySelector('.text-muted').textContent = new Date().toLocaleString();

    toast_container.appendChild(toast_template);

    var toast = new bootstrap.Toast(toast_template);
    toast.show();

    toast_template.addEventListener('hidden.bs.toast', function () {
        toast_template.remove();
    });
}

const theme_switch = document.getElementById('theme-switch');
const saved_theme = localStorage.getItem('theme');
const saved_switch_position = localStorage.getItem('switchPosition');

if (saved_switch_position) {
    theme_switch.checked = saved_switch_position === 'true';
}

if (saved_theme) {
    document.documentElement.setAttribute('data-bs-theme', saved_theme);
}

theme_switch.addEventListener('click', () => {
    if (document.documentElement.getAttribute('data-bs-theme') === 'dark') {
        document.documentElement.setAttribute('data-bs-theme', 'light');
    } else {
        document.documentElement.setAttribute('data-bs-theme', 'dark');
    }
    localStorage.setItem('theme', document.documentElement.getAttribute('data-bs-theme'));
    localStorage.setItem('switchPosition', theme_switch.checked);
});
