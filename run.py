import os
import sys
import time
import fcntl
import logging
import argparse
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, USLT
from lrclib import LrcLibAPI

# Constants
LOCK_FILE = "/tmp/run_py.lock"

# Logging setup
def setup_logging():
    log_level_env = os.getenv("LOG_LEVEL", "INFO").upper()
    numeric_level = getattr(logging, log_level_env, logging.INFO)

    # Réinitialiser tous les handlers pour s'assurer qu'on applique bien la config
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logging.debug(f"Log level set to: {log_level_env}")

# Function to acquire a lock
def acquire_lock():
    """Acquire a lock to ensure only one instance is running."""
    global lock_file
    try:
        lock_file = open(LOCK_FILE, "w")
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)  # Non-blocking exclusive lock
        logging.info("Lock acquired. Running the script.")
    except BlockingIOError:
        logging.error("Another instance of the script is already running. Exiting.")
        sys.exit(1)  # Exit if unable to acquire the lock

# Function to release the lock
def release_lock():
    """Release the lock when the script finishes."""
    global lock_file
    if lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_UN)
        lock_file.close()
        os.remove(LOCK_FILE)
        logging.info("Lock released. Script finished.")

# Function to check if the file exists
def check_file_exists(file_path):
    if os.path.isfile(file_path):
        logging.debug(f"File found: {file_path}")
        return True
    else:
        logging.error(f"File not found: {file_path}. Please check the path.")
        return False

# Function to check if lyrics already exist in ID3 tags
def has_lyrics(file_path):
    try:
        audio = ID3(file_path)
        for tag in audio.values():
            if isinstance(tag, USLT):
                return tag.text.strip()
        return None
    except Exception as e:
        logging.error(f"Error while checking lyrics for {file_path}: {e}")
        return None

# Function to add or replace lyrics in the ID3 tags
def add_or_replace_lyrics(file_path, lyrics):
    try:
        lyrics_with_timestamp = process_synced_lyrics(lyrics)

        audio = ID3(file_path)
        existing_lyrics = has_lyrics(file_path)

        if existing_lyrics:
            logging.info(f"Replacing existing lyrics in {file_path}.")
            audio.delall("USLT")

        audio.add(USLT(
            encoding=3,
            lang="eng",
            desc="Lyrics",
            text=lyrics_with_timestamp
        ))
        audio.save()
        logging.info(f"Lyrics successfully saved in ID3 tags for {file_path}!")
    except Exception as e:
        logging.error(f"Error while adding lyrics to ID3 tags for {file_path}: {e}")

# Function to process synced lyrics
def process_synced_lyrics(lyrics):
    lines = lyrics.split("\n")
    synced_lyrics = ["[00:00.00] ..."]
    for line in lines:
        if line.strip():
            synced_lyrics.append(line)
    return "\n".join(synced_lyrics)

# Function to process a specific MP3 file
def process_file(file_path):
    if not check_file_exists(file_path):
        return

    api = LrcLibAPI(user_agent=os.getenv("USER_AGENT", "lrclib-docker v0.0.2 (https://github.com/2t0m/lrclib-docker)"))

    try:
        audio = EasyID3(file_path)
        track_name = audio.get("title", [""])[0]
        artist_name = audio.get("artist", [""])[0]
        album_name = audio.get("album", [""])[0]
        duration = int(audio.info.length) if hasattr(audio, "info") else None

        existing_lyrics = has_lyrics(file_path)
        if existing_lyrics:
            logging.info(f"Lyrics already present in the file: {file_path}. Skipping.")
            return

        lyrics_result = api.get_lyrics(
            track_name=track_name,
            artist_name=artist_name,
            album_name=album_name,
            duration=duration,
        )

        lyrics = lyrics_result.synced_lyrics or lyrics_result.plain_lyrics
        if lyrics:
            logging.info(f"Lyrics found for {track_name}.")
            add_or_replace_lyrics(file_path, lyrics)
        else:
            logging.warning(f"No lyrics found for {track_name}.")
        time.sleep(int(os.getenv("API_SLEEP_TIME", 25)))

    except Exception as e:
        logging.error(f"Error while retrieving metadata or lyrics for {file_path}: {e}")

# Function to process all MP3 files in a directory
def process_directory(directory_path, mp3_limit):
    if not os.path.isdir(directory_path):
        logging.error(f"The specified path is not a valid directory: {directory_path}")
        return

    mp3_count = 0
    for file_name in os.listdir(directory_path):
        file_path = os.path.join(directory_path, file_name)
        if file_path.lower().endswith(".mp3"):
            if mp3_limit > 0 and mp3_count >= mp3_limit:
                logging.info(f"Reached the MP3 limit of {mp3_limit}. Stopping.")
                break
            logging.info(f"Processing file: {file_path}")
            process_file(file_path)
            mp3_count += 1

# Main function
def main():
    parser = argparse.ArgumentParser(description="Add synchronized lyrics to MP3 files.")
    parser.add_argument("--folder", type=str, required=True, help="Path to the folder containing MP3 files.")
    parser.add_argument("--mp3-limit", type=int, default=int(os.getenv("MP3_LIMIT", 100)), help="Limit the number of MP3 files processed. Set 0 for unlimited.")
    args = parser.parse_args()

    mp3_limit = args.mp3_limit if args.mp3_limit > 0 else float("inf")
    process_directory(args.folder, mp3_limit)

# Run the script with lock management
if __name__ == "__main__":
    try:
        acquire_lock()
        main()
    finally:
        release_lock()
