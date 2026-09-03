# Offline Demo report builder

Run `python3 tools/report/build_demo_report.py` to rebuild using the checked-in
`source_commit.txt`, or use `--record-source-commit` when intentionally refreshing
the checked-in derivative. The latter records `git rev-parse HEAD` before writing
the HTML.

The generated report is committed separately from the source changes that feed it.
Consequently, the footer/marker intentionally names the **parent source commit**,
not the later commit that adds the derived HTML bytes. Host tests require a byte-
identical rebuild from that marker.

`demo_README.md` and `demo_README.zh-CN.md` are the maintained delivery-entry
templates. The `demo` snapshot copies them to the repository root; `main` retains
its engineering README. The local-link checker treats these two files as templates:
their root-relative links are validated after the snapshot copy, not from
`tools/report/` on `main`.
