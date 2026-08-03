# Skills Collection

个人收藏 AI Skill(如 Claude/OpenAI 的 Skill 定义)的同步与展示站点。

你**只需要维护 `config.json` 里的一个 GitHub URL 列表**,系统会自动完成:拉取 → 提取描述 → 翻译中文 → 自动打标签 → 生成静态站点 → 部署到 Cloudflare Pages,并且把原始 Skill 文件也拷贝到本地方便打包带走。

## ✨ 功能特性

- 🔗 **极简配置**:只维护 `config.json` 的 `skills` 字符串数组
- ⚡ **稀疏检出**:只拉取目标子路径,最小化数据量(`--depth 1 --filter=blob:none --sparse`)
- 🌐 **自动翻译**:`deep-translator` 免费接口,源语言自动检测,目标 `zh-CN`,带 MD5 缓存(不重复调用)
- 🏷️ **自动标签**:三层策略自动生成**中文功能标签**,并自动写回 `config.json`(可手动微调)
- 📦 **原始 Skill 拷贝**:每个 Skill 完整目录拷贝到本地 `skills/`,一次性打包带走
- 🖥️ **纯静态前端**:卡片网格 + 中文/原文对照 + 模糊搜索 + 标签筛选 + 数量统计,零后端
- 📡 **RSS 订阅**:自动生成 `feed.xml`,首页一键订阅
- 🤖 **全自动 CI**:GitHub Actions 定时/推送/手动触发,自动提交并部署

---

## 🚀 快速开始

```bash
# 1. 安装依赖(Python 3.10+ 与 git)
pip install -r requirements.txt

# 2. 在 config.json 里填写你要收藏的 GitHub Skill 地址
#    (见下方「配置」)

# 3. 运行同步脚本
python scripts/sync.py

# 4. 本地预览(不要直接双击 index.html,file:// 下 fetch 会被拦截)
python -m http.server 8000
# 浏览器访问 http://localhost:8000/public/
```

---

## 📁 目录结构

```
skills-collection/
├── config.json               # ★ 唯一需要手动维护的配置
├── scripts/
│   └── sync.py               # 主同步脚本(Python 3.10+,仅依赖标准库 + PyYAML + deep-translator)
├── site/                     # 前端源码(每次同步复制到 public/)
│   ├── index.html
│   ├── style.css
│   └── app.js
├── public/                   # 发布目录(Cloudflare Pages 根)— 脚本生成
│   ├── index.html
│   ├── style.css
│   ├── app.js
│   ├── skills.json           # Skill 元数据(含中文描述与标签)
│   └── feed.xml              # RSS 订阅源
├── skills/                   # 原始 Skill 文件拷贝(默认,可整目录打包带走)
├── translation_cache.json    # 翻译缓存(原文 MD5 → 译文,建议提交到仓库)
├── requirements.txt
├── .gitignore
├── .github/workflows/sync.yml  # 自动同步工作流
└── README.md
```

---

## ⚙️ 配置:`config.json`

```json
{
  "skills": [
    "https://github.com/affaan-m/ECC/tree/main/docs/ja-JP/skills/dart-flutter-patterns",
    "https://github.com/anthropics/skills/tree/main/skills/frontend-design",
    "https://github.com/obra/superpowers/tree/main/skills"
  ],
  "skills_dir": "skills",
  "skill_tags": {
    "https://github.com/obra/superpowers/tree/main/skills": ["需求探索", "创意规划", "头脑风暴", "工作流"]
  }
}
```

### 支持的字段

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `skills` | ✅ | GitHub URL 字符串数组 |
| `skills_dir` | ❌ | 原始 Skill 拷贝目录,默认 `"skills"`;设 `null` / `""` / `false` 关闭拷贝 |
| `skill_tags` | ❌ | URL → 标签数组的映射,**自动维护**(见「标签系统」),也可手动覆盖 |

### 支持的 URL 形态

| 形态 | 说明 |
| --- | --- |
| `https://github.com/user/repo` | 整仓,在根目录查找 Skill 文件 |
| `https://github.com/user/repo/tree/branch/path/to/skill` | 指定分支的子路径(稀疏检出) |
| `https://github.com/user/repo/blob/branch/path/to/skill.md` | 同上,blob 形式 |
| `https://github.com/user/repo.git` | 带 `.git` 后缀亦可 |

