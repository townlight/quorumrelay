# BoardDocs public selector correction

Scope: original tasks 6 (retrieval), 8 (neutral preservation), and 9 (contract research). Source-only development; no package, installed consumer, release or vendor-write claim.

Two independent public clients corroborate the `a.public-file` selector with `unique` and `href` attributes:

- [RCSD client](https://github.com/dweekly/rcsd-meetings/blob/main/scripts/scrape-boarddocs.mjs), Git blob `c19afe91e05dae319e3b90141b1757e45067136a`, function `parsePublicFilesHtml`.
- [Laravel client](https://github.com/WiserWebSolutions/laravel-boarddocs-scraper/blob/main/src/Parsing/FileLinkParser.php), Git blob `d32a8aae45c76871c49c4a6c30137b871751376a`, public anchor selection and private/admin/executive exclusions.

Both are third-party implementations, not official vendor schemas or raw server-response fixtures. RCSD's `data/sample-detail.json` is a Simbli policy response, not BoardDocs meeting evidence. No code from either client was executed, and their browser identity workarounds were not adopted. The existing guarded print-detail request remains unchanged. The selectors are applied only when supplied in that already-selected response; no new endpoint traversal is inferred.

Reproduction: the new regression failed because a direct public anchor was omitted while private-marked and template anchors were collected. The change recognizes explicit public anchors, excludes private/admin/executive class contexts and suppressed script/style/template contexts, and retains deduplicated href strings. Unclassified anchors remain excluded. These are source declarations, not independent permission verification. No href becomes an automatic download or normalized document locator.

Compact `YYYYMMDD` dates already parse correctly through Python's ISO date parser. The new assertion confirms that behavior; no date implementation change was necessary.

Validation: 19 affected BoardDocs tests passed, including SQLite save/reopen and ZIP export/import equality for normalized data and original fields carrying the new anchor. Affected Ruff and diff checks passed. Machine bindings and execution receipt are in the adjacent JSON file. Existing official/live acceptance remains unverified; the synthetic fixture is explicitly labeled.
