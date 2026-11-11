# Technical Specification — Pushkinskaya Street Explorer

| Item | Value |
|---|---|
| Project | Pushkinskaya Street Tourist Guide — landmark recognition system |
| Location | Pushkinskaya Street, Rostov-on-Don, Russia |
| Document version | 1.0 |
| Date | 11 November 2026 |
| Code baseline | `c7aad1e` (`main`, pushed to GitVerse and the GitHub mirror) |
| Status | Implemented and demo-ready; the remaining verification gaps are listed in Appendix B |
| Primary repository | <https://gitverse.ru/smothkd/Tourist_Guide> |
| Mirror | <https://github.com/smothkd54/Tourist_Guide> |

This document answers the 90 questions in the six requested sections. Every
answer describes the code and deployment that exist in this repository, not an
intended future design. Where a figure was not measured, the answer says so
instead of inventing one. The source of truth for behaviour is the code; the
README, `docs/gitverse.md` and this document are kept consistent with it.

---

## System at a glance

```
Browser / PWA ─┐
               ├── HTTP/JSON ──> Caddy (:80/:443) ──> Flask + gunicorn (:5000) ──> PostgreSQL 16
Android app  ──┘                      │                        │
                                      │                        ├── TFLite model (8.39 MB, float16)
                                      │                        ├── landmarks.json / photos (disk)
                                      │                        └── public OSRM (walking routes)
                                      └── static frontend, gzip, cache headers
```

| Fact | Value |
|---|---|
| Landmarks in the catalogue | 46 |
| Landmarks the camera can recognise | 29 classes |
| Published, credited photos | 38 (8 landmarks are text-only) |
| Model | EfficientNetB0 → float16 TFLite, 8.39 MB |
| Test accuracy | 60.0% (39/65) on a held-out split |
| Answer precision / coverage at 0.35 | 82% / 52% |
| Inference latency (40-sample benchmark) | p50 54.4 ms, p95 60.4 ms |
| Serving memory (TFLite runtime) | about 87 MB RSS (versus about 392 MB for TensorFlow) |
| Database tables | 7 + `schema_migrations` |
| Automated tests | 79; JSON mode 68 passed + 11 skipped, PostgreSQL mode 78 passed + 1 skipped |
| Cost of the running demo | $0 (local laptop, free CI, public OSRM/OSM) |

---

# 1. Frontend Part

The frontend is a single-page application in `frontend/index.html`, served by
Flask at `/app` (and through Caddy in the composed stack). It uses no build
step and no frontend framework.

### 1. What is the main goal of the frontend? / Who will use the frontend?

**Users.** Tourists and visitors walking Pushkinskaya Street, people planning a
visit from elsewhere, local residents, and the evaluators of the demo. No
account is needed: every visitor is anonymous.

**Goal.** Let a visitor point a phone camera at a building and get a useful
answer in seconds, then browse verified information, see what is nearby, plan a
walking route, share it, and report a problem with the data. The interface also
has to stay usable on a weak mobile connection, which is why it is a PWA with
cached landmarks and photos.

**Success conditions.** A photo is identified (or clearly rejected with the top
5 candidates) and the correct detail card opens; a walk can be planned and
reopened from a shared link; a report reaches the operator; all of this works
without installing an app.

### 2. What is the main goal of the frontend?

To turn the backend's four capabilities — recognition, catalogue, nearby
search, and route planning — into a self-explanatory tourist workflow on one
page, with visible photo credits and honest confidence values. The frontend
never hides uncertainty: below the confidence threshold it says "No match
found" and still shows the five best scores.

### 3. What screens or pages are needed?

One page with five tabs plus overlays:

| Screen | Purpose |
|---|---|
| **Identify** (default) | Drag/drop or choose a photo, preview it, run recognition, show the result, confidence and top-5 bars |
| **Browse Sites** | Grid of all 46 landmarks with a photo where a credited one exists; click opens the detail modal |
| **Near Me** | Browser geolocation → `/nearby`; Leaflet map, radius selector, distance-sorted list; manual coordinates if geolocation fails |
| **Plan a Walk** | Two modes: "My Visit List" (custom stops, start point, auto-optimise or keep order) and "Suggest for My Time" (15–240 minutes) |
| **Manage Photos** | In-session grid for swapping a displayed photo; it does not upload to the server |
| **Landmark detail** (modal) | Photos, credit line, address, year, description, fun fact, architect/style, text-to-speech, visit-list toggle, report form |
| **Report form** (inside modal) | Category, message, send status |
| **Identification queue** (panel) | Up to 5 offline predictions with `queued`/`processing`/`done`/`failed` states |
| **Shared walk** | `/app?itinerary=<uuid>` loads a saved itinerary into Plan a Walk |

The root `/` is a JSON health check, not a page. The favicon and the service
worker are served by Flask; there is no separate admin page.

### 4. How does the user move between screens?

- The header tab bar calls `switchTab(name)`, which toggles the five panels
  without a page reload. The active tab is highlighted.
- Clicking any landmark card or a recognition result opens the modal; the close
  button, the backdrop, or `Escape`-style dismissal closes it.
- "Report a problem" replaces the report slot inside the modal with the form;
  the modal stays open.
- "See the whole street on a map" switches to Near Me and renders all
  landmarks; "Add to Visit List" updates the Plan a Walk tab.
- A shared link (`?itinerary=<uuid>`) is read on load and the saved route is
  rendered in Plan a Walk.
- On a narrow screen the tab bar scrolls horizontally; there is no router and
  no browser-history entry per tab.

### 5. What data is shown on each screen?

| Screen | Data |
|---|---|
| Identify | Preview image; on success: name (EN/RU), confidence badge, address, year, description, fun fact, architect/style, top-5 bars with percentages; on failure: "No match found", the server message and top-5 |
| Browse Sites | 46 cards: thumbnail or placeholder, name, type, address, year; the detail modal adds the full description, fun fact, photo credit (author · licence · Wikimedia Commons link) and visit-list state |
| Near Me | Accuracy warning when the browser reports >500 m or >5000 m; map markers; list with distance in metres; if nothing is inside the radius, the nearest landmark and its distance |
| Plan a Walk | Visit list with order and count; start selector; optimise/keep-order switch; suggested-route time input; result: stops with visit minutes, walking/visiting/total minutes, route geometry on a map, share link |
| Manage Photos | Landmark grid with the current image and an in-session replacement control |
| Header | Connection dot and status text, language button (EN/RU), offline queue badge |

Photo credits come from `photo_attribution`; the frontend escapes third-party
Commons metadata before inserting it into HTML.

### 6. What forms and input fields are needed?

| Form | Fields |
|---|---|
| Identify | File input (`accept="image/*"`), drag-and-drop zone, preview, "Identify this landmark" button |
| Report | Category `<select>` (`wrong_photo`, `wrong_info`, `closed`, `other`), message `<textarea maxlength="2000">`, "Send report" button |
| Near Me | "Use my location" button, radius `<select>` (300/500/1000/2000 m), manual latitude/longitude number inputs shown on geolocation failure |
| Plan a Walk (custom) | Visit-list toggles, start `<select>`, radio "Auto-optimize"/"Keep my order", "Plan route" |
| Plan a Walk (suggested) | Minutes `<input type="number" min="15" max="240" step="15">`, start `<select>`, "Suggest route" |
| Global | Language toggle, queue "Process Now", share-link copy |

There is no login, registration, payment, or photo-upload form. The public
catalogue is read-only.

### 7. What rules check the user input?

The browser performs quick checks; the API repeats every check because it is
the authority.

| Input | Browser rule | Server rule |
|---|---|---|
| Photo | File picker restricted to images; a file must be selected | Body ≤10 MB; base64/data-URI decodes; JPEG/PNG decodable |
| Report message | Trimmed length ≥10; `maxlength=2000` | String, trimmed, 10–2000 characters |
| Report category | Fixed four options | Must be one of the four |
| Landmark id in report | Taken from the open card | Must exist in the catalogue |
| Latitude/longitude | Numeric input; both required | Finite, lat −90…90, lon −180…180 |
| Radius | 300–2000 m in the UI | 1–50,000 m, finite |
| Route minutes | 15–240 in the UI (deliberately narrower) | 15–480 |
| Visit list | Non-empty; start must be in the list; only geocoded landmarks are offered | Non-empty list of known ids, duplicates removed, start ∈ list, `optimize` boolean |
| Shared itinerary id | Read from the query string | Must parse as a UUID; 404 if absent |

The client also stores the visit list and language in `localStorage`. The API
is the only place where a crafted request can be rejected reliably.

### 8. What error messages are shown to the user?

| Situation | Message |
|---|---|
| Offline | "You're offline — showing cached data. Route planning and identification require a connection." |
| API unreachable in Near Me | "API unreachable." |
| Geolocation unsupported | "Geolocation not supported." |
| Geolocation denied/failed | The browser's message, followed by manual coordinate inputs |
| Poor accuracy | "Location accuracy is approximately N km…" or "…N m — nearby results may include a few misses." |
| Report too short | "Please write at least 10 characters." |
| Report sending/success | "Sending..." / "Thank you - the report was received." |
| Report failure | The API's `error` text, or "Could not send the report" |
| Low-confidence identification | "No match found" plus "Confidence too low. Try a clearer photo or a different angle." and the top-5 |
| Bad image | "Image decode failed. Send a valid JPEG or PNG." |
| Model missing | "Model not loaded. Run train.py first." (HTTP 503) |
| Too many requests | "Rate limit exceeded. Try again in a minute." / "Too many reports. Try again in a minute." |
| Route error | The API's message (missing start, out-of-range minutes, unknown landmark, OSRM failure) |
| Queue full | "Queue full (5 items). Remove an item or wait for processing." |
| Bad shared link | "Itinerary not found" or "Invalid itinerary id" |

### 9. What happens while data is loading, empty, or successful?

**Loading.** Identify replaces the button label with a spinner and "Running
model..."; Near Me shows "Getting your location..."; route and report buttons
show their progress text; the header starts at "Connecting...". Requests have
no artificial delay.

**Empty.** Browse shows whatever the catalogue contains (46 records, so never
empty in the demo). A landmark without a published photo shows a placeholder.
An empty visit list says "Your route is empty. Add landmarks from Explore." In
Near Me, an empty result still reports the nearest landmark and its distance,
so the user can tell "nothing within 500 m" from "the API is broken". The
offline queue badge is hidden at zero.

**Success.** The identification card, nearby list, or route result replaces the
placeholder immediately; reports show a green thank-you and clear the textarea;
a saved walk shows its share link. Photo and landmark responses are cached by
the service worker for the next offline visit.

**Failure.** The message is shown in place, in red, and the previous content is
not silently discarded. Predictions made offline are queued (maximum 5) and
processed in order when connectivity returns.

### 10. How should the layout change for phones, tablets, and computers?

The layout is fluid rather than device-specific:

