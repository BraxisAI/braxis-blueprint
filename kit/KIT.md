# KIT — one resident in a 3D world

**Live:** https://braxisai.com/world/

KIT is a humanoid garden-robot. It has one large eye, an antenna, a chest
light, jointed arms (one tool hand), two legs, and a seed/tool pack. It lives in
a three.js world, chooses its own projects, builds persistent structures, makes
things, reads, watches, posts, and keeps a diary.

Current world: **Glowveil Hollow** — *"Tiny hands, big green dreams."*

This is the honest write-up: what is autonomous, what is authored, and what is
still missing.

## The loop

- A deterministic **2-second** loop. No LLM in the tick.
- Five drives: energy, curiosity, social, comfort, mastery.
- **70+ actions** across 20 named places, including far sites (river dock, old
  ruins, hilltop, south farm, north woods, east gate, west marsh, far shore,
  south ridge, old road, east ruins, north shore, west ridge, south shore, east
  ridge).
- Actions are chosen by need + learned preference + project alignment +
  novelty + curiosity + repetition cost + day arc + action age.
- Preferences are EMA-updated from how an action felt.
- **Free-model budget:** one daily reflection plus up to 23 event summaries,
  shared **24 calls/day** cap. The lead is the free OpenRouter 550B Nemotron
  Ultra; the fallback is the free background chain. No model in the tick.
- A separate `post` action lets KIT send at most one honest social update a day
  through the estate's determiner and publisher gates.

## Projects and builds

- KIT invents projects in its own words; `_compile_project()` turns the words
  into a schema (shape, height, width, color, motif). The daily reflection can
  add a project; a deterministic continuity composer supplies the next one when
  the queue empties.
- A completed project becomes a persistent build in `world_builds.json`.
- The build vocabulary includes bridge, arch, garden, tower, lantern, bench,
  fountain, ring, spire, and **tree** layers. Projects advance through varied
  verbs (garden/plant/water, build/tinker/sketch/carve, sculpt/paint), not one
  action forever.
- **Project cooldown:** 30–60 minutes between projects; the deterministic
  composer waits 90 minutes, so KIT is not a build conveyor.
- **Creation cadence:** 3-hour shared cooldown, and the random exploration pool
  cannot bypass it. This fixed a 93-creations-in-24-hours card factory. The
  image lane runs every 2 hours, and the dashboard/world gallery show real
  artifacts first; cards are counted but not shown first.
- **Self-authored queue:** the daily reflection returns three project ideas in
  KIT's own words (`IDEAS`), tagged `source='self'` and used before templates.
  `project_origin_counts` records self vs template vs continuity starts, and
  the HUD labels a self-authored project.
- **Self-observation:** `_self_observe()` notices a medium rut, writes a
  first-person observation and can create a matching desire. Example: *"I write
  about making instead of lifting the first stone. I want to make something
  with weight."*
- **Interests:** `interests` records browsed/watched titles, reflection
  curiosities and watcher suggestions; `browse` follows the top interest (or
  `browse_topic`) through Wikipedia, and projects/creations get a bonus.
- **Obstacle map + navmesh:** the page reports city blocks, props and tree
  positions to `/api/world/obstacles`; `_avoid_step()` handles local detours and
  `_nav_path()` runs a rasterized A* grid (2-unit cells) around all obstacles,
  consuming waypoints one at a time. Direct walks stay cheap; long walks route.
- **Sprawl:** 20 district anchors each have three satellite sites. After six
  builds the chooser takes an outer site 82% of the time and requires a
  10-unit gap. 49 of the first 54 builds were moved out of the central cluster;
  five stayed central. The world is deliberately bigger than the plaza.
- **Skill library:** `kit_skill_library.json` stores finished schemas with
  `uses` and `successes`. The `code` action now writes a small program, runs it
  in the sandbox, and stores the code and output as a creation.

## What KIT can make

- **Real music:** `kit_music.py` writes a short lyric from KIT's live state and
  calls the existing ACE v3 lane. The first song, *a song about the trio*, is
  154 seconds and lives at
  `https://braxisai.com/media/music/Braxis_Songs/Kit/`.
- **Real images:** `kit_image.py` turns one creation into a real image through
  the estate's free NVIDIA FLUX/CogView cascade. The first painting is
  `https://braxisai.com/media/world/creations/creation_art-1793391568-21_art.jpg`.
