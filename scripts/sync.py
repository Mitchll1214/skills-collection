#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
skills-collection 同步脚本
==========================

读取根目录 config.json 中的 GitHub URL 列表,逐个:
  1. 解析 URL(仓库地址 / 子路径 / 分支)
  2. 稀疏检出(最小化拉取量)
  3. 查找 Skill 文件并提取 description
  4. 翻译为中文(deep-translator,带 MD5 缓存)
  5. 生成 public/skills.json,并将 site/ 静态文件复制到 public/

用法:
    python scripts/sync.py

测试钩子(不影响生产默认行为):
    SKILLS_ALLOW_ANY_GIT=1  允许任意 git 地址,格式: git-url#子路径@分支
                            (便于用本地仓库做端到端测试)
    SKILLS_TRANSLATOR=mock  使用假翻译器(离线验证缓存/回退逻辑)
"""

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(os.environ.get("SKILLS_CONFIG", ROOT / "config.json"))
SITE_DIR = ROOT / "site"
PUBLIC_DIR = ROOT / "public"
CACHE_PATH = ROOT / "translation_cache.json"
SKILLS_JSON = PUBLIC_DIR / "skills.json"

# 优先匹配的 Skill 文件名(大小写不敏感)
SKILL_FILE_NAMES = (
    "SKILL.md", "skill.md",
    "SKILL.yaml", "skill.yaml", "SKILL.yml", "skill.yml",
    "SKILL.json", "skill.json",
)
# 遍历兜底时支持的文件扩展名
SUPPORTED_EXTS = {".md", ".yaml", ".yml", ".json", ".txt"}

# https://github.com/{user}/{repo}(.git)?[/tree|/blob/{branch}[/sub/path]][?...]
GITHUB_URL_RE = re.compile(
    r"^https?://(?:www\.)?github\.com/"
    r"(?P<user>[^/?#]+)/(?P<repo>[^/?#]+)(?:\.git)?"
    r"(?:/(?P<kind>tree|blob)/(?P<branch>[^/?#]+)(?:/(?P<path>[^?#]*))?)?[^?#]*$"
)


def log(msg: str) -> None:
    print(f"[sync] {msg}", flush=True)


# ---------------------------------------------------------------- git 操作

def git(*args: str, cwd=None, check: bool = True) -> subprocess.CompletedProcess:
    """调用系统 git 命令,失败时抛出 RuntimeError。"""
    proc = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 失败: {proc.stderr.strip() or proc.stdout.strip()}")
    return proc


def fetch_repo(repo_url: str, subpath: str, branch: str, dest: Path) -> None:
    """稀疏检出目标仓库/子路径到 dest。

    - 子路径为空:整仓 clone(--depth 1)
    - 子路径非空:--filter=blob:none --sparse + sparse-checkout set
    若指定分支不存在,自动回退到仓库默认分支。
    """
    def clone_once(with_branch: bool) -> None:
        args = ["clone", "--depth", "1"]
        if subpath:
            args += ["--filter=blob:none", "--sparse"]
        if with_branch:
            args += ["--branch", branch]
        git(*args, repo_url, str(dest))

    try:
        clone_once(True)
    except RuntimeError:
        log(f"  分支 '{branch}' 检出失败,回退到仓库默认分支")
        force_rmtree(dest)  # 清理首次失败可能残留的目录,避免二次 clone 冲突
        if dest.exists():
            raise RuntimeError(f"无法清理首次克隆的残留目录 {dest},放弃重试")
        clone_once(False)

    if subpath:
        git("sparse-checkout", "set", subpath, cwd=dest)
        try:
            git("checkout", branch, cwd=dest)
        except RuntimeError:
            pass  # 默认分支场景无需切换


# ---------------------------------------------------------------- URL 解析

def parse_github_url(raw: str) -> dict:
    m = GITHUB_URL_RE.match(raw)
    if not m:
        raise ValueError(f"不支持的 URL(目前仅支持 GitHub 仓库): {raw}")
    user, repo, kind, branch, path = m.groups()
    if repo.endswith(".git"):
        repo = repo[:-4]
    subpath = path.strip("/") if path else ""
    branch = branch or "main"
    repo_url = f"https://github.com/{user}/{repo}.git"
    name_hint = subpath.rstrip("/").split("/")[-1] if subpath else repo
    return {
        "repo_url": repo_url,
        "subpath": subpath,
        "branch": branch,
        "name_hint": name_hint,
        "raw": raw,
    }


def parse_any_git_url(raw: str) -> dict:
    """测试/高级模式:任意 git 地址,格式 `git-url#子路径@分支`。"""
    base, subpath, branch = raw, "", "main"
    if "#" in raw:
        base, frag = raw.split("#", 1)
        if "@" in frag:
            subpath, branch = frag.rsplit("@", 1)
        else:
            subpath = frag
    base = base.strip()
    if not base:
        raise ValueError(f"无效的 git 地址: {raw}")
    subpath = subpath.strip("/")
    name_hint = subpath.split("/")[-1] if subpath else base.rstrip("/").split("/")[-1]
    if name_hint.endswith(".git"):
        name_hint = name_hint[:-4]
    return {
        "repo_url": base,
        "subpath": subpath,
        "branch": branch,
        "name_hint": name_hint,
        "raw": raw,
    }


def parse_url(raw: str) -> dict:
    if os.environ.get("SKILLS_ALLOW_ANY_GIT") == "1":
        return parse_any_git_url(raw)
    return parse_github_url(raw)


# ---------------------------------------------------------------- 描述提取

def parse_skill_file(path: Path):
    """解析 Skill 文件,返回 dict(YAML frontmatter / 纯 YAML / JSON),失败返回 None。"""
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None
    if path.suffix.lower() in (".yaml", ".yml", ".json"):
        try:
            import yaml
            return yaml.safe_load(text)
        except Exception:
            return None
    # Markdown / txt: 解析 --- 开头的 YAML frontmatter
    if text.lstrip("\ufeff").startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            try:
                import yaml
                return yaml.safe_load(parts[1])
            except Exception:
                return None
    return None


def extract_description(path: Path) -> str | None:
    data = parse_skill_file(path)
    if isinstance(data, dict):
        for key in ("description", "Description", "DESCRIPTION"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def find_skill_file(subdir: Path) -> Path | None:
    """在检出目录中查找 Skill 文件:优先约定文件名,否则取第一个支持的文件。"""
    for name in SKILL_FILE_NAMES:
        p = subdir / name
        if p.is_file():
            return p
    for p in sorted(subdir.rglob("*")):
        if ".git" in p.parts:
            continue
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS:
            return p
    return None


# ---------------------------------------------------------------- 翻译与缓存

def build_translator():
    """返回 (translate_fn, None)。翻译失败时 translate_fn 抛出异常或返回 None。"""
    mode = os.environ.get("SKILLS_TRANSLATOR", "google")
    if mode == "mock":
        def mock_translate(text: str) -> str:
            log("  [mock] 调用翻译")
            return f"[zh] {text}"
        return mock_translate
    try:
        from deep_translator import GoogleTranslator
    except ImportError:
        log("警告: 未安装 deep-translator,翻译不可用,将回退为原文。请先 pip install -r requirements.txt")
        return None
    translator = GoogleTranslator(source="auto", target="zh-CN")

    def translate(text: str) -> str:
        # Google 免费接口单次长度有限制,超长截断
        return translator.translate(text[:4500])

    return translate


def load_cache() -> dict:
    if CACHE_PATH.is_file():
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            log(f"  缓存文件损坏,将重新翻译: {e}")
    return {}


def save_cache(cache: dict) -> None:
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"已写入翻译缓存: {CACHE_PATH} ({len(cache)} 条)")


def translate_with_cache(cache: dict, translate, text: str) -> tuple[str, bool]:
    """按原文 MD5 缓存翻译结果,返回 (译文, 是否命中缓存)。失败时回退原文。"""
    key = hashlib.md5(text.encode("utf-8")).hexdigest()
    if key in cache:
        log(f"  翻译缓存命中: {key[:8]}")
        return cache[key], True
    if translate is None:
        return text, False
    try:
        result = translate(text)
    except Exception as e:
        log(f"  翻译失败,回退原文: {e}")
        return text, False
    result = str(result).strip()
    if not result:
        return text, False
    cache[key] = result
    log(f"  翻译完成(缓存 {key[:8]})")
    return result, False


# ---------------------------------------------------------------- 原始 Skill 拷贝

def force_rmtree(path: Path) -> None:
    """删除目录,先清除只读属性(Windows 下 git 的 pack 文件为只读)。"""
    if not path.exists():
        return
    for root, dirs, files in os.walk(path):
        for name in dirs + files:
            try:
                os.chmod(os.path.join(root, name), stat.S_IWRITE)
            except OSError:
                pass

    def _onerror(func, p, exc_info):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except OSError:
            pass

    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_onerror)
    else:
        shutil.rmtree(path, onerror=_onerror)


def copy_skill_dir(src: Path, dest: Path, name: str, used_names: set) -> Path:
    """把 Skill 所在目录完整拷贝到 dest/<name>/,名称冲突时自动追加序号。"""
    dest.mkdir(parents=True, exist_ok=True)
    candidate, i, target = name, 2, dest / name
    while candidate in used_names or target.exists():
        candidate = f"{name}-{i}"
        target = dest / candidate
        i += 1
    used_names.add(candidate)
    shutil.copytree(src, target, ignore=shutil.ignore_patterns(".git"))
    return target


# ---------------------------------------------------------------- 标签提取

# 关键词标签规则:标签 -> 匹配关键词(description 小写包含即命中)
TAG_KEYWORDS = {
    "ai": ["claude", "anthropic", "llm", "gpt", "openai", "agent", "ai "],
    "coding": ["code", "coding", "programming", "代码", "编码", "开发"],
    "frontend": ["frontend", "front-end", "web", "html", "css", "javascript",
                  "typescript", "react", "vue", "ui"],
    "design": ["design", "界面", "设计", "ux"],
    "backend": ["backend", "server", "api", "database", "数据库"],
    "python": ["python", "django", "flask"],
    "dart": ["dart", "flutter"],
    "test": ["test", "testing", "测试", "qa"],
    "git": ["git", "github", "repo"],
    "data": ["data", "sql", "analytics", "数据", "分析"],
    "writing": ["writing", "write", "写作", "文案", "内容"],
    "translate": ["translat", "翻译", "language", "i18n"],
    "research": ["research", "search", "研究", "搜索"],
    "automation": ["automation", "workflow", "自动", "工作流"],
    "mobile": ["mobile", "android", "ios", "移动"],
}
MAX_TAGS = 4


def extract_tags(skill_file: Path, description: str) -> list[str]:
    """为 Skill 打标签:优先读 frontmatter 的 tags 字段,否则按关键词库从 description 提取。"""
    data = parse_skill_file(skill_file)
    if isinstance(data, dict):
        raw = data.get("tags") or data.get("Tags")
        if isinstance(raw, list):
            tags = [str(t).strip() for t in raw if str(t).strip()]
            if tags:
                return tags[:MAX_TAGS]
        if isinstance(raw, str):
            tags = [t.strip() for t in raw.replace("，", ",").split(",") if t.strip()]
            if tags:
                return tags[:MAX_TAGS]
    if not description:
        return []
    low = description.lower()
    tags = [tag for tag, kws in TAG_KEYWORDS.items() if any(k in low for k in kws)]
    return tags[:MAX_TAGS]


# ---------------------------------------------------------------- 主流程

def process_url(url: str, cache: dict, translate, copy_dest: Path | None = None,
                used_names: set | None = None) -> dict:
    info = parse_url(url)
    log(f"[{info['name_hint']}] 拉取 {info['repo_url']}"
        f" (分支={info['branch']}, 子路径={info['subpath'] or '/'})")
    tmp = Path(tempfile.mkdtemp(prefix="skills-"))
    try:
        fetch_repo(info["repo_url"], info["subpath"], info["branch"], tmp)
        root = tmp / info["subpath"] if info["subpath"] else tmp
        if not root.is_dir():
            raise RuntimeError(f"子路径不存在: {info['subpath']}")
        skill_file = find_skill_file(root)
        if skill_file is None:
            raise RuntimeError(f"在 {info['subpath'] or '根目录'} 下未找到 Skill 文件")
        commit = git("rev-parse", "HEAD", cwd=tmp).stdout.strip()

        description = extract_description(skill_file)
        if not description:
            description = skill_file.stem
            log(f"  未提取到 description,使用文件名兜底: {description}")
        else:
            log(f"  提取到 description({len(description)} 字符)")
        description_zh, _ = translate_with_cache(cache, translate, description)
        tags = extract_tags(skill_file, description)

        if copy_dest is not None:
            target = copy_skill_dir(skill_file.parent, copy_dest,
                                    info["name_hint"], used_names)
            log(f"  已拷贝原始 Skill 到 {target.relative_to(ROOT)}")

        file_rel = skill_file.relative_to(root).as_posix()
        item = {
            "name": info["name_hint"],
            "description": description,
            "description_zh": description_zh,
            "source_url": info["raw"],
            "commit": commit,
            "file": file_rel,
            "branch": info["branch"],
            "tags": tags,
        }
        log(f"  成功: name={item['name']}, commit={commit[:7]}, file={file_rel}")
        return item
    finally:
        force_rmtree(tmp)


def write_feed(items: list[dict]) -> None:
    """生成 RSS 2.0 订阅源 public/feed.xml(首页订阅按钮指向它)。"""
    import xml.etree.ElementTree as ET

    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "Skills Collection"
    ET.SubElement(channel, "link").text = "https://github.com/Mitchll1214/skills-collection"
    ET.SubElement(channel, "description").text = "个人收藏的 AI Skill 清单,自动同步更新"
    ET.SubElement(channel, "generator").text = "skills-collection/sync.py"
    for s in items:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = s.get("name") or "(未命名)"
        ET.SubElement(item, "link").text = s.get("source_url") or ""
        guid = s.get("source_url") or s.get("commit") or ""
        ET.SubElement(item, "guid", {"isPermaLink": "false"}).text = guid
        desc = s.get("description") or ""
        if s.get("description_zh"):
            desc += f"\n\n中文: {s['description_zh']}"
        if s.get("tags"):
            desc += f"\n标签: {', '.join(s['tags'])}"
        ET.SubElement(item, "description").text = desc
    ET.ElementTree(rss).write(PUBLIC_DIR / "feed.xml", encoding="utf-8", xml_declaration=True)
    log(f"已生成订阅源 {PUBLIC_DIR / 'feed.xml'}")


def copy_site() -> None:
    if SITE_DIR.is_dir():
        for p in SITE_DIR.iterdir():
            if p.is_file():
                shutil.copy2(p, PUBLIC_DIR / p.name)


def main() -> int:
    if not CONFIG_PATH.is_file():
        log(f"找不到配置文件: {CONFIG_PATH}")
        return 1
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        log(f"config.json 解析失败: {e}")
        return 1
    urls = config.get("skills")
    if not isinstance(urls, list):
        log("config.json 中的 skills 必须是一个字符串数组")
        return 1

    cache = load_cache()
    translate = build_translator()
    items, failures = [], []

    # 原始 Skill 拷贝目录:config.json 的 "skills_dir" 字段或环境变量 SKILLS_DIR,
    # 默认根目录下 skills/。显式设为 null / "" / false 可关闭拷贝。
    if "skills_dir" in config:
        raw_dir = config["skills_dir"]
    else:
        raw_dir = os.environ.get("SKILLS_DIR", "skills")
    copy_dest = None
    used_names = None
    if raw_dir not in (None, "", False):
        copy_dest = Path(str(raw_dir))
        if not copy_dest.is_absolute():
            copy_dest = ROOT / copy_dest
        try:
            copy_dest = copy_dest.resolve()
        except OSError:
            pass
        # 路径防护:禁止指向项目根/祖先或关键目录,避免误清空项目
        if copy_dest == ROOT or copy_dest in ROOT.parents \
                or copy_dest in (ROOT / "public", ROOT / "site", ROOT / "scripts"):
            log(f"[ERROR] skills_dir 路径不合法(会清空项目关键目录): {raw_dir}")
            return 1
        if copy_dest.exists():
            log(f"清空拷贝目录 {copy_dest}(该目录由脚本完全管理)")
            force_rmtree(copy_dest)
        copy_dest.mkdir(parents=True, exist_ok=True)
        used_names = set()

    for i, url in enumerate(urls, 1):
        log(f"[{i}/{len(urls)}] 处理: {url}")
        try:
            items.append(process_url(url, cache, translate, copy_dest, used_names))
        except Exception as e:
            failures.append((url, str(e)))
            log(f"[ERROR] 跳过该条目: {e}")

    # 手动功能标签:config.json 的 "skill_tags"(URL -> 标签数组)覆盖自动标签,
    # 便于针对每个收藏的 Skill 按其实际功能打上更贴切的标签。
    manual_tags = config.get("skill_tags")
    if isinstance(manual_tags, dict):
        for item in items:
            tags = manual_tags.get(item["source_url"])
            if isinstance(tags, list):
                cleaned = [str(t).strip() for t in tags if str(t).strip()]
                if cleaned:
                    item["tags"] = cleaned[:MAX_TAGS]

    save_cache(cache)

    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    SKILLS_JSON.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"已写入 {SKILLS_JSON} ({len(items)} 条)")
    write_feed(items)
    copy_site()
    log(f"已将 site/ 静态文件复制到 {PUBLIC_DIR}")

    if failures:
        log(f"完成: 成功 {len(items)}/{len(urls)},失败 {len(failures)} 条:")
        for u, e in failures:
            log(f"  - {u}: {e}")
    else:
        log(f"完成: 全部 {len(items)} 条成功")
    return 0


if __name__ == "__main__":
    sys.exit(main())
