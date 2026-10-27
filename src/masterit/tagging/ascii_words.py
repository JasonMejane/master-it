# SoundTag's patterns were written for JavaScript, whose \b only sees ASCII word characters,
# whatever the case flag.
WORD_START = r"(?<!(?-i:[A-Za-z0-9_]))"
WORD_END = r"(?!(?-i:[A-Za-z0-9_]))"
