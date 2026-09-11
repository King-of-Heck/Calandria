// Plain text of one side of a list of change rows: "modified" keeps the inserted and unchanged
// segments after the row's marker, "original" the deleted and unchanged ones after the old
// marker; a row that has no paragraph on that side (oi or ni null) adds nothing; one line per
// paragraph. No DOM: importable under node.
export function textOf(rows, side) {
  const keep = side === "modified" ? new Set(["ins", "eq"]) : new Set(["del", "eq"]);
  const lines = [];
  for (const row of rows) {
    if (side === "modified" ? row.ni === null || row.ni === undefined : row.oi === null || row.oi === undefined) continue;
    const marker = side === "original" && row.num_changed && row.old_marker !== null && row.old_marker !== undefined
      ? row.old_marker : (row.marker || "");
    const body = row.segments.filter((s) => keep.has(s.m)).map((s) => s.t).join("");
    lines.push(marker ? `${marker} ${body}` : body);
  }
  return lines.join("\n");
}
