from typing import Any, Dict
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.label import Label
from kivy.uix.progressbar import ProgressBar
from kivy.uix.checkbox import CheckBox
from kivy.clock import Clock
from kivy.core.window import Window
import threading
from pathlib import Path
import pyperclip
from plyer import notification
from kivy.uix.popup import Popup
from kivy.uix.filechooser import FileChooserListView
import asyncio
import re
import subprocess
import platform
import os

class DownloaderGUI(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = 10
        self.spacing = 10
        
        # Add spotify client initialization
        from downloader import init_spotify_client
        self.spotify_client = init_spotify_client()
        
        # Set default output directory
        default_output = Path.home() / "Music" / "Downloads"
        default_output.mkdir(parents=True, exist_ok=True)
        
        # Input section
        input_section = BoxLayout(orientation='vertical', size_hint_y=0.3)
        input_row = BoxLayout(orientation='horizontal', size_hint_y=0.5)
        
        self.input_field = TextInput(
            multiline=False,
            hint_text='Enter URL or file path',
            size_hint_x=0.7
        )
        paste_btn = Button(
            text='Paste',
            size_hint_x=0.15,
            on_press=self.paste_clipboard
        )
        browse_btn = Button(
            text='Browse',
            size_hint_x=0.15,
            on_press=self.browse_files
        )
        
        input_row.add_widget(self.input_field)
        input_row.add_widget(paste_btn)
        input_row.add_widget(browse_btn)
        
        self.url_label = Label(
            text='',
            size_hint_y=0.5
        )
        
        input_section.add_widget(input_row)
        input_section.add_widget(self.url_label)
        
        # Output section
        output_section = BoxLayout(orientation='vertical', size_hint_y=0.3)
        
        output_dir_row = BoxLayout(orientation='horizontal')
        self.output_dir = TextInput(
            multiline=False,
            hint_text='Output directory',
            text=str(default_output),
            size_hint_x=0.8
        )
        browse_output_btn = Button(
            text='Browse',
            size_hint_x=0.2,
            on_press=self.browse_output
        )
        output_dir_row.add_widget(self.output_dir)
        output_dir_row.add_widget(browse_output_btn)
        
        self.filename_prefix = TextInput(
            multiline=False,
            hint_text='File name prefix'
        )
        
        output_section.add_widget(output_dir_row)
        output_section.add_widget(self.filename_prefix)
        
        # Notification checkbox
        notify_row = BoxLayout(orientation='horizontal', size_hint_y=0.1)
        self.notify_checkbox = CheckBox(active=True)
        notify_label = Label(text='Enable notifications')
        notify_row.add_widget(self.notify_checkbox)
        notify_row.add_widget(notify_label)
        
        # Action buttons
        action_section = BoxLayout(orientation='horizontal', size_hint_y=0.2)
        
        download_btn = Button(
            text='Download Song',
            on_press=self.download_song
        )
        split_btn = Button(
            text='Download & Split',
            on_press=self.download_and_split
        )
        smart_mix_btn = Button(
            text='Download, Split & Smart Mix',
            on_press=self.download_split_mix
        )
        
        action_section.add_widget(download_btn)
        action_section.add_widget(split_btn)
        action_section.add_widget(smart_mix_btn)
        
        # Progress section
        self.progress_bar = ProgressBar(
            max=100,
            size_hint_y=None,
            height='40dp'  # Set fixed height of 40 density-independent pixels
        )
        self.log_field = TextInput(
            readonly=True,
            multiline=True,
            size_hint_y=1  # Take up all remaining space
        )
        
        # Add all sections to main layout
        self.add_widget(input_section)
        self.add_widget(output_section)
        self.add_widget(notify_row)
        self.add_widget(action_section)
        self.add_widget(self.progress_bar)
        self.add_widget(self.log_field)
        
        # Initialize variables
        self.current_task = None
        self.spotify_song = None
        self.yt_url = None
        
        # Bind input field to URL checker
        self.input_field.bind(text=self.on_input_change)
        
    def log(self, message):
        Clock.schedule_once(lambda dt: self.update_log(message))
        
    def update_log(self, message):
        self.log_field.text += f"{message}\n"
        # Schedule the scroll after the text is actually rendered
        Clock.schedule_once(lambda dt: setattr(self.log_field, '_cursor', self.log_field.get_cursor_from_index(len(self.log_field.text))))
        
    def update_progress(self, value):
        self.progress_bar.value = value
        
    def paste_clipboard(self, instance):
        self.input_field.text = pyperclip.paste()
        
    def show_file_chooser(self, is_file=True):
        content = BoxLayout(orientation='vertical')
        
        file_chooser = FileChooserListView(
            path='.',
            filters=['*'] if is_file else [],
            dirselect=not is_file
        )
        
        buttons = BoxLayout(
            size_hint_y=None,
            height='48dp'
        )
        
        select_btn = Button(text='Select')
        cancel_btn = Button(text='Cancel')
        
        buttons.add_widget(select_btn)
        buttons.add_widget(cancel_btn)
        
        content.add_widget(file_chooser)
        content.add_widget(buttons)
        
        popup = Popup(
            title='Choose a file' if is_file else 'Choose a directory',
            content=content,
            size_hint=(0.9, 0.9)
        )
        
        def select(instance):
            if file_chooser.selection:
                if is_file:
                    self.input_field.text = file_chooser.selection[0]
                else:
                    self.output_dir.text = file_chooser.selection[0]
            popup.dismiss()
            
        def cancel(instance):
            popup.dismiss()
            
        select_btn.bind(on_press=select)
        cancel_btn.bind(on_press=cancel)
        
        popup.open()
    
    def browse_files(self, instance):
        self.show_file_chooser(is_file=True)
            
    def browse_output(self, instance):
        self.show_file_chooser(is_file=False)
        
    def on_input_change(self, instance, value):
        # Handle URLs
        if "spotify.com" in value or "youtube.com" in value:
            threading.Thread(target=self.process_url, args=(value,)).start()
        # Handle file paths
        elif os.path.isfile(value.strip('"\'')): 
            file_path = Path(value.strip('"\''))
            # Set the filename (without extension) as the prefix
            Clock.schedule_once(lambda dt: setattr(self.filename_prefix, 'text', file_path.stem))
            Clock.schedule_once(lambda dt: self.update_url_label(f"File: {file_path.name}"))
            
    def process_url(self, url):
        try:
            self.log(f"Processing URL: {url}")
            if "open.spotify.com" in url:
                self.log("Detected Spotify URL, fetching song details...")
                from downloader import get_song_from_client, get_song_url
                self.spotify_song = get_song_from_client(url, self.spotify_client)
                self.log(f"Found Spotify song: {self.spotify_song.display_name}")
                self.log("Converting to YouTube URL...")
                self.yt_url = get_song_url(self.spotify_song)
                self.log(f"Found matching YouTube URL: {self.yt_url}")
                Clock.schedule_once(lambda dt: self.update_url_label(f"YouTube URL: {self.yt_url}"))
                Clock.schedule_once(lambda dt: setattr(self.filename_prefix, 'text', self.spotify_song.display_name))
            elif "youtube.com" in url:
                self.log("Detected YouTube URL")
                self.yt_url = url
                Clock.schedule_once(lambda dt: self.update_url_label(f"YouTube URL: {self.yt_url}"))
                from downloader import get_yt_title
                self.log("Fetching YouTube video title...")
                title = get_yt_title(url)
                self.log(f"Found video title: {title}")
                Clock.schedule_once(lambda dt: setattr(self.filename_prefix, 'text', title))
        except Exception as e:
            self.log(f"Error processing URL: {str(e)}")
            
    def update_url_label(self, text):
        self.url_label.text = text
        
    def show_notification(self, title, message):
        if not self.notify_checkbox.active:
            return
            
        try:
            notification.notify(
                title=title,
                message=message,
                app_icon=None,
                timeout=10,
            )
        except NotImplementedError:
            # Fallback for macOS
            if platform.system() == 'Darwin':
                try:
                    subprocess.run([
                        'osascript', 
                        '-e', 
                        f'display notification "{message}" with title "{title}"'
                    ])
                except Exception as e:
                    self.log(f"Failed to show notification: {str(e)}")
            else:
                self.log(f"System notifications not supported on this platform")
            
    def download_song(self, instance):
        if not self.validate_inputs():
            return
        self.current_task = "download"
        threading.Thread(target=self.download_task).start()
        
    def download_and_split(self, instance):
        if not self.validate_inputs():
            return
        self.current_task = "split"
        threading.Thread(target=self.download_task).start()
        
    def download_split_mix(self, instance):
        if not self.validate_inputs():
            return
        self.current_task = "mix"
        threading.Thread(target=self.download_task).start()
        
    def validate_inputs(self):
        if not self.input_field.text:
            self.log("Error: Please enter a URL or file path")
            return False
        if not self.output_dir.text:
            self.log("Error: Please select an output directory")
            return False
        return True
        
    def download_task(self):
        try:
            from downloader import download_yt_song, separate_audio, remix_audio
            
            self.log(f"Starting download task: {self.current_task}")
            output_path = Path(self.output_dir.text.strip('"\''))
            self.log(f"Output directory: {output_path.absolute()}")
            
            def download_progress(data):
                if data["status"] == "downloading":
                    progress = data.get("downloaded_bytes", 0) / data.get("total_bytes", 1) * 100
                    self.update_progress(progress)
                    if "total_bytes" in data:
                        downloaded_mb = data["downloaded_bytes"] / 1024 / 1024
                        total_mb = data["total_bytes"] / 1024 / 1024
                        self.log(f"Downloaded: {downloaded_mb:.1f}MB / {total_mb:.1f}MB")
            
            # Initialize temp_file as None
            temp_file = None
            
            # Check if the input is a file path
            input_path = self.input_field.text.strip('"\'')
            
            if os.path.isfile(input_path):
                self.log(f"Using existing file: {input_path}")
                temp_file = Path(input_path)
            else:
                # Check if the input is a URL
                if not self.yt_url:
                    raise ValueError("Input is not a valid URL for downloading")

                self.log(f"Preparing to download from YouTube URL: {self.yt_url}")
                temp_path = output_path / "tmp.m4a"
                self.log(f"Temporary file will be saved to: {temp_path.absolute()}")
                
                ytdl_opts = {
                    'format': 'm4a/bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'm4a',
                    }],
                    'progress_hooks': [download_progress],
                    'cookiesfrombrowser': ('safari',),
                    'outtmpl': {"default": str(temp_path)},
                }
                self.log("Starting YouTube download...")
                temp_file = download_yt_song(self.yt_url, ytdl_opts, output_path, temp_path, "m4a", self.spotify_song)
                self.log(f"Download completed. File saved to: {temp_file.absolute()}")

            # Check if we have a valid temp_file before proceeding
            if temp_file is None:
                raise ValueError("Failed to obtain input file")

            if self.current_task in ["split", "mix"]:
                self.log(f"Preparing to separate audio tracks from: {temp_file}")
                separated_paths = separate_audio(str(temp_file), output_path, "mp3", progress_hook=self.print_progress)
                self.log("Audio separation completed.")
                self.log(f"Vocals saved to: {separated_paths['vocals']}")
                self.log(f"Drums saved to: {separated_paths['drums']}")
                self.log(f"Bass saved to: {separated_paths['bass']}")
                self.log(f"Other saved to: {separated_paths['other']}")
                self.update_progress(75)
                
                if self.current_task == "mix":
                    remix_file = output_path / f"{self.filename_prefix.text}_smartmix.mp3"
                    self.log(f"Creating smart mix, output will be saved to: {remix_file.absolute()}")
                    remix_audio(
                        str(separated_paths['vocals']),
                        str(separated_paths['drums']),
                        str(remix_file)
                    )
                    self.log("Smart mix creation completed")
                    
            self.update_progress(100)
            self.log("All tasks completed successfully!")
            self.show_notification("Download Complete", "All tasks completed successfully!")
            
        except Exception as e:
            self.log(f"Error during download task: {str(e)}")
            self.show_notification("Error", str(e))

    def print_progress(self, x: Dict[str, Any]) -> None:
        audio_length = x.get("audio_length")
        segment_offset = x.get("segment_offset")
        progress = segment_offset / audio_length * 100
        self.log(f"Separating audio: {progress:.2f}%")
        self.update_progress(progress)

class DownloaderApp(App):
    def build(self):
        return DownloaderGUI()

if __name__ == '__main__':
    Window.size = (800, 600)
    DownloaderApp().run()