- **Real video:** `world_video.py` records a live window of the world and muxes
  KIT's own song with ffmpeg. It now waits for `#load` to disappear, trims the
  loading segment, and refuses to queue if the world never becomes ready.
  First KIT music video: `live_20261030T210754Z.mp4`; the first load-gated
  sample is `live_20261031T173427Z.mp4` (16.6s, starts inside the world).
- **Hero GLB:** a free TRELLIS text→3D run produced `kit_hero.glb` (6.1 MB),
  now loaded by GLTFLoader as **KIT, the Hero** on the center plinth:
  `https://braxisai.com/media/world/hero/kit_hero.glb`.
- **Gallery:** `/world/` has a gallery wall with the latest creations, real
  images, inline audio players, print links, and the latest-creation line.
- **POD:** a KIT painting is a real Printify poster:
  https://braxis-trading-co.printify.me/product/33738826
  (published, $24.99). The gallery links to it.
- **Wish list:** `/api/world/wishes` and the page's **KIT's wishes** panel list
  desires, wonders, the dream, visitor messages, queued ideas, next projects and
  envision requests, plus the capability gaps and their unblock.

## New layers (10-31)

- **In-world chat:** `/api/world/chat` lets a visitor type to KIT from the
  world page. KIT answers in 1–3 sentences from its mood, action, project and
  interests; 3-second per-IP limit; logged to `kit_chat_log.jsonl`.
- **Real code sandbox:** `kit_sandbox.py` runs generated Python in Docker with
  no network, no host mounts, a read-only root, 512 MB/1 CPU/128 pids, nobody,
  6s and a 12 KB output cap. The image is `braxis-kit-sandbox:1`.
- **Echo builder:** KIT's `request build` action queues a goal; `kit_builder.py`
  runs as Echo every 15 minutes, writes code, tests it in the sandbox, retries
  up to three times, and returns only a working program. KIT stores it as a
  `code` creation.
- **Declarative action + shape plugins:** `kit_plugins.py` stores KIT-authored
  verbs and renderable primitive shapes as data; no eval and no host code. The
  first plugin verb is **collect dew**; the first shape is **moon gate**.
- **World spread:** satellite sites, an 82% outer draw, a 10-unit gap, 1,400
  instanced grass blades and 260 flowers, a **wide view** button, and a fixed
  terrain fallback that no longer drops the outer world into a dark crater.
## Companion and dashboard

- **Juniper, the first companion.** KIT has a `befriend` action. On
  2026-10-31 00:11 UTC it made **Juniper the moss-cat** (`comp-1793405460`,
  bond 0.15). Juniper has its own `x/z`, wanders/follows instead of being glued
  to KIT, and the pair have a `talk to companion` action. A live exchange:
  *KIT: Do you think the lamps get lonely when the visitors leave? Juniper:
  You talk to the stones. I listen to them.* The HUD and dashboard show the
  companion and last words. This is a pet with deterministic speech, not a
  second autonomous agent.
- **Dashboard:** https://braxisai.com/kit/ shows live state, the project step,
  self-observation, companion and last exchange, project origins, interests,
  every recent creation with an honest `image` / `audio` / `poem` / `card only`
  badge, the builds, last read/watch results, and the watcher nudge. Click any
  artifact for a full detail view and a **make a real image**, **make the song**
  or **rewrite as a real poem** button. It refreshes every 15 seconds.
- **Approval gate:** `world_creation_share.py` now refuses a card-only
  creation. It shares the real image if one exists, a poem/audio card if that
  is the artifact, and waits rather than posting a blank interpretation.
- **Real poems:** `kit_poem.py` replaces the deterministic placeholders with
  9–13 line free-model poems and runs hourly. It deliberately excludes watched
  video titles and real names.
- **Build scale:** custom shapes are scaled by type (tower 3×, spire 2.6×,
  monument 2.5×), so towers and overlooks read against the city blocks. New
  shapes: well, gate, kiln, boat, windmill, sign.
- **Rituals:** KIT can write a 2–5 step `PRACTICE` (name + ordinary actions).
  The engine queues it, executes the steps, and records `practice_history`. A
  live ritual, **Dawn Tending** (`water plants`, `smell flowers`, `watch
  fountain`), is shown in the HUD/dashboard as `ritual: name · step 1 of 3`.