> 分支默认 `main`;URL 中 `/tree/` 或 `/blob/` 后第一段为分支名。若指定分支不存在,脚本自动回退到仓库默认分支。

### Skill 文件查找规则

优先匹配(大小写不敏感):`SKILL.md` / `skill.yaml` / `skill.yml` / `skill.json`;
若无,则取子路径下第一个支持扩展名(`.md/.yaml/.yml/.json/.txt`)的文件;
description 支持 YAML frontmatter(Markdown)、纯 YAML、JSON;提取失败时用文件名兜底。

---

## 🔄 同步流程(`scripts/sync.py`)

对 `config.json` 中的每个 URL:

1. **解析 URL**:仓库地址 / 子路径 / 分支
2. **稀疏检出**:子路径非空 → `--sparse` + `sparse-checkout set`;为空 → 整仓 `--depth 1`
3. **查找 Skill 文件**并提取 `description`
4. **翻译为中文**(带缓存),失败回退原文
5. **自动打标签**(见「标签系统」)
6. **拷贝原始 Skill 目录**到 `skills/<name>/`(重名自动加 `-2` 序号,不含 `.git`)
7. 生成元数据条目:`name` / `description` / `description_zh` / `source_url` / `commit` / `file` / `branch` / `tags`

最后统一写入 `public/skills.json`、生成 `public/feed.xml`,把 `site/` 静态文件复制到 `public/`,并把新 URL 的标签自动写回 `config.json`。

**错误处理**:单个 URL 失败(解析/拉取/提取)会跳过并打印日志,不影响其他条目;`skills.json` 只包含成功条目。

---

## 🏷️ 标签系统

每个 Skill 生成 **1–6 个标签**,按准确度采用三层策略:

1. **frontmatter `tags` 字段**(最准确,直接采用)
2. **双语功能词典**(标签全部为中文,共 24 类):人工智能 / 编程开发 / 前端开发 / 后端开发 / 界面设计 / Python 开发 / Flutter 开发 / 移动开发 / 软件测试 / 版本控制 / 数据处理 / 机器学习 / 写作 / 翻译 / 研究 / 自动化 / 运维部署 / 安全 / 文档 / 游戏开发 / 营销 / 区块链 / 物联网
3. **技术专有名词提取**:从 description 抓取大写开头的技术栈名(如 `GoRouter`、`BLoC`、`Riverpod`、`FastAPI`),自动过滤停用词与通用缩写(API / SQL / HTML 等);与中文主题重叠的专名(如 `Flutter` vs `Flutter 开发`)自动去重

### `skill_tags` 自动维护

每次同步,新 URL 的自动标签会**自动写回** `config.json` 的 `skill_tags`(仅新增缺失的 URL,**不覆盖**你手动改过的标签),由 CI 一并提交。所以你只需要维护 `skills` 列表;想微调某个 Skill 的标签,直接改 `config.json` 里对应 URL 的数组:

```json
{
  "skills": ["https://github.com/user/repo/tree/main/skills/foo"],
  "skill_tags": {
    "https://github.com/user/repo/tree/main/skills/foo": ["移动开发", "架构模式"]
  }
}
```

> 想完全回归自动标签,删除整个 `skill_tags` 键即可。

---

## 📦 原始 Skill 拷贝(`skills_dir`)

同步时把每个 Skill **所在目录完整拷贝**到本地(不含 `.git`),方便一次性拉取收藏:

- 默认 `skills/`,每个 Skill 一个子目录;重名自动追加序号(`skills-2`)
- 通过 `config.json` 的 `skills_dir` 指定任意文件夹(绝对/相对路径均可),或环境变量 `SKILLS_DIR`
- 该目录由脚本**完全管理**(每次运行先清空再重建),请勿手动放文件

---

## 📡 RSS 订阅

脚本生成 `public/feed.xml`(RSS 2.0,每条含名称 / 来源链接 / 中文描述 / 标签),首页顶部有「📡 订阅 RSS」按钮,`<head>` 中已声明 `<link rel="alternate" type="application/rss+xml">`。

- 部署后完整订阅地址:`https://<你的-pages-域名>/feed.xml`
- 本地预览:`http://localhost:8000/public/feed.xml`
- 也可订阅仓库更新:`https://github.com/<owner>/<repo>/commits/main.atom`

---

## 🖥️ 前端功能

