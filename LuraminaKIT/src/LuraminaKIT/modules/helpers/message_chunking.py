#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Splits long text into Discord-sized chunks without cutting through markdown structure."""

from langchain_text_splitters import MarkdownTextSplitter

DISCORD_MAX_MESSAGE_LENGTH = 2000


def chunk_message(text: str, max_length: int = DISCORD_MAX_MESSAGE_LENGTH) -> list[str]:
    """Split `text` into chunks Discord will accept, preferring markdown-aware boundaries.

    Uses `langchain_text_splitters.MarkdownTextSplitter` so headers, code fences, and
    lists aren't split blindly mid-token the way a naive `text[:n]` slice would. Any
    piece the splitter still leaves too long (e.g. one unbroken oversized token) is
    hard-sliced as a last resort, so the `max_length` invariant always holds.

    Args:
        text: The text to split.
        max_length: Maximum length of each returned chunk. Defaults to Discord's
            2000-character message limit.

    Returns:
        `[text]` unchanged if it already fits, otherwise the split chunks in order.
    """
    if len(text) <= max_length:
        return [text]

    splitter = MarkdownTextSplitter(chunk_size=max_length, chunk_overlap=0)
    chunks = splitter.split_text(text)

    return [piece
            for chunk in chunks
            for piece in (chunk[i:i + max_length] for i in range(0, len(chunk), max_length))]
