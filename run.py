import os
import sys
import time
import fcntl
import logging
import argparse
from mutagen.id3 import ID3, USLT
from mutagen import File
from lrclib import LrcLibAPI
from concurrent.futures import ThreadPoolExecutor

# Constants
LOCK_FILE = "/tmp/run_py.lock"

# Logging setup
def setup_logging():
    log_level_env = os.getenv("LOG_LEVEL", "INFO").upper()
    numeric_level = getattr(logging, log_level_env, logging.INFO)

    # Reset all handlers to ensure proper configuration
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
        audio = File(file_path)
        if isinstance(audio, ID3):
            for tag in audio.values():
                if isinstance(tag, USLT):
                    return tag.text.strip()
        return None
    except Exception as e:
        logging.error(f"Error while checking lyrics for {file_path}: {e}")
        return None

# Function to add or replace lyrics in the tags
def add_or_replace_lyrics(file_path, lyrics):
    try:
        # Process synchronized lyrics
        lyrics_with_timestamp = process_synced_lyrics(lyrics)

        # Open the audio file
        if file_path.lower().endswith(".mp3"):
            try:
                # Load the MP3 file with ID3 tags
                audio = ID3(file_path)
            except Exception as e:
                logging.error(f"Error loading ID3 tags for {file_path}: {e}")
                return
        elif file_path.lower().endswith(".ogg"):
            try:
                # Load the OGG file
                audio = File(file_path, easy=False)
                if not audio:
                    logging.warning(f"Unsupported file format for {file_path}")
                    return
            except Exception as e:
                logging.error(f"Error loading OGG file for {file_path}: {e}")
                return
        else:
            logging.warning(f"Unsupported file format for lyrics: {file_path}")
            return

        # Add or replace lyrics
        if file_path.lower().endswith(".mp3"):
            try:
                existing_lyrics = has_lyrics(file_path)
                if existing_lyrics:
                    logging.info(f"Replacing existing lyrics in {file_path}.")
                    audio.delall("USLT")

                audio.add(USLT(
                    encoding=3,  # UTF-8
                    lang="eng",
                    desc="Lyrics",
                    text=lyrics_with_timestamp
                ))
                audio.save()
                logging.info(f"Lyrics successfully added to ID3 tags for {file_path}!")
            except Exception as e:
                logging.error(f"Error saving ID3 tags for {file_path}: {e}")

        elif file_path.lower().endswith(".ogg"):
            try:
                if "lyrics" in audio:
                    logging.info(f"Replacing existing lyrics in {file_path}.")
                audio["lyrics"] = lyrics_with_timestamp
                audio.save()
                logging.info(f"Lyrics successfully added to Vorbis tags for {file_path}!")
            except Exception as e:
                logging.error(f"Error saving Vorbis tags for {file_path}: {e}")

    except Exception as e:
        logging.error(f"Error adding lyrics to tags for {file_path}: {e}")

# Function to process synced lyrics
def process_synced_lyrics(lyrics):
    lines = lyrics.split("\n")
    synced_lyrics = ["[00:00.00] ..."]
    for line in lines:
        if line.strip():
            synced_lyrics.append(line)
    return "\n".join(synced_lyrics)

# Function to process a specific music file
def process_file(file_path):
    if not check_file_exists(file_path):
        return

    api = LrcLibAPI(user_agent=os.getenv("USER_AGENT", "lrclib-docker v0.0.2 (https://github.com/2t0m/lrclib-docker)"))

    try:
        logging.info(f"Processing file: {file_path}")

        existing_lyrics = has_lyrics(file_path)
        if existing_lyrics:
            logging.info(f"Lyrics already present in the file: {file_path}. Skipping.")
            return

        audio = File(file_path, easy=True)
        if not audio:
            logging.warning(f"Unsupported file format: {file_path}")
            return

        track_name = audio.get("title", [""])[0]
        artist_name = audio.get("artist", [""])[0]
        album_name = audio.get("album", [""])[0]
        duration = int(audio.info.length) if hasattr(audio, "info") else None

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

# Function to process all music files in a directory recursively
def process_directory(directory_path, file_limit):
    if not os.path.isdir(directory_path):
        logging.error(f"The specified path is not a valid directory: {directory_path}")
        return []

    # Supported extensions
    supported_extensions = [".mp3", ".ogg"]

    file_count = 0
    files_to_process = []

    for root, _, files in os.walk(directory_path):  # Recursively walk through directories
        for file_name in files:
            file_path = os.path.join(root, file_name)
            if any(file_path.lower().endswith(ext) for ext in supported_extensions):
                if file_limit > 0 and file_count >= file_limit:
                    logging.info(f"Reached the file limit of {file_limit}. Stopping.")
                    return files_to_process
                files_to_process.append(file_path)
                file_count += 1

    return files_to_process

# Main function
def main():
    parser = argparse.ArgumentParser(description="Add synchronized lyrics to music files.")
    parser.add_argument("--folder", type=str, required=True, help="Path to the folder containing music files.")
    parser.add_argument("--file-limit", type=int, default=int(os.getenv("FILE_LIMIT", 100)), help="Limit the number of music files processed. Set 0 for unlimited.")
    args = parser.parse_args()

    file_limit = args.file_limit if args.file_limit > 0 else float("inf")
    files_to_process = process_directory(args.folder, file_limit)

    # Get max parallel processes from environment variable
    max_parallel = int(os.getenv("MAX_PARALLEL", 1))

    # Process files in parallel
    with ThreadPoolExecutor(max_workers=max_parallel) as executor:
        executor.map(process_file, files_to_process)

# Run the script with lock management
if __name__ == "__main__":
    try:
        acquire_lock()
        main()
    finally:
        release_lock()