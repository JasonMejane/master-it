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
  Each pasted link shows as pending at once; a playlist's videos are listed as pending as
  soon as yt-dlp resolves it, right after their link. Each video ends as completed
  (non-fatal errors as warnings) or failed, reported once; a file not converted to the chosen
  codec counts as failed, a row still pending at the end fails as "Not downloaded" (cancelled
  when the download was cancelled).
  Codec and quality configurable (mp3/opus/m4a/flac), default mp3 192.
- **Rename**: bulk remove substring, bulk prefix/suffix, single-file rename.
- **Library tab**: lists this session's downloads, or any opened folder (recursive, hidden
  entries skipped). A live "New name" column previews the rename of the selected rows.
- **Rename rules**: "Remove text" is case-insensitive and only tidies around what it removed
  (emptied brackets, doubled spaces, stranded separators). Names Windows cannot read
  (`/ \ : * ? " < > |`, control characters) or starting with "." are refused. A rename onto
  an existing file is refused, including chains (b → ab while ab moves too). Inline edit
  (double-click/F2) renames one file; a typed extension is ignored.
- **Move**: select files → "Move selected to…" → folder picker → confirmation dialog listing
  moves and skipped conflicts → background move with progress. Destinations are flattened.
  Cross-drive moves copy (exclusive create, never overwriting) then delete the source; a
  failed copy is removed. Emptied source folders are removed inside the opened folder (or the
  download folder in session view), never the download folder itself nor its content while a
  download runs. Closing waits for a running move.
- **Manual tags**: form beside the Library table edits Title, Artist, Album, Album artist,
  Year, Genre, Track and Comment of the selected files (mp3 as ID3v2.4, flac/opus/ogg Vorbis
  comments, m4a atoms; wav refused per file). Values shared by the selection are shown,
  differing ones as "<multiple values>"; a clear action on any field with a value removes it
  from all; multi-value tags show joined by "; ". Comment falls back to the description
  (in yt-dlp Vorbis files: the URL then the whole video description); removing it also
  removes the description, synopsis and purl keys, even when hidden behind a comment. Only edited fields are written (a field typed back
  to its loaded text is no edit), an emptied field removes the tag. Edits preview in the
  table's tag columns, are discarded on selection change, and are refused for malformed
  Year (`2024[-05[-17]]`) or Track (`3[/12]`, 1–9999); problems show inside the form.
  Writes run in the background like moves; closing waits for them.
- **Cover**: read-only view above the tag form showing the selection's embedded cover (front
  cover preferred); "<multiple covers>" when they differ, "No cover" when there is none.
- **Auto-tag**: "Auto-tag selected" runs `soundtag --json --overwrite <files>` in the
  background; an "Auto-tag" column shows each file's status for the session (pending,
  tagged, skipped, failed, stopped) and tag columns refresh. Cancel stops SoundTag after
  its current file; closing the app cancels, then waits. Disabled with a hint when
  `soundtag` is not on PATH.
- **Repack**: "Repack selected" moves files into the library layout
  `<Root>/<Artist>/<Artist> - <Title>.<ext>` built from their tags (characters Windows
  refuses become "-", leading dots/spaces and trailing dots/spaces dropped, reserved
  device names such as "Con" get a "_", names cut to 255 bytes; files without artist or
  title are skipped), then auto-tags the moved files and those already in place. One
  confirmation lists moves, files in place and skips. The library root is picked in the
  Library tab (asked on first repack) and saved in settings.

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
- **File operations as plans**: one relocation engine (`library/relocation.py`) for rename,
  move and the future repack layout; each operation only supplies a destination maker.
  Preview → apply (undo possible later).
- **Tooling**: uv, pytest + pytest-qt + pytest-cov (≥ 90%), ruff (complexity ≤ 3),
  pyright (strict).

## Package layout

```
src/masterit/
  download/  YtDlpDownloader, options builder, progress events
  library/   audio listing, rename rules, destinations, relocation plan (rename/move/layout)
  tags/      TagStore (mutagen), bulk/single tag edits
  tagging/   Tagger protocol, SoundTagCliTagger
  repack/    RepackPipeline: clean → move → tag
  gui/       MainWindow, tabs/panels, QThreadPool workers
```

## Roadmap

Status (2026-10-27): phases 0–6 done; phase 7 in progress (7a done).

0. Scaffold — done (`ba9e9c7`).
1. Download core (yt-dlp faked in tests) — done (`dba3f8a`).
2. GUI shell + Download tab (live progress, cancel) — done (`93c3c59`).
3. Library tab + rename (bulk/single, live preview) — done (`27f1d5c`).
4. Move (shared relocation engine, confirmation, background job, safe cleanup) — done.
5. Manual tag edit (bulk/single); `gui/library_panel.py` split into source, rename, move
   and tag sub-widgets sharing a `LibraryContext` — done.
6. Repack pipeline + SoundTag adapter — done. SoundTag gained opus/m4a, several
   sources per run and `--json` events. SoundTag runs with `--overwrite`: yt-dlp already
   writes title, artist, year, genre and cover, so it would otherwise skip downloads.
   The library layout is another destination maker of the relocation engine.
7. Native Python tagger: port SoundTag (`3e4899f`, without CLI/TUI) into `tagging/`, then
   replace `SoundTagCliTagger`. Overwrite mode only (what MasterIt uses); API keys in a
   settings dialog (QSettings); stdlib urllib behind an injectable `HttpTransport`; a failed
   file reports its reason, no timed lookup log. Synchronous: files run one at a time in
   the worker thread. One commit per step:
   a. `tagging/web/`: HTTP transport (http(s) only), JSON/image reads, rate limiter, caches — done.
   b. Library paths: file-name parser, folder context, library path, album plan.
   c. Matching and merge: track matching, track metadata, metadata chain.
   d. Providers: Deezer, MusicBrainz/ListenBrainz, Discogs, iTunes, Last.fm, YouTube cover.
   e. Album resolver and album tagging.
   f. Processing (write policy), `NativeTagger`, settings dialog, adapter removed.

Known limits:
- A same-drive rename/move can overwrite a file created at the target in the instant
  between the check and the rename (no portable no-replace rename on FAT/exFAT).
- Rename chains (b → ab while ab moves too) are refused rather than ordered.
- Selecting files reads their tags and covers on the GUI thread (cached); a huge selection
  may stall.
- Editing a multi-value tag writes the typed text as a single value; the layout uses it
  joined ("A; B") as the artist folder.
- SoundTag reports no reason for a failed file in its JSON events (it stays in its log).
- A file inside an album folder (`<Artist> - <Album>`) brings its whole album into the
  SoundTag run; those extra files get statuses too.
- Moves of a repack cannot be cancelled, only the tagging after them. Cancel stops
  SoundTag after its current file; a second Cancel (or second close) stops it at once.
- Two stops within 200 ms count as one in SoundTag, so a fast double click only stops it
  after the current file.
- Windows: SoundTag only handles SIGINT, so the first Cancel already stops it at once
  (CTRL_BREAK).
- Windows: `soundtag` is an npm `.cmd` wrapper run through cmd.exe, where file names with
  `&`, `%` or `^` can break the command line (not handled yet; Linux is the target).
- Auto-tag requests: the timeout bounds each socket operation and is checked again once
  headers and each body chunk arrive, so a stalling service can exceed it by one socket
  timeout; DNS lookups are not bounded.
- Layout on case-insensitive drives: an artist folder existing with another casing is
  reused, but the file is not seen as in place on later repacks.
