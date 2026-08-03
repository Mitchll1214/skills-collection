/* skills-collection 前端逻辑:加载 skills.json,卡片网格 + 模糊搜索。 */
(function () {
  "use strict";

  var grid = document.getElementById("grid");
  var search = document.getElementById("search");
  var countEl = document.getElementById("count");
  var emptyEl = document.getElementById("empty");
  var banner = document.getElementById("banner");
  var filterBar = document.getElementById("tag-filters");

  var skills = [];

  function showBanner(text) {
    banner.textContent = text;
    banner.hidden = false;
  }

  function matches(s, q) {
    if (!q) return true;
    var hay = [s.name, s.description, s.description_zh, s.source_url, s.file]
      .concat(s.tags || [])
      .filter(Boolean)
      .join("\n")
      .toLowerCase();
    return hay.indexOf(q) !== -1;
  }

  function buildCard(s) {
    var card = document.createElement("article");
    card.className = "card";

    var title = document.createElement("h2");
    title.textContent = s.name || "(未命名)";
    card.appendChild(title);

    if (s.description) {
      var desc = document.createElement("p");
      desc.className = "desc";
      desc.textContent = s.description;
      card.appendChild(desc);
    }

    if (s.description_zh) {
      var zh = document.createElement("div");
      zh.className = "zh";
      var tag = document.createElement("span");
      tag.className = "zh-tag";
      tag.textContent = "中文";
      zh.appendChild(tag);
      zh.appendChild(document.createTextNode(s.description_zh));
      card.appendChild(zh);
    }

    if (s.tags && s.tags.length) {
      var tags = document.createElement("div");
      tags.className = "tags";
      s.tags.forEach(function (t) {
        var b = document.createElement("button");
        b.type = "button";
        b.className = "tag";
        b.textContent = t;
        b.title = "点击筛选此标签";
        b.addEventListener("click", function () {
          search.value = t;
          render();
        });
        tags.appendChild(b);
      });
      card.appendChild(tags);
    }

    var footer = document.createElement("div");
    footer.className = "card-footer";

    var link = document.createElement("a");
    link.className = "source";
    link.href = s.source_url || "#";
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = "查看来源 ↗";
    footer.appendChild(link);

    var meta = document.createElement("div");
    meta.className = "meta";
    if (s.commit) {
      var badge = document.createElement("span");
      badge.className = "badge";
      badge.title = "commit " + s.commit;
      badge.textContent = "#" + String(s.commit).slice(0, 7);
      meta.appendChild(badge);
    }
    if (s.file) {
      var fileBadge = document.createElement("span");
      fileBadge.className = "badge";
      fileBadge.textContent = s.file;
      meta.appendChild(fileBadge);
    }
    if (meta.childNodes.length > 0) {
      footer.appendChild(meta);
    }

    card.appendChild(footer);
    return card;
  }

  function buildFilters(list) {
    var counts = {};
    list.forEach(function (s) {
      (s.tags || []).forEach(function (t) { counts[t] = (counts[t] || 0) + 1; });
    });
    filterBar.innerHTML = "";
    Object.keys(counts).sort().forEach(function (t) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "tag-filter";
      b.dataset.tag = t;
      b.textContent = t + " · " + counts[t];
      b.title = "按标签筛选";
      b.addEventListener("click", function () {
        search.value = (search.value === t) ? "" : t;
        render();
      });
      filterBar.appendChild(b);
    });
  }

  function render() {
    var q = (search.value || "").trim().toLowerCase();
    var filtered = skills.filter(function (s) { return matches(s, q); });

    grid.innerHTML = "";
    filtered.forEach(function (s) { grid.appendChild(buildCard(s)); });

    countEl.textContent = filtered.length + " / " + skills.length;
    emptyEl.hidden = filtered.length !== 0;

    filterBar.querySelectorAll(".tag-filter").forEach(function (b) {
      b.classList.toggle("active", b.dataset.tag === q);
    });
  }

  async function init() {
    try {
      var res = await fetch("skills.json", { cache: "no-store" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      skills = await res.json();
      if (!Array.isArray(skills)) throw new Error("skills.json 格式不正确");
    } catch (e) {
      showBanner(
        "无法加载 skills.json(" + e.message + ")。" +
        "如果你是通过双击文件直接打开的,请改用本地服务器预览:" +
        " 在项目目录执行 `python -m http.server` 后访问 http://localhost:8000/public/"
      );
    }
    buildFilters(skills);
    render();
  }

  search.addEventListener("input", render);
  document.addEventListener("DOMContentLoaded", init);
})();
