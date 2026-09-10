"""The local server behind the viewer: stdlib http.server on 127.0.0.1, one comparison in memory.

API (JSON unless stated; errors are {"error": message} with 400 for bad input, 409 when no
comparison is loaded, 404 / 405 / 413 as usual). A POST carrying an Origin that is not this
server, or a Sec-Fetch-Site other than same-origin / none, is refused with 403 before its body is
read: a loopback server is reachable from every page the browser has open.
  GET  /                      the viewer page; GET /static/<name> its script and style
  GET  /api/state             {"version", "loaded", "names"}
  POST /api/compare           {"a": {"name", "data" (base64 .docx)}, "b": {...}, "options"?: {...},
                              "render_set"?: NAME, "change_bars"?: true|false}
                              -> the full payload (names, options, summary, changes, page_count,
                              anchors, marks, render_sets, render_set_styles, render_set,
                              change_bars, pages (SVG strings), report_lines)
  POST /api/layout            {"options": {...}, "render_set"?: NAME, "change_bars"?: true|false}
                              -> the full payload after re-compare + re-layout
                              (options: ignore_case, count_numbering, show_equal, show_insertions,
                              show_deletions, show_formatting; every key optional, merged over the
                              current options; render_set and change_bars default to "Standard" and
                              true when omitted)
  GET  /api/pages?render_set=NAME&change_bars=0|1
                              -> {"render_set", "change_bars", "pages", "report_lines"}
  GET  /api/pdf?render_set=NAME&change_bars=0|1&report=first|last|none
                              -> application/pdf as an attachment
  POST /api/ping              {"ok": true}; the page sends one every 2 s
  POST /api/quit              {"ok": true}, then the server stops
The server also stops --idle seconds after the last request once the page has been seen
(default 8, so closing the window stops it; 0 = never), and --grace seconds (default 120) after
start if no page ever arrives. A machine that sleeps does not count as silence.
"""
