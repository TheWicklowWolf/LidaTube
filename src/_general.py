import re
import unidecode
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TPE2, TYER, TRCK, TCON
from mutagen.flac import FLAC
from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis
from mutagen.mp4 import MP4


def convert_to_lidarr_format(input_string):
    bad_characters = r'\/<>?*:|"'
    good_characters = "++  !--  "
    translation_table = str.maketrans(bad_characters, good_characters)
    result = input_string.translate(translation_table)
    return result.strip()


def string_cleaner(input_string):
    if isinstance(input_string, str):
        raw_string = re.sub(r'[\/:*?"<>|]', " ", input_string)
        temp_string = re.sub(r"\s+", " ", raw_string)
        stripped_string = temp_string.strip()
        normalised_string = unidecode.unidecode(stripped_string)
        return normalised_string

    elif isinstance(input_string, list):
        cleaned_strings = []
        for string in input_string:
            raw_string = re.sub(r'[\/:*?"<>|]', " ", string)
            temp_string = re.sub(r"\s+", " ", raw_string)
            stripped_string = temp_string.strip()
            normalised_string = unidecode.unidecode(stripped_string)
            cleaned_strings.append(normalised_string)
        return cleaned_strings


def add_metadata(logger, song, req_album, full_file_path):
    try:
        file_extension = re.search(r"\.[^.]*$", full_file_path).group().lower()

        if file_extension == ".flac":
            audio = FLAC(full_file_path)
            audio["title"] = song["track_title"]
            audio["tracknumber"] = str(song["track_number"])
            audio["artist"] = song["artist"]
            audio["albumartist"] = req_album["artist"]
            audio["album"] = req_album["album_name"]
            audio["date"] = str(req_album["album_year"])
            audio["genre"] = req_album["album_genres"]
            audio.save()

        elif file_extension in [".opus", ".webm"]:
            # Handle both .opus and .webm (opus in webm container)
            try:
                audio = OggOpus(full_file_path)
                audio["title"] = song["track_title"]
                audio["tracknumber"] = str(song["track_number"])
                audio["artist"] = song["artist"]
                audio["albumartist"] = req_album["artist"]
                audio["album"] = req_album["album_name"]
                audio["date"] = str(req_album["album_year"])
                audio["genre"] = req_album["album_genres"]
                audio.save()
            except Exception as e:
                logger.warning(f"Could not add metadata to {file_extension} file: {e}")

        elif file_extension in [".m4a", ".aac", ".mp4"]:
            # Handle AAC/M4A files
            try:
                audio = MP4(full_file_path)
                audio["\xa9nam"] = song["track_title"]
                audio["trkn"] = [(int(song["track_number"]), 0)]
                audio["\xa9ART"] = song["artist"]
                audio["aART"] = req_album["artist"]
                audio["\xa9alb"] = req_album["album_name"]
                audio["\xa9day"] = str(req_album["album_year"])
                audio["\xa9gen"] = req_album["album_genres"]
                audio.save()
            except Exception as e:
                logger.warning(f"Could not add metadata to {file_extension} file: {e}")

        elif file_extension == ".ogg":
            # Handle Vorbis files
            try:
                audio = OggVorbis(full_file_path)
                audio["title"] = song["track_title"]
                audio["tracknumber"] = str(song["track_number"])
                audio["artist"] = song["artist"]
                audio["albumartist"] = req_album["artist"]
                audio["album"] = req_album["album_name"]
                audio["date"] = str(req_album["album_year"])
                audio["genre"] = req_album["album_genres"]
                audio.save()
            except Exception as e:
                logger.warning(f"Could not add metadata to {file_extension} file: {e}")

        elif file_extension == ".mp3":
            metadata = ID3(full_file_path)
            metadata.add(TIT2(encoding=3, text=song["track_title"]))
            metadata.add(TRCK(encoding=3, text=str(song["track_number"])))
            metadata.add(TPE1(encoding=3, text=song["artist"]))
            metadata.add(TPE2(encoding=3, text=req_album["artist"]))
            metadata.add(TALB(encoding=3, text=req_album["album_name"]))
            metadata.add(TYER(encoding=3, text=str(req_album["album_year"])))
            metadata.add(TCON(encoding=3, text=str(req_album["album_genres"])))
            metadata.save()

        logger.warning(f"Metadata added for {full_file_path}")

    except Exception as e:
        logger.error(f"Error adding metadata for {full_file_path}: {e}")