- A centred content column with a maximum width; card grids use
  `repeat(auto-fill, minmax(...))`, so a desktop shows 3–4 columns, a tablet 2,
  and a phone 1.
- At `@media (max-width: 600px)` the header and control rows wrap, the tab bar
  scrolls horizontally, paddings shrink, the modal gets a 10 px margin and a
  90 vh height limit, and the queue panel becomes full width.
- Maps keep a fixed usable height; images use `object-fit: cover`.
- Touch targets are buttons rather than hover-only controls, so the same page
  works with a finger on a phone and a mouse on a laptop.
- The PWA manifest uses `display: standalone`, `orientation: any`, and the dark
  theme, so an installed copy behaves like an app on Android.

There is no separate tablet layout and no desktop-only feature.

### 11. What colors, fonts, and style rules are used?

| Token | Value |
|---|---|
| Background | `#0f0f0f` |
| Surface | `#1a1a1a` |
| Border | `#2a2a2a` |
| Text | `#e8e8e8` |
| Muted text | `#888` |
| Accent (gold) | `#c8a96e` |
| Success / error | `#4caf78` / `#e05c5c` |
| Corner radius | `10px` |
| Font | `system-ui, sans-serif` |

The style is a dark "night street" palette with a single gold accent used for
actions, confidence bars, and map markers. Cards use a surface colour and a
1 px border instead of shadows. Icons are inline SVG or emoji; there is no icon
font and no CSS framework. Spacing is in pixels, typography uses a small number
of sizes, and the accent is never the only signal (errors also use text and
colour).

### 12. What languages and themes are needed?

- **Languages.** Landmark names switch between English and Russian using
  `name_ru`; the choice is stored in `localStorage`. The interface chrome
  itself is English. The Android client has full EN/RU string resources.
  Server messages are English. There is no third language and no machine
  translation.
- **Themes.** One dark theme. The PWA manifest sets `background_color
  #0f0f0f` and `theme_color #c8a96e`. A light theme is not implemented.
- **Content language.** Descriptions are English; Russian names are shown when
  available. The seed data carries both name columns for every landmark.

### 13. Which browsers and versions must be supported?

The target is current evergreen browsers: Chrome/Edge 90+, Firefox 90+,
Safari 15+ on iOS/iPadOS, and Android Chrome. The code uses `fetch`,
`async/await`, CSS grid/flex, service workers, `navigator.geolocation`, and the
Web Speech API for "Listen"; Internet Explorer is not supported.

Practical limits: service workers and install prompts require HTTPS or
localhost; iOS restricts some PWA behaviour and speech voices; the in-app
browser used for development is Chromium-based. The demo was exercised in
Chromium and on Android Chrome through `adb reverse`. There is **no automated
cross-browser matrix** and no formal version certification, so the versions
above are support targets, not a tested guarantee.

### 14. How does the frontend connect to the backend?

`const API = window.location.origin` — the page talks to the same origin that
served it, so no base URL or key is embedded. Requests are JSON over `fetch`:

| Call | Used for |
|---|---|
| `GET /landmarks` | Catalogue on load |
| `GET /photos/available` | Which landmarks have a real photo |
| `GET /photo/<id>` | Thumbnail (also cached by the service worker) |
| `POST /predict` | Base64 image → identification |
| `GET /nearby?lat=&lon=&radius_m=` | Nearby list |
| `POST /plan-custom` | Visit-list route |
| `GET /plan?start=&minutes=` | Suggested route |
| `POST /reports` | Anonymous problem report |
| `POST /itineraries`, `GET /itineraries/<id>` | Save and reopen a shared walk |

When the page is served from Flask/Caddy the origin matches automatically.
During separate development, Flask-CORS allows `localhost` and `127.0.0.1` on
any port (anchored patterns, so `localhost.evil.com` is rejected). There is no
authentication header, cookie, or API key in the browser. Errors are read from
the JSON `error` field and shown in place. The service worker caches the app
shell, landmarks and photos, and queues up to five predictions in
`localStorage` while offline.

### 15. How will the frontend be tested and checked for speed?

**Testing.** Manual end-to-end checks cover every tab, the report dialog, the
shared-itinerary link, offline mode, and geolocation fallbacks; these are the
checks used before the demo. Automated tests exercise the API that the frontend
calls (79 tests) but there is no Selenium/Playwright suite for the DOM. The
service worker and cache version are checked by loading the app twice and
toggling the network.

**Speed.** No Lighthouse score, WebPageTest run, or frontend load test has been
recorded, so no frontend performance number is claimed. The design choices that
protect speed are: a single HTML file with no framework or CDN, self-hosted
Leaflet, gzip and cache headers from Caddy, cache-first landmarks/photos, a
3-second network-first app shell, and an 8.39 MB model with p95 inference of
60.4 ms server-side. A Lighthouse run is listed as a follow-up in Appendix B
rather than presented as a result.

---

# 2. Backend Part

The backend is a Flask application (`backend/app.py`) served by gunicorn,
with a PostgreSQL access layer (`backend/db.py`), an OSRM route planner
(`backend/route_planner.py`), and a TFLite inference wrapper.

### 1. What is the main goal of the backend?

To expose the landmark catalogue, on-device-style image recognition, nearby
search, walking-route planning, anonymous reports, and shareable itineraries as
one small JSON API that both the web frontend and the Android app can use. It
must run without paid cloud inference, keep working in read-only mode when the
database is absent, and fail loudly when the model is missing rather than
serving wrong answers.

### 2. Which user roles exist?

| Role | How it is identified | Exists as an account? |
|---|---|---|
| Anonymous visitor | No credential | No |
| Operator / administrator | `X-Admin-Token` header or a shell on the host | No |
| Metrics scraper | `X-Metrics-Token` header (when configured) | No |
| Developer / CI | Repository and environment access | No application account |

There are no registered users, passwords, sessions, or per-user data.

### 3. What actions can each role do?

**Anonymous visitor**

- Read the catalogue and one landmark; read model metadata and health.
- List available photos and fetch a photo.
- Identify an image (`POST /predict`).
- Search nearby landmarks.
- Plan a suggested or custom route.
- Create an anonymous report and read a shared itinerary.
- Read Prometheus metrics only if no metrics token is configured.

**Operator / administrator**

- Read aggregate statistics (`/admin/stats`).
- List reports with status filter and pagination (`/admin/reports`).
- Change a report to `open`, `resolved`, or `dismissed`
  (`PATCH /admin/reports/<id>`), or use `scripts/admin.py` locally.
- Run migrations, seed, backup, restore, and inspect logs.

**Metrics scraper**

- Read `/metrics` with the header token.

Visitors cannot read reports, change report status, or write catalogue data.
There is no endpoint that deletes a landmark, photo, itinerary, or report.

### 4. What business rules must be followed?

1. **Photo publishing.** A photo may be published only with a non-empty
   author, licence, licence URL, and source URL. The database enforces this;
   at most one published photo per landmark is allowed.
2. **Recognition scope.** Only 29 validated classes are served. Two classes
   with no validation photos are masked and the remaining probabilities are
   renormalised.
3. **Confidence.** The answer threshold is 0.35. Below it the API returns
   `identified: false`, the message, and the top 5; it never presents a guess as
   a fact.
4. **Catalogue is canonical.** Landmark ids in reports and routes must exist.
5. **Routes.** A walk is 15–480 minutes; custom routes need at least one stop,
   a start inside the list, and coordinates; unknown ids are rejected.
6. **Reports.** Four categories only; message 10–2000 characters after
   trimming; anonymous; status is `open`/`resolved`/`dismissed`.
7. **Writes need PostgreSQL.** If `DATABASE_URL` is unset or the database is
   down, reports and itinerary writes return 503; reads continue from JSON.
8. **Uploads.** Request bodies are capped at 10 MB; images are processed in
   memory and never stored.
9. **Rate limits.** Route planning and report creation are limited per client
   per minute (details in question 11).
10. **CORS.** Only loopback origins are allowed by default; configured origins
    are anchored regular expressions, not loose wildcards.

