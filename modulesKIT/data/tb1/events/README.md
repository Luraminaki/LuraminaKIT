# Archived event images

One subfolder per event key, holding two different kinds of image:

- **Banner backups** — local copies of the `image_url` banner referenced in
  [`../events.json`](../events.json). These are purely insurance against link rot
  on the external hosts (Terra Battle Wiki, Discord CDN, etc.) — **nothing in this
  repo loads or serves these**. Discord always renders the *live* URL from
  `events.json`, not a local copy. If a live link ever dies (as already happened
  to `arachnobot`'s original Discord CDN chart — see `events.json`'s comment on
  that entry), the fix is to re-host the archived copy somewhere with a stable URL
  and update `image_url`, not to wire this folder into the app.
- **`flowchart.png`** — the one filename that *is* actually served, when an
  event's `EventInfo.flowchart_file` is set. `TB1View.__init__` (see
  `api_views.py`) registers a dedicated route for it and advertises it as a real
  Discord attachment via `RouteDescriptor.attachment_paths` — LuraminaKIT fetches
  and sends it alongside the event's text card. See `events.py`'s
  `EventCatalog.flowchart_path`.
