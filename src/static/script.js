const get_wanted_lidarr = document.getElementById('get-lidarr-wanted-btn');
const stop_lidarr = document.getElementById('stop-lidarr-btn');
const reset_lidarr = document.getElementById('reset-lidarr-btn');
const lidarr_spinner = document.getElementById('lidarr-spinner');
const lidarr_progress_bar = document.getElementById('lidarr-progress-status-bar');
const lidarr_table = document.getElementById('lidarr-table').getElementsByTagName('tbody')[0];
const select_all_checkbox = document.getElementById("select-all-checkbox");

const start_ytdlp = document.getElementById('start-ytdlp-btn');
const stop_ytdlp = document.getElementById('stop-ytdlp-btn');
const reset_ytdlp = document.getElementById('reset-ytdlp-btn');
const ytdlp_progress_bar = document.getElementById('ytdlp-progress-status-bar');
const ytdlp_table = document.getElementById('ytdlp-table').getElementsByTagName('tbody')[0];

const config_modal = document.getElementById('config-modal');
const save_message = document.getElementById("save-message");
const save_changes_button = document.getElementById("save-changes-btn");
const lidarr_address = document.getElementById("lidarr-address");
const lidarr_api_key = document.getElementById("lidarr-api-key");
const sleep_interval = document.getElementById("sleep-interval");
const sync_schedule = document.getElementById("sync-schedule");
const minimum_match_ratio = document.getElementById("minimum-match-ratio");
const socket = io();

// Track which album rows are expanded
const expanded_albums = new Set();

// Cache previous ytdlp data for differential updates
let prev_ytdlp_data = [];
let prev_ytdlp_status = "";

// Map of album_key -> album row element for O(1) progress lookups
const album_row_map = new Map();

lidarr_progress_bar.style.width = "0%";
lidarr_progress_bar.setAttribute("aria-valuenow", 0);

function check_if_all_true() {
    const checkboxes = document.querySelectorAll('input[name="lidarr_item"]');
    let all_checked = true;
    checkboxes.forEach(function (checkbox) {
        if (!checkbox.checked) {
            all_checked = false;
        }
    });
    select_all_checkbox.checked = all_checked;
}

const PROGRESS_BAR_COLORS = ["bg-primary", "bg-danger", "bg-dark", "bg-warning", "bg-success"];
const STATUS_COLOR_MAP = {
    "running": "bg-success",
    "stopped": "bg-warning",
    "idle": "bg-primary",
    "complete": "bg-dark",
    "failed": "bg-danger"
};

function update_progress_bar(percentage, status) {
    ytdlp_progress_bar.style.width = percentage + "%";
    ytdlp_progress_bar.setAttribute("aria-valuenow", percentage);
    ytdlp_progress_bar.classList.remove("progress-bar-animated");
    ytdlp_progress_bar.classList.remove(...PROGRESS_BAR_COLORS);

    const color = STATUS_COLOR_MAP[status];
    if (color) {
        ytdlp_progress_bar.classList.add(color);
    }
    if (status === "running") {
        ytdlp_progress_bar.classList.add("progress-bar-animated");
    }
    ytdlp_progress_bar.classList.add("progress-bar-striped");
}

