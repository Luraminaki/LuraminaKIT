#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Apr 21 13:47:01 2025

@author: Luraminaki
"""

import csv
import time
import mmap
import pathlib
import random
import linecache
import logging
import unidecode
from collections.abc import Generator
from typing import ClassVar, TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from modulesKIT.modules.helpers.generic_config import AppConfig

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

random.seed(int(time.time()))

CWD = pathlib.Path.cwd()

_DEFAULT_QUOTE_ARGS = {'quote': 'Nothing wrong with a man taking pleasure in his work.', 'author': 'John Doe'}


class Quote(BaseModel):
    """A single quote parsed from a CSV row.

    `extra='ignore'` lets this be built straight from a CSV row dict even when the
    source file has extra columns (e.g. FamousQuotes.csv has a GENRE column).

    Attributes:
        quote: The quote text.
        author: The quote's author.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra='ignore')

    quote: str
    author: str


class QuoteFileInfo(BaseModel):
    """Cached metadata about a quote CSV file.

    Attributes:
        nbr_lines: Number of data lines (excluding the header).
        header: Column names, in file order.
    """

    nbr_lines: int
    header: list[str]


class AnyQuotes:
    """Picks random quotes from the CSV files configured for this module."""

    def __init__(self, module_name: str | None = None,
                 modules_config: 'AppConfig | None' = None) -> None:
        """Index every CSV file for `module_name` under the configured data directory.

        Args:
            module_name: Name of this module, used to look up its config and data folder.
            modules_config: Loaded application configuration.

        Raises:
            ValueError: If `module_name` or `modules_config` is missing.
        """
        if not modules_config or not module_name:
            raise ValueError(f"{self.__class__.__name__} -- Invalid module_name configuration file provided -- {module_name} : {modules_config}")

        self.module_name: str = module_name
        self.module_data: dict[str, str] = modules_config.modules[self.module_name].data

        data_path: pathlib.Path = pathlib.Path(modules_config.directories.data_directory) / self.module_name
        input_files: Generator[pathlib.Path] = data_path.glob('*.csv', case_sensitive=False)
        self.q_data: dict[pathlib.Path, QuoteFileInfo] = {}

        for q_file in input_files:
            nbr_lines: int = 0

            with q_file.open('r', encoding='utf-8') as qf:
                reader = csv.reader(qf, delimiter=';')
                header = next(reader)

                # `mmap` maps the file from byte 0 regardless of how far `csv.reader`
                # has read via its own buffer, so this re-reads (and counts) the
                # header row too -- corrected for below. `access=ACCESS_READ` since
                # `qf` is opened read-only (this loop never writes to `buf`).
                buf = mmap.mmap(qf.fileno(), 0, access=mmap.ACCESS_READ)

                while buf.readline():
                    nbr_lines += 1

            nbr_lines -= 1  # exclude the header row counted above

            self.q_data[q_file] = QuoteFileInfo(nbr_lines=nbr_lines, header=header)

    def pretty_quote(self, source_file: str, data_quote: Quote) -> str:
        """Render `data_quote` through this module's configured template.

        Args:
            source_file: Stem of the CSV file the quote came from.
            data_quote: The quote to render.

        Returns:
            The rendered quote string.
        """
        template: str = self.module_data.get('template', '')
        return (template.replace('<quote>', '\n- '.join(unidecode.unidecode(data_quote.quote).split(' - ')))
                        .replace('<author>', unidecode.unidecode(data_quote.author))
                        .replace('<source_file>', unidecode.unidecode(source_file)))

    def get_random_quote_from_csv(self) -> str:
        """Pick a random quote from a random indexed CSV file and render it.

        Returns:
            The rendered quote, or `''` if no quote file is available.
        """
        if not self.q_data:
            logger.warning("Quote file folder is either empty or failed to be loaded")
            return ''

        q_file, q_details = random.choice(list(self.q_data.items()))
        # `linecache` is 1-based over the raw file, where line 1 is always the
        # header (excluded from `nbr_lines`) -- draw from [2, nbr_lines + 1] to
        # land only on real data rows.
        q_line: str = linecache.getline(str(q_file.absolute()),
                                        random.randint(2, q_details.nbr_lines + 1)).rstrip('\r\n')

        q_data_raw = {elem_type.lower(): elem
                      for elem_type, elem in zip(q_details.header, q_line.split(';'))}
        q_data = Quote(**q_data_raw) if q_data_raw.get('quote') and q_data_raw.get('author') else Quote(**_DEFAULT_QUOTE_ARGS)

        return self.pretty_quote(q_file.stem,
                                 data_quote=q_data)
