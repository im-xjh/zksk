# Project Memory

- Environment: Windows workspace. Prefer `md_to_word_report.cmd` for local use because PowerShell `.ps1` files can be blocked by execution policy.
- Encoding: keep scripts UTF-8 compatible and avoid raw Chinese string literals in Python source when practical. The converter stores Chinese font names as Unicode escapes and reads Markdown with `utf-8-sig`.
- Word style rule: body `small2` means title size 2, level-1 heading small 2, body small 2; body `3` means title small 2, level-1 heading small 2, body size 3. Level-2 and deeper headings use the body size and are bold.
- Git workflow: every project change should be committed locally. After the initial push to the private GitHub repo `zksk`, do not push future commits to the cloud unless explicitly asked.