- **卡片网格**:名称、原始描述、中文描述(高亮块)、来源链接、commit 短哈希、文件路径
- **标签徽章**:每张卡片展示标签,点击即筛选
- **标签筛选栏**:顶部汇总全部标签(带数量),点击筛选、再点取消,激活态高亮
- **模糊搜索**:按名称 / 描述 / 中文描述 / 标签 / 来源模糊匹配,实时过滤
- **数量统计**:显示「筛选后数量 / 总数」
- **安全性**:全部 `textContent` 渲染,天然转义,无 XSS 风险
- **响应式**:移动端单列,桌面端自适应网格

---

## 💬 翻译与缓存

- 翻译:`deep-translator` 的 `GoogleTranslator`(免费,无需 API Key),源语言自动检测,目标 `zh-CN`
- 缓存:原文 MD5 → 译文,存于 `translation_cache.json`;**重复运行不重复调用翻译接口**
- 失败回退:网络不通 / 超时时回退为原文,且**不写入缓存**,下次重试
- 强制重翻:删除 `translation_cache.json` 后运行即可

---

## 🤖 自动化(GitHub Actions)

`.github/workflows/sync.yml` 触发时机:

- `push` 到 `main` 且修改了 `config.json`
- 每日 UTC 03:00 定时
- 手动触发(仓库 Actions 页 → **Run workflow**)

流程:检出 → 安装依赖 → `python scripts/sync.py` → 自动提交 `public/`、`skills/`、`translation_cache.json`、`config.json` 的变更回 `main`。

> 提交/推送使用内置 `GITHUB_TOKEN` 自写步骤,不依赖任何第三方 action(无 Node 20 弃用警告)。

---

## ☁️ 部署到 Cloudflare Pages

1. 将仓库推送到 GitHub;
2. Cloudflare Dashboard → **Workers & Pages** → **Create → Pages → Connect to Git**;
3. 选择本仓库,配置:
   - **Build command**:留空(或 `echo "No build required"`)
   - **Build output directory**:`public`
4. 保存后,每次 `main` 更新(含 GitHub Actions 的自动提交)自动重新部署。

---

## 🧪 离线 / 无网测试

脚本内置环境变量钩子,不影响生产默认行为:

```bash
# 1) 允许任意 git 地址(本地仓库端到端测试):
#    格式 git-url#子路径@分支
set SKILLS_ALLOW_ANY_GIT=1
python scripts/sync.py

# 2) 使用假翻译器(验证缓存与回退逻辑,不调用 Google 接口)
set SKILLS_TRANSLATOR=mock
python scripts/sync.py

# 3) 指定其他配置文件(默认根目录 config.json)
set SKILLS_CONFIG=D:\path\to\my-config.json
python scripts/sync.py

# 4) 指定拷贝目录(覆盖 config.json 的 skills_dir)
set SKILLS_DIR=my-skills
python scripts/sync.py
```

---

## ❓ 常见问题

- **某个 URL 拉取失败 / 没找到 Skill 文件?** 该条目被跳过并打印日志,不影响其他条目;可在 Actions 日志或本地终端查看原因。
- **页面空白?** 请通过 HTTP 访问(本地 `python -m http.server` 或 Pages 域名),不要直接双击 `index.html`(`file://` 下 fetch 被 CORS 拦截,页面会给出提示)。
- **看不到最新内容?** 静态资源可能被浏览器/CDN 缓存,`Ctrl+F5` 强制刷新;页面已带 `no-cache` 声明。
- **标签不是想要的?** 在 `config.json` 的 `skill_tags` 里给对应 URL 手动指定标签(会覆盖自动标签并持久保留)。
- **想全部重新翻译?** 删除 `translation_cache.json` 后运行。
- **GitHub Actions 失败?** 常见于网络波动导致个别仓库拉取失败(条目被跳过,不影响整体);可手动 `Run workflow` 重试。
- **只支持 GitHub 仓库 URL**,其他平台暂不支持。

---

## 📄 技术约束

- Python 3.10+(用系统 `git` 命令,`subprocess` 调用,无 GitPython 依赖)
- 统一 UTF-8 编码;输出日志带 `[sync]` 前缀便于排查
- 幂等:重复运行结果一致(除 commit 可能更新);`skills/` 与 `public/` 由脚本完全管理
- 前端零依赖(纯 HTML/CSS/JS),数据预生成于 JSON,无需后端
