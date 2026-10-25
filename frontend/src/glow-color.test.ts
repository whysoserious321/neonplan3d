import assert from "node:assert/strict";
import { test } from "node:test";
import { overrideGlowColor } from "./devices.ts";

const glow = { color: [1, 0.71, 0.28] as [number, number, number], level: 0.6 };

test("an own glow colour replaces the colour and keeps the level", () => {
  assert.deepEqual(overrideGlowColor(glow, "#ff0000"), { color: [1, 0, 0], level: 0.6 });
});

test("an off light stays off; unset or invalid colours change nothing", () => {
  assert.equal(overrideGlowColor(null, "#ff0000"), null);
  assert.equal(overrideGlowColor(glow, null), glow);
  assert.equal(overrideGlowColor(glow, "red"), glow);
});
