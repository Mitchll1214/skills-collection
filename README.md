# Skills Collection

只需维护一个 GitHub URL 列表,自动拉取 Skill、翻译中文、打上功能标签,生成静态展示站点并部署到 Cloudflare Pages。

> **核心价值** — 你只写 `config.json` 里的 URL;同步、翻译、标签、站点、部署全部自动完成。

---

## 一个 URL 如何变成一张卡片

你要维护的全部内容,只有这个数组:

```jsonc
// config.json
{
  "skills": ["https://github.com/user/repo/tree/main/skills/foo"]
}
```

推送后,CI 自动完成:

1. **稀疏检出** — 只拉取目标子路径(`--filter=blob:none --sparse`)
2. **提取 + 翻译** — 读取 `description`,免费接口翻译为中文(带缓存,重复运行零调用)
3. **自动标签** — 生成中文功能标签,并写回 `config.json` 的 `skill_tags`
4. **增量拷贝** — 原始 Skill 完整拷贝到 `skills/`(只补新增,不覆盖你改过的文件)
5. **生成 + 部署** — 产出 `public/` 静态站(卡片网格、搜索、标签筛选、RSS)并部署 Cloudflare Pages

## 特性一览

| 能力 | 说明 |
| --- | --- |
| 极简配置 | 只维护 `skills` URL 数组,`skill_tags` 自动维护 |
| 稀疏检出 | 最小化拉取量,大仓库也快 |
| 自动翻译 | Google 免费接口,源语言自动检测,失败回退原文 |
| 中文标签 | 三层策略(手动 tags → 双语词典 → 技术专名),精确到技术栈 |
| 增量拷贝 | `skills/` 只补缺失,保留已有内容 |
| RSS 订阅 | 自动生成 `feed.xml`,首页一键订阅 |
| 防循环 CI | 任意提交触发;自动提交带 `[skip ci]`,不会死循环 |

## 快速开始

```bash
git clone https://github.com/Mitchll1214/skills-collection
cd skills-collection
pip install -r requirements.txt

python scripts/sync.py          # 本地同步(生成 public/ 与 skills/)
python -m http.server 8000      # 预览 http://localhost:8000/public/
```

之后把新收藏的 Skill 地址追加到 `config.json`,推送即自动同步并部署。

## 配置

### `config.json`

```json
{
  "skills": [
    "https://github.com/anthropics/skills/tree/main/skills/frontend-design",
    "https://github.com/obra/superpowers/tree/main/skills"
  ],
  "skills_dir": "skills",
  "skills_incremental": true,
  "skill_tags": {
    "https://github.com/obra/superpowers/tree/main/skills": ["需求探索", "创意规划", "头脑风暴", "工作流"]
  }
}
```

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `skills` | ✅ | GitHub URL 字符串数组 |
| `skills_dir` | ❌ | Skill 拷贝目录,默认 `"skills"`;设 `null` / `""` / `false` 关闭拷贝 |
| `skills_incremental` | ❌ | 默认 `true`(增量拷贝);`false` 为每次清空重建 |
| `skill_tags` | ❌ | URL → 标签数组,**自动维护**,可手动覆盖 |

### 支持的 URL 形态

| 形态 | 说明 |
| --- | --- |
| `https://github.com/user/repo` | 整仓,根目录查找 Skill 文件 |
| `https://github.com/user/repo/tree/branch/path` | 指定分支的子路径(稀疏检出) |
| `https://github.com/user/repo/blob/branch/path.md` | blob 形式 |
| `https://github.com/user/repo.git` | 带 `.git` 后缀 |

分支默认 `main`,指定分支不存在时自动回退仓库默认分支。

## 自动化与部署

| 触发方式 | 说明 |
| --- | --- |
| `push` 到 `main` | 任意代码 / `config.json` 变更都触发同步 |
| 定时 | 每日 UTC 03:00 |
| 手动 | Actions 页 → Run workflow |

流程:`sync.py` 同步 → 自动提交 `public/` `skills/` `translation_cache.json` `config.json` 回 main(`[skip ci]` 防循环)→ Cloudflare Pages 监听 main 自动部署。

可选:在仓库 Secrets 添加 `CF_DEPLOY_HOOK`(Cloudflare Pages 的 Deploy Hook URL),工作流会在同步后直接 `curl` 触发部署;未配置则靠 main 更新兜底。

## 目录结构

```
├── config.json               # ★ 唯一需要手动维护的配置
├── scripts/sync.py           # 同步脚本(Python 3.10+)
├── site/                     # 前端源码(index.html / style.css / app.js)
├── public/                   # 发布目录(Pages 根)— 脚本生成
│   ├── index.html · style.css · app.js
│   ├── skills.json           # Skill 元数据(含中文描述与标签)
│   └── feed.xml              # RSS 订阅源
├── skills/                   # 原始 Skill 拷贝(增量维护)
├── translation_cache.json    # 翻译缓存(建议提交,避免重复翻译)
└── .github/workflows/sync.yml
```

## 常见问题

<details>
<summary><b>某个 URL 拉取失败?</b></summary>

该条目被跳过并打印日志,不影响其他条目;可查看 Actions 日志定位原因。
</details>

<details>
<summary><b>页面空白 / 看不到最新内容?</b></summary>

通过 HTTP 访问(`python -m http.server` 或 Pages 域名),不要直接双击 `index.html`(`file://` 下 fetch 被 CORS 拦截)。更新后 `Ctrl+F5` 强刷;页面已带 `no-cache` 声明。
</details>

<details>
<summary><b>标签不是想要的?</b></summary>

在 `config.json` 的 `skill_tags` 里给对应 URL 手动指定(覆盖自动标签且持久保留)。想全回归自动,删除整个 `skill_tags` 键。
</details>

<details>
<summary><b>想全部重新翻译?</b></summary>

删除 `translation_cache.json` 后运行即可。
</details>

<details>
<summary><b>离线 / 无网怎么测试?</b></summary>

```bash
set SKILLS_ALLOW_ANY_GIT=1        # 允许任意 git 地址(git-url#子路径@分支)
set SKILLS_TRANSLATOR=mock        # 假翻译器,离线验证缓存与回退
set SKILLS_CONFIG=D:\my-config.json
set SKILLS_DIR=my-skills
python scripts/sync.py
```
</details>

## 版权

© 2026 Mitchll · 保留所有权利
