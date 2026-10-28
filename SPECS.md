# MasterIt – specs

## Goal

- Download audio from YouTube links with yt-dlp.
- Repack the files into a library: clean the names, move the files, tag the files.
- Get the tags from online music services.

## User flow

1. Open the app.
2. Paste one or more links.
3. Start the download. The app shows the progress live.
4. Examine the results. The app shows the downloads of this session, or a folder that you open.
5. Repack the files. Examine each change before the app applies it.

## Features

- **Download**: Many links at one time. Playlists. Codec mp3, opus, m4a or flac (default mp3 192).
- **Rename**: Remove text, add a prefix or a suffix, rename one file. A preview shows the new names.
- **Move**: Move the selected files to a folder. A dialog shows the moves and the conflicts first.
- **Manual tags**: Edit the tags of the selected files. The app writes only the changed fields.
- **Cover**: Show the embedded cover of the selection.
- **Auto-tag**: Find the tags and the cover on Discogs, ListenBrainz, MusicBrainz, Deezer,
  iTunes and Last.fm. The app replaces the old tags.
- **Repack**: Ask for the artist and the album. Move the files into the library layout.
  Auto-tag the files.
- **Settings**: API keys, library root, window size and position.

## Decisions

- **GUI**: PySide6. The core has no Qt and its tests run without a display.
- **Library layout**: `<Root>/<Artist>/<Artist> - <Album>/<Artist> - <Title>.<ext>`.
- **File operations**: One relocation engine for rename, move and repack.
  Each operation gives a plan. Preview the plan, then apply it.
- **Auto-tagging**: `Tagger` protocol. `NativeTagger` in `tagging/` implements it.
  It is a Python port of SoundTag (`3e4899f`). It uses overwrite mode only.
- **Background work**: Downloads, moves and tag writes run in worker threads.
  When you close the app, it waits for them or cancels them.
- **Install**: `uv tool install` from the git repo. `masterit --install-desktop` adds a desktop entry.
- **Tooling**: uv, pytest (coverage ≥ 90%), ruff (complexity ≤ 3), pyright (strict).

## Package layout

```
src/masterit/
  download/  yt-dlp downloader, options, progress events
  library/   audio listing, rename rules, relocation plans
  tags/      tag store and tag edits
  tagging/   Tagger protocol and NativeTagger
  repack/    repack pipeline: clean → move → tag
  desktop/   desktop entry install
  gui/       main window, tabs, workers
```

## Known limits

- A rename or move on the same drive can overwrite a file that appears at the target at that moment.
- The app refuses rename chains. It does not put them in order.
- A large selection can stop the GUI for some time, because the GUI thread reads the tags.
- You cannot cancel the moves of a repack. You can cancel only the tagging.
- "Stop now" cannot stop a request that the app sent. The request ends at its timeout.
- A tagged file needs free space for one copy of itself.
- On case-insensitive drives, a repack does not see a file in place if the artist folder has a different case.
