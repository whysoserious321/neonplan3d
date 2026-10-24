import assert from "node:assert/strict";
import { test } from "node:test";
import type { Room } from "./model.ts";
import { generateWalls } from "./geometry/walls.ts";

const room = (id: string, x0: number, x1: number, extra: Partial<Room> = {}): Room => ({
  id,
  name: id,
  area_id: null,
  points: [[x0, 0], [x1, 0], [x1, 4], [x0, 4]],
  floor_material: "wood",
  ...extra,
});

test("a colour set on one room edge colours that wall only", () => {
  // edge 0 runs along z = 0 (the north wall)
  const walls = generateWalls([room("a", 0, 4, { wall_colors: ["#ff0000", null, null, null] })], { exterior: 0.3, interior: 0.1 }).walls;
  const coloured = walls.filter((w) => w.color);
  assert.equal(coloured.length, 1);
  assert.equal(coloured[0].color, "#ff0000");
  assert.ok(coloured[0].a[1] === 0 && coloured[0].b[1] === 0);
});

test("a wall two rooms share takes the colour of either room", () => {
  const rooms = [room("a", 0, 4), room("b", 4, 8, { wall_colors: [null, null, null, "#00ff00"] })];
  const shared = generateWalls(rooms, { exterior: 0.3, interior: 0.1 }).walls.filter((w) => w.roomRight !== null);
  assert.equal(shared.length, 1);
  assert.equal(shared[0].color, "#00ff00");
});

test("walls of different colours are not merged, bad colours are ignored", () => {
  const rooms = [room("a", 0, 4, { wall_colors: ["#ff0000", "nope", null, null] })];
  const walls = generateWalls(rooms, { exterior: 0.3, interior: 0.1 }).walls;
  assert.equal(walls.length, 4);
  assert.equal(walls.filter((w) => w.color).length, 1);
});

test("a free wall carries its own colour", () => {
  const walls = generateWalls([room("a", 0, 4)], { exterior: 0.3, interior: 0.1 }, [{ id: "f1", a: [2, 0.5], b: [2, 3.5], color: "#0000ff" }]).walls;
  assert.equal(walls.find((w) => w.free === "f1")?.color, "#0000ff");
});
