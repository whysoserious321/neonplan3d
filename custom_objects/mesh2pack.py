"""Turn a simple 3D model (OBJ or GLB, e.g. from Fusion) into the source of a NeonPlan 3D furniture pack.

Model every part of the furniture as its own body (boxes, cylinders), name it with the tokens below and give it a
colour. Each body becomes one pack part; its bounding box gives position and size. The overall bounding box of all
bodies is the size of the furniture.

    python custom_objects/mesh2pack.py cabinet.obj --id studio.wall_cabinet --name "Wall cabinet 80" --publisher Me \\
        --mount wall --wall-y 1.45 --out private/packs/wall_cabinet.json
    python tools/fp3dpack.py sign private/packs/wall_cabinet.json --key KEYFILE
    python tools/fp3dpack.py verify private/packs/wall_cabinet.fp3dpack

Body names are tokens joined by "_", the rest is a free label (it is ignored):
    cyl            a cylinder (upright, or lying along the width or depth when it is longest there)
    loft           a box whose top is another rectangle (the top is read from the body's highest vertices)
    glow           shines in the colour and brightness of the linked light (lamps)
    screen         a screen: shows the linked media player on its front (TV, monitor)
    edges, edgesglow, edgesfaint   glowing edges
    top-8b5a2b     own colour for the top face
    role-wood      a palette role instead of the body's colour (follows the look: body, fabric, cushion, wood,
                   white, metal, dark, glass, plant, pot, accent)
    fix-wdh        the measures that stay when the furniture is resized (w, d, h)
    rot45          the part is turned by 45 degrees about the vertical axis
Example: "edgesfaint_door_left", "cyl_glow_bulb", "role-metal_handle", "carcass_top-cfc9ba".

A body's colour is its material colour (OBJ: Kd of the .mtl next to the file; GLB: base colour); without one the part
takes the palette role "body".

Axes: --up y (default; Fusion and glTF) or z says which axis points up; --front says which side is the front of the
furniture after that (+z default; +x, -x, -z). --unit is cm for OBJ and m for GLB unless given.
Only the standard library is needed (the pack is checked with voluptuous when that is installed).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import re
import struct
import sys

ROLES = {"body", "fabric", "cushion", "wood", "white", "metal", "dark", "glass", "plant", "pot", "accent"}
UNITS = {"mm": 0.001, "cm": 0.01, "m": 1.0}
MAX_PARTS = 60

Vec = tuple[float, float, float]


class ModelError(Exception):
    pass


# ------------------------------------------------------------------ readers: {body name: (vertices, colour)}


def read_obj(path: Path, mtl: Path | None = None) -> dict[str, tuple[list[Vec], Vec | None]]:
    vertices: list[Vec] = []
    bodies: dict[str, set[int]] = {}
    order: list[str] = []
    material_of: dict[str, str] = {}
    current = "body"
    material = ""
    mtl_files: list[Path] = [mtl] if mtl else []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        t = line.strip().split()
        if not t:
            continue
        if t[0] == "v" and len(t) >= 4:
            vertices.append((float(t[1]), float(t[2]), float(t[3])))
        elif t[0] in ("o", "g") and len(t) >= 2:
            current = t[1]
        elif t[0] == "usemtl" and len(t) >= 2:
            material = t[1]
            material_of.setdefault(current, material)
        elif t[0] == "mtllib" and len(t) >= 2 and not mtl:
            mtl_files.append(path.parent / " ".join(t[1:]))
        elif t[0] == "f":
            ids = bodies.setdefault(current, set())
            if current not in order:
                order.append(current)
            for token in t[1:]:
                i = int(token.split("/")[0])
                ids.add(i - 1 if i > 0 else len(vertices) + i)
    colours: dict[str, Vec] = {}
    for file in mtl_files:
        if file.exists():
            name = ""
            for line in file.read_text(encoding="utf-8", errors="replace").splitlines():
                t = line.strip().split()
                if len(t) >= 2 and t[0] == "newmtl":
                    name = t[1]
                elif len(t) >= 4 and t[0] == "Kd":
                    colours[name] = (float(t[1]), float(t[2]), float(t[3]))
    return {
        name: ([vertices[i] for i in sorted(bodies[name])], colours.get(material_of.get(name, ""))) for name in order
    }


def _matmul(a: list[float], b: list[float]) -> list[float]:
    return [sum(a[k * 4 + r] * b[c * 4 + k] for k in range(4)) for c in range(4) for r in range(4)]


def _node_matrix(node: dict) -> list[float]:
    if "matrix" in node:
        return list(node["matrix"])
    tx, ty, tz = node.get("translation", [0, 0, 0])
    qx, qy, qz, qw = node.get("rotation", [0, 0, 0, 1])
    sx, sy, sz = node.get("scale", [1, 1, 1])
    r = [
        1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy + qz * qw), 2 * (qx * qz - qy * qw),
        2 * (qx * qy - qz * qw), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz + qx * qw),
        2 * (qx * qz + qy * qw), 2 * (qy * qz - qx * qw), 1 - 2 * (qx * qx + qy * qy),
    ]  # fmt: skip
    return [
        r[0] * sx, r[1] * sx, r[2] * sx, 0,
        r[3] * sy, r[4] * sy, r[5] * sy, 0,
        r[6] * sz, r[7] * sz, r[8] * sz, 0,
        tx, ty, tz, 1,
    ]  # fmt: skip


def _srgb(c: float) -> float:
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def read_glb(path: Path) -> dict[str, tuple[list[Vec], Vec | None]]:
    data = path.read_bytes()
    if data[:4] != b"glTF":
        raise ModelError("not a GLB file (glTF with external files is not supported, export as .glb)")
    gltf: dict = {}
    blob = b""
    pos = 12
    while pos + 8 <= len(data):
        length, kind = struct.unpack_from("<II", data, pos)
        chunk = data[pos + 8 : pos + 8 + length]
        if kind == 0x4E4F534A:
            gltf = json.loads(chunk.decode("utf-8"))
        elif kind == 0x004E4942:
            blob = chunk
        pos += 8 + length

    def positions(accessor: dict) -> list[Vec]:
        view = gltf["bufferViews"][accessor["bufferView"]]
        stride = view.get("byteStride", 12)
        start = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
        return [struct.unpack_from("<fff", blob, start + i * stride) for i in range(accessor["count"])]

    bodies: dict[str, tuple[list[Vec], Vec | None]] = {}

    def walk(index: int, parent: list[float]) -> None:
        node = gltf["nodes"][index]
        world = _matmul(parent, _node_matrix(node))
        if "mesh" in node:
            mesh = gltf["meshes"][node["mesh"]]
            points: list[Vec] = []
            colour: Vec | None = None
            for prim in mesh["primitives"]:
                for x, y, z in positions(gltf["accessors"][prim["attributes"]["POSITION"]]):
                    points.append(
                        (
                            world[0] * x + world[4] * y + world[8] * z + world[12],
                            world[1] * x + world[5] * y + world[9] * z + world[13],
                            world[2] * x + world[6] * y + world[10] * z + world[14],
                        )
                    )
                if colour is None and "material" in prim:
                    factor = gltf["materials"][prim["material"]].get("pbrMetallicRoughness", {}).get("baseColorFactor")
                    if factor:
                        colour = (_srgb(factor[0]), _srgb(factor[1]), _srgb(factor[2]))
            name = node.get("name") or mesh.get("name") or f"node{index}"
            bodies[name] = (points, colour)
        for child in node.get("children", []):
            walk(child, world)

    identity = [1.0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
    scene = gltf["scenes"][gltf.get("scene", 0)]
    for root in scene["nodes"]:
        walk(root, identity)
    return bodies


# ------------------------------------------------------------------ conversion


def parse_name(name: str) -> dict:
    """The tokens of a body name; whatever is not a token is the label."""
    info: dict = {"shape": "box", "label": []}
    for token in name.split("_"):
        low = token.lower()
        if low in ("cyl", "loft"):
            info["shape"] = low
        elif low in ("glow", "screen"):
            info[low] = True
        elif low == "edges":
            info["edges"] = True
        elif low in ("edgesglow", "edgesfaint"):
            info["edges"] = low[5:]
        elif m := re.fullmatch(r"top-([0-9a-f]{6})", low):
            info["top"] = "#" + m.group(1)
        elif m := re.fullmatch(r"role-([a-z]+)", low):
            if m.group(1) not in ROLES:
                raise ModelError(f"{name}: unknown palette role {m.group(1)!r} (one of {', '.join(sorted(ROLES))})")
            info["role"] = m.group(1)
        elif m := re.fullmatch(r"fix-([wdh]{1,3})", low):
            info["fix"] = m.group(1)
        elif m := re.fullmatch(r"rot(-?\d{1,3})", low):
            info["rot"] = float(m.group(1))
        else:
            info["label"].append(token)
    return info


def to_item_frame(p: Vec, up: str, front: str) -> Vec:
    """Model coordinates to the furniture frame: x right, y up, z towards the front."""
    x, y, z = p if up == "y" else (p[0], p[2], -p[1])
    if front == "-z":
        x, z = -x, -z
    elif front == "+x":
        x, z = -z, x
    elif front == "-x":
        x, z = z, -x
    return (x, y, z)


def hex_of(rgb: Vec) -> str:
    return "#" + "".join(f"{round(min(1.0, max(0.0, c)) * 255):02x}" for c in rgb)


def _r(value: float) -> float:
    return round(value, 4)


def _span(value: float) -> float:
    return _r(min(1.0, max(0.001, value)))


def convert(bodies: dict[str, tuple[list[Vec], Vec | None]], args: argparse.Namespace) -> dict:
    scale = UNITS[args.unit]
    shaped: list[tuple[str, dict, list[Vec], Vec | None]] = []
    for name, (points, colour) in bodies.items():
        if not points:
            continue
        pts = [tuple(c * scale for c in to_item_frame(p, args.up, args.front)) for p in points]
        shaped.append((name, parse_name(name), pts, colour))  # type: ignore[arg-type]
    if not shaped:
        raise ModelError("no bodies found in the file")
    if len(shaped) > MAX_PARTS:
        raise ModelError(f"{len(shaped)} bodies, but a furniture has at most {MAX_PARTS} parts: merge bodies")
    if len(shaped) == 1:
        print("note: only one body found; give each part its own body (export groups/objects)", file=sys.stderr)

    lo = [min(p[i] for _, _, pts, _ in shaped for p in pts) for i in range(3)]
    hi = [max(p[i] for _, _, pts, _ in shaped for p in pts) for i in range(3)]
    width, height, depth = hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]
    if min(width, height, depth) < 0.01 or max(width, height, depth) > 10:
        raise ModelError(
            f"size {width:.3f} x {depth:.3f} x {height:.3f} m is outside 0.01 .. 10 m: check --unit (now {args.unit})"
        )
    cx, cz = (lo[0] + hi[0]) / 2, (lo[2] + hi[2]) / 2

    parts = []
    for name, info, pts, colour in shaped:
        bl = [min(p[i] for p in pts) for i in range(3)]
        bh = [max(p[i] for p in pts) for i in range(3)]
        w, h, d = bh[0] - bl[0], bh[1] - bl[1], bh[2] - bl[2]
        if min(w, h, d) <= 1e-6:
            raise ModelError(f"{name}: the body is flat (a size is zero); give it a thickness")
        part: dict = {
            "shape": info["shape"],
            "x": _r(((bl[0] + bh[0]) / 2 - cx) / width),
            "z": _r(((bl[2] + bh[2]) / 2 - cz) / depth),
            "w": _span(w / width),
            "d": _span(d / depth),
            "y": _r((bl[1] - lo[1]) / height),
            "h": _span(h / height),
        }
        if info.get("role"):
            part["color"] = info["role"]
        elif colour is not None:
            part["color"] = hex_of(colour)
        else:
            part["color"] = "body"
        if "top" in info:
            part["top"] = info["top"]
        if "edges" in info:
            part["edges"] = info["edges"]
        for key in ("glow", "screen", "fix", "rot"):
            if key in info:
                part[key] = info[key]
        if info["shape"] == "cyl":
            longest = max(w, d, h)
            if longest == w and w > 1.0001 * max(d, h):
                part["axis"] = "x"
            elif longest == d and d > 1.0001 * max(w, h):
                part["axis"] = "z"
        if info["shape"] == "loft":
            top = [p for p in pts if p[1] >= bh[1] - h * 0.01]
            tl = [min(p[i] for p in top) for i in (0, 2)]
            th = [max(p[i] for p in top) for i in (0, 2)]
            part["tx"] = _r(((tl[0] + th[0]) / 2 - cx) / width)
            part["tz"] = _r(((tl[1] + th[1]) / 2 - cz) / depth)
            part["tw"] = _span((th[0] - tl[0]) / width)
            part["td"] = _span((th[1] - tl[1]) / depth)
        parts.append(part)

    short = args.id.split(".", 1)[-1]
    item: dict = {
        "id": short,
        "name": {"en": args.name, **({"de": args.name_de} if args.name_de else {})},
        "size": [round(width, 3), round(depth, 3), round(height, 3)],
        "parts": parts,
        "symbol": [{"shape": "rect", "x": 0, "z": 0, "w": 1, "d": 1}],
    }
    if args.electric:
        item["electric"] = True
    if args.mount != "floor":
        item["mount"] = args.mount
    if args.wall_y is not None:
        item["wall_y"] = args.wall_y
    if args.surface:
        item["surface"] = True
    if args.hole:
        item["hole"] = True
    if args.light:
        item["light"] = args.light
    for key in ("group", "family"):
        if getattr(args, key):
            item[key] = getattr(args, key)
    for key in ("room", "tags"):
        if getattr(args, key):
            item[key] = [s.strip() for s in getattr(args, key).split(",") if s.strip()]
    return {
        "format": "fp3dpack",
        "version": 1,
        "id": args.id,
        "name": args.pack_name or args.name,
        "publisher": args.publisher,
        "items": [item],
    }


def check(payload: dict) -> None:
    """Check the pack against the real schema when voluptuous is installed."""
    try:
        root = Path(__file__).resolve().parent.parent
        spec = importlib.util.spec_from_file_location(
            "fp3d_packs", root / "custom_components" / "neonplan3d" / "packs.py"
        )
        assert spec and spec.loader
        packs = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(packs)
    except ImportError:
        print(
            "note: voluptuous/cryptography not installed, the pack was not checked (sign/verify will)", file=sys.stderr
        )
        return
    try:
        packs.validate_payload(payload)
    except packs.PackError as err:
        raise ModelError(f"the pack is not valid: {err}") from err


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("model", type=Path, help=".obj or .glb")
    p.add_argument(
        "--id", required=True, help='pack id, e.g. "studio.wall_cabinet" (the item id is the part after the dot)'
    )
    p.add_argument("--name", required=True, help="name of the furniture (English)")
    p.add_argument("--name-de", help="name of the furniture (German, optional)")
    p.add_argument("--pack-name", help="name of the pack (default: the furniture name)")
    p.add_argument("--publisher", required=True)
    p.add_argument("--unit", choices=sorted(UNITS), help="unit of the model (default: cm for OBJ, m for GLB)")
    p.add_argument("--up", choices=["y", "z"], default="y")
    p.add_argument("--front", choices=["+z", "-z", "+x", "-x"], default="+z")
    p.add_argument("--mtl", type=Path, help="material file for an OBJ (default: the one named in the OBJ)")
    p.add_argument("--mount", choices=["floor", "surface", "wall", "ceiling"], default="floor")
    p.add_argument("--wall-y", type=float, help="height of the bottom edge above the floor in metres (mount wall)")
    p.add_argument("--surface", action="store_true", help="the top carries other furniture")
    p.add_argument("--hole", action="store_true", help="stairs")
    p.add_argument("--electric", action="store_true", help="can link a switch and a power sensor")
    p.add_argument(
        "--light",
        choices=[
            "ceiling",
            "downlight",
            "spot",
            "panel",
            "pendant",
            "floor",
            "uplight",
            "table",
            "wall",
            "strip",
            "bollard",
            "garden",
        ],
        help="makes the furniture a lamp of this kind",
    )
    p.add_argument("--group", help="library group: lamp, sofa, table, storage, bed, kitchen, appliance, bath, ...")
    p.add_argument("--room", help="comma separated rooms: living, bedroom, kitchen, ...")
    p.add_argument("--tags", help="comma separated search words")
    p.add_argument("--family", help="variants of one furniture share a family id")
    p.add_argument("--out", type=Path, help="pack source to write (default: next to the model)")
    return p


def main() -> None:
    args = build_parser().parse_args()
    suffix = args.model.suffix.lower()
    args.unit = args.unit or ("m" if suffix in (".glb", ".gltf") else "cm")
    try:
        if suffix == ".obj":
            bodies = read_obj(args.model, args.mtl)
        elif suffix == ".glb":
            bodies = read_glb(args.model)
        else:
            raise ModelError("give an .obj or .glb file")
        payload = convert(bodies, args)
        check(payload)
    except (ModelError, ValueError, KeyError) as err:
        sys.exit(f"error: {err}")
    out = args.out or args.model.with_suffix(".json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    item = payload["items"][0]
    print(
        f"{out}: {args.name}, {item['size'][0]} x {item['size'][1]} x {item['size'][2]} m, {len(item['parts'])} parts"
    )


if __name__ == "__main__":
    main()
