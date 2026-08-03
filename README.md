# Skills Collection

个人收藏 AI Skill(如 Claude/OpenAI 的 Skill 定义)的同步与展示站点。

你只需维护 `config.json` 里的一个 GitHub URL 列表,系统会自动:

1. **拉取** 每个 URL 对应的仓库/子路径(稀疏检出,最小化数据量)
2. **提取** Skill 文件中的 `description`(支持 YAML frontmatter / 纯 YAML / JSON)
3. **翻译** 为中文(`deep-translator` 免费接口,带 MD5 缓存)
4. **生成** 静态站点(纯前端卡片网格 + 模糊搜索),部署到 Cloudflare Pages

---

## 目录结构

```
skills-collection/
├── config.json               # ★ 唯一需要手动维护的配置(字符串数组)
├── scripts/
│   └── sync.py               # 主同步脚本(Python 3.10+)
├── site/                     # 前端源码(构建时复制到 public/)
│   ├── index.html
│   ├── style.css
│   └── app.js
├── public/                   # 发布目录(Cloudflare Pages 根) — 脚本生成
│   ├── index.html
│   ├── style.css
│   ├── app.js
│   └── skills.json           # 脚本生成的 Skill 元数据
├── skills/                   # 原始 Skill 文件拷贝(脚本生成,默认) — 可整目录打包带走
├── translation_cache.json    # 翻译缓存(自动生成,建议提交到仓库)
├── requirements.txt
├── .github/workflows/sync.yml
└── README.md
```

---

## 配置:`config.json`

仅包含一个 JSON 对象,键为 `"skills"`,值为 GitHub URL 字符串数组:

```json
{
  "skills": [
    "https://github.com/affaan-m/ECC/tree/main/docs/ja-JP/skills/dart-flutter-patterns",
    "https://github.com/anthropics/skills",
    "https://github.com/obra/superpowers/tree/main/skills"
  ]
}
```

支持的 URL 形态(均可):

| 形态 | 说明 |
| --- | --- |
| `https://github.com/user/repo` | 整仓,在根目录查找 Skill 文件 |
| `https://github.com/user/repo/tree/branch/path/to/skill` | 指定分支的子路径(稀疏检出) |
| `https://github.com/user/repo/blob/branch/path/to/skill.md` | 同上,blob 形式 |
| `https://github.com/user/repo.git` | 带 `.git` 后缀亦可 |

> 分支默认 `main`;URL 中的 `/tree/` 或 `/blob/` 后第一段为分支名。若指定分支不存在,脚本自动回退到仓库默认分支。

### 原始 Skill 拷贝(`skills_dir`)

同步时会把每个 Skill 所在目录**完整拷贝**到本地,方便一次性拉取收藏的 Skill(可整目录打包带走,不含 `.git`)。

- 默认拷贝到根目录 `skills/`,每个 Skill 一个子目录(`skills/<name>/`);重名自动追加序号(如 `skills-2`)。
- 可通过 `config.json` 的可选字段 `"skills_dir"` 指定任意文件夹(绝对/相对路径均可);设为 `null` / `""` / `false` 则关闭拷贝。
- 也可用环境变量 `SKILLS_DIR` 覆盖。
- 注意:该目录由脚本**完全管理**,每次运行会先清空再重建(与 `public/` 一致),不要手动往里放文件。

```json
{
  "skills_dir": "my-skills",
  "skills": ["https://github.com/user/repo/tree/main/skills/foo"]
}
```

查找 Skill 文件的优先级:目录下的 `SKILL.md` / `skill.yaml` / `skill.yml` / `skill.json`(大小写不敏感)→ 若无,则取第一个支持扩展名(`.md/.yaml/.yml/.json/.txt`)的文件。

### 标签(`tags`)

每个 Skill 会生成 1–6 个标签,写入 `skills.json` 的 `tags` 字段,前端以徽章展示(点击标签可筛选)。标签按准确度自动生成:

1. **frontmatter 的 `tags` 字段**(最准确,直接采用);
2. **双语功能词典**匹配 `description` / 名称 / 文件路径(标签全部中文,覆盖 人工智能 / 编程开发 / 前端开发 / 后端开发 / 界面设计 / Python 开发 / Flutter 开发 / 移动开发 / 软件测试 / 数据处理 / 机器学习 / 运维部署 / 写作 / 翻译 等 24 类主题);
3. **技术专有名词提取**:从 `description` 抓取大写开头的技术栈名(如 `GoRouter`、`BLoC`、`Riverpod`、`Dio`),自动过滤常见英文停用词。

