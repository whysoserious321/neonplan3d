# Custom objects (own furniture for NeonPlan 3D)

Everything for making your own furniture lives here: the converter, your Fusion models and this guide.
Fork-only (branch `custom-colours-and-own-furniture`). Background and the signing key are described in `../FORK.md` ("Own furniture").

```
custom_objects/
  mesh2pack.py          converter: OBJ/GLB bodies -> furniture pack source (.json), stdlib only
  models/
    guitar_test.f3d     Fusion model of the test guitar (open it in Fusion)
    guitar_test.obj     its OBJ export (+ guitar_test.mtl, keep both together)
  packs/
    guitar_test.json    generated pack source
    guitar_test.fp3dpack  the signed pack to import (no private key inside)
```

(Packs live here and not in `private/`: a test in CI refuses anything tracked under `private/`.)

The signing tool is **not** moved here: `tools/fp3dpack.py` belongs to upstream (docs, shop and tests use it, and
moving it would conflict on every rebase). Call it from the repo root as shown below.

## What a pack can contain

Furniture is never a mesh. Each item is at most **60 parts** of three kinds, with flat colours:

| shape  | made from                                                         |
|--------|-------------------------------------------------------------------|
| `box`  | any body (its bounding box)                                       |
| `cyl`  | a body named `cyl_…` (upright, or lying along width/depth when that is its longest side) |
| `loft` | a body named `loft_…` (box whose top is a smaller/other rectangle) |

The converter reads only each body's **bounding box**. Holes, cuts, fillets and curves are ignored (a body with a
hole still becomes a solid box). To fake a hole use several boxes around it, or a dark box on the face.
No textures, and the 3D view is unlit.

## Fusion rules

1. One **solid body per part**. Only keep the bodies you want visible (hidden ones are exported too).
2. Real size, standing on the floor (z = 0 when Z is up; the converter measures from the lowest point anyway).
3. Overall bounding box of all bodies = size of the furniture.
4. Name each body with tokens joined by `_`; the rest is a free label:

| token | meaning |
|-------|---------|
| `cyl`, `loft` | shape (see above) |
| `role-wood` | palette role instead of a fixed colour (follows the look): body, fabric, cushion, wood, white, metal, dark, glass, plant, pot, accent |
| `top-RRGGBB` | own colour for the top face |
| `glow` | shines in the colour/brightness of the linked light (lamps) |
| `screen` | shows the linked media player on its front (TV, monitor) |
| `edges`, `edgesglow`, `edgesfaint` | glowing edges |
| `fix-wdh` | measures that stay when resized (w, d, h) |
| `rotN` | part turned by N degrees about the vertical axis |

   Example: `body_role-wood`, `cyl_neck_role-dark`, `loft_shoulder-l_role-wood`.
   Don't start a label with a token word (`rot…`, `top-`, `role-`, `fix-`, `edges…`).
5. Colour comes from the name (`role-…`) or from the body's appearance colour. A body with no material and no
   `role-` token falls back to the role `body`, so give every body one of the two.

Fusion tips (this install: Z-up, mm):
- Sketch on the `XZ` plane (front view), extrude along Y. **Symmetric** extrude distance is *half* the total depth.
- Rename a body: click it in the browser, press **F2**.
- Export: File ▸ Export ▸ type *OBJ* (and *Fusion Archive (*.f3d)* to keep the model). Fusion writes cm and keeps
  body names as `g` groups in the OBJ.

## Quick start (no flags)

From the repo root, convert `models/guitar_test.obj` with all defaults (id `studio.guitar_test`, Z-up, pack source
written to `custom_objects/packs/guitar_test.json`). It prints the settings it used, then signs and verifies the pack with
your key (`--key`, default `~/.neonplan3d/own-pack-key.pem`; `--no-sign` stops after writing the JSON), so the
`.fp3dpack` is ready to import:

```
python custom_objects/mesh2pack.py
```

For another model just give its path, the id and name come from the file name:
`python custom_objects/mesh2pack.py custom_objects/models/chair.obj`. The flags below are only needed to override this.

## Workflow by hand (all flags, separate steps)

Run from the repo root (`C:\Users\sachi\Desktop\neonplan3d`). Needs `pip install voluptuous cryptography`
for checking and signing. The pack source and the signed pack go to `custom_objects/packs/` (committed).

```
python custom_objects/mesh2pack.py custom_objects/models/guitar_test.obj --id studio.guitar_test --name "Guitar test" --publisher sachi --up z --group decor --out custom_objects/packs/guitar_test.json
python tools/fp3dpack.py sign custom_objects/packs/guitar_test.json --key %USERPROFILE%\.neonplan3d\own-pack-key.pem
python tools/fp3dpack.py verify custom_objects/packs/guitar_test.fp3dpack
```

Then in Home Assistant: **Extensions ▸ Import furniture pack**, pick the `.fp3dpack`.
A higher `release` in the JSON replaces an installed pack with the same id.

Flags worth knowing: `--up z|y` (Fusion here is Z-up), `--unit cm|mm|m`, `--front`, `--light strip|floor|table|…`
(makes it a lamp), `--group`, `--room`, `--tags`, `--mount floor|surface|wall|ceiling --wall-y M`, `--surface`,
`--electric`. See `python custom_objects/mesh2pack.py --help`.

Requirements for it to import on the Pi: the backend with the key in `custom_components/neonplan3d/packs.py`
must be deployed and Home Assistant restarted (steps in `../FORK.md`). The pack id must start with `studio.`.
The private key stays outside the repo (back it up!).

## Tests

```
python -m pytest tests/test_mesh2pack.py --noconftest
```
