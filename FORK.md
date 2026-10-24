# FORK.md – custom colours fork of NeonPlan 3D

Notes for the next person or AI agent who has to keep this fork up to date. Read this first, then `CLAUDE.md`
(upstream's notes; its "talk to the user in German" line does not apply here: this fork's owner writes English, so
answer in English).

This is **not** the official NeonPlan 3D. Upstream is `Mastershort/neonplan3d` (MIT). The name belongs to upstream; do
not present this fork as official. Pro features and the shop are untouched: nothing here unlocks anything.

- Fork: `whysoserious321/neonplan3d`, working branch **`custom-fill`** (the default branch stays a clean upstream copy).
- Remotes in a clone: `origin` = the fork, `upstream` = `https://github.com/Mastershort/neonplan3d.git`.
- Based on upstream 2.0.0 (commit `81e0e9c`). The fork's commits sit on top of it.

## What the fork adds

All colours are optional; with nothing set, the look is identical to upstream.

| Feature | Where the user sets it | Stored as |
|---|---|---|
| Global **fill** colour (walls, floors, furniture bodies; Neon look only) | ⚙ bar colour picker next to the accent picker (remembered per device, `prefs` key `fill`); card option `neon_fill: "#rrggbb"` (card editor field) | device pref / card config, no server storage |
| **Wall colour** per room edge and per free wall | Editor → room → wall list, "Wall colour" field; free wall form | `Room.wall_colors?: (string\|null)[]` (index = edge), `FreeWall.color` |
| **Floor colour** per room | Editor → room form, under "Material" | `Room.floor_color` |
| **Furniture colour** per piece | Editor → furniture form, under "Rotation" (not for lamps) | `Furniture.color` |
| **Colour field** with text box (accepts `#rrggbb`, `rrggbb`, `r, g, b`, `rgb(...)`) and swatches of colours already used in the plan | all of the above in the editor | – |

All stored colours are `#rrggbb` strings or null/absent.

### Where the code is

- `frontend/src/viewer/theme.ts` – GLSL `fp3dThemed()`: the Neon branch remaps dark navy surfaces to `uFill` when
  `uFillOn == 1`. `fillUniform` / `fillOnUniform` mirror `accentUniform` / `accentOnUniform`. The fill rule is checked
  **before** the accent rule (navy surfaces also match the "cyan surface" accent test).
- `frontend/src/viewer/geo.ts` – `isNavySurface()` (the same rule in TypeScript), `tintNavy()` (recolours the triangles
  of one furniture piece), `BODY_LEVEL`.
- `frontend/src/viewer/viewer3d.ts` – `setFill()` (hex to a linear colour for the shader).
- `frontend/src/viewer/build.ts` – wall solids use `wall.color` (top face 1.25x lighter); floors use `room.floor_color`
  (also stored in `roomTris.color`, which the room highlight restores); furniture calls `tintNavy()` after `pushFurniture()`.
- `frontend/src/geometry/walls.ts` – `Wall.color`; `colorOf()` reads `Room.wall_colors` / `FreeWall.color`; walls of
  different colours are **not** merged in `mergeCollinear()`. A wall two rooms share takes the first colour set.
- `frontend/src/color-input.ts` – `parseColorText()` and `usedColors()` (pure, tested).
- `frontend/src/components/editor.ts` – `colorField()` helper and its CSS (`.fp3d-colorfield`, `.fp3d-hex`,
  `.fp3d-swatch`); `setColor()` in the wall rows; `wall_colors` is spliced alongside `wall_thickness` when a corner is
  inserted or deleted (`insertVertex`-style code near `wall_thickness.splice`, and `deleteVertex`).
- `frontend/src/components/view3d.ts`, `card.ts`, `card-config.ts`, `card-editor.ts`, `panel.ts`, `i18n.ts` (de + en
  keys: `fill*`, `wall_color*`, `floor_color*`, `furn_color*`, `color_reset`, `color_used`) – plumbing and labels.
- `frontend/src/import/simple.ts` – `wall_colors` is cleared where the other per-edge arrays are.
- `custom_components/neonplan3d/schema.py` – validates `wall_colors`, `floor_color`, `Furniture.color`,
  `FreeWall.color` (`^#[0-9a-fA-F]{6}$`). (The schemas use `extra=vol.ALLOW_EXTRA`, so unknown keys survive anyway.)
- `frontend/build.mjs` – size budgets raised a little: `neonplan3d.js` 692 KB, `neonplan3d-3d.js` 816 KB,
  `neonplan3d-card-editor.js` 271 KB. `neonplan3d-editor.js` is tight (about 928 of 930 KB): raise its budget with a note
  if a rebase pushes it over.
- Tests: `frontend/src/fill.test.ts`, `walls-color.test.ts`, `color-input.test.ts`.

### Colour maths (easy to get wrong)

