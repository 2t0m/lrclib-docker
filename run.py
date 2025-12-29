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
from collections import Counter

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
        logging.debug(f"Checking for lyrics in file: {file_path}")
        # Force loading as ID3
        audio = ID3(file_path)
        for tag_key, tag in audio.items():
            if isinstance(tag, USLT):
                lyrics = tag.text.strip()
                logging.debug(f"Found USLT tag: {tag_key}, Lyrics: {lyrics}")
                if lyrics:
                    logging.info("Lyrics already found.")
                    return lyrics
        logging.debug(f"No lyrics found in file: {file_path}")
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
    global files_processed, files_with_lyrics, files_with_downloaded_lyrics, files_without_lyrics

    logging.debug(f"Starting processing for file: {file_path}")
    if not check_file_exists(file_path):
        logging.debug(f"Skipping file as it does not exist: {file_path}")
        return

    files_processed += 1

    # Log all tags in the MP3 file only if log level is DEBUG
    if logging.getLogger().isEnabledFor(logging.DEBUG):
        log_mp3_tags(file_path)

    api = LrcLibAPI(user_agent=os.getenv("USER_AGENT", "lrclib-docker"))

    try:
        logging.info(f"Processing file: {file_path}")

        # Check for existing lyrics
        existing_lyrics = has_lyrics(file_path)
        if existing_lyrics:
            logging.info(f"Lyrics already present in the file: {file_path}. Skipping.")
            logging.debug("Lyrics already found, skipping API call.")
            return "existing", file_path

        audio = File(file_path, easy=True)
        if not audio:
            logging.warning(f"Unsupported file format: {file_path}")
            return

        track_name = audio.get("title", [""])[0]
        artist_name = audio.get("artist", [""])[0]
        album_name = audio.get("album", [""])[0]
        duration = int(audio.info.length) if hasattr(audio, "info") else None

        # Normalize ampersands (& and ＆ fullwidth) to standard &
        if artist_name:
            artist_name = artist_name.replace("＆", "&")  # Replace fullwidth ampersand
        if track_name:
            track_name = track_name.replace("＆", "&")
        if album_name:
            album_name = album_name.replace("＆", "&")

        logging.debug(f"Metadata for {file_path}: Track='{track_name}', Artist='{artist_name}', Album='{album_name}', Duration={duration}")

        lyrics_result = None

        # First try
        try:
            logging.warning(f"First try: track='{track_name}', artist='{artist_name}', album='{album_name}', duration={duration}")
            lyrics_result = api.get_lyrics(
                track_name=track_name,
                artist_name=artist_name,
                album_name=album_name,
                duration=duration,
            )
            lyrics = lyrics_result.synced_lyrics or lyrics_result.plain_lyrics
            if not lyrics:
                logging.warning("First try failed.")
        except Exception as e:
            logging.warning(f"First try failed with exception: {e}")
            lyrics = None

        # Second try
        try:
            logging.warning(f"Second try: track='{track_name}', artist='{artist_name}', album='', duration={duration}")
            lyrics_result = api.get_lyrics(
                track_name=track_name,
                artist_name=artist_name,
                album_name="",
                duration=duration,
            )
            lyrics = lyrics_result.synced_lyrics or lyrics_result.plain_lyrics
            if not lyrics:
                logging.warning("Second try failed.")
        except Exception as e:
            logging.warning(f"Second try failed with exception: {e}")
            lyrics = None

        # Third try: all artists séparés par virgule, no album
        if not lyrics:
            try:
                import re
                artist_parts = [p.strip().replace("Jungkook", "Jung Kook") for p in re.split(r"[\/,]", artist_name)]
                alt_artist = ", ".join(artist_parts)
                logging.warning(f"Third try: track='{track_name}', artist='{alt_artist}', album='', duration={duration}")
                lyrics_result = api.get_lyrics(
                    track_name=track_name,
                    artist_name=alt_artist,
                    album_name="",
                    duration=duration,
                )
                lyrics = lyrics_result.synced_lyrics or lyrics_result.plain_lyrics
                if not lyrics:
                    logging.warning("Third try failed.")
            except Exception as e:
                logging.warning(f"Third try failed with exception: {e}")
                lyrics = None

        # Fourth try: only first artist, no album
        if not lyrics:
            try:
                import re
                first_artist = re.split(r"[\/,]", artist_name)[0].strip()
                logging.warning(f"Fourth try: track='{track_name}', artist='{first_artist}', album='', duration={duration}")
                lyrics_result = api.get_lyrics(
                    track_name=track_name,
                    artist_name=first_artist,
                    album_name="",
                    duration=duration,
                )
                lyrics = lyrics_result.synced_lyrics or lyrics_result.plain_lyrics
                if not lyrics:
                    logging.warning("Fourth try failed.")
            except Exception as e:
                logging.warning(f"Fourth try failed with exception: {e}")
                lyrics = None

        # Log the API response
        if lyrics_result is not None:
            logging.debug(f"API response for {file_path}: {lyrics_result}")

        if lyrics:
            logging.info(f"Lyrics found for {track_name}.")
            add_or_replace_lyrics(file_path, lyrics)
            return "downloaded", file_path
        else:
            logging.warning(f"No lyrics found for {track_name}.")
            return "none", file_path
    except Exception as e:
        logging.error(f"Error while retrieving metadata or lyrics for {file_path}: {e}")
        return "none"
    finally:
        time.sleep(int(os.getenv("API_SLEEP_TIME", 5)))

