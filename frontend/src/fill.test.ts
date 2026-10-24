import assert from "node:assert/strict";
import { test } from "node:test";
import { fillOnUniform, fillUniform, parseAccent } from "./viewer/theme.ts";

test("the fill is off by default and parses like the accent", () => {
  assert.equal(fillOnUniform.value, 0);
  // the stock navy of furniture bodies (0x172238)
  assert.deepEqual(fillUniform.value.toArray().map((v) => Math.round(v * 255)), [23, 33, 56]);
  assert.deepEqual(parseAccent("#ff8000"), [1, 128 / 255, 0]);
  assert.equal(parseAccent("red"), null);
  assert.equal(parseAccent(null), null);
});
