import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFile } from "node:fs/promises";

const require = createRequire(import.meta.url);
const { formatPublishedAt, renderArticle } = require("../app.js");

test("formatPublishedAt renders Beijing month day and time", () => {
  assert.equal(formatPublishedAt("2026-07-29T09:30:00+08:00"), "07月29日 09:30");
});

test("renderArticle escapes text and keeps a safe article URL", () => {
  const html = renderArticle({
    account_name: "<公众号>",
    title: "<script>alert(1)</script>",
    summary: "摘要",
    published_at: "2026-07-29T09:30:00+08:00",
    url: "https://mp.weixin.qq.com/s/example"
  });
  assert.doesNotMatch(html, /<script>/);
  assert.match(html, /target="_blank"/);
  assert.match(html, /rel="noopener noreferrer"/);
});

test("page avoids a missing favicon request", async () => {
  const page = await readFile(new URL("../index.html", import.meta.url), "utf8");
  assert.match(page, /<link rel="icon" href="data:,">/);
});

test("feed errors remain visible without logging to the browser console", async () => {
  const app = await readFile(new URL("../app.js", import.meta.url), "utf8");
  assert.doesNotMatch(app, /console\.error/);
});

test("page labels an unavailable generated time", async () => {
  const app = await readFile(new URL("../app.js", import.meta.url), "utf8");
  assert.match(app, /更新时间待生成/);
});
