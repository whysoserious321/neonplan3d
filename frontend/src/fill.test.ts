import assert from "node:assert/strict";
import { test } from "node:test";
import { Color } from "three";
import { fillOnUniform, fillUniform, parseAccent } from "./viewer/theme.ts";
import { GeoBuffer, isNavySurface, tintNavy } from "./viewer/geo.ts";

test("the fill is off by default and parses like the accent", () => {
  assert.equal(fillOnUniform.value, 0);
  // the stock navy of furniture bodies (0x172238), as the shader sees it (linear)
  const navy = new Color(0x172238);
  for (const [i, v] of [navy.r, navy.g, navy.b].entries()) assert.ok(Math.abs(fillUniform.value.toArray()[i] - v) < 0.001);
  assert.deepEqual(parseAccent("#ff8000"), [1, 128 / 255, 0]);
  assert.equal(parseAccent("red"), null);
  assert.equal(parseAccent(null), null);
});

test("only the dark navy surfaces count as fill", () => {
  const c = (hex: number) => new Color(hex);
  for (const hex of [0x172238, 0x131d31, 0x0e1629, 0x243661, 0x0b111f]) assert.ok(isNavySurface(c(hex).r, c(hex).g, c(hex).b), hex.toString(16));
  // glass, plants, bright signal colours and lines are left alone
  for (const hex of [0x1c3a52, 0x12302e, 0xffb300, 0x37e0ff]) assert.ok(!isNavySurface(c(hex).r, c(hex).g, c(hex).b), hex.toString(16));
});

test("tintNavy gives a body its picked colour and keeps the shading", () => {
  const buf = new GeoBuffer();
  const body = new Color(0x172238);
  const top = new Color(0x1d2b47);
  const lamp = new Color(0xffb300);
  buf.tri([0, 0, 0], [1, 0, 0], [0, 1, 0], body);
  buf.tri([0, 0, 0], [1, 0, 0], [0, 1, 0], top, top, lamp);
  tintNavy(buf, 0, 2, 0x8b1a1a);
  const picked = new Color(0x8b1a1a);
  // the body shows the picked colour itself
  assert.ok(Math.abs(buf.c[0] - picked.r) < 0.01 && Math.abs(buf.c[1] - picked.g) < 0.01 && Math.abs(buf.c[2] - picked.b) < 0.01);
  // the lighter top stays lighter, the signal colour is untouched
  assert.ok(buf.c[9] > picked.r);
  assert.equal(buf.c[15], lamp.r);
});