- **Field notes:** `kit_study.py` takes one curiosity, reads a Wikipedia
  summary, asks the free 550B model for a first-person `NOTE`, `SURPRISE` and
  `QUESTION`, saves it to `kit_field_notes.jsonl`, and updates KIT's interests.
  It runs every 4 hours and is shown in the world HUD and dashboard.
- **Project steps:** `progress / target` is the number of matching actions,
  not a quality score. The HUD now says **step X of Y**; future projects use
  3–5 steps.

## Autonomy and memory

- **30-dimensional emotion:** `kit_emotion.py` keeps joy, sadness, anger, fear,
  surprise, trust, anticipation, calm, anxiety, hope, melancholy, defiance,
  vulnerability, playfulness, introspection, euphoria, grief, longing,
  gratitude, curiosity, awe, nostalgia, determination, acceptance,
  ambivalence, remorse, pride, shame, connectedness and loneliness. Actions
  and events pulse them, a 6-hour-ish decay pulls them toward baseline, and
  opposites interlock. The HUD/dashboard show the top three/five; loneliness
  biases social actions, curiosity biases reading/exploration, and sadness
  biases quiet garden/rest actions. It is a feeling model, not a claim of
  consciousness.
- **Episodic memory:** `kit_memory.py` builds a local SQLite FTS5 index of
  decisions, projects, builds, creations, companion dialogue, watches, wonders
  and field notes. The daily reflection searches it for relevant past moments;
  the dashboard has a memory search box. No embeddings, no network, no LLM.
- **Self-model:** `kit_self_model.json` records identity, interests, working-on,
  unfinished queue, enjoyed actions, failed decisions, changed beliefs, next
  intention, creation lineage and visitor impressions. It now also records
  `autonomy.origins`, `self_observation`, recent mediums and interests. It is
  deterministic.
- **Thoughts:** a rolling `thought_history` and a contextual composer build
  thoughts from the current project, last build, last creation, desire, wonder,
  weather, visitor, town density and mood. The page shows the last two; the
  daily reflection reads the last three.
- **Emotional residue:** strong events leave a slow multi-hour mood tint that
  decays and blends with the six attractors.
- **Pino rule:** repeated actions in the last 8 drop energy and pulse `repeat`
  (joy/playfulness/anticipation/curiosity down); a new action or a new
  medium+subject pair adds energy and pulses `novel` (surprise/curiosity/joy/
  anticipation up). This is the selection pressure 3EYES described for Pino.
