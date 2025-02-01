from pathlib import Path
import shlex
import shutil
from typing import Any, Callable, Dict
import spotdl
import os

import subprocess
import spotdl.providers
import spotdl.providers.audio
import spotdl.utils
from spotdl.utils.formatter import create_file_name
from spotdl.utils.config import get_temp_path
from spotdl.utils.metadata import embed_metadata
from spotdl.utils.ffmpeg import convert, get_ffmpeg_path
import yt_dlp
import tempfile
output_dir = "outputdir"

from yt_dlp.options import create_parser
YT_DLP_PARSER = create_parser()
YT_DLP_PARSER.parse_args(shlex.split("--cookies-from-browser safari"))
def get_song(url: str) -> spotdl.Song:
    obj = spotdl.Spotdl("7f201a372f4044ba8e8a48ac9baf5ed9", "c0e1db5e2cb747c481a6b70fbc94aa64", no_cache=True)
    song = spotdl.Song.from_url(url)
    print(song)
    return song

def get_song_url(song: spotdl.Song) -> Path:
    audio_downloader = spotdl.providers.audio.YouTubeMusic(
        output_format=format
    )
    download_url = audio_downloader.search(song)
    return download_url

def convert_file(temp_file: Path, output_path: Path, song: spotdl.Song, format: str = "wav", progress_hook: Callable[[Dict[str, Any]], None] = None) -> Path:
    ffmpeg_exec = get_ffmpeg_path()
    if ffmpeg_exec is None:
        print("ffmpeg is not installed")
    ffmpeg = str(ffmpeg_exec.absolute())

    filename = create_file_name(song=song, template="{artists} - {title}.{output-ext}", file_extension=format)
    output_file = output_path / filename
    print(output_file)

    def ffmpeg_progress_hook(progress: int) -> None:
        progress = 50 + int(progress * 0.45)
        print(f"Converting {progress:.2f}%")

    if progress_hook is None:
        progress_hook = ffmpeg_progress_hook

    success, result = convert(
        input_file=temp_file,
        output_file=output_file,
        ffmpeg=ffmpeg,
        output_format=format,
        ffmpeg_args=None,
        progress_handler=progress_hook,
    )
    return output_file

def embed_song_metadata(output_file: Path, song: spotdl.Song) -> None:
    embed_metadata(output_file, song, skip_album_art=False)

def print_progress(x: Dict[str, Any]) -> None:
    audio_length = x.get("audio_length")
    segment_offset = x.get("segment_offset")
    progress = segment_offset / audio_length * 100
    print(f"Separating {progress:.2f}%")


# extension must be mp3
def separate_audio(input_file: str, output_dir: Path, format: str, progress_hook: Callable[[Dict[str, Any]], None] = None) -> Dict[str, Path]:
    import demucs.api
    # make sure format is mp3 or wav
    if format not in ["mp3", "wav", "flac"]:
        raise ValueError("Format must be mp3 or wav")
    
    if progress_hook is None:
        progress_hook = print_progress

    separator = demucs.api.Separator(
        callback=progress_hook
    )
    print("separating audio")
    tensor, separated = separator.separate_audio_file(input_file)
    print(separated.keys())
    
    output_filenames = {}
    for stem, source in separated.items():
        output_path = output_dir / f"{Path(input_file).stem}_{stem}.{format}"
        output_filenames[stem] = output_path
        demucs.api.save_audio(source, str(output_path), samplerate=separator.samplerate)
    
    return output_filenames

def remix_audio(vocals_path: str, drums_path: str, output_file: str) -> None:

    ffmpeg_cmd = [
        '/opt/homebrew/bin/ffmpeg', '-i', vocals_path, '-i', drums_path,
        '-filter_complex', '[1:a]lowpass=f=200[a1];[0:a][a1]amix=inputs=2:duration=longest',
        output_file
    ]

    try:
        process = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            print(f"FFmpeg error: {stderr}")
    except Exception as e:
        print(f"An error occurred: {e}")


final_filename = None
def my_hook(d):
    if d['status'] == 'finished':
        print('Done downloading, now post-processing ...')
    elif d['status'] == 'downloading':
        progress = d.get('downloaded_bytes') / d.get('total_bytes') * 100
        print(f"Downloading {progress:.2f}%")
    elif d['status'] == 'error':
        print(f"Error: {d.get('error')}")

def init_spotify_client():
    return spotdl.Spotdl("7f201a372f4044ba8e8a48ac9baf5ed9", "c0e1db5e2cb747c481a6b70fbc94aa64", no_cache=True)

def get_song_from_client(url: str, client: spotdl.Spotdl) -> spotdl.Song:
    song = spotdl.Song.from_url(url)
    print(song)
    return song

def download_yt_song(yt_url: str, ytdl_opts: dict, output_dir: Path, temp_file: Path, format: str, spotify_song: Any = None) -> Path:
    with yt_dlp.YoutubeDL(ytdl_opts) as ydl:
        info = ydl.extract_info(yt_url, download=True)
        title = info['title']
        if spotify_song is not None:
            title = spotify_song.display_name
            embed_song_metadata(temp_file, spotify_song)

        source_audio = output_dir / f"{title}.{format}"
        shutil.copy(temp_file, source_audio)
        # Clean up temporary file
        if temp_file.exists():
            temp_file.unlink()
    return source_audio

def get_yt_title(url: str) -> str:
    """
    Get the title of a YouTube video from its URL.
    
    Args:
        url (str): YouTube video URL
        
    Returns:
        str: Title of the video
    """
    ytdl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
    }
    
    with yt_dlp.YoutubeDL(ytdl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            return info.get('title', '')
        except Exception as e:
            print(f"Error getting YouTube title: {e}")
            return ''

# Example usage
if __name__ == "__main__":
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    song_url = "https://open.spotify.com/track/6fTt0CH2t0mdeB2N9XFG5r"
    song_url = "https://music.youtube.com/playlist?list=OLAK5uy_nFo92tn6Fyjfc_jdHRb0-BnW7taPF_RjI&si=HC9Ost2gjI9HtxNL"
    song_url = "https://open.spotify.com/track/6FGPpwHlUBnl0TLGKyN4Nl?si=db36f2aca209422d"
    source_audio = None
    title = None
    format = "m4a"

    yt_url = None
    spotify_song = None
    if "open.spotify.com" in song_url:
        spotify_song = get_song(song_url)
        yt_url = get_song_url(spotify_song)
    elif "music.youtube.com" in song_url:
        yt_url = song_url
    else:
        raise ValueError("Invalid song url")
    
    temp_file = output_dir / "tmp.m4a"
    if temp_file.exists():
        temp_file.unlink()
        
    ytdl_opts = {
        'format': 'm4a/bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'm4a',
        }],
        'progress_hooks': [my_hook],
        'cookiesfrombrowser': ('safari',),
        'outtmpl': {"default": str(temp_file)},
    }

    source_audio = download_yt_song(yt_url, ytdl_opts, output_dir, temp_file, format, spotify_song)
    
    separated_paths = separate_audio(str(source_audio), output_dir, "mp3")
    remix_file = output_dir / f"{title} smartmix.{format}"
    remix_audio(str(separated_paths['vocals']), str(separated_paths['drums']), str(remix_file))