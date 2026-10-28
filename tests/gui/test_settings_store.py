from pathlib import Path

from PySide6.QtCore import QByteArray, QSettings

from masterit.download.settings import AudioCodec, DownloadSettings
from masterit.gui.settings_store import SettingsStore
from masterit.tagging.native_setup import TaggerKeys, get_default_user_agent


def make_store(tmp_path: Path) -> SettingsStore:
    return SettingsStore(QSettings(str(tmp_path / "test.conf"), QSettings.Format.IniFormat))


def test_defaults_to_given_folder_and_mp3_192(tmp_path: Path):
    settings = make_store(tmp_path).load_download_settings(Path("/music/YT_DL"))
    assert settings == DownloadSettings(Path("/music/YT_DL"), AudioCodec.MP3, "192")


def test_saved_download_settings_are_loaded_back(tmp_path: Path):
    saved = DownloadSettings(Path("/elsewhere"), AudioCodec.FLAC, "320")
    make_store(tmp_path).save_download_settings(saved)
    assert make_store(tmp_path).load_download_settings(Path("/music")) == saved


def test_unknown_codec_falls_back_to_mp3(tmp_path: Path):
    store = make_store(tmp_path)
    store.save_download_settings(DownloadSettings(Path("/music")))
    QSettings(str(tmp_path / "test.conf"), QSettings.Format.IniFormat).setValue(
        "download/codec", "wav"
    )
    assert make_store(tmp_path).load_download_settings(Path("/music")).codec == AudioCodec.MP3


def test_window_geometry_round_trips(tmp_path: Path):
    make_store(tmp_path).save_window_geometry(QByteArray(b"geometry"))
    assert make_store(tmp_path).load_window_geometry() == QByteArray(b"geometry")


def test_missing_window_geometry_is_none(tmp_path: Path):
    assert make_store(tmp_path).load_window_geometry() is None


def test_unknown_quality_falls_back_to_default(tmp_path: Path):
    make_store(tmp_path).save_download_settings(DownloadSettings(Path("/music"), quality="999"))
    assert make_store(tmp_path).load_download_settings(Path("/music")).quality == "192"


def test_hand_edited_value_with_comma_stays_text(tmp_path: Path):
    (tmp_path / "test.conf").write_text("[download]\noutput_dir=/music/a,b\n")
    settings = make_store(tmp_path).load_download_settings(Path("/x"))
    assert settings.output_dir == Path("/music/a,b")


def test_window_geometry_is_written_to_disk_at_once(tmp_path: Path):
    store = make_store(tmp_path)
    store.save_window_geometry(QByteArray(b"geometry"))
    assert "geometry" in (tmp_path / "test.conf").read_text()


def test_library_root_is_unset_by_default(tmp_path: Path):
    assert make_store(tmp_path).load_library_root() is None


def test_saved_library_root_is_loaded_back(tmp_path: Path):
    make_store(tmp_path).save_library_root(Path("/music/Library, Main"))
    assert make_store(tmp_path).load_library_root() == Path("/music/Library, Main")


def test_tagger_keys_default_to_the_app_user_agent(tmp_path: Path):
    assert make_store(tmp_path).load_tagger_keys() == TaggerKeys(get_default_user_agent())


def test_saved_tagger_keys_are_loaded_back(tmp_path: Path):
    keys = TaggerKeys("Agent, with comma", "token", "key", "secret", "lastfm", "youtube")
    make_store(tmp_path).save_tagger_keys(keys)
    assert make_store(tmp_path).load_tagger_keys() == keys


def test_the_default_user_agent_is_not_frozen_by_saving(tmp_path: Path):
    store = make_store(tmp_path)
    store.save_tagger_keys(TaggerKeys(f" {get_default_user_agent()} "))
    raw = QSettings(str(tmp_path / "test.conf"), QSettings.Format.IniFormat)
    assert not raw.contains("tagging/musicbrainz_user_agent")
    store.save_tagger_keys(TaggerKeys(""))
    assert make_store(tmp_path).load_tagger_keys().musicbrainz_user_agent == ""
