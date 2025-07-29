# Video Clipper GUI

A simple desktop GUI for clipping and downloading sections of YouTube videos using yt-dlp.

![Screenshot of Video Clipper](https://github.com/Guanaco-dev/video-clipper-gui/blob/main/icon.png)
*(Tip: Replace the icon above with a real screenshot of your application running!)*

## Features

*   Paste a YouTube URL to fetch video information.
*   Select from all available video formats, including pre-merged (video+audio) and video-only streams.
*   Automatically handles audio selection for video-only formats.
*   Choose a start and end time for your clip.
*   Download the final clip as a single `.mkv` file.

## Dependencies

This application requires `yt-dlp` and `ffmpeg` to be installed on your system.

*   **yt-dlp:** Follow the [official installation instructions](https://github.com/yt-dlp/yt-dlp#installation).
*   **ffmpeg:** On Debian-based systems (like Ubuntu or Mint), run: `sudo apt install ffmpeg`.

## Installation & Usage

1.  Go to the [**Releases Page**](https://github.com/Guanaco-dev/video-clipper-gui/releases).
2.  Download the latest `Video_Clipper-x86_64.AppImage` file.
3.  Make the file executable. You can do this in your file manager (Right-click -> Properties -> Permissions -> Allow executing) or in the terminal:
    ```bash
    chmod +x Video_Clipper-x86_64.AppImage
    ```
4.  Double-click the AppImage to run! For the best experience, install [AppImageLauncher](https://github.com/TheAssassin/AppImageLauncher/wiki) to automatically integrate it into your application menu.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
