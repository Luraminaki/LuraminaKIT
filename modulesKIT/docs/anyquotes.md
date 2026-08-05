# anyquotes

Picks a random quote from CSV files and renders it through a configurable template.

- **Launcher**: `main_anyquotes.py`
- **Default port**: `8001`
- **Data**: `data/anyquotes/*.csv` — semicolon-delimited, one quote per line. Any columns beyond `QUOTE`/`AUTHOR` are ignored (e.g. `FamousQuotes.csv`'s `GENRE` column), see `anyquotes.Quote`. Every `*.csv` file under the module's data folder is indexed at startup; add a new file to add a new source, no code changes needed.
- **Config** (`modulesKIT/config.json`, under `modules.anyquotes.data`):
  - `template` — the quote's render template. `<quote>`, `<author>`, and `<source_file>` (the CSV's filename stem) are substituted in.

## Routes / Discord commands

| Discord command | Route | Params |
|---|---|---|
| `!quote` | `GET /api/anyquotes/quote` | none |

## Example

```bash
curl "http://127.0.0.1:8001/api/anyquotes/quote"
```

## See also

- [`../HOWTO.md`](../HOWTO.md) — `anyquotes` is the reference implementation walked through there for building a new module.