# Function to process all music files in a directory recursively
def process_directory(directory_path, file_limit):
    logging.debug(f"Scanning directory: {directory_path} with file limit: {file_limit}")
    if not os.path.isdir(directory_path):
        logging.error(f"The specified path is not a valid directory: {directory_path}")
        return []

    # Supported extensions
    supported_extensions = [".mp3", ".ogg"]

    file_count = 0
    files_to_process = []

    for root, _, files in os.walk(directory_path):  # Recursively walk through directories
        logging.debug(f"Entering directory: {root}")
        for file_name in files:
            file_path = os.path.join(root, file_name)
            if any(file_path.lower().endswith(ext) for ext in supported_extensions):
                if file_limit > 0 and file_count >= file_limit:
                    logging.info(f"Reached the file limit of {file_limit}. Stopping.")
                    return files_to_process
                logging.debug(f"File added to processing list: {file_path}")
                files_to_process.append(file_path)
                file_count += 1

    logging.debug(f"Total files to process: {len(files_to_process)}")
    return files_to_process

# Function to log MP3 tags
def log_mp3_tags(file_path):
    try:
        # Force loading as ID3
        audio = ID3(file_path)
        logging.info(f"Tags found in {file_path}:")
        for tag_key, tag in audio.items():
            logging.info(f"  Tag: {tag_key}, Value: {tag}")
    except Exception as e:
        logging.error(f"Error while reading tags for {file_path}: {e}")

# Global counters
files_processed = 0
files_with_lyrics = 0
files_with_downloaded_lyrics = 0
files_without_lyrics = 0

# Main function
def main():
    # Configure logging
    setup_logging()

    parser = argparse.ArgumentParser(description="Add synchronized lyrics to music files.")
    parser.add_argument("--folder", type=str, required=True, help="Path to the folder containing music files.")
    parser.add_argument("--file-limit", type=int, default=int(os.getenv("FILE_LIMIT", 100)), help="Limit the number of music files processed. Set 0 for unlimited.")
    args = parser.parse_args()

    logging.debug(f"Arguments received: folder={args.folder}, file_limit={args.file_limit}")

    file_limit = args.file_limit if args.file_limit > 0 else float("inf")
    files_to_process = process_directory(args.folder, file_limit)

    # Get max parallel processes from environment variable
    max_parallel = int(os.getenv("MAX_PARALLEL", 1))
    logging.debug(f"Max parallel processes: {max_parallel}")

    # Process files in parallel
    with ThreadPoolExecutor(max_workers=max_parallel) as executor:
        results = list(executor.map(process_file, files_to_process))

    filtered_results = [r for r in results if r is not None]
    summary = Counter(result for result, _ in filtered_results)
    no_lyrics_files = [file_path for result, file_path in filtered_results if result == "none"]

    print("Processing summary:")
    print(f"-> Total files processed: {len(results)}")
    print(f"-> Files with existing lyrics: {summary['existing']}")
    print(f"-> Files with downloaded lyrics: {summary['downloaded']}")
    print(f"-> Files without lyrics: {summary['none']}")

    if no_lyrics_files:
        logging.warning("\nFiles without lyrics:")
        for f in no_lyrics_files:
            logging.warning(f"- {f}")

# Run the script with lock management
if __name__ == "__main__":
    try:
        acquire_lock()
        main()
    finally:
        release_lock()