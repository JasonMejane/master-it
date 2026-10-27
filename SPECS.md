# MasterIt – specs

## Goal

GUI to download audio from YouTube links with yt-dlp, then optionally repack the
results (clean names, move, tag) into a library that SoundTag can maintain.

## User flow

1. Open the app.
2. Paste one or more links.
3. App runs yt-dlp; progress is shown live.
4. Results are listed (this session's downloads by default; any folder can be opened
   to repack older downloads).
5. User asks for a repack: clean names → move → tag, each previewed before applying.

## Features

- **Download**: multi-URL input; options ported from `Scripts/YT_Audio_DL/ytdl.py`
  (title cleaning of "(Official Video)" etc., thumbnail embed, playlist subfolder).
  "Artist - Title" titles are split into tags only when yt-dlp found no artist; files are
  named `Artist - Title.<ext>` when the artist is known.
  Each video ends as completed (non-fatal errors as warnings) or failed, reported once;
  a file not converted to the chosen codec counts as failed.
  Codec and quality configurable (mp3/opus/m4a/flac), default mp3 192.
- **Rename**: bulk remove substring, bulk prefix/suffix, single-file rename.
- **Move**: select files, choose destination, preview, apply; conflicts reported.
- **Manual tags**: ID3v2.4 (mutagen) edit, bulk and single.
- **Auto-tag**: via SoundTag (Deezer, Discogs, MusicBrainz…), tags + cover, overwrite.

## Decisions

- **GUI**: PySide6; core is Qt-free and tested without a display.
- **Library layout**: SoundTag's — `<Root>/<Artist>/<Artist> - <Title>.<ext>`, album
  tracks `<Root>/<Artist>/<Artist> - <Album>/<Artist> - <Title>.<ext>`. Root in settings.
- **Auto-tagging**: `Tagger` protocol + `SoundTagCliTagger` adapter calling SoundTag
  as a subprocess. SoundTag gets a `--json` option (NDJSON event per file) so the
  coupling does not depend on its human log format. Reimplementing SoundTag
  (~5–7k LOC of tuned matching logic) would double maintenance; a `NativeTagger`
  can later replace the adapter behind the same protocol if needed.
- **Window**: tabs — Download (links, output folder, format, quality, progress table) and
  Library (Phase 3). Settings and window geometry persist via QSettings; default output
  folder is the system Music folder + `YT_DL`. Download is disabled when ffmpeg is missing.
- **Closing during a download**: cancels and closes once the current step ends; a second
  close quits at once.
- **File operations as plans**: preview → apply (undo possible later).
- **Tooling**: uv, pytest + pytest-qt + pytest-cov (≥ 90%), ruff (complexity ≤ 3),
  pyright (strict).

## Package layout

```
src/masterit/
  download/  YtDlpDownloader, options builder, progress events
  library/   TrackFile, RenamePlan, MovePlan, library layout
  tags/      TagStore (mutagen), bulk/single tag edits
  tagging/   Tagger protocol, SoundTagCliTagger
  repack/    RepackPipeline: clean → move → tag
  gui/       MainWindow, tabs/panels, QThreadPool workers
```

## Roadmap

0. Scaffold — done.
1. Download core (yt-dlp faked in tests) — done.
2. GUI shell + Download tab (live progress, cancel) — done.
3. Results table + rename (bulk/single, preview).
4. Move plans + apply.
5. Manual tag edit (bulk/single).
6. Repack pipeline + SoundTag adapter (+ `--json` in SoundTag). Run SoundTag with
   `--overwrite`: yt-dlp already writes title, artist, year, genre and cover, so SoundTag
   would otherwise skip downloads as fully tagged.
7. Optional: native Python tagger.
