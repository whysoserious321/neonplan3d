"""custom_objects/mesh2pack.py: bodies of an OBJ/GLB model become the parts of a furniture pack."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import struct

import pytest

_spec = importlib.util.spec_from_file_location(
    "mesh2pack", Path(__file__).resolve().parent.parent / "custom_objects" / "mesh2pack.py"
)
assert _spec and _spec.loader
m2p = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m2p)


def _cuboid(lo: tuple[float, float, float], size: tuple[float, float, float]) -> list[tuple[float, float, float]]:
    x, y, z = lo
    w, h, d = size
    return [(x + dx * w, y + dy * h, z + dz * d) for dx in (0, 1) for dy in (0, 1) for dz in (0, 1)]


def _obj(path: Path, bodies: dict[str, tuple[list, str]]) -> Path:
    """Write bodies (name -> (corner points of a cuboid, material)) as an OBJ with one faces line per body."""
    lines = ["mtllib model.mtl"]
    mtl = []
    start = 1
    for name, (points, material) in bodies.items():
        lines += [f"v {x} {y} {z}" for x, y, z in points]
        lines += [f"o {name}", f"usemtl {material}", "f " + " ".join(str(start + i) for i in range(len(points)))]
        start += len(points)
    colours = {"green": "0.2902 0.4196 0.3647", "cream": "0.851 0.831 0.78", "grey": "0.5 0.5 0.5"}
    for material, kd in colours.items():
        mtl += [f"newmtl {material}", f"Kd {kd}"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    path.with_name("model.mtl").write_text("\n".join(mtl) + "\n", encoding="utf-8")
    return path


def _args(**over: object) -> argparse.Namespace:
    base = ["--id", "studio.wall_cabinet", "--name", "Wall cabinet 80", "--publisher", "Me", "--unit", "cm"]
    args = m2p.build_parser().parse_args(["model.obj", *base])
    for key, value in over.items():
        setattr(args, key, value)
    return args


def _cabinet(tmp_path: Path) -> dict:
    # cm, Y up, front at +z; offsets from the left / back / bottom edge of the whole piece
    path = _obj(
        tmp_path / "cabinet.obj",
        {
            "carcass_top-cfc9ba": (_cuboid((0, 0, 0), (80, 70, 31)), "cream"),
            "edgesfaint_door_l": (_cuboid((0.2, 0, 31), (39.7, 70, 1.8)), "green"),
            "edgesfaint_door_r": (_cuboid((40.1, 0, 31), (39.7, 70, 1.8)), "green"),
            "role-metal_handle_l": (_cuboid((36.2, 4, 32.8), (1.2, 12, 2.2)), "grey"),
            "role-metal_handle_r": (_cuboid((42.6, 4, 32.8), (1.2, 12, 2.2)), "grey"),
        },
    )
    return m2p.convert(m2p.read_obj(path), _args(mount="wall", wall_y=1.45))


def test_wall_cabinet_example(tmp_path: Path) -> None:
    payload = _cabinet(tmp_path)
    item = payload["items"][0]
    assert payload["id"] == "studio.wall_cabinet" and item["id"] == "wall_cabinet"
    assert item["size"] == [0.8, 0.35, 0.7]
    assert item["mount"] == "wall" and item["wall_y"] == 1.45
    carcass, door_l, door_r, handle_l, handle_r = item["parts"]
    assert carcass == {
        "shape": "box", "x": 0.0, "z": -0.0571, "w": 1.0, "d": 0.8857, "y": 0.0, "h": 1.0,
        "color": "#d9d4c7", "top": "#cfc9ba",
    }  # fmt: skip
    assert (door_l["x"], door_r["x"], door_l["z"], door_l["w"], door_l["d"]) == (
        -0.2494,
        0.2494,
        0.4114,
        0.4963,
        0.0514,
    )
    assert door_l["color"] == "#4a6b5d" and door_l["edges"] == "faint"
    assert (handle_l["x"], handle_r["x"], handle_l["z"], handle_l["y"], handle_l["h"]) == (
        -0.04,
        0.04,
        0.4686,
        0.0571,
        0.1714,
    )
    assert handle_l["color"] == "metal"


def test_cylinder_axis_loft_and_lamp_flags(tmp_path: Path) -> None:
    path = _obj(
        tmp_path / "lamp.obj",
        {
            "cyl_pole": (_cuboid((9, 0, 9), (2, 100, 2)), "grey"),
            "cyl_roller": (_cuboid((0, 0, 8), (20, 4, 4)), "grey"),
            "cyl_leg": (_cuboid((0, 0, 0), (4, 10, 20)), "grey"),
            # a shade: wide bottom, narrow top
            "loft_glow_shade": (
                _cuboid((0, 100, 0), (20, 0.0001, 20)) + _cuboid((5, 130, 5), (10, 0.0001, 10)),
                "cream",
            ),
        },
    )
    payload = m2p.convert(m2p.read_obj(path), _args(light="floor", group="lamp", tags="lamp, floor"))
    item = payload["items"][0]
    assert item["light"] == "floor" and item["group"] == "lamp" and item["tags"] == ["lamp", "floor"]
    pole, roller, leg, shade = item["parts"]
    assert "axis" not in pole  # upright
    assert roller["axis"] == "x" and leg["axis"] == "z"
    assert shade["shape"] == "loft" and shade["glow"] is True
    assert shade["tw"] == 0.5 and shade["td"] == 0.5 and shade["tx"] == 0.0 and shade["tz"] == 0.0


def test_unit_up_and_front(tmp_path: Path) -> None:
    # millimetres, Z up, the front along -y: a deep thin shelf with a lip at the front
    path = _obj(
        tmp_path / "shelf.obj",
        {"board": (_cuboid((0, 0, 0), (800, 300, 18)), "grey"), "lip": (_cuboid((0, 0, 18), (800, 10, 40)), "grey")},
    )
    payload = m2p.convert(m2p.read_obj(path), _args(unit="mm", up="z"))
    item = payload["items"][0]
    assert item["size"] == [0.8, 0.3, 0.058]
    board, lip = item["parts"]
    # model +y is the back of the piece (item z = -y): the lip at y 0..10 sits at the front (+z)
    assert lip["z"] > board["z"]
    front_x = m2p.convert(m2p.read_obj(path), _args(unit="mm", up="z", front="+x"))["items"][0]["size"]
    assert front_x == [0.3, 0.8, 0.058]


def test_errors(tmp_path: Path) -> None:
    flat = _obj(tmp_path / "flat.obj", {"plane": ([(0, 0, 0), (10, 0, 0), (10, 0, 10), (0, 0, 10)], "grey")})
    with pytest.raises(m2p.ModelError):
        m2p.convert(m2p.read_obj(flat), _args())
    many = _obj(tmp_path / "many.obj", {f"b{i}": (_cuboid((i, 0, 0), (0.5, 5, 5)), "grey") for i in range(61)})
    with pytest.raises(m2p.ModelError, match="at most 60"):
        m2p.convert(m2p.read_obj(many), _args())
    with pytest.raises(m2p.ModelError, match="role"):
        m2p.parse_name("role-sofa_x")


def test_glb_with_node_transform(tmp_path: Path) -> None:
    corners = _cuboid((0, 0, 0), (1, 1, 1))
    blob = b"".join(struct.pack("<fff", *p) for p in corners)
    gltf = {
        "asset": {"version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"name": "glow_strip", "mesh": 0, "translation": [0.5, 0, 0], "scale": [0.6, 0.02, 0.02]}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "material": 0}]}],
        "materials": [{"pbrMetallicRoughness": {"baseColorFactor": [1, 1, 1, 1]}}],
        "accessors": [{"bufferView": 0, "count": 8, "componentType": 5126, "type": "VEC3"}],
        "bufferViews": [{"buffer": 0, "byteLength": len(blob)}],
        "buffers": [{"byteLength": len(blob)}],
    }
    js = json.dumps(gltf).encode()
    js += b" " * (-len(js) % 4)
    total = 12 + 8 + len(js) + 8 + len(blob)
    path = tmp_path / "strip.glb"
    path.write_bytes(
        b"glTF"
        + struct.pack("<II", 2, total)
        + struct.pack("<II", len(js), 0x4E4F534A)
        + js
        + struct.pack("<II", len(blob), 0x004E4942)
        + blob
    )
    args = _args(unit="m", mount="surface")
    payload = m2p.convert(m2p.read_glb(path), args)
    item = payload["items"][0]
    assert item["size"] == [0.6, 0.02, 0.02]
    assert item["parts"][0]["glow"] is True and item["parts"][0]["color"] == "#ffffff"
