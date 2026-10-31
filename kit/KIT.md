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
- **40+ actions** across 20 named places, including far sites (river dock, old
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
- **Obstacle map:** the page reports city blocks, props and tree positions to
  `/api/world/obstacles`; `_avoid_step()` takes a detour around them instead of
  walking through.
- **Sprawl:** after 10 builds, KIT takes a deliberate 55% far-site draw; the
  world is deliberately bigger than the plaza.
- **Skill library:** `kit_skill_library.json` stores finished schemas with
  `uses` and `successes`; `_write_code()` composes a variation from a stored
  fragment.

## What KIT can make

- **Real music:** `kit_music.py` writes a short lyric from KIT's live state and
  calls the existing ACE v3 lane. The first song, *a song about the trio*, is
  154 seconds and lives at
  `https://braxisai.com/media/music/Braxis_Songs/Kit/`.
- **Real images:** `kit_image.py` turns one creation into a real image through
  the estate's free NVIDIA FLUX/CogView cascade. The first painting is
  `https://braxisai.com/media/world/creations/creation_art-1793391568-21_art.jpg`.
- **Real video:** `world_video.py` records a live window of the world and muxes
  KIT's own song with ffmpeg. First KIT music video:
  `https://braxisai.com/media/world/live_20261030T210754Z.mp4`.
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

## Companion and dashboard

- **Juniper, the first companion.** KIT has a `befriend` action. On
  2026-10-31 00:11 UTC it made **Juniper the moss-cat** (`comp-1793405460`,
  bond 0.12). The 3D page renders a small four-legged companion that follows
  KIT; the HUD and dashboard show its name and bond. This is a pet with simple
  page behavior, not a second autonomous agent.
- **Dashboard:** https://braxisai.com/kit/ shows live state, the project step,
  self-observation, companion, project origins, interests, every recent
  creation with an honest `image` / `audio` / `poem` / `card only` badge, the
  builds, last read/watch results, and the watcher nudge. It refreshes every
  15 seconds from the world API.
- **Project steps:** `progress / target` is the number of matching actions,
  not a quality score. The HUD now says **step X of Y**; future projects use
  3–5 steps.

## Autonomy and memory

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
  blueprints come back. The watcher now also reads the last twelve creations
  and leaves a medium-rut nudge (for example, four poems in twelve), which
  lowers KIT's preference for that medium. It enables; it does not command.
- **Telegram:** KIT has its own bot and replies from live state. Chat cannot
  execute changes.
- **Safety:** visitor and browsed text is sanitized (`_safe_external`), audited
  in `kit_external_events.jsonl`, and visitor ideas queue in `pending_ideas`;
  KIT accepts one only at a project boundary. `_write_code()` writes recipes,
  never executes code.

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
- The action list is authored; KIT now authors project goals and observations,
  but it does not yet author new mechanics or execute code. This is bounded
  autonomy, not consciousness or independence.
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
- KIT cannot execute code, payments, or account changes from chat.

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
- `dashboard.html` — the standalone `/kit/` dashboard.
- `kit_chat.py` — Telegram conversation loop.
- `kit_reset.py` — archive/reset; `--blank` for self-invented projects.

*KIT is bounded autonomy with self-selection today. The point of the next layer
is to make the options, not just the choice, partly its own.*
