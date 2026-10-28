// Plain text of one side of a list of change rows: "modified" keeps the inserted and unchanged
// segments after the row's marker, "original" the deleted and unchanged ones after the old
// marker; a row that has no paragraph on that side (oi or ni null) adds nothing; one line per
// paragraph. A shared segment printed differently in the original (a contents line's page
// number) carries that text as "o". No DOM: importable under node.
export function linesOf(rows, side) {
  const keep = side === "modified" ? new Set(["ins", "eq"]) : new Set(["del", "eq"]);
  const lines = [];
  for (const row of rows) {
    if (side === "modified" ? row.ni === null || row.ni === undefined : row.oi === null || row.oi === undefined) continue;
    const marker = side === "original" && row.num_changed && row.old_marker !== null && row.old_marker !== undefined
      ? row.old_marker : (row.marker || "");
    const body = row.segments.filter((s) => keep.has(s.m)).map((s) => side === "original" && s.o !== undefined ? s.o : s.t).join("");
    lines.push(marker ? `${marker} ${body}` : body);
  }
  return lines;
}

// One paragraph per line; the count of lines is the count of paragraphs copied.
export function textOf(rows, side) {
  return linesOf(rows, side).join("\n");
}