### 5. What actions does the backend provide to the frontend and mobile app?

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/` | Health and model/database status |
| GET | `/metrics` | Prometheus metrics |
| GET | `/landmarks` | All 46 catalogue records |
| GET | `/landmarks/<id>` | One record or 404 |
| GET | `/nearby` | Landmarks inside a radius |
| GET | `/plan` | Suggested walking route (OSRM) |
| POST | `/plan-custom` | Route through chosen landmarks |
| GET | `/route` | Pre-generated route file (legacy fallback) |
| POST | `/predict` | Image recognition |
| GET | `/model/info` | Training metadata |
| GET | `/photo/<id>` | Published thumbnail |
| GET | `/photos/available` | Ids that have a photo |
| POST | `/reports` | Create an anonymous report |
| GET | `/itineraries/<id>` | Read a shared walk |
| POST | `/itineraries` | Save a walk and return its id |
| GET | `/admin/stats` | Operator counters |
| GET | `/admin/reports` | Operator report queue |
| PATCH | `/admin/reports/<id>` | Change report status |
| GET | `/app`, `/app/`, `/app/<file>` | Web app and static assets |
| GET | `/sw.js`, `/favicon.ico` | Service worker and icon |

The Android client uses `/landmarks`, `/predict`, `/plan-custom`, and
`/reports`; it does not call the admin routes.

### 6. What input does each action need?

| Action | Input |
|---|---|
| `/landmarks` | None |
| `/landmarks/<id>` | Path id (string) |
| `/nearby` | `lat`, `lon` (required floats), `radius_m` (default 500) |
| `/plan` | `start` (required id), `minutes` (default 60), `visit` (optional) |
| `/plan-custom` | JSON `{landmarks: [ids], start: id, optimize?: bool}` |
| `/predict` | JSON `{image: "<base64 or data-URI JPEG/PNG>"}` |
| `/reports` | JSON `{landmark_id?: id, category, message}` |
| `/itineraries` | Same JSON as `/plan-custom` |
| `/itineraries/<id>` | UUID path |
| `/admin/stats` | `X-Admin-Token` |
| `/admin/reports` | Token; optional `status`, `limit`, `offset` |
| `/admin/reports/<id>` | Token; UUID path; JSON `{status}` |
| `/metrics` | `X-Metrics-Token` only when configured |

### 7. What output does each action return?

| Action | Success output |
|---|---|
| `/` | `{status, model_loaded, classes, landmarks, data_source, database}`; `503` when model/landmarks are missing |
| `/landmarks` | Array of landmark objects, including `photo_attribution` when published |
| `/landmarks/<id>` | One landmark object or `{error}` |
| `/nearby` | `{query, count, landmarks[], nearest_landmark_distance_m?, nearest_landmark_name?, nearest_landmark_id?}`; each landmark has `distance_m` |
| `/plan`, `/plan-custom` | `{stops[], total_walking_minutes, total_visit_minutes, total_minutes, route_geometry}` |
| `/predict` | `{identified: true, landmark_id, class_id, name, confidence, confidence_pct, top5[], info}` or `{identified: false, message, confidence, top5[]}` |
| `/reports` | `201 {id, status, created_at}` |
| `/itineraries` | `201 {id, route}` |
| `/itineraries/<id>` | `{id, start_landmark_id, mode, minutes, total_minutes, route, created_at}` |
| `/admin/stats` | Counts, database size, `data_source`, model block |
| `/admin/reports` | Array of reports with landmark name, category, message, status, timestamps |
| `PATCH /admin/reports/<id>` | `{id, status, resolved_at}` |
| `/metrics` | Prometheus text |
| `/photo/<id>` | Image bytes or 404 JSON |

### 8. How is the input checked?

Checks happen in this order: Flask body limit → JSON parsing (`silent=True`, so
malformed JSON becomes `{}`) → type checks → range/enum checks → cross-checks
against the catalogue → base64/image decoding. Exact rules:

- **Nearby:** `float()` conversion; `math.isfinite` for all three; lat/lon
  bounds; radius `0 < r ≤ 50000`.
- **Plan:** `start` required; integer conversion; minutes 15–480; visit 0–120;
  at least two geocoded landmarks; start must exist and have coordinates.
- **Custom plan:** body must contain `landmarks` and `start`; list non-empty;
  all ids strings; `optimize` boolean; duplicates removed with order preserved;
  ids must exist; start must be in the list; at least one stop must have
  coordinates.
- **Predict:** model loaded; body has `image`; base64 (raw or data URI) decodes;
  Pillow decodes it as an image. Any failure returns "Image decode failed. Send
  a valid JPEG or PNG."
- **Reports:** category in the enum; message a string, trimmed, 10–2000;
  optional landmark id must exist.
- **Admin reports:** status enum; `limit` 1–200; `offset` ≥0.
- **UUID routes:** `uuid.UUID()` parse before any database work.
- **Photos:** only a known file extension is served from the photo directory.
- **Rate limits:** checked after validation, so a malformed request does not
  consume the route quota.

All SQL uses parameters; no value is interpolated into a statement.

### 9. How do login and user verification work?

There is no login. The public API has no sessions, cookies, passwords, or user
table. Identity is not needed because no public action is tied to a person:
reports are anonymous and itineraries are shareable by unguessable UUID.

Two shared secrets protect non-public surfaces:

- `ADMIN_TOKEN` — required in `X-Admin-Token` for `/admin/*`. Comparison uses
  `secrets.compare_digest`. If the variable is unset the routes return 503; a
  wrong value returns 401.
- `METRICS_TOKEN` — optional in `X-Metrics-Token` for `/metrics`. If unset,
  metrics are open (loopback development); if set, a wrong value returns 401.

The Android app stores no credential. The operator's real authentication is
possession of a shell/account on the host and the token in `.env`.

### 10. How are access rights checked?

| Surface | Control |
|---|---|
| Public read/route/predict/report | No credential; input validation and rate limits |
| `/admin/*` | Header token, constant-time compare, 503 if disabled |
| `/metrics` | Optional header token |
| Database | Credentials in `DATABASE_URL`; app role owns the tables |
| Network | Web and DB ports bound to `127.0.0.1`; Caddy is the only public listener |
| Files | Container runs as non-root `appuser`; model/data/log mounts |
| CI | Repository permissions; tokens are not committed |

There is no row-level security and no object ownership: every visitor can read
the same catalogue and every report is visible to the operator. That matches
the anonymous design.

### 11. What error codes and messages are returned?

| Code | When | Example message |
|---|---|---|
| 200 | Success | — |
| 201 | Report or itinerary created | — |
| 400 | Validation failure | "Provide numeric lat, lon and radius_m query params"; "'message' must be between 10 and 2000 characters"; "Unknown landmark IDs: [...]" |
| 401 | Wrong admin/metrics token | "Unauthorized" |
| 404 | Missing landmark/photo/route/report/itinerary | "Not found"; "Itinerary not found"; "No photo for this landmark" |
| 413 | Body over 10 MB | "Request body too large. Maximum size is 10MB." |
| 429 | Rate limit | "Rate limit exceeded. Try again in a minute."; "Too many reports. Try again in a minute." |
| 503 | Model missing, database needed/unavailable, admin disabled, OSRM failure | "Model not loaded. Run train.py first."; "This feature needs the database..."; "Could not store the report. Try again later."; "OSRM routing failed" |

Rate-limit details, from the code: the OSRM limiter allows
`max(1, 10 // GUNICORN_WORKERS)` requests per 60 s **per worker** (5/min with
the default two workers, so about 10/min across the process pool); the report
limiter allows 5 per 60 s per worker. Both are in-memory, keyed by the first
`X-Forwarded-For` hop or the socket address, and reset on restart. The README's
older "30 requests/minute" line is not what the code enforces and is corrected
in the documentation pass.

### 12. What events are written to logs?

- **Startup:** model path and runtime, LFS-pointer detection, class count,
  landmark count, data source (`postgres`/`json`), and a loud error when
  PostgreSQL is configured but unreachable.
- **Requests of interest:** a stored report (id, landmark, category), image
  decode failures (warning), OSRM failures (error with start/minutes), database
  failures for report/itinerary writes.
- **Access logs:** gunicorn writes request lines to stdout; Caddy writes its own
  access log to stdout in the container.
- **Not logged:** image bytes, base64 payloads, tokens, report message text,
  or full personal data. Report ids and landmark ids are logged.

`backend/logging_setup.py` sends the same logger to stderr and to
`logs/<name>.log` with `RotatingFileHandler` (5 MB × 3 backups, UTF-8,
emoji-stripped). `LOG_DIR` changes the directory. The gunicorn/container
stdout is available through `docker logs`.

### 13. Which outside services are used?

| Service | Use | Required at runtime? |
|---|---|---|
| Public OSRM demo server (`router.project-osrm.org`) | Walking duration/distance matrix and route geometry | Yes, for route planning only |
| OpenStreetMap tiles | Leaflet basemap in the browser | Yes, for the map background only |
| Wikimedia Commons | Photo source and licence verification | No; used offline by the audit script and seed data |
| GitVerse | Primary Git host and backend CI | Development only |
| GitHub | Mirror, Android build, Docker/Trivy, photo audit | Development only |
| Docker Hub / GitVerse registry | Base images (`python:3.11-slim`, `postgres:16-alpine`, `caddy:2`, runner image) | Build/deploy time |
| Let's Encrypt via Caddy | HTTPS certificate when a domain is configured | Only in a public deployment |

There is no cloud vision API, no paid map key, no email/SMS provider, and no
push-notification provider. If OSRM is unavailable, `/plan*` returns 503;
recognition, browsing and nearby search keep working.

### 14. How are files, images, notifications, and long tasks handled?

- **Images.** `/predict` receives base64 inside JSON, decodes in memory, and
  discards it after inference. `/photo/<id>` streams a published thumbnail from
  `data/photos`; `/photos/available` lists ids. The frontend and Android cache
  photos client-side. There is no user image upload or storage endpoint.
- **Files.** The model (`models/`), catalogue (`data/`), and logs (`logs/`) are
  mounted volumes in Compose. Large assets are in Git LFS; the Docker job pulls
  only the TFLite file.
- **Notifications.** The server sends none. The Android app creates local
  notifications (6-hour status worker and AlarmManager reminders); the web app
  uses in-page queue/status indicators only.
- **Long tasks.** Recognition is synchronous (p95 60 ms). Route planning calls
  OSRM synchronously with a 30 s HTTP timeout; gunicorn allows 120 s per
  request. There is no Celery/RQ worker, no background job table, and no
  streaming. The 6-hour Android worker is client-side.
- **Backups.** Shell scripts, not a service (see Section 6).

### 15. How will the backend be tested and checked for speed?

**Tests.** 79 pytest tests across `test_api.py`, `test_db.py`, and
`test_dataset_manifest.py`:

- JSON mode: 68 passed, 11 skipped (PostgreSQL-only tests).
- PostgreSQL mode: 78 passed, 1 skipped.
- Coverage areas: health and LFS-pointer detection, CORS anchoring, landmarks,
  nearby bounds, prediction validation and a real-model smoke test, route
  validation and rate limiting, report validation and storage, itinerary
  creation/read, admin authorization, schema constraints, and dataset/class
  order consistency.
- `ruff check .` is clean and is part of CI.

**Speed.** The TFLite benchmark (`models/tflite_benchmark.json`, 40 samples)
reports p50 54.4 ms, p95 60.4 ms, max 63.6 ms, with top-1 agreement 1.0 against
Keras. The serving process uses roughly 87 MB RSS with the TFLite runtime
instead of roughly 392 MB with TensorFlow. Gunicorn runs two workers by
default, each with its own model and database pool. **No load test (Locust,
k6, ab) has been run**, so throughput, concurrent-user capacity, and cold-start
time under load are not claimed. The health endpoint exposes database latency
for a live check.

---

# 3. Database Part

PostgreSQL 16 is the deployment source of truth. The catalogue is also
committed as JSON (`data/landmarks.json`, `data/photo_attribution.json`); when
`DATABASE_URL` is unset or the database is unreachable at boot, reads use that
fallback and writes return 503. The schema is defined by one Alembic migration,
`migrations/versions/0001_initial.py`.

### 1. What main data objects exist?

| Object | Kind | Purpose |
|---|---|---|
| `landmarks` | table | The 46 catalogue records |
| `photos` | table | Published thumbnails and their credit/licence |
| `model_classes` | table | The 29 classifier classes and their split counts |
| `itineraries` | table | A saved walk (UUID, start, totals, route JSON) |
| `itinerary_items` | table | Ordered stops of a saved walk |
| `reports` | table | Anonymous problem reports |
| `schema_migrations` | table | Alembic version bookkeeping |
| JSON files | fallback | `landmarks.json`, `photo_attribution.json`, `photo_sources.json`, `class_names.json` |

### 2. What fields belong to each data object?

**`landmarks`** — `id`, `name`, `name_ru`, `address`, `year_built`,
`building_type`, `style`, `architect`, `description`, `fun_fact`, `lat`, `lon`,
`coordinate_source`, `angles`, `source_photos`, `sort_order`, `created_at`,
`updated_at`.

**`photos`** — `id`, `landmark_id`, `filename`, `stored_path`, `sha256`,
`mime`, `width`, `height`, `author`, `license`, `license_url`, `source`,
`source_url`, `is_published`, `verified_at`, `created_at`.

**`model_classes`** — `class_name`, `landmark_id`, `class_index`,
`is_validated`, `mapping_note`, `train_images`, `val_images`, `test_images`.

**`itineraries`** — `id`, `start_landmark_id`, `minutes`, `mode`,
`total_minutes`, `total_distance_m`, `route`, `created_at`.

**`itinerary_items`** — `itinerary_id`, `position`, `landmark_id`,
`dwell_minutes`.

**`reports`** — `id`, `landmark_id`, `category`, `message`, `status`,
`created_at`, `resolved_at`.

**`schema_migrations`** — `version_num` (Alembic's version table).

### 3. What type is each field?

| Field(s) | PostgreSQL type | Nullability / default |
|---|---|---|
| `landmarks.id` | `text` | PK, not null |
| `landmarks.name` | `text` | not null |
| `landmarks.name_ru`, `address`, `building_type`, `style`, `architect`, `description`, `fun_fact`, `coordinate_source` | `text` | nullable |
| `landmarks.year_built` | `smallint` | nullable |
| `landmarks.lat`, `lon` | `double precision` | nullable |
| `landmarks.angles` | `text[]` | not null, default `'{}'` |
| `landmarks.source_photos` | `jsonb` | not null, default `'[]'` |
| `landmarks.sort_order` | `integer` | not null, default 0 |
| `landmarks.created_at`, `updated_at` | `timestamptz` | not null, default `now()` |
| `photos.id` | `text` | PK |
| `photos.landmark_id` | `text` | not null, FK → landmarks |
| `photos.stored_path` | `text` | not null |
| `photos.sha256` | `char(64)` | nullable |
| `photos.mime` | `text` | not null, default `image/jpeg` |
| `photos.width`, `height` | `integer` | nullable |
| `photos.is_published` | `boolean` | not null, default true |
| `photos.verified_at`, `created_at` | `timestamptz` | `verified_at` nullable |
| `model_classes.class_name` | `text` | PK |
| `model_classes.class_index` | `smallint` | not null, unique |
| `model_classes.is_validated` | `boolean` | not null, default true |
| `model_classes.train_images`, `val_images`, `test_images` | `smallint` | not null, default 0 |
| `itineraries.id` | `uuid` | PK, default `gen_random_uuid()` |
| `itineraries.start_landmark_id` | `text` | not null, FK → landmarks |
| `itineraries.minutes`, `total_minutes` | `smallint` | nullable |
| `itineraries.total_distance_m` | `integer` | nullable |
| `itineraries.mode` | `text` | not null, default `custom` |
| `itineraries.route` | `jsonb` | not null |
| `itinerary_items.position` | `smallint` | not null, part of PK |
| `itinerary_items.dwell_minutes` | `smallint` | nullable |
| `reports.id` | `uuid` | PK, default `gen_random_uuid()` |
| `reports.category`, `message`, `status` | `text` | not null; status default `open` |
| `reports.created_at`, `resolved_at` | `timestamptz` | `resolved_at` nullable |

### 4. What is the unique key for each data object?

- `landmarks` — primary key `id` (slug such as `pushkin_monument`).
- `photos` — primary key `id`; partial unique index
  `photos_one_published_per_landmark` on `landmark_id WHERE is_published`, so
  one landmark cannot have two published photos.
- `model_classes` — primary key `class_name`; unique index on `class_index`.
- `itineraries` — primary key `id` (UUID).
- `itinerary_items` — composite primary key `(itinerary_id, position)`.
- `reports` — primary key `id` (UUID).
- `schema_migrations` — primary key `version_num`.

### 5. How are data objects connected?

```
landmarks 1 ─── N photos              (FK RESTRICT on delete)
landmarks 1 ─── N model_classes       (FK SET NULL on delete)
landmarks 1 ─── N itineraries         (FK RESTRICT on delete)
itineraries 1 ─ N itinerary_items     (FK CASCADE on delete)
landmarks 1 ─── N itinerary_items     (FK RESTRICT on delete)
landmarks 1 ─── N reports             (FK SET NULL on delete)
```

A landmark is never deleted while a photo, itinerary, or route stop refers to
it. A report survives deletion of its landmark as an unattributed report.
Deleting an itinerary removes its stops. `model_classes.landmark_id` may be
null for a merged class; `kramer_estate` maps to `kramer_mansion` through
`mapping_note`/the alias table.

### 6. What rules must the data follow?

| Rule | Enforcement |
|---|---|
| Published photo needs author, licence, licence URL and source URL | `photos_published_needs_credit` check |
| One published photo per landmark | partial unique index |
| Latitude −90…90, longitude −180…180 | `landmarks_lat_range`, `landmarks_lon_range` |
| Year built 1000…2100 | `landmarks_year_range` |
| Sort order ≥0 | `landmarks_sort_order_non_negative` |
| Photo dimensions >0 when present | `photos_width_positive`, `photos_height_positive` |
| Class index ≥0, split counts ≥0 | `model_classes_*` checks |
| Route minutes 15…480 | `itineraries_minutes_range` |
| Mode is `custom` or `suggested` | `itineraries_mode` |
| Totals are non-negative | `itineraries_total_*` checks |
| Stop position ≥0, dwell 0…120 | `itinerary_items_*` checks |
| Report category in four values | `reports_category` |
| Report message 10…2000 characters | `reports_message_length` |
| Report status in three values | `reports_status` |
| `updated_at` maintained automatically | `landmarks_set_updated_at` trigger |

### 7. What indexes are needed for fast search?

| Index | Columns | Purpose |
|---|---|---|
| `landmarks_lat_lon_idx` | `(lat, lon)` | Coordinate range work / future SQL nearby queries |
| `landmarks_sort_order_idx` | `(sort_order)` | Stable catalogue order |
| `landmarks_name_trgm_idx` | GIN on `name` (`gin_trgm_ops`) | Fuzzy/case-insensitive name search |
| `landmarks_name_ru_trgm_idx` | GIN on `name_ru` | Russian name search |
| `photos_landmark_idx` | `(landmark_id)` | Join a landmark to its photos |
| `photos_one_published_per_landmark` | unique partial | Publishing rule |
| `model_classes_class_index_key` | unique `(class_index)` | Map model output index to a class |
| `model_classes_landmark_idx` | `(landmark_id)` | Class → landmark lookup |
| `itineraries_created_idx` | `(created_at DESC)` | Newest shared walks |
| `itinerary_items_landmark_idx` | `(landmark_id)` | Stops for a landmark |
| `reports_status_created_idx` | `(status, created_at DESC)` | Operator queue |

Honest note: the current API loads the catalogue once into memory and computes
`/nearby` with Haversine in Python, so `landmarks_lat_lon_idx` and the trigram
indexes are not on the hot request path today. They keep the schema ready for
SQL-side search and make `psql` exploration fast.

### 8. What data history or audit is needed?

- `schema_migrations` records which revision is applied.
- `created_at`/`updated_at` on landmarks, `created_at` on photos/itineraries/
  reports, `resolved_at` on reports, and `verified_at` on photos provide basic
  timestamps.
- The catalogue itself is versioned in Git (JSON, seed script, migration), so a
  content change is traceable to a commit.
- Report status changes are **not** historised: only the current `status` and
  `resolved_at` are kept. There is no generic `audit_log` table and no trigger
  that records old/new values.
- Backups provide point-in-time recovery at the dump granularity (daily).

If an audit trail is required later, add an append-only `report_events` table
(or a generic audit table) written by the same transaction as the update.

### 9. How will database changes be made and tracked?

Alembic, configured by `alembic.ini`; `migrations/env.py` reads `DATABASE_URL`
and never stores credentials. The workflow is:

```bash
alembic upgrade head          # apply
alembic current               # show applied revision
alembic downgrade -1          # revert one revision
alembic revision -m "add ..." # create a new revision
```

Migration files are reviewed and committed with the code. The container
entrypoint runs `alembic upgrade head` before seeding and starting gunicorn, so
a fresh volume converges automatically. The initial revision is
`0001_initial.py` (`down_revision = None`). Its `downgrade()` drops the six
domain tables (a destructive operation; see question 11 and Section 6,
question 14).

### 10. How often is backup done?

`scripts/backup.sh` is designed for a daily cron run; the documented example is
03:00. It writes to `/var/backups/pushkinskaya` by default (or a directory
argument) and keeps **7 days**:

- `models_<timestamp>.tar.gz` — model and metadata;
- `data_<timestamp>.tar.gz` — catalogue, attribution, published photos
  (excluding `data/raw` and training images);
- `logs_<timestamp>.tar.gz` — log files;
- `db_<timestamp>.dump` — `pg_dump --format=custom` when `DATABASE_URL` is set.

The backup is not scheduled by Docker Compose and is not copied off the
machine automatically. For the demo, run it manually before the presentation.
Compose does not define a backup service.

### 11. How is data restored after a failure?

```bash
DATABASE_URL=postgresql://... ./scripts/db_restore.sh /path/db_20261103_030000.dump
```

`db_restore.sh` runs `pg_restore --clean --if-exists`, re-applies
`alembic upgrade head`, then verifies the seed counts. Files are restored by
unpacking the matching `models_`/`data_`/`logs_` archives into the project
directory, then `docker compose up -d --build`. Verification is
`GET /` (`data_source: postgres`, 46 landmarks), `python scripts/admin.py stats`
and a spot check of a photo and a report.

At the documented daily cadence the recovery point objective is up to 24 hours
of reports/itineraries; recovery time is minutes on the same laptop. There is
no point-in-time recovery (WAL archiving), no replica, and no off-site copy.

### 12. What personal data is stored, and how is it protected?

By design: **no account, name, email, phone, password, or precise location is
stored in the database.** `/nearby` uses the coordinates only to compute a
response and does not persist them. Reports are anonymous and contain only the
optional landmark id, category, free-text message, status and timestamps.

Residual personal data:

- a report's free text could contain personal data if the user types it; the
  operator should avoid collecting it and can dismiss/delete the row manually;
- web-server/gunicorn access logs can contain IP addresses; those logs rotate
  at 5 MB × 3 and backups are kept 7 days;
- no cookies or tracking scripts are used.

Protection: PostgreSQL listens on `127.0.0.1` only, the password is in `.env`
(gitignored), admin routes need a header token, the container runs as a
non-root user, and database dumps are readable only by the host account that
creates them. There is no encryption at rest beyond the host's disk, no
retention policy beyond backup rotation, and no published privacy notice in the
repository. Those are documented gaps, not claimed features.

### 13. Who can read, add, change, or delete data?

| Actor | Read | Add | Change | Delete |
|---|---|---|---|---|
| Anonymous visitor | Catalogue, photos, own shared itinerary | Report, itinerary | No | No |
| Admin with token | Stats, report queue | No | Report status | No |
| Operator shell | Everything | Seed/migrate | Everything | SQL only |
| App database role | All tables | All tables | All tables | All tables (no API) |

The API exposes no delete endpoint. The app role owns the schema and therefore
has DDL rights; a production hardening step would split migration and runtime
roles and revoke `DELETE` from the runtime role. There is no row-level security
because there are no tenants or accounts.

### 14. How large will the data become over time?

The fixed catalogue is tiny:

| Data | Size estimate |
|---|---|
| 46 landmarks (text + JSON fields) | <0.2 MB |
| 38 photo rows + 29 class rows | <0.1 MB |
| Indexes and PostgreSQL overhead | a few MB |
| One itinerary (route JSON + stops) | roughly 5–20 KB |
| One report | roughly 0.5–1 KB |

At demo scale (hundreds of walks and reports) the database stays well under
100 MB, while the photo files on disk are about 17 MB and the model files about
42 MB. A rough linear projection: 100,000 itineraries ≈ 0.5–2 GB and 100,000
reports ≈ 50–100 MB plus indexes. The exact current size is available from
`GET /admin/stats` (`database_bytes`) or `scripts/admin.py stats`; it was not
recorded in this document because it changes with test data.

### 15. What test data is needed?

- **Catalogue fixture:** the real seed (46 landmarks, 29 classes, 38 published
  photos) loaded by `scripts/seed_db.py`; `--check` verifies the counts without
  writing.
- **PostgreSQL test database:** `pushkinskaya_test`, migrated and seeded in CI
  and locally. `tests/conftest.py` truncates `reports`, `itinerary_items` and
  `itineraries` between tests and clears the in-memory report limiter.
- **JSON mode:** uses the committed JSON catalogue; no database needed.
- **Model:** most tests use a mock; one smoke test loads the real TFLite file.
- **No production personal data** is copied into tests. Report and itinerary
  fixtures are synthetic.
- **Dataset manifest:** `data/images_v2/manifests/split.json` is checked for
  split/class-order consistency; the images themselves are not in Git.

---

# 4. Mobile App Part

The mobile client is a native Android application in `android/`, written in
Kotlin with Jetpack Compose. It is not a WebView wrapper.

### 1. Which mobile platforms are needed?

Android only. Package `app.pushkinskaya.android`, `minSdk 28` (Android 9),
`targetSdk`/`compileSdk 35`, version `0.1.0` (`versionCode 1`). There is no iOS
build, no Flutter/React Native layer, and no tablet-specific product. The web
PWA covers other platforms.

### 2. Which devices and screen sizes must be supported?

Android phones from API 28 upward, in portrait and landscape. Compose uses
`fillMaxSize`, `LazyColumn`, and a bottom navigation bar, so it adapts to
typical 360–430 dp phone widths and to font scaling. The demo device is a
physical `INKOSI_PRO` (`A152509001692`). Tablets are not a tested target; there
is no two-pane layout. Small-screen/landscape polish and a formal device matrix
are not claimed.

### 3. What screens are needed?

| Screen | Content |
|---|---|
| **Explore** | Search field, offline banner, landmark list with photo, type/year, status badge, add/remove route |
| **Detail** | Photo with credit, name (EN/RU), address, year, description, fun fact, architect/style, "Listen" (TTS), add/remove route, "Report a problem" dialog |
| **Identify** | "Take photo" (system camera), "Choose from gallery", preview, "Identifying…", result name/confidence, top-5, "Open details" |
| **Routes** | Visit list, reorder/remove, optimise switch, "Plan route", totals, stops, reminder buttons (15 min / 1 h / 3 h) |
| **More** | Language EN/RU, "Refresh data", notification settings shortcut, photo-credit note |

The report dialog has four categories, a 10–2000 character message, send/
cancel, and sent/failed states. Notifications open the matching detail screen
via deep links.

### 4. How does the user move between screens?

A Compose `NavHost` inside a `Scaffold`. The bottom `NavigationBar` has four
destinations — Explore, Identify, Routes, More — and uses
`popUpTo(startDestination)` with `saveState`/`restoreState` so tab switches
keep their state. Detail is pushed as `detail/{id}` and popped with Back.
Deep links are `pushkinskaya://landmark/{id}` (notification → detail) and
`pushkinskaya://routes` (reminder → route tab). The start destination is
Explore.

### 5. What works without internet?

- **Explore and Detail** render from the Room cache after the first successful
  refresh; an offline banner shows the error and a "refresh" action.
- **Visit list** and language choice are local and fully usable.
- Previously loaded photos are served from Coil's disk/memory cache.
- **Identify, route planning, shared itineraries, and reports need the
  network.** Unlike the PWA, the Android app does not queue offline writes.
- Notification history is local; the 6-hour status check simply retries later.

### 6. How is data synced when internet returns?

`LandmarkRepository.refresh()` calls `GET /landmarks`, maps the DTOs to Room
entities and `upsert`s them. The server is authoritative, so a refreshed list
overwrites cached rows; there is no merge conflict because clients never edit
catalogue data. Before the upsert it records the old statuses of landmarks on
the visit list; after the upsert it returns the ones whose status changed, and
the worker posts a notification. Explore refreshes on first load and on the
More → "Refresh data" button; the periodic worker runs every 6 hours with a
connected-network constraint. Deletions are not propagated because the
catalogue has no delete flow.

### 7. What notifications are sent?

Two local channels, no server push and no FCM:

- **Place status** — after a 6-hour WorkManager check, if a landmark on the
  visit list changed status, one notification per change; tapping opens its
  detail.
- **Reminders** — "Remind me to start" at 15 minutes, 1 hour, or 3 hours,
  scheduled with `AlarmManager` (`setExactAndAllowWhileIdle` when exact alarms
  are allowed, otherwise inexact); tapping opens the Routes tab.

Android 13+ asks for `POST_NOTIFICATIONS`; if denied, the app explains
"Allow notifications to get reminders." Android 12+ exact alarms need the
special permission; without it the alarm still fires, just not to the minute.

### 8. What device permissions are needed?

| Permission | Why |
|---|---|
| `INTERNET` | API calls and photo loading |
| `ACCESS_NETWORK_STATE` | WorkManager network constraint / offline detection |
| `POST_NOTIFICATIONS` | Status and reminder notifications (runtime, API 33+) |
| `SCHEDULE_EXACT_ALARM` | Exact route reminders (special access, API 31+) |

Camera and gallery use the system `TakePicture` and `PickVisualMedia`
contracts, so the app does **not** request `CAMERA` or storage/media
permissions. Debug builds allow cleartext traffic for `127.0.0.1`; release
builds set `usesCleartextTraffic=false`.

### 9. What device features are used?

Camera capture, photo picker, `ImageDecoder` (resize/rotate to a 1024 px JPEG),
Room/SQLite, DataStore Preferences, WorkManager, AlarmManager, notifications
and notification channels, deep links, Coil image loading, and Android
TextToSpeech ("Listen"). There is no GPS/location use in the Android app (Near
Me exists only on the web), and no Bluetooth, NFC, contacts, or background
location.

### 10. How do login and user verification work?

There is no login in the mobile app and no stored credential. It calls the same
anonymous API as the web client. Reports are anonymous; the app never sends a
user id. The debug build talks to `http://127.0.0.1:5000/` through
`adb reverse`; the release build expects an HTTPS base URL (currently the
placeholder `https://your-domain.com/`). Admin functions are not exposed in the
app.

### 11. What data is stored on the phone?

| Store | Contents |
|---|---|
| Room `pushkinskaya.db` | `landmarks` cache and `route_items` (visit list) |
| DataStore Preferences | Language (`en`/`ru`) |
| Coil cache | Downloaded landmark photos |
| Notification state | System-managed channels and posted notifications |
| No storage | No tokens, passwords, report drafts, or uploaded images |

The Room database uses `fallbackToDestructiveMigration()` because both tables
are caches of server data; a schema change refetches instead of shipping a
migration. Photos selected for identification are read, resized in memory, and
sent; they are not copied into app storage.

### 12. How are speed, battery use, and mobile data use kept good?

- Photos are downscaled to a 1024 px long side and JPEG quality 80 before
  upload (typically a few hundred KB instead of several MB).
- OkHttp uses a 15 s connect timeout and a 60 s read timeout; calls are
  coroutine-based and off the main thread.
- Room serves the list instantly and avoids refetching on every screen.
- WorkManager batches the status check every 6 hours with a network
  constraint; there is no polling loop and no background location.
- Coil caches images; the API responses are small (46 landmarks).
- Compose avoids a WebView and its startup cost.

No battery or data profiler run has been recorded, so no percentage savings are
claimed; these are design measures, not measured results.

### 13. How are app updates released?

There is no store release and no auto-update. The GitHub mirror's `android` job
builds `assembleDebug` and uploads the APK plus the unit-test report as
artifacts. The demo installs it over USB:

```bat
adb reverse tcp:5000 tcp:5000
adb install -r app\build\outputs\apk\debug\app-debug.apk
```

A release build increments `versionCode`/`versionName`, replaces the placeholder
`API_BASE_URL` with the real HTTPS host, and is signed with a release key
(not configured in the repository). The GitVerse pipeline does not build
Android because a cold Gradle build does not reliably fit the 30-minute job cap.

### 14. What store rules must be followed?

The app is **not published** on Google Play, so store review rules do not apply
to the demo. If it were published, the relevant rules would be:

- a privacy policy stating that there are no accounts and reports are
  anonymous, plus the data-safety form;
- a clear notification-permission rationale and user control of the two
  channels;
- target API 35 (already set);
- correct photo attribution and licence compliance for every image;
- no misleading recognition claims — show confidence and the top-5, and label
  low confidence as "not sure";
- content policy for the free-text report (moderation/abuse handling);
- a signed AAB, store listing, and content rating.

Sideloading still requires respecting the photo licences: the credit line is
shown in Detail and in More.

### 15. How will the mobile app be tested?

- **Unit tests:** `ApiParsingTest` (5 JUnit tests) checks DTO parsing for a
  landmark, a confident prediction, a low-confidence prediction, a route plan,
  and the `isNotOpen` status helper. Run with
  `./gradlew testDebugUnitTest`.
- **CI:** the GitHub `android` job runs `assembleDebug testDebugUnitTest`,
  uploads the APK and the HTML test report.
- **Manual device checks:** install over `adb reverse`, then verify Explore/
  Detail, camera and gallery identification, the report dialog (validation,
  send, thank-you, retry), route planning, reminders, language switch, offline
  banner, and deep links.
- **Not present:** instrumentation tests, Compose UI tests, and an emulator
  smoke test (the emulator job was removed because it failed on the runner
  without a readable log). On-device verification is currently pending because
  the demo phone is not attached to this workstation (`adb devices` is empty).

---

# 5. General Project Questions

### 1. What problem does the project solve?

Pushkinskaya Street in Rostov-on-Don is a dense historic street, but a visitor
standing in front of a building has no quick way to know what it is, when it
was built, why it matters, or what is worth seeing next. Generic map apps show
a pin, not a verified story; search results are scattered and often in the
wrong language. The project solves three concrete problems:

1. **Identification** — a photo of a facade returns the landmark and its story.
2. **Curation** — 46 landmarks with checked coordinates, descriptions, fun
   facts, and legally credited photos in one place.
3. **Visit planning** — nearby discovery and a walking route that fits the
   available time, shareable with a companion.

It also has to work at zero hosting cost and on a weak mobile connection,
because the demo cannot depend on a paid cloud service.

### 2. What is inside and outside the project scope?

**Inside**

- 46 landmark records for Pushkinskaya Street, with EN/RU names and coordinates.
- A 29-class image classifier trained on free-licensed photos, served as TFLite.
- A responsive web PWA and a native Android client.
- Catalogue browsing, nearby search, custom and time-based route planning.
- Photo credits and a licence-verification pipeline.
- Anonymous problem reports and shareable itineraries.
- PostgreSQL schema, migrations, seed, admin CLI, backups.
- Automated tests, CI on GitVerse and GitHub, and deployment documentation.

**Outside**

- iOS, Windows Phone, or a cross-platform store release.
- User accounts, profiles, favourites synced across devices, or payments.
- Public photo uploads, comments, ratings, or social features.
- Real-time opening hours, ticket sales, or indoor navigation.
- Full Russian localisation of the web interface (landmark names only).
- A production cloud deployment, custom domain, or 24/7 operations.
- Recognition of all 46 landmarks (only 29 classes are validated).
- A content-management UI for the catalogue (the operator edits JSON/SQL and
  reseeds).

### 3. Who are the users?

| User | Need |
|---|---|
| Tourist on the street | "What is this building?" and "What is near me?" |
| Visitor planning at home | Browse the street, build and share a walk |
| Local resident | Look up a facade or report a wrong/closed listing |
| Student/evaluator | See a complete, reproducible engineering project |
| Operator | Triage reports, keep the catalogue and credits correct |
| Developer/maintainer | Run tests, CI, migrations, backups |

### 4. What user roles exist?

- **Anonymous visitor** — all public read, recognition, route and report
  actions.
- **Operator/administrator** — token-protected statistics and report triage;
  shell access for migrations/backups.
- **Metrics scraper** — optional token-protected `/metrics`.
- **Developer/maintainer** — repository, CI and deployment access.

There is no registered "end user" role and no role hierarchy inside the app.

### 5. What are the main user stories or use cases?

1. As a tourist, I photograph a facade and get the landmark name, confidence,
   description and a way to open the full card.
2. As a tourist, I browse all 46 sites and read the verified history and fun
   fact.
3. As a tourist, I press "Use my location" and see what is within 500 m, sorted
   by distance.
4. As a visitor, I add sites to a visit list, choose a start, and get an
   optimised walking route with time totals.
5. As a visitor with one hour, I ask for a suggested route and follow it.
6. As a visitor, I share the walk as a link and my companion opens the same
   route.
7. As a visitor, I report a wrong photo or a closed building anonymously.
8. As an operator, I list open reports, resolve one, and see updated counts.
9. As a user with no signal, I still browse cached landmarks and photos.
10. As an Android user, I identify with the camera and set a reminder to start.

### 6. What must the system do?

| ID | Functional requirement |
|---|---|
| FR1 | Serve the 46-landmark catalogue and individual records |
| FR2 | Identify an uploaded image against 29 classes and return confidence + top 5 |
| FR3 | Refuse to answer below 0.35 confidence and say so |
| FR4 | Return landmarks within a radius, sorted by distance, with a nearest fallback |
| FR5 | Plan a suggested route for 15–480 minutes via OSRM |
| FR6 | Plan a custom route through chosen stops, optionally optimised |
| FR7 | Persist and reopen a shareable itinerary by UUID |
| FR8 | Accept anonymous reports in four categories with 10–2000 characters |
| FR9 | Provide token-protected stats and report triage |
| FR10 | Fall back to JSON reads when PostgreSQL is absent; reject writes with 503 |
| FR11 | Serve a responsive PWA with offline catalogue/photo caching |
| FR12 | Provide an Android client with camera/gallery, routes, reports, reminders |
| FR13 | Show author, licence and source for every published photo |
| FR14 | Expose health and Prometheus metrics for operations |
| FR15 | Keep the model, data and database reproducible through scripts and CI |

### 7. What quality rules must the system meet?

| Quality | Rule / evidence |
|---|---|
| Correctness | 79 tests; PostgreSQL constraints; validation at the API boundary |
| Recognition honesty | Threshold 0.35, top-5 always shown, masked unvalidated classes |
| Performance | p95 inference 60.4 ms; health and reads answer immediately during a DB outage |
| Reliability | JSON read fallback; DB backoff; container healthcheck and restart policy |
| Security | No accounts; admin/metrics header tokens; parameterised SQL; non-root container; loopback binding |
| Privacy | No personal data stored; anonymous reports; no cookies/trackers |
| Maintainability | `ruff` clean; typed modules; one migration; documented scripts |
| Portability | Docker Compose; pinned base image digest; no cloud-specific service |
| Licensing | Publishing constraint requires a full credit; 38 credited photos |
| Accessibility/usability | Semantic buttons, visible labels, keyboard-friendly forms, text + colour errors; dark contrast |
| Cost | $0 runtime |

Targets that are **not** met or not measured are listed in Appendix B (for
example, no Lighthouse score and no load test).

### 8. What limits exist?

| Limit | Value / consequence |
|---|---|
| Cash budget | $0; no paid host, map key, or cloud vision |
| Always-on server | None; demo runs on a laptop with Docker |
| Recognised landmarks | 29 of 46 classes; 17 are browse-only |
| Model accuracy | 60.0% top-1 on the held-out split; 52% coverage at 0.35 |
| Upload size | 10 MB request body |
| Route time | 15–480 minutes |
| Rate limits | ~10 route requests/min across workers; 5 reports/min per worker |
| CI | GitVerse: 30-min job cap, 15-min default runner timeout, 1000 min/month, 500 MB artifacts, 2 GB LFS/month, 100 MB/file over HTTP |
| Android | API 28+, no iOS, no store distribution |
| Team | One developer, part-time; no dedicated QA/DevOps |
| Database | Single instance, daily backup, no replica/PITR |
| Network | OSRM/OSM public services can rate-limit or fail |

### 9. What assumptions are made?

1. The demo phone runs Android 9+ with a camera and can use USB debugging.
2. The demo laptop can run Docker Desktop/WSL2 with at least 4 GB free RAM.
3. `adb reverse` is available, so the phone can reach `127.0.0.1:5000`.
4. The venue network permits localhost/USB traffic; no inbound public port is
   needed.
5. Public OSRM and OpenStreetMap tiles are reachable when route planning or the
   map is used; the rest of the app does not depend on them.
6. Every published photo's author/licence/source was verified when seeded.
7. GitVerse remains available for the primary repository and CI.
8. Users accept that reports are anonymous and that recognition can be wrong;
   the UI communicates both.

### 10. What risks exist?

| Risk | Impact | Mitigation |
|---|---|---|
| Model misidentifies a building (no "unknown" class) | Wrong story shown | 0.35 threshold, top-5, "not sure" wording, easy report |
| OSRM demo server rate-limits or is down | No route planning | 503 with a clear message; browse/identify still work; pre-generated `/route` fallback exists |
| GitVerse runner/platform limits | CI gap | Backend on GitVerse; Android/Docker on GitHub; documented in `docs/gitverse.md` |
| LFS object problems | Fresh clone/image build fails | 40 objects uploaded and verified by fresh clone; curl fallback documented; Docker on GitHub |
| Phone not detected before the demo | Android demo impossible | `adb devices` check, USB cable/driver fallback, APK artifact, emulator not required |
| Single developer / bus factor | Maintenance risk | README, CONTRIBUTING, this spec, scripts, CI |
| Admin token leaked or weak | Report data exposure | Long random token in `.env`, header-only, rotate; admin not exposed publicly |
| No off-site backup | Data loss if laptop fails | Manual copy of dumps before demo; documented gap |
| Photo licence error | Legal/attribution risk | DB constraint, audit script, credit visible, 8 text-only landmarks |
| Venue network blocks external services | Map/route demo fails | Local stack; cached data; offline-capable browse; test before demo |

### 11. What is the project timeline and what are the milestones?

The repository has 52 commits between 19 June 2026 and 9 November 2026. The
phases visible in history are:

| Phase | Dates | Milestone |
|---|---|---|
| 1. Initial guide | 19–20 Jun 2026 | Flask app, catalogue, photos via LFS, dynamic OSRM routes, map fixes |
| 2. Model and clients | Jun–Oct 2026 | Dataset splits, EfficientNetB0 training, TFLite conversion, PWA, Android client |
| 3. Data platform | 3 Nov 2026 | PostgreSQL migration (7 tables), seed, reports, itineraries, backups |
| 4. CI hardening | 6–8 Nov 2026 | Dual-mode tests, GitVerse import, LFS upload, pipeline hardening |
| 5. CI diagnosis | 9 Nov 2026 | LFS 400 workaround, discovery that GitVerse runners have no Docker daemon |
| 6. Delivery | 11 Nov 2026 | Docker moved to GitHub, specification and documentation pass |

The exact dates of the model retrain and Android work are not listed because
they span several commits and the migration date is the only fixed data-platform
milestone. The remaining work is verification, not new features (Appendix B).

### 12. Who is on the team, and what are their duties?

| Role | Person | Duties |
|---|---|---|
| Developer/maintainer | Repository owner (`smothkd` on GitVerse, `smothkd54` on GitHub) | Design, backend, frontend, Android, model, database, CI, docs, demo |
| Academic supervisor | Not named in the repository | Requirements, review, acceptance |
| Operator | Same as developer for the demo | Start the stack, triage reports, backups, phone setup |
| External providers | GitVerse, GitHub, OSM/OSRM, Wikimedia, Docker | Hosting, CI, maps, photo sources, base images |

There is no separate designer, QA engineer, DevOps engineer, or support team.
This is a deliberate single-developer scope and is the main resourcing risk.

### 13. What rules define acceptance of the project?

| Criterion | Status |
|---|---|
| 46 landmarks, 29 classes, 38 published/credited photos seeded | Pass (`seed_db.py --check`) |
| JSON test suite green (68 passed / 11 skipped) | Pass |
| PostgreSQL test suite green (78 passed / 1 skipped) | Pass |
| `ruff check .` clean | Pass |
| Compose stack healthy, `/` reports `data_source: postgres` | Pass |
| Web identify, browse, nearby, route, report, shared itinerary | Pass in browser |
| GitVerse backend CI green | Pass — backend job green in `2038908`, `2046652`, `2046662`; whole run green for `c7aad1e` (`2068018`) |
| GitHub Android + Docker/Trivy jobs green | Pass for `c7aad1e` (android 151 s, docker-build 96 s) |
| Photo credits visible in web and Android | Pass; Android on-device check pending |
| Android report dialog verified on the physical phone | **Pending** (phone not attached) |
| Branch protection on `main` | **Pending** (GitVerse web UI) |
| Documentation matches the implementation | Pass after this document and the README/CI pass |
| $0 runtime cost | Pass |
| All 90 specification questions answered | This document |

Acceptance for the demo is the union of the passing rows; the pending rows are
explicitly not claimed as complete.

### 14. What documents must be created?

| Document | Status |
|---|---|
| `README.md` — overview, setup, API, testing, deployment | Present |
| `CONTRIBUTING.md` — local setup and workflow | Present |
| `docs/gitverse.md` — repository, LFS, CI limits | Present |
| `docs/technical-specification.md` — this document | Present |
| `.env.example` — required settings | Present |
| API reference | In README and Section 2 |
| Database schema/migration | `migrations/versions/0001_initial.py` |
| Backup/restore scripts | `scripts/backup.sh`, `scripts/db_restore.sh` |
| Photo attribution record | `data/photo_attribution.json` |
| `LICENSE` | **Missing** (GitVerse shows an "Add" prompt) |
| `SECURITY.md` | **Missing** |
| `CODE_OF_CONDUCT.md` | **Missing** |
| Privacy notice | **Missing** (no accounts, but a short notice is advisable) |

The missing files are documentation gaps, not code gaps; they are listed in
Appendix B.

### 15. How will GitVerse at https://gitverse.ru/ be used for repository, branches, commits, issues, and reviews?

**Repository.** GitVerse is the primary remote:
`git@gitverse.ru:smothkd/Tourist_Guide.git`, imported with full history
(including the commits before the import). `origin` is GitVerse; `github` is a
push mirror. A fresh clone was verified to resolve all 40 LFS objects (TFLite
8,797,436 B, Keras 33,004,242 B, photo 749,587 B). Authentication is SSH with
the registered key. LFS for `https://gitverse.ru/` forces the pure SSH
transfer because the 33 MB Keras file is rejected by the storage CDN over
HTTPS.

**Branches.** `main` is the protected integration branch. Feature work should
use short-lived branches such as `feat/android-report` or `fix/lfs-pull`, merged
through a merge request. At the time of writing the repository has a single
`main` branch and the developer commits directly; this is the documented
process, not a claim that it is already enforced.

**Commits.** Imperative, scoped messages that explain the why, for example
`Fall back to the LFS batch API when git-lfs gets a 400` or
`Run the Docker smoke test only where a Docker daemon exists`. Each commit
should build and pass tests; generated files are not committed.

**Issues.** Use GitVerse Issues for the backlog and bug reports: one issue per
defect with steps to reproduce, expected/actual, and the affected endpoint or
screen. Labels such as `bug`, `ci`, `docs`, `android` keep triage simple.
Issues are not yet used in the repository (the project predates the GitVerse
import).

**Reviews.** A merge request should have a description, the linked issue, and
a green `CI` run before merge. With one developer, the practical review is
self-review plus CI, with the academic supervisor reviewing milestone changes
when available. Branch protection is intended to require the `CI` workflow and
one approval; it is **not yet enabled** because it needs the authenticated
GitVerse web UI.

**CI/CD.** The `CI` workflow (`.gitverse/workflows/ci.yaml`) runs on push, pull
request and manual dispatch; results are visible under the repository's CI/CD
tab. The Docker image and Android APK are built on the GitHub mirror, where a
Docker daemon and a longer job budget exist. Releases/tags are not yet used;
the current version is identified by commit SHA.

---

# 6. Deployment Questions

### 1. Which environments are needed, such as development, test, and production?

| Environment | Where | Database | Purpose |
|---|---|---|---|
| Development | Developer laptop, `python backend/app.py` | JSON or local PostgreSQL | Fast iteration |
| Test | Local pytest and CI runners | JSON mode + `pushkinskaya_test` | Automated verification |
| Demo ("production-like") | Laptop, Docker Compose | `postgres:16-alpine` in Compose | Supervisor demo |
| CI | GitVerse and GitHub ephemeral runners | PostgreSQL installed by CI / service container | Build and test |
| Public production | Not deployed | — | Out of scope |

There is no separate staging environment. The demo environment is the closest
thing to production and is rebuilt from the same `Dockerfile` and
`docker-compose.yml`.

### 2. Where will the application run: own server, cloud, or university server?

On the developer's own laptop, using Docker Desktop. No cloud runtime and no
university server are used. The reasons are documented in the README: the
Render/Neon free tier was unreachable from Rostov-on-Don (TLS resets), Yandex
Cloud needs an account and payment method, and the requirement is a $0 demo
without an always-on PC. GitVerse hosts the source and backend CI; it is not
the runtime host. The phone reaches the laptop over USB with
`adb reverse tcp:5000 tcp:5000`.

### 3. What hardware, operating system, network ports, and firewall rules are needed?

**Hardware/OS.** A Windows 11 x86-64 laptop with Docker Desktop (WSL2 backend)
is the tested setup. A practical minimum is 4 CPU cores, 8 GB RAM, and about
10 GB free disk (sizing recommendation, not a measured requirement). The
serving process needs roughly 87 MB RSS; the model and photos occupy about
60 MB on disk; Docker images add a few hundred MB.

**Ports**

| Port | Service | Binding | Exposure |
|---|---|---|---|
| 80 | Caddy | `0.0.0.0:80` | Host only; no router forwarding |
| 443 | Caddy | `0.0.0.0:443` | Only if a domain/HTTPS is configured |
| 5000 | Flask/gunicorn | `127.0.0.1:5000` | Loopback; Caddy and `adb reverse` reach it |
| 5432 | PostgreSQL | `127.0.0.1:5432` | Loopback only |

**Firewall rules.** No inbound rule is required for the demo. Windows Firewall
may block port 80 for other LAN devices, which is acceptable because the demo
runs on the same machine. The phone does not use the LAN: USB `adb reverse`
creates a private tunnel. Outbound 443 is needed for OSRM/OSM (map/routes),
GitVerse/GitHub (development), and Docker pulls; outbound 22 is needed for the
GitVerse SSH remote.

### 4. How is the frontend built and served?

There is no build step. `frontend/index.html`, `frontend/manifest.json`,
`frontend/static/` (self-hosted Leaflet and favicon) and the root `sw.js` are
served by Flask:

- `/app` and `/app/` → `index.html`;
- `/app/<path>` → static assets;
- `/sw.js`, `/favicon.ico` → root service worker and icon.

In Compose, Caddy reverse-proxies to `web:5000`, applies gzip, caches
`/app/static/*` for 24 h, caches the app shell for 1 h, and marks API responses
`no-cache`. The PWA is installable from the browser; the service worker caches
the shell, landmarks and photos. No Node.js, bundler, or CDN is involved.

### 5. How is the backend built and started?

The `Dockerfile` uses a digest-pinned `python:3.11-slim`, installs
`requirements-serve.txt` (no TensorFlow), copies the project, installs the
package, removes build tools, creates a non-root `appuser`, and exposes 5000.
The entrypoint is idempotent:

```
alembic upgrade head            (only when DATABASE_URL is set)
python scripts/seed_db.py --if-empty
python preflight_check.py
gunicorn -w 2 --timeout 120 -b 0.0.0.0:5000 backend.app:app
```

Build and start:

```bash
docker compose up -d --build
docker compose ps
curl http://127.0.0.1:5000/
```

The healthcheck runs every 30 s with a 90 s start period; `restart:
unless-stopped` brings the service back after a crash. `GUNICORN_WORKERS`
defaults to 2.

### 6. How is the database installed and connected?

Compose starts `postgres:16-alpine` with a named volume `db_data`, a
`pg_isready` healthcheck every 5 s (12 retries), and a loopback port mapping
`127.0.0.1:5432:5432`. The web service `depends_on` the database being healthy.
Inside the compose network the connection string is

```
postgresql://<POSTGRES_USER>:<POSTGRES_PASSWORD>@db:5432/<POSTGRES_DB>
```

and Compose sets it explicitly, overriding any host-side `DATABASE_URL` in
`.env`. On the host, Alembic/seed/tests use
`postgresql://...@127.0.0.1:5432/pushkinskaya`. `POSTGRES_PASSWORD` is required;
Compose refuses to start without it.

### 7. How are database changes applied?

Automatically on container start (`alembic upgrade head`) and manually with the
same command from the host. Migrations are versioned files in
`migrations/versions/`; `alembic current` shows the applied revision;
`alembic downgrade -1` reverts one revision. The seed is idempotent
(`scripts/seed_db.py`, `--if-empty` on boot, `--check` to verify). A schema
change therefore ships as: migration file + seed adjustment (if needed) + code
+ tests, reviewed together.

### 8. How are settings and secrets stored?

In `.env` (gitignored), with `.env.example` as the template. Compose uses
`${VAR:?message}` for required values, so an empty `POSTGRES_PASSWORD`,
`ADMIN_TOKEN` or `METRICS_TOKEN` stops the stack instead of starting an
insecure one.

| Variable | Purpose |
|---|---|
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Database |
| `DATABASE_URL` | Host-side connection for Alembic/seed/tests; Compose overrides it inside the container |
| `ADMIN_TOKEN` | `X-Admin-Token` for `/admin/*` |
| `METRICS_TOKEN` | `X-Metrics-Token` for `/metrics` |
| `GUNICORN_WORKERS` | Worker count (default 2) |
| `MODEL_PATH`, `LOG_DIR` | Container paths |
| `CORS_ORIGINS` | Extra allowed origins (pipe-delimited) |
| `DB_POOL_MIN`, `DB_POOL_MAX`, `DB_POOL_RETRY_SECONDS` | Pool and backoff tuning |

Secrets are never committed. Tokens are sent in headers, not URLs, so they do
not appear in access logs. `.gitconfig-gitverse` (commit identity, LFS setting)
is machine-local and gitignored. Rotation means generating a new value, updating
`.env`, and restarting the stack; there is no secret manager.

### 9. What web server, domain name, and SSL certificate are used?

Caddy 2 is the reverse proxy. The local `Caddyfile` listens on `:80` (plain
HTTP) and proxies to `web:5000`; it adds gzip and cache headers. It also
contains a commented production block:

```
your-domain.com {
    encode gzip
    reverse_proxy web:5000
    ...
}
```

Uncommenting it and pointing a DNS A record at the host makes Caddy obtain and
renew a Let's Encrypt certificate automatically. **No domain name and no
certificate are configured for the current demo**, so the demo URL is
`http://127.0.0.1:5000/` (or `http://localhost/` through Caddy). The Android
release build's HTTPS base URL is a placeholder until such a deployment exists.

### 10. How is automatic build and release done?

| Pipeline | Trigger | Jobs |
|---|---|---|
| GitVerse `.gitverse/workflows/ci.yaml` | push/PR to `main`, manual | `ruff`, JSON tests, install PostgreSQL, migrate/seed, PostgreSQL tests |
| GitHub `.github/workflows/ci.yml` | push/PR to `main` | Android `assembleDebug testDebugUnitTest` + APK/test artifacts; Docker build + smoke + Trivy (CRITICAL/HIGH, fixable) |
| GitHub `photo-audit.yml` | schedule/manual | Re-fetch author/licence from Wikimedia |

There is **no automated deployment**: a release is a manual
`git pull` + `docker compose up -d --build` on the demo laptop. There is no
container registry push, no image tag beyond `latest`, and no app-store
release. The Android APK is downloaded from the GitHub Actions artifact and
sideloaded.

The GitVerse Docker job was removed after run `2046662`/job `4030942` proved
that its cloud runner has no Docker socket:

```
ERROR: failed to connect to the docker API at unix:///var/run/docker.sock
```

The model download itself succeeded there (curl fallback: HTTP 200,
8,797,436 bytes), so the limitation is the daemon, not LFS. The GitHub mirror
runs the same image checks. The duplicate GitHub backend job was removed after
the GitVerse backend job went green, so each platform now runs the checks it can
actually support.

### 11. How are monitoring and health checks done?

- **Health endpoint** `GET /`: `200` with
  `{status, model_loaded, classes, landmarks, data_source, database}` when the
  model and catalogue are loaded; `503` when the model is missing or is an LFS
  pointer, or the catalogue is empty. A database outage does **not** fail the
  endpoint while JSON reads work; it appears in `database` and
  `database_error`.
- **Container healthcheck:** `curl -f http://localhost:5000/` every 30 s,
  timeout 5 s, start period 90 s, 3 retries.
- **Restart policy:** `unless-stopped` for db, web and Caddy.
- **Metrics:** `GET /metrics` exposes request counts by endpoint/status, a
  prediction-confidence histogram, OSRM success/failure, and uptime. With
  `METRICS_TOKEN` set, the scrape must send `X-Metrics-Token`.
- **Manual checks:** `docker compose ps`, `docker compose logs`,
  `python scripts/admin.py stats`, and a browser smoke test.

There is no external uptime monitor, no alerting, and no Grafana/Prometheus
server in the demo. The metrics endpoint is ready for one.

### 12. Where are logs collected, and how long are they kept?

| Log | Destination | Retention |
|---|---|---|
| Application | `logs/app.log` (and other logger names), stderr | Rotating: 5 MB × 3 backups per logger |
| Gunicorn/container stdout | Docker `json-file` log | Docker default (no max-size configured) |
| Caddy | Container stdout | Docker default |
| Backups | `logs_<timestamp>.tar.gz` | 7 days |

View with `docker compose logs -f web`, `docker compose logs caddy`, or the
files in `logs/`. Logs contain startup state, report ids, and errors; they do
not contain image bytes, tokens, or report text. Access logs may contain IP
addresses. There is no central log server and no long-term archive; the 7-day
backup is the only retention beyond the container's own files. Configuring
Docker log rotation (`max-size`, `max-file`) is a recommended hardening step.

### 13. How are backups and recovery done?

`scripts/backup.sh` (daily cron at 03:00 in the documentation) archives
`models/`, `data/` (excluding raw/training images) and `logs/`, and runs
`pg_dump --format=custom` when `DATABASE_URL` is set. It keeps 7 days and
prints the retained count.

Recovery:

1. Restore the database:
   `DATABASE_URL=... ./scripts/db_restore.sh <dump>` — this runs
   `pg_restore --clean --if-exists`, `alembic upgrade head`, and a seed-count
   check.
2. Unpack the matching `models_`/`data_` archives into the project.
3. `docker compose up -d --build`.
4. Verify `GET /` (46 landmarks, `data_source: postgres`), a photo, and an
   admin stat.

RPO is up to 24 hours; RTO is minutes on the same laptop. Backups are local by
default; copying them off the machine is manual and is the main recovery gap.

### 14. How is rollback to a previous version done?

Application rollback:

```bash
git log --oneline
git checkout <previous-commit>
docker compose up -d --build
```

Because images are rebuilt rather than pulled from a registry, the rollback
uses the source at the previous commit. Database rollback is separate:

- `alembic downgrade -1` works only if the revision's `downgrade()` is safe.
  The initial migration's downgrade **drops all domain tables**, so it is
  destructive and must not be used to "undo" a data change.
- For data loss or a bad migration, restore the last `pg_dump` with
  `db_restore.sh`.
- There is no blue/green deployment, no image tag history, and no automatic
  rollback; the operator verifies `/` and the main flows after switching.

### 15. How are scaling, access control, and cost managed?

**Scaling.** One host, one web container, two gunicorn workers, one database.
Vertical scaling means more workers/CPU/RAM. Horizontal scaling is limited by
design: the catalogue is loaded per process, the rate limiter and metrics are
in-memory per worker, and there is no shared session store. A scale-out design
would need a shared rate-limit store (Redis), a stateless metrics pipeline, an
object store/CDN for photos, and a managed PostgreSQL. The current traffic
(demo) does not need it.

**Access control.** Web and database ports bind to loopback; Caddy is the only
public listener; `/admin/*` and `/metrics` require header tokens; the container
runs as `appuser`; the database password is in `.env`; there are no user
accounts to manage. Public exposure would add a firewall, HTTPS, token
rotation, and possibly a reverse-proxy IP allowlist.

**Cost.** $0: no cloud runtime, no paid map/vision API, free public GitVerse and
GitHub tiers, public OSRM/OSM, and a laptop that is already owned. The trade-off
is availability: the demo is not online when the laptop is off, and public OSRM
has no SLA. GitVerse's free CI quotas (1000 min/month, 2 GB LFS/month) are
monitored by keeping the pipeline to two jobs and no matrix.

---

# Appendix A — Measurement register

| Metric | Value | How it was obtained |
|---|---|---|
| Catalogue size | 46 landmarks | `seed_db.py --check` |
| Model classes | 29 | `models/class_names.json`, seed |
| Published photos | 38 | seed/`/admin/stats` |
| Text-only landmarks | 8 | 46 − 38 |
| Test accuracy | 60.0% (39/65) | Held-out test split, `evaluate.py` |
| Precision at 0.35 / 0.40 | 82% / 94% | Held-out split |
| Coverage at 0.35 | 52% | Held-out split |
| TFLite size | 8.39 MB (8,797,436 B) | `models/tflite_benchmark.json` |
| Inference p50 / p95 / max | 54.4 / 60.4 / 63.6 ms | 40 runs, `tflite_benchmark.json` |
| Keras top-1 agreement | 1.0 | Parity check in the same report |
| Serving RSS | ~87 MB | TFLite runtime measurement vs ~392 MB TensorFlow (README) |
| Tests | 79 total; 68+11 JSON, 78+1 PostgreSQL | `pytest` |
| Lint | clean | `ruff check .` |
| GitVerse backend job | 2m13s / 2m29s / 2m24s, success in runs `2038908`, `2046652`, `2046662`; full run green for `c7aad1e` (`2068018`, 2m56s) |
| GitHub CI | Android 151 s, Docker 96 s, success | Run `42966202544` (`c7aad1e`) |
| Database tables | 7 + `schema_migrations` | Migration |
| Rate limits | ~10 route/min across 2 workers; 5 reports/min/worker | `backend/app.py` |
| Upload cap | 10 MB | `MAX_CONTENT_LENGTH` |
| LFS objects | 40 files; TFLite 8,797,436 B; Keras 33,004,242 B | Fresh-clone verification |

# Appendix B — Known gaps and unmeasured items

These are stated so the document cannot be read as claiming more than was
verified:

1. **No Lighthouse/WebPageTest score** and no frontend load test.
2. **No backend load test** (throughput/concurrency/cold-start under load).
3. **Android on-device verification is pending**: `adb devices` is empty, so
   the camera, report dialog, reminders, and deep links were not re-checked on
   the physical `INKOSI_PRO` in this session.
4. **GitVerse branch protection is not enabled** (needs the authenticated web
   UI). The policy is documented, not enforced.
5. **GitVerse cloud runners have no Docker daemon**; the Docker smoke test runs
   on GitHub. The GitVerse Docker job was removed rather than left red.
6. **No `LICENSE`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, or privacy notice** in
   the repository.
7. **No off-site backup, WAL/PITR, replica, or image registry tags.**
8. **The web UI is not fully Russian**; only landmark names switch language.
9. **No Google Play release**; the APK is sideloaded, so store rules are not
   exercised.
10. **Recognition is partial**: 29 of 46 landmarks, 60.0% top-1, 52% coverage at
    0.35, and no "not a landmark" class.
11. **No server push notifications**; Android uses local 6-hour polling and
    alarms, so status alerts can be hours late.
12. **No Compose UI/instrumentation tests**; Android unit tests cover parsing
    only.
13. **No central log aggregation or alerting**; retention is the local rotation
    plus 7-day backups.

One earlier inconsistency is now closed: the README route limit said "30
requests/minute", while the code enforces about 10/minute across the default
two workers. README, `docs/gitverse.md` and this document now state the code's
value.

# Appendix C — Demo runbook

1. `cd Tourist_project`
2. Confirm `.env` has `POSTGRES_PASSWORD`, `ADMIN_TOKEN`, `METRICS_TOKEN`,
   `DATABASE_URL`.
3. `docker compose up -d --build`
4. `docker compose ps` → db healthy, web up, caddy up.
5. `curl http://127.0.0.1:5000/` → `status: ok`, `data_source: postgres`,
   `landmarks: 46`.
6. Open `http://127.0.0.1:5000/app`.
7. Web scenarios: identify a sample photo; browse and open a card (show the
   credit); Near Me with manual coordinates if geolocation is denied; build a
   two-stop walk, save/share, reopen the link; submit a report; show
   `/admin/stats` with the token.
8. Phone: `adb devices`; `adb reverse tcp:5000 tcp:5000`;
   `adb install -r android\app\build\outputs\apk\debug\app-debug.apk`.
9. Android scenarios: Explore, camera/gallery identify, Detail credit, report
   dialog (short message → error; valid → thank-you), route plan, reminder.
10. Before closing: `python scripts/admin.py stats`, `./scripts/backup.sh` (if
    bash is available), and `docker compose down` (keep the volume).

# Appendix D — Glossary

| Term | Meaning |
|---|---|
| Landmark | One of the 46 catalogue records |
| Class | One of the 29 labels the model can output |
| Validated class | A class with enough held-out photos to be served |
| LFS | Git Large File Storage, used for the model and photos |
| PWA | Progressive Web App (installable, service-worker cached) |
| OSRM | Open Source Routing Machine; public walking-route service |
| Itinerary | A saved walk with a UUID and shareable link |
| RPO/RTO | Recovery point/time objective |
| TFLite | TensorFlow Lite runtime and model format |
| Top-5 | The five highest class probabilities returned with a prediction |

---

*End of specification. The code baseline is `c7aad1e`; when the code changes,
update this document and the README in the same commit.*