function escape_html(str) {
    if (!str) return "";
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function get_track_status_html(track) {
    if (track.link) {
        let icon = "&#128279;";
        let status_class = "text-info";
        if (track.download_status === "done" || track.download_status === "exists") {
            icon = "&#10003;";
            status_class = "text-success";
        } else if (track.download_status === "error") {
            icon = "&#10007;";
            status_class = "text-danger";
        } else if (track.download_status === "downloading") {
            icon = "&#8635;";
            status_class = "text-warning";
        }
        const safe_title = escape_html(track.title_of_link);
        const safe_link = escape_html(track.link);
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
    const detail_rows = document.querySelectorAll('.detail-' + idx);
    detail_rows.forEach(function (dr) {
        dr.classList.toggle("d-none");
    });
    const arrow_span = document.querySelector('.arrow-' + idx);
    if (arrow_span) {
        arrow_span.textContent = expanded_albums.has(album_key) ? "\u25BC " : "\u25B6 ";
    }
}

select_all_checkbox.addEventListener("change", function () {
    const is_checked = this.checked;
    const checkboxes = document.querySelectorAll('input[name="lidarr_item"]');
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

config_modal.addEventListener('show.bs.modal', function () {
    socket.emit("load_settings");
    function handle_settings_loaded(settings) {
        lidarr_address.value = settings.lidarr_address;
        lidarr_api_key.value = settings.lidarr_api_key;
        sleep_interval.value = settings.sleep_interval;
        sync_schedule.value = settings.sync_schedule.join(', ');
        minimum_match_ratio.value = settings.minimum_match_ratio;
        const version_el = document.getElementById("version-display");
        if (version_el && settings.version) {
            version_el.textContent = "v" + settings.version;
        }
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
    const checked_indices = [];
    const checkboxes = document.getElementsByName("lidarr_item");

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
    prev_ytdlp_data = [];
    album_row_map.clear();
});

// Manual download submit handler
document.getElementById("manual-download-submit-btn").addEventListener("click", function () {
    const artist = document.getElementById("manual-artist").value.trim();
    const album = document.getElementById("manual-album").value.trim();
    const year = document.getElementById("manual-year").value.trim();
    const tracks = document.getElementById("manual-tracks").value.trim();
    const url = document.getElementById("manual-url").value.trim();

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
    const modal = bootstrap.Modal.getInstance(document.getElementById("manual-download-modal"));
    modal.hide();
    document.getElementById("manual-artist").value = "";
    document.getElementById("manual-album").value = "";
    document.getElementById("manual-year").value = "";
    document.getElementById("manual-tracks").value = "";
    document.getElementById("manual-url").value = "";
});

socket.on("lidarr_update", (response) => {
    lidarr_table.innerHTML = '';
    let all_checked = true;
    if (response.status === "busy") {
        get_wanted_lidarr.disabled = true;
        lidarr_spinner.classList.remove('d-none');
    } else {
        get_wanted_lidarr.disabled = false;
        lidarr_spinner.classList.add('d-none');
    }

    select_all_checkbox.style.display = "block";
    select_all_checkbox.checked = false;

    response.data.forEach((item, i) => {
        if (!item.checked) {
            all_checked = false;
        }
        const row = lidarr_table.insertRow();

        const cell1 = row.insertCell(0);
        const cell2 = row.insertCell(1);
        const cell3 = row.insertCell(2);

        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.className = "form-check-input";
        checkbox.id = "lidarr_" + i;
        checkbox.name = "lidarr_item";
        checkbox.checked = item.checked;
        checkbox.addEventListener("change", function () {
            check_if_all_true();
        });

        const label = document.createElement("label");
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

// Build a single album row + its track detail rows in the ytdlp table
function build_ytdlp_album(entry, idx) {
    const album_key = entry.artist + "|" + entry.album_name;
    const is_expanded = expanded_albums.has(album_key);

    // Main album row
    const row = ytdlp_table.insertRow();
    row.className = "album-row";
    row.style.cursor = "pointer";
    row.dataset.albumKey = album_key;
    row.dataset.idx = idx;

    const cell_item = row.insertCell(0);
    const cell_item_status = row.insertCell(1);

    const arrow = is_expanded ? "\u25BC " : "\u25B6 ";
    const manual_badge = entry.is_manual ? ' <span class="badge bg-info">Manual</span>' : '';
    cell_item.innerHTML = `<span class="expand-arrow arrow-${idx}">${arrow}</span>${escape_html(entry.artist)} - ${escape_html(entry.album_name)}${manual_badge}`;
    cell_item_status.innerHTML = escape_html(entry.status);
    cell_item_status.classList.add("text-center");

    row.addEventListener("click", function () {
        toggle_album_expand(album_key, idx);
    });

    // Store in map for O(1) progress lookups
    album_row_map.set(album_key, row);

    // Track detail rows
    if (entry.missing_tracks) {
        entry.missing_tracks.forEach(function (track) {
            const detail_row = ytdlp_table.insertRow();
            detail_row.className = "detail-" + idx + " track-detail-row";
            detail_row.dataset.albumKey = album_key;
            if (!is_expanded) {
                detail_row.classList.add("d-none");
            }

            const cell_track = detail_row.insertCell(0);
            const cell_source = detail_row.insertCell(1);

            const track_num = String(track.absolute_track_number).padStart(2, '0');
            cell_track.innerHTML = `<small class="text-muted ms-3">${track_num}. ${escape_html(track.track_title)}</small>`;
            cell_source.innerHTML = get_track_status_html(track);
            cell_source.classList.add("text-center");
        });
    }
}

// Check if track data has changed between two album entries
function tracks_changed(prev_entry, new_entry) {
    if (!prev_entry.missing_tracks && !new_entry.missing_tracks) return false;
    if (!prev_entry.missing_tracks || !new_entry.missing_tracks) return true;
    if (prev_entry.missing_tracks.length !== new_entry.missing_tracks.length) return true;
    for (let i = 0; i < new_entry.missing_tracks.length; i++) {
        const pt = prev_entry.missing_tracks[i];
        const nt = new_entry.missing_tracks[i];
        if (pt.link !== nt.link || pt.download_status !== nt.download_status || pt.title_of_link !== nt.title_of_link) {
            return true;
        }
    }
    return false;
}

socket.on("ytdlp_update", (response) => {
    const new_data = response.data;
    const data_length_changed = new_data.length !== prev_ytdlp_data.length;

    // If the number of albums changed, we need a full rebuild
    if (data_length_changed) {
        ytdlp_table.innerHTML = '';
        album_row_map.clear();
        new_data.forEach(function (entry, idx) {
            build_ytdlp_album(entry, idx);
        });
    } else {
        // Differential update: only touch rows that changed
        new_data.forEach(function (entry, idx) {
            const prev_entry = prev_ytdlp_data[idx];
            const album_key = entry.artist + "|" + entry.album_name;

            // Check if this album's identity changed (different album at same index)
            const prev_key = prev_entry ? (prev_entry.artist + "|" + prev_entry.album_name) : null;
            if (prev_key !== album_key) {
                // Album identity changed at this index, need full rebuild
                ytdlp_table.innerHTML = '';
                album_row_map.clear();
                new_data.forEach(function (e, i) {
                    build_ytdlp_album(e, i);
                });
                return;
            }

            const album_row = album_row_map.get(album_key);

            // Update status cell if changed
            if (album_row && prev_entry.status !== entry.status) {
                album_row.cells[1].innerHTML = escape_html(entry.status);
            }

            // Update track detail rows if track data changed
            if (tracks_changed(prev_entry, entry)) {
                // Remove old detail rows for this album
                const old_details = ytdlp_table.querySelectorAll('.detail-' + idx);
                old_details.forEach(function (dr) { dr.remove(); });

                // Insert new detail rows after the album row
                const is_expanded = expanded_albums.has(album_key);
                if (entry.missing_tracks && album_row) {
                    let insert_after = album_row;
                    entry.missing_tracks.forEach(function (track) {
                        const detail_row = document.createElement("tr");
                        detail_row.className = "detail-" + idx + " track-detail-row";
                        detail_row.dataset.albumKey = album_key;
                        if (!is_expanded) {
                            detail_row.classList.add("d-none");
                        }

                        const cell_track = document.createElement("td");
                        const cell_source = document.createElement("td");

                        const track_num = String(track.absolute_track_number).padStart(2, '0');
                        cell_track.innerHTML = `<small class="text-muted ms-3">${track_num}. ${escape_html(track.track_title)}</small>`;
                        cell_source.innerHTML = get_track_status_html(track);
                        cell_source.classList.add("text-center");

                        detail_row.appendChild(cell_track);
                        detail_row.appendChild(cell_source);

                        insert_after.after(detail_row);
                        insert_after = detail_row;
                    });
                }
            }
        });
    }

    prev_ytdlp_data = JSON.parse(JSON.stringify(new_data));
    prev_ytdlp_status = response.status;

    update_progress_bar(response.percent_completion, response.status);
});

// Lightweight per-track download progress updates (O(1) lookup via map)
socket.on("download_progress", function (data) {
    const album_key = data.artist + "|" + data.album_name;
    const row = album_row_map.get(album_key);
    if (row) {
        row.cells[1].innerHTML = escape_html(data.status);
    }
});

socket.on("new_toast_msg", function (data) {
    show_toast(data.title, data.message);
});

function show_toast(header, message) {
    const toast_container = document.querySelector('.toast-container');
    const toast_el = document.getElementById('toast-template').cloneNode(true);
    toast_el.classList.remove('d-none');

    toast_el.querySelector('.toast-header strong').textContent = header;
    toast_el.querySelector('.toast-body').textContent = message;
    toast_el.querySelector('.text-muted').textContent = new Date().toLocaleString();

    toast_container.appendChild(toast_el);

    const toast = new bootstrap.Toast(toast_el);
    toast.show();

    toast_el.addEventListener('hidden.bs.toast', function () {
        toast_el.remove();
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
