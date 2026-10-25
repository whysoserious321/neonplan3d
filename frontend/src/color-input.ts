// Colour text typed or pasted into a colour field: "#8b1a1a", "8b1a1a", "#b22", "139, 26, 26" or "rgb(139,26,26)".

/** "#rrggbb" (lower case) for any of the forms above, null for anything else. */
export function parseColorText(text: string | null | undefined): string | null {
  const s = (text ?? "").trim().toLowerCase();
  const hex = /^#?([0-9a-f]{3}|[0-9a-f]{6})$/.exec(s);
  if (hex) {
    const h = hex[1].length === 3 ? [...hex[1]].map((c) => c + c).join("") : hex[1];
    return `#${h}`;
  }
  const rgb = /^(?:rgb\()?\s*(\d{1,3})\s*[,;\s]\s*(\d{1,3})\s*[,;\s]\s*(\d{1,3})\s*\)?$/.exec(s);
  if (!rgb) return null;
  const parts = rgb.slice(1, 4).map(Number);
  if (parts.some((v) => v > 255)) return null;
  return `#${parts.map((v) => v.toString(16).padStart(2, "0")).join("")}`;
}

/** The colours set anywhere in a plan (walls, floors, furniture), most used first, for quick reuse. */
export function usedColors(floors: readonly { rooms: readonly { wall_colors?: (string | null)[]; floor_color?: string | null }[]; furniture: readonly { color?: string | null; glow_color?: string | null }[]; walls?: readonly { color?: string | null }[] }[]): string[] {
  const count = new Map<string, number>();
  const add = (c: string | null | undefined) => {
    const v = parseColorText(c);
    if (v) count.set(v, (count.get(v) ?? 0) + 1);
  };
  for (const f of floors) {
    for (const r of f.rooms) {
      add(r.floor_color);
      for (const c of r.wall_colors ?? []) add(c);
    }
    for (const m of f.furniture) {
      add(m.color);
      add(m.glow_color);
    }
    for (const w of f.walls ?? []) add(w.color);
  }
  return [...count.entries()].sort((a, b) => b[1] - a[1]).map(([c]) => c).slice(0, 12);
}
