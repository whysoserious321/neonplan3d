import assert from "node:assert/strict";
import { test } from "node:test";
import { GeoBuffer, tintNavy } from "./viewer/geo.ts";
import { SHADE_SENTINEL, shadeFactors } from "./viewer/lamp-colors.ts";
import { pushLampModel } from "./viewer/viewer3d.ts";

const lamp = (kind: "floor" | "table" | "wall" | "strip") => {
  const buf = new GeoBuffer();
  pushLampModel(buf, { lamp: kind, x: 0, z: 0, size: [0.4, 0.4, 1.6], base: 0, rotation: 0, variant: null, roll: 0, upright: false, rise: 0 }, 2.5, SHADE_SENTINEL);
  return buf;
};

test("an own lamp colour tints the lamp's body and leaves the shade to the light", () => {
  const plain = lamp("floor");
  const tinted = lamp("floor");
  tintNavy(tinted, 0, tinted.count, 0x8b1a1a);
  const shade = shadeFactors(plain.c);
  const shadeAfter = shadeFactors(tinted.c);
  assert.ok(shade.some((f) => f > 0), "the lamp has a shade");
  assert.deepEqual(shadeAfter, shade);
  assert.notDeepEqual(Array.from(tinted.c), Array.from(plain.c), "the body took the colour");
  for (let v = 0; v < shade.length; v++) {
    if (shade[v] > 0) assert.deepEqual([...tinted.c.slice(v * 3, v * 3 + 3)], [...plain.c.slice(v * 3, v * 3 + 3)]);
  }
});
