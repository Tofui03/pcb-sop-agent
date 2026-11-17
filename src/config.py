"""Knobs for v1. Later milestones add the model names here."""

# v1 does not use a tokenizer. One token counts as 4 characters.
# That is a rough English-sized estimate. Chinese is often denser than
# this, and the windows stay character counts so a cut is deterministic.
# 500 tokens -> 2000 characters. 50 tokens of overlap -> 200 characters.
CHARS_PER_TOKEN = 4

TARGET_CHUNK_TOKENS = 500
OVERLAP_TOKENS = 50

MAX_CHUNK_CHARS = TARGET_CHUNK_TOKENS * CHARS_PER_TOKEN
OVERLAP_CHARS = OVERLAP_TOKENS * CHARS_PER_TOKEN