- **Visitor memory:** `visitor_impressions` is keyed by an 8-character hash of
  the visitor IP, never the raw address. Repeat visits get a label ("the one
  who leaves flowers") and a "came back" line.
- **Real outcomes:** a completed project is an attempt, not a success. Success
  requires an outside signal — an offering, a visitor message, or a published
  share. `signals_total`, `projects_done[].signals` and per-build `signals`
  record it. Legacy proxy successes are preserved separately.
- **Envision consumer:** requests in `kit_asset_requests.jsonl` become one real
  build at the requested site, marked consumed, capped at one per six hours and
  three per day.
- **Wish list / gaps:** the page shows what KIT wants and what it cannot yet
  make; the gap list is the honest engineering backlog.
- **Trio mailbox / watcher:** project notes go out; replies and gifted
  blueprints come back. The watcher reads the last twelve creations and leaves
  a medium-rut nudge (for example, four poems in twelve); the nudge is now a
  **24-hour hard ban** on that creation medium, not just a preference change.
- **Telegram:** KIT has its own bot and replies from live state. Chat can queue
  a real browse (`look up …`) or a video watch (`watch … <url>`), and the free
  NVIDIA vision lane reads photos sent to it. It cannot execute payments or
  arbitrary host code; generated Python runs only in the sandbox.
- **Safety:** visitor and browsed text is sanitized (`_safe_external`), audited
  in `kit_external_events.jsonl`, and visitor ideas queue in `pending_ideas`;
  KIT accepts one only at a project boundary. Generated code runs in
  `braxis-kit-sandbox:1`: no network, no host mounts, read-only root, 512 MB/1
  CPU/128 pids, nobody, 6s, 12 KB output. No runtime `pip install`.

## Authored vs self-generated (honest)

**Authored by us:** the action list, project templates, starting blueprints,
medium/subject seeds, desire seeds, shape vocabulary, and the garden-robot
identity in the prompt.

**Self-generated by KIT:** which action/project/medium/subject it chooses and
when; its daily desires, world name/tagline, wonders, new subjects, creative
combinations; whether it accepts or declines a visitor idea; its hobby; its
project schemas and variations; the three project ideas in its self-authored
queue; its self-observations and curiosity targets.

The option space is still mostly curated. The next layer is letting successful
novelty expand the options, not just the choices.

## Free-will modules: evaluated, not copied

Kept: entropy curiosity, evolved desires, mood attractors, emotional residue,
dreams, resonance, self-chosen projects, visitor refusal, creative preferences,
thought memory, outcome signals.

Skipped: LLM-per-decision gate, meta-learning/evolutionary prompt, random
world-event pool, artist lyric memory, event-triggered LLM reflection. The old
modules are in the private recovery archive.

## Stack / cost

- No model in the tick. KIT's lead is the **free OpenRouter 550B Nemotron
  Ultra**; fallback is the free background chain. **24 autonomous calls/day**
  shared by the reflection and event summaries; chat is on demand. Paid
  OpenRouter lanes are reserved for Vesper/MAYA and never enter KIT's chain.
- Procedural three.js/canvas art; a real image lane at most 1/day.
- Existing ACE music lane at most 1 track/day.
- Playwright + ffmpeg for clips; no model.
- JSON memory; no vector DB for one resident.
- Social posts route through the estate's determiner and `shared/ship_gate.py`;
  no model per post.

## Limitations

- The first free TRELLIS hero GLB is live on the center plinth; more hero
  subjects and arbitrary-build swapping are the next 3D step. Most builds are
  still low-poly procedural geometry.
- The core action list is authored, but KIT can now add **declarative action
  plugins** (`define` → validated name/place/effects) and **shape plugins**
  (`design` → validated primitive parts). It can write and run code only in
  the sandbox; it cannot install a new mechanic on the host or execute
  payments. This is bounded autonomy, not consciousness or independence.
- The daily reflection is one free-model call; quality varies. It writes the
  self-authored project queue and curiosity target.
- Browsing is real page reading. Watching now works: the VM fetches TikTok with
  yt-dlp and the local watch-skill, and watches a PC-fetched YouTube file.
  KIT has real results for *How Janas runs big AI models on small laptops* and
  *Someone Just Rebuilt Adobe for Free*. YouTube cannot be fetched from the VM
  (bot wall); the PC residential IP is required for that leg.
- The local 8B is too slow for a blocking lane (one success at 141s, two
  timeouts); KIT uses the free remote 550B instead. TokenHarbor is configured
  with `:free` models, not paid.
- The sandbox has numpy, pandas, matplotlib, Pillow, scipy, sympy and networkx
  baked in. New packages require a reviewed image rebuild; no runtime pip.
- KIT cannot execute payments or account changes from chat.

## Files

- `world_life.py` — brain, state, HTTP API, tick, projects, builds, signals.
- `world_creation_share.py` — gallery card, social share, Printify pilot.
- `kit_music.py` — ACE v3 song generation.
- `kit_image.py` — real image generation.
- `kit_diary.py` — daily diary post.
- `world_video.py` — live world clip, optionally muxed with KIT's song.
- `world_share.py` — build capture and determiner routing.
- `kit_watcher.py` — the dreamkeeper and medium-rut auditor.
- `kit_watch_vm.py` — VM watch worker: TikTok via yt-dlp, local watch-skill,
  posts results to KIT.
- `kit_poem.py` — free-writing poem worker; upgrades template poems.
- `kit_study.py` — field-note worker: Wikipedia summary → free-model note.
- `kit_emotion.py` — 30-dimensional emotion state, decay and interlocks.
- `kit_plugins.py` — declarative action and shape plugin registry.
- `kit_builder.py` — Echo's code builder for KIT's requests.
- `kit_sandbox.py` — Docker package sandbox.
- `kit_notebook.py` — KIT's instant-download notebook product.
- `digital_guide.py` — generic instant-download guide product.
- `kit-sandbox.Dockerfile` / `kit-sandbox-build.sh` — package image definition/rebuild.
- `kit_memory.py` — local SQLite FTS5 episodic memory; used by reflection and
  the dashboard search.
- `dashboard.html` — the standalone `/kit/` dashboard.
- `kit_chat.py` — Telegram conversation loop.
- `kit_reset.py` — archive/reset; `--blank` for self-invented projects.

*KIT is bounded autonomy with self-selection today. The point of the next layer
is to make the options, not just the choice, partly its own.*