**`skill_tags` 自动维护**:`sync.py` 每次运行会把新 URL 的自动标签写回 `config.json` 的 `skill_tags` 字段(仅新增缺失的 URL,**不覆盖**你手动改过的标签)。也就是说,你只需要维护 `skills` 列表,标签会自动补齐;想微调某个 Skill 的标签,直接改 `config.json` 里对应 URL 的数组即可:

```json
{
  "skills": ["https://github.com/user/repo/tree/main/skills/foo"],
  "skill_tags": {
    "https://github.com/user/repo/tree/main/skills/foo": ["移动开发", "架构模式"]
  }
}
```

（想完全回归自动标签,删掉 `skill_tags` 键即可;工作流会自动把更新后的 `config.json` 一并提交）

### 订阅地址(RSS)

脚本会生成 `public/feed.xml`(RSS 2.0),首页顶部有「📡 订阅 RSS」按钮。部署到 Cloudflare Pages 后,完整订阅地址为:

```
https://<你的-pages-域名>/feed.xml
```

（本地预览时为 `http://localhost:8000/public/feed.xml`;也可直接订阅仓库更新:`https://github.com/Mitchll1214/skills-collection/commits/main.atom`）

---

## 本地运行

需要 **Python 3.10+** 和 **git**。

```bash
pip install -r requirements.txt
python scripts/sync.py
```

输出:

- `public/skills.json` — 所有 Skill 元数据数组(每项含 `name` / `description` / `description_zh` / `source_url` / `commit` / `file` / `branch`)
- `translation_cache.json` — 翻译缓存(原文 MD5 → 译文)
- `skills/` — 每个收藏 Skill 的原始文件拷贝(默认,见上文 `skills_dir` 配置)
- `public/` 下会同步复制 `site/` 的静态文件

本地预览(注意:`file://` 直接双击无法跨文件 fetch,请用本地服务器):

```bash
python -m http.server 8000
# 浏览器访问 http://localhost:8000/public/
```

### 离线/无网测试

脚本内置两个环境变量钩子,不影响生产默认行为:

```bash
# 1) 允许任意 git 地址(可用本地仓库做端到端测试):
#    格式 git-url#子路径@分支
set SKILLS_ALLOW_ANY_GIT=1
python scripts/sync.py

# 2) 使用假翻译器(离线验证缓存与回退逻辑,不调用 Google 接口)
set SKILLS_TRANSLATOR=mock
python scripts/sync.py

# 3) 指定其他配置文件(默认读取根目录 config.json)
set SKILLS_CONFIG=D:\path\to\my-config.json
python scripts/sync.py
```

---

## 翻译与缓存

- 翻译使用 `deep-translator` 的 `GoogleTranslator`(免费,无需 API Key),源语言自动检测,目标语言 `zh-CN`。
- 缓存键为原文的 MD5。**重复运行不会重复调用翻译接口**,命中直接复用。
- 翻译失败(网络不通、超时等)时**回退为原文**,且不写入缓存,下次运行会重试。
- 如需强制全部重新翻译,删除 `translation_cache.json` 再运行即可。
- `translation_cache.json` 建议提交到仓库,CI 定时任务就不用反复翻译。

---

## 自动化(GitHub Actions)

`.github/workflows/sync.yml` 会在以下时机自动运行:

- `push` 到 `main` 且修改了 `config.json`
- 每日 UTC 03:00 定时
- 手动触发(仓库 Actions 页面点击 `Run workflow`)

流程:检出 → 安装依赖 → 运行 `python scripts/sync.py` → 自动提交 `public/` 与 `translation_cache.json` 的变更回 `main`。

---

## 部署到 Cloudflare Pages

1. 将仓库推送到 GitHub。
2. Cloudflare Dashboard → **Workers & Pages** → **Create → Pages → Connect to Git**。
3. 选择本仓库,配置:
   - **Build command**:留空(或 `echo "No build required"`)
   - **Build output directory**:`public`
4. 保存后,每次 `main` 分支更新(含 GitHub Actions 的自动提交)都会触发重新部署。

---

## 常见问题

- **某个 URL 拉取失败 / 没找到 Skill 文件?** 该条目会被跳过并打印日志,不影响其他条目;`skills.json` 只包含成功条目。
- **页面打开是空白的?** 确认你是通过 HTTP 访问(`python -m http.server` 或已部署的 Pages 域名),而非直接双击 `index.html`。
- **描述里可能有 Markdown/HTML?** 前端全部使用 `textContent` 渲染,天然转义,无 XSS 风险;以纯文本形式展示。
- **当前只支持 GitHub 仓库 URL**,其他平台暂不支持。
