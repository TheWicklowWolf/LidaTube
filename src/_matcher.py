from thefuzz import fuzz
import _general
import re

ALBUM_KEYWORDS_TO_REMOVE = [
    "extended",
    "limited",
    "deluxe",
    "special",
    "remastered",
    "anniversary",
    "collector's",
    "ultimate",
    "bonus",
]
SONG_KEYWORDS_TO_REMOVE = [
    "radio",
    "limited",
    "remastered",
    "bonus",
    "feat",
    "featuring",
    "live",
    "edit",
    "version",
    "acoustic",
    "studio",
    "cover",
    "instrumental",
    "extended",
    "mix",
    "demo",
    "original",
    "reissue",
    "track",
    "official",
    "lyric",
]


def remove_album_keywords(text):
    ret = text
    for keyword in ALBUM_KEYWORDS_TO_REMOVE:
        if keyword in ret:
            ret = re.sub(r"(\s*\(\s*)?(" + re.escape(keyword) + r")(?:\s*\))?", "", ret)
    return ret


def remove_song_keywords(text):
    ret = text
    for keyword in SONG_KEYWORDS_TO_REMOVE:
        if keyword in ret:
            ret = re.sub(r"(\s*\(\s*)?(" + re.escape(keyword) + r")(?:\s*\))?", "", ret)
    return ret


def album_matcher(minimum_match_ratio, artist, album_name, cleaned_artist, cleaned_album, search_results, item_wanted_type="Album"):
    if not search_results:
        return None
    best_match_rating = 0
    best_match_item = None
    for item in search_results:
        if item["type"] != item_wanted_type:
            continue
        raw_album_match_ratio = fuzz.ratio(album_name, item["title"])
        artists_string = "".join([item["artists"][x]["name"] for x in range(1, len(item["artists"]))])
        raw_artist_match_ratio = fuzz.ratio(artist, artists_string)

        cleaned_yt_album_name = _general.string_cleaner(item["title"]).lower()
        cleaned_album_match_ratio = fuzz.ratio(cleaned_album, cleaned_yt_album_name)
        cleaned_artists_string = _general.string_cleaner(artists_string).lower()
        cleaned_artist_match_ratio = fuzz.ratio(cleaned_artist, cleaned_artists_string)

        cleaned_yt_album_title_minus_keywords = remove_album_keywords(cleaned_yt_album_name)
        album_ratio_minus_keywords = fuzz.ratio(cleaned_album, cleaned_yt_album_title_minus_keywords)

        cleaned_yt_artist_minus_keywords = remove_album_keywords(cleaned_artists_string)
        artist_ratio_minus_keywords = fuzz.ratio(cleaned_artist, cleaned_yt_artist_minus_keywords)

        combined_rating = (raw_album_match_ratio + raw_artist_match_ratio + cleaned_album_match_ratio + cleaned_artist_match_ratio + album_ratio_minus_keywords + artist_ratio_minus_keywords) / 6

        if combined_rating > best_match_rating:
            best_match_rating = combined_rating
            best_match_item = item
            if combined_rating == 100:
                break

    if best_match_rating > minimum_match_ratio:
        return best_match_item
    else:
        return None


def song_matcher(minimum_match_ratio, artist, cleaned_artist, song_title, cleaned_song_title, search_results, item_wanted_type="song"):
    if not search_results:
        return None
    best_match_rating = 0
    best_match_item = None
    for item in search_results:
        if item["resultType"] != item_wanted_type:
            continue

        artists_string = "".join([x["name"] for x in item["artists"]])
        raw_artist_match_ratio = fuzz.ratio(artist, artists_string)
        if artist.lower() in artists_string.lower():
            raw_artist_match_ratio = 100

        cleaned_artists_string = _general.string_cleaner(artists_string).lower()
        cleaned_artist_match_ratio = fuzz.ratio(cleaned_artist, cleaned_artists_string)

        cleaned_yt_song_title = _general.string_cleaner(item["title"]).lower()
        cleaned_song_title_ratio = fuzz.ratio(cleaned_song_title, cleaned_yt_song_title)
        if song_title.lower() in item["title"].lower():
            cleaned_song_title_ratio = 100

        cleaned_song_title_minus_keywords = remove_song_keywords(cleaned_song_title)
        cleaned_yt_title_minus_keywords = remove_song_keywords(cleaned_yt_song_title)
        cleaned_song_title_minus_keywords_ratio = fuzz.ratio(cleaned_song_title_minus_keywords, cleaned_yt_title_minus_keywords)

        combined_rating = (raw_artist_match_ratio + cleaned_artist_match_ratio + cleaned_song_title_ratio + cleaned_song_title_minus_keywords_ratio) / 4

        if combined_rating > best_match_rating:
            best_match_rating = combined_rating
            best_match_item = item
            if combined_rating == 100:
                break

    if best_match_rating > minimum_match_ratio:
        return best_match_item
    else:
        return None


def song_matcher_yt(minimum_match_ratio, query_text, search_results):
    if not search_results:
        return None
    best_match_rating = 0
    best_match_item = None

    for item in search_results:
        title = item.get("title", "")
        title_similarity = fuzz.ratio(query_text, title)
        if query_text in title:
            title_similarity = 100

        cleaned_title = _general.string_cleaner(title)
        cleaned_query_text = _general.string_cleaner(query_text)
        cleaned_title_similarity = fuzz.ratio(cleaned_query_text, cleaned_title)
        if cleaned_query_text in cleaned_title:
            cleaned_title_similarity = 100

        cleaned_title_minus_keywords = remove_song_keywords(cleaned_title)
        cleaned_query_text_minus_keywords = remove_song_keywords(cleaned_query_text)
        cleaned_title_minus_keywords_similarity = fuzz.ratio(cleaned_query_text_minus_keywords, cleaned_title_minus_keywords)
        if cleaned_query_text_minus_keywords in cleaned_title_minus_keywords:
            cleaned_title_minus_keywords_similarity = 100

        combined_match_ratio = (title_similarity + cleaned_title_similarity + cleaned_title_minus_keywords_similarity) / 3

        if combined_match_ratio > best_match_rating:
            best_match_rating = title_similarity
            best_match_item = item

            if combined_match_ratio == 100:
                break

    if best_match_rating > minimum_match_ratio:
        return best_match_item
    else:
        return None
