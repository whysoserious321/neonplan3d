import assert from "node:assert/strict";
import { test } from "node:test";
import { parseColorText, usedColors } from "./color-input.ts";

test("colour text in the usual forms becomes #rrggbb", () => {
  assert.equal(parseColorText("#8B1A1A"), "#8b1a1a");
  assert.equal(parseColorText("8b1a1a"), "#8b1a1a");
  assert.equal(parseColorText(" #b22 "), "#bb2222");
  assert.equal(parseColorText("139, 26, 26"), "#8b1a1a");
  assert.equal(parseColorText("rgb(139,26,26)"), "#8b1a1a");
  assert.equal(parseColorText("0 0 255"), "#0000ff");
});

test("anything else is refused", () => {
  for (const bad of ["", "red", "#12345", "256, 0, 0", "1, 2", null, undefined]) assert.equal(parseColorText(bad as string), null, String(bad));
});

test("used colours come most used first, without duplicates", () => {
  const floors = [
    { rooms: [{ wall_colors: ["#ff0000", null, "#FF0000", "#00ff00"], floor_color: "#00ff00" }], furniture: [{ color: "#00ff00" }, { color: null }], walls: [{ color: "#0000ff" }] },
  ];
  assert.deepEqual(usedColors(floors), ["#00ff00", "#ff0000", "#0000ff"]);
});
