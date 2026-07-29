(function () {
  "use strict";

  const ARTICLE_FIELDS = ["id", "account_name", "title", "summary", "published_at", "url"];

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function formatPublishedAt(iso) {
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) {
      throw new TypeError("文章发布时间无效");
    }

    const parts = new Intl.DateTimeFormat("zh-CN", {
      timeZone: "Asia/Shanghai",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false
    }).formatToParts(date);
    const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
    return `${values.month}月${values.day}日 ${values.hour}:${values.minute}`;
  }

  function articleUrl(value) {
    const url = new URL(value);
    if (url.protocol !== "https:" || url.hostname !== "mp.weixin.qq.com") {
      throw new TypeError("文章链接无效");
    }
    return url.href;
  }

  function isWechatArticleUrl(value) {
    if (typeof value !== "string") {
      return false;
    }
    try {
      articleUrl(value);
      return true;
    } catch {
      return false;
    }
  }

  function isParseableTime(value) {
    return typeof value === "string" && !Number.isNaN(Date.parse(value));
  }

  function invalidFeed() {
    throw new TypeError("文章数据格式无效");
  }

  function validateFeed(feed) {
    if (
      !feed ||
      typeof feed !== "object" ||
      Array.isArray(feed) ||
      feed.version !== 1 ||
      feed.window_days !== 10 ||
      !(feed.generated_at === null || isParseableTime(feed.generated_at)) ||
      !Number.isInteger(feed.article_count) ||
      feed.article_count < 0 ||
      !Array.isArray(feed.articles) ||
      feed.article_count !== feed.articles.length
    ) {
      invalidFeed();
    }

    for (const article of feed.articles) {
      if (
        !article ||
        typeof article !== "object" ||
        Array.isArray(article) ||
        Object.keys(article).length !== ARTICLE_FIELDS.length ||
        !ARTICLE_FIELDS.every((field) => Object.hasOwn(article, field)) ||
        !ARTICLE_FIELDS.every((field) => typeof article[field] === "string") ||
        !isParseableTime(article.published_at) ||
        !isWechatArticleUrl(article.url)
      ) {
        invalidFeed();
      }
    }

    return feed;
  }

  function renderArticle(article) {
    const url = articleUrl(article.url);
    const summary = article.summary ? `<p class="article-summary">${escapeHtml(article.summary)}</p>` : "";
    return `<article class="article-row"><p class="article-meta">${escapeHtml(article.account_name)}　${formatPublishedAt(article.published_at)}</p><a class="article-title" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(article.title)}</a>${summary}</article>`;
  }

  function renderPage(feed) {
    validateFeed(feed);
    const count = feed.article_count;
    const articles = [...feed.articles].sort((left, right) => new Date(right.published_at) - new Date(left.published_at));
    const meta = document.getElementById("feed-meta");
    const status = document.getElementById("feed-status");
    const list = document.getElementById("article-list");
    const updatedAt = feed.generated_at ? `更新于 ${formatPublishedAt(feed.generated_at)}，` : "更新时间待生成，";

    meta.textContent = `${updatedAt}最近 ${feed.window_days} 天共 ${count} 篇`;
    if (articles.length === 0) {
      status.textContent = "最近没有可展示的文章";
      list.replaceChildren();
      return;
    }

    list.innerHTML = articles.map(renderArticle).join("");
    status.textContent = "";
  }

  async function loadFeed() {
    const status = document.getElementById("feed-status");
    try {
      const response = await fetch("./feed.json", { cache: "no-store" });
      if (!response.ok) {
        throw new Error(`文章数据加载失败（${response.status}）`);
      }
      renderPage(await response.json());
    } catch (error) {
      status.textContent = "文章数据加载失败，请稍后刷新页面";
    }
  }

  if (typeof module !== "undefined") {
    module.exports = { formatPublishedAt, renderArticle, validateFeed };
  }

  if (typeof document !== "undefined") {
    loadFeed();
  }
}());
