import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFile } from "node:fs/promises";

const require = createRequire(import.meta.url);
const { formatPublishedAt, renderArticle, validateFeed } = require("../app.js");

function validFeed() {
  return {
    version: 1,
    generated_at: "2026-07-29T10:00:00+08:00",
    window_days: 10,
    article_count: 1,
    articles: [{
      id: "article-1",
      account_name: "京宣",
      title: "文章标题",
      summary: "文章摘要",
      published_at: "2026-07-29T09:30:00+08:00",
      url: "https://mp.weixin.qq.com/s/example"
    }]
  };
}

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

test("validateFeed accepts the Task 1 feed schema", () => {
  const feed = validFeed();
  assert.deepEqual(validateFeed(feed), feed);
});

test("validateFeed rejects an inconsistent article count", () => {
  const feed = validFeed();
  feed.article_count = 2;
  assert.throws(() => validateFeed(feed), /文章数据格式无效/);
});

test("validateFeed rejects a non-ten-day window", () => {
  const feed = validFeed();
  feed.window_days = 7;
  assert.throws(() => validateFeed(feed), /文章数据格式无效/);
});

test("validateFeed rejects a wrong version, invalid generated time, or non-string article field", () => {
  const wrongVersion = validFeed();
  wrongVersion.version = 2;
  assert.throws(() => validateFeed(wrongVersion), /文章数据格式无效/);

  const invalidGeneratedAt = validFeed();
  invalidGeneratedAt.generated_at = "not-a-date";
  assert.throws(() => validateFeed(invalidGeneratedAt), /文章数据格式无效/);

  const invalidArticle = validFeed();
  invalidArticle.articles[0].title = 1;
  assert.throws(() => validateFeed(invalidArticle), /文章数据格式无效/);
});

test("validateFeed rejects an article with unexpected fields or a non-WeChat URL", () => {
  const feed = validFeed();
  feed.articles[0].unexpected = "field";
  assert.throws(() => validateFeed(feed), /文章数据格式无效/);

  delete feed.articles[0].unexpected;
  feed.articles[0].url = "https://example.com/article";
  assert.throws(() => validateFeed(feed), /文章数据格式无效/);
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