Vertex colours are **linear** (three.js `Color`), and the shader sees them linear. The Neon surfaces are dark navy
(furniture body `0x172238`, wall `0x131d31`, floor `0x0e1629`). The rule, in both GLSL and `isNavySurface()`:
`max(r,g,b) < 0.42 && b >= g && g < b*0.45 && r < b*0.5`. The 0.45 keeps glass (`0x1c3a52`) and plants out. An own
colour is applied as `own * min(max(r,g,b) / 0.04, 2)`, so a body shows exactly the picked colour and tops stay lighter.
Own wall/floor colours are used as given. Blueprint and Day remap colours in the shader as before; bright saturated own
colours survive there as "signal colours", dull ones do not.

## Keeping up with upstream (the main job)

HACS is **not** used for this install; updating through HACS would overwrite the fork with the official version.

1. Make sure the working tree is clean, then:
   ```
   git fetch upstream
   git rebase upstream/main        # on branch custom-fill
   ```
2. Resolve conflicts. Expect them in `editor.ts`, `i18n.ts`, `model.ts`, `schema.py`, `theme.ts`, and **always** in
   the compiled bundles `custom_components/neonplan3d/frontend/*.js`. For the bundles take either side, then rebuild.
   If upstream added its own colour fields, merge with theirs instead of keeping a parallel field.
3. Rebuild and check (from `frontend/`): `npm ci`, `npm run typecheck`, `npm test`, `npm run build` (bundles are
   committed and CI fails when stale; the build prints each bundle against its budget). Python: `ruff check` and
   `ruff format` on `custom_components` if ruff is installed (HA integration tests only run in upstream's Linux CI).
4. Visual check (see below), commit the rebuilt bundles, push with `--force-with-lease` after a rebase (ask the owner
   first; pushing rewrites the fork's branch).
5. Deploy to the Pi (see below). If upstream bumped the plan storage version, the migration is one-way: back up
   `.storage/neonplan3d.*` first.

## Visual check without Home Assistant

`frontend/screenshot.mjs` / `npm run screenshot` render `preview/index.html` (mock data) with a local Chrome. A quick
ad-hoc check: serve the repo root with any static server, open `/preview/index.html?lang=en` (German is the default),
open the Editor tab and change the document through the editor element:
`document.querySelector("neonplan3d-panel").shadowRoot.querySelector("fp3d-editor").change((d) => { ... })`, then
switch to the 3D tab. To test with the owner's real plan, load their `neonplan3d-full-*.json` backup with
`e.setDoc(structuredClone(data.building))`; keep that file out of the repo (never commit real plans, IPs or device
names). The preview has no Home Assistant, so its "restore backup" cannot work there.

## Deploying to the Raspberry Pi

The owner runs Home Assistant on a Raspberry Pi 5; config is under `/home/test/HomeAssistant/config` (files are
owned by root, so use `sudo`). Ask the owner for the Pi's address and for permission before touching it; they log in
with an SSH key from this PC. Do not store the address in the repo. Docker shows no containers for the `test` user, so
restart Home Assistant from its UI (Settings → System → Restart); the owner does that.

1. Owner makes a Home Assistant backup and a NeonPlan export (⚙ → 💾 Backup) first.
2. On the Pi, back up: copy `custom_components/neonplan3d` and `config/.storage/neonplan3d.*` to
   `~/neonplan-backup` (the original 1.19.0 install is already there; use a dated folder for later backups).
3. Pack and copy (PowerShell on Windows, full paths, no `%VAR%`):
   ```
   tar -czf C:\Users\<user>\neonplan3d.tgz -C <repo>\custom_components neonplan3d
   scp C:\Users\<user>\neonplan3d.tgz test@<pi>:/home/test/neonplan3d.tgz
   ```
4. Swap on the Pi:
   ```
   ssh -t test@<pi> 'sudo rm -rf /home/test/HomeAssistant/config/custom_components/neonplan3d && sudo tar -xzf ~/neonplan3d.tgz -C /home/test/HomeAssistant/config/custom_components && sudo chown -R root:root /home/test/HomeAssistant/config/custom_components/neonplan3d'
   ```
5. Owner restarts Home Assistant, hard-refreshes (Ctrl+F5, or clears the Companion app cache) and checks the log for
   `neonplan3d` errors.
6. Rollback: remove the folder, copy the backup folder and the `.storage/neonplan3d.*` files back, restart.

## Practical notes for agents on this machine

- Git is installed but not on the PATH of every shell: prepend `C:\Program Files\Git\cmd` (or call it by full path).
  The repo-local git identity is `whysoserious321`.
- `git push` works from the agent's shell once the owner has signed in via Git Credential Manager; if it prints
  "terminal prompts disabled", ask the owner to run the push in their own terminal.
- PowerShell treats `%VAR%` literally and `docker ps --format "{{...}}"` needs different quoting; keep remote commands in
  single quotes.
- The agent's terminal tool allows only a few open tabs; close finished ones.
- HACS: do not press Update / Remove / Redownload on the official NeonPlan entry. Removing deletes the files.
- Confirm with the owner before pushing, deploying or restarting anything. They prefer English and short step lists.

## Ideas not done yet

- Separate fill colours for walls, floors and furniture (the global fill is one colour).
- Colours that survive the Blueprint and Day looks as chosen (they are remapped there).
- Tint outdoor objects separately: the global fill also recolours navy fence posts and driveways.
- Colours for pack furniture parts, lamps and roofs.
