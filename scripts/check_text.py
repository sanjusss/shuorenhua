#!/usr/bin/env python3
"""中文文本「不说人话」检查器。

供各类 AI 编程 agent 在生成或修改 Markdown 文档后运行，检查四类问题：
①生造词/禁用词（banned_terms.tsv，字面匹配，分 block/warn 两级）
②禁用句式（banned_patterns.txt，逐条正则匹配）
③超长句（CJK 字数超过阈值，默认 60）
④中英混杂（与中文字符相邻出现、且不在 en_whitelist.txt 白名单的英文词）

数据文件默认位于脚本所在目录的 ../data/，可用 --data-dir 覆盖；
数据文件缺失时打印警告并跳过对应检查，不会崩溃。

用法示例：
    python3 check_text.py a.md b.md        # 检查文件
    python3 check_text.py --stdin < a.md   # 检查标准输入，路径显示为 <stdin>
    python3 check_text.py --self-test      # 运行内置自检

退出码：有 BLOCK 命中为 1，否则为 0；--exit-zero 强制为 0。
"""
import argparse
import re
import sys
from pathlib import Path

# 四类检查的类别名（用于输出与统计）
CAT_TERM = "生造词"
CAT_PAT = "禁用句式"
CAT_LONG = "长句"
CAT_MIX = "中英混杂"

FENCE_RE = re.compile(r"^\s*(```|~~~)")              # fenced code block 边界行
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")            # 行内代码 `...`
URL_RE = re.compile(r"https?://\S+")                 # URL
WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.+\-]*")   # 英文词
SENT_SPLIT_RE = re.compile(r"[。！？；]")            # 中文句末切分标点
CJK_IDEO_RE = re.compile(r"[\u4e00-\u9fff]")         # CJK 汉字（长句计数用）
CJK_ADJ_RE = re.compile(r"[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]")  # 汉字及全角标点


def _blank(match):
    """把命中片段替换为等长空格，保持行号与列位置不变。"""
    return " " * (match.end() - match.start())


def preprocess(lines):
    """剔除 fenced code block、行内代码、URL，返回逐行空格化结果。

    fenced code block 通过 ``` 或 ~~~ 边界行切换状态，块内整行替换为空格；
    行内代码与 URL 只替换命中片段本身。
    """
    out, in_fence = [], False
    for line in lines:
        if FENCE_RE.match(line):
            in_fence = not in_fence
            out.append(" " * len(line))
        elif in_fence:
            out.append(" " * len(line))
        else:
            line = INLINE_CODE_RE.sub(_blank, line)
            out.append(URL_RE.sub(_blank, line))
    return out


class Rules:
    """从数据目录加载的检查规则集合。"""

    def __init__(self):
        self.terms = []       # [(词, 级别, 建议替换)]
        self.patterns = []    # [编译后的正则]
        self.whitelist = set()

    def load(self, data_dir, quiet=False):
        """读取三个数据文件；缺失时打印警告（quiet 时静默）并跳过对应检查。"""
        self._load_terms(data_dir / "banned_terms.tsv", quiet)
        self._load_patterns(data_dir / "banned_patterns.txt", quiet)
        self._load_whitelist(data_dir / "en_whitelist.txt", quiet)

    def _load_terms(self, path, quiet):
        if not path.is_file():
            if not quiet:
                print(f"警告: 缺失 {path}，跳过生造词/禁用词检查", file=sys.stderr)
            return
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            cols = line.split("\t")
            if len(cols) < 4 or cols[1] not in ("block", "warn"):
                print(f"警告: {path.name} 条目格式不符（需四列 Tab 分隔，级别为 block/warn）: {raw}",
                      file=sys.stderr)
                continue
            self.terms.append((cols[0], cols[1], cols[2]))

    def _load_patterns(self, path, quiet):
        if not path.is_file():
            if not quiet:
                print(f"警告: 缺失 {path}，跳过禁用句式检查", file=sys.stderr)
            return
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            try:
                self.patterns.append(re.compile(line))
            except re.error as exc:
                print(f"警告: {path.name} 正则无法编译，已跳过: {line} ({exc})", file=sys.stderr)

    def _load_whitelist(self, path, quiet):
        if not path.is_file():
            if not quiet:
                print(f"警告: 缺失 {path}，中英混杂检查将报出所有英文词", file=sys.stderr)
            return
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip().lower()
            if line and not line.startswith("#"):
                self.whitelist.add(line)


def check_line(line, rules, max_len):
    """对预处理后的一行执行四类检查，返回 [(级别, 类别, 命中, 建议)]。"""
    issues = []
    # ① 生造词/禁用词：字面匹配，每行每词只报一次
    for word, level, advice in rules.terms:
        if word in line:
            issues.append((level, CAT_TERM, word, advice))
    # ② 禁用句式：逐条正则匹配，每行每条只报一次
    for pat in rules.patterns:
        m = pat.search(line)
        if m and m.group(0):
            issues.append(("block", CAT_PAT, m.group(0)[:30], "删除或改写该句式"))
    # ③ 超长句：按 。！？；切分（换行天然切分），CJK 汉字数超阈值即报
    for seg in SENT_SPLIT_RE.split(line):
        seg = seg.strip()
        n = len(CJK_IDEO_RE.findall(seg))
        if n > max_len:
            shown = re.sub(r"\s+", " ", seg)[:30]
            shown += "…" if len(seg) > 30 else ""
            issues.append(("warn", CAT_LONG, shown, f"该句含 {n} 个汉字，超过 {max_len}，请按语义拆分短句"))
    # ④ 中英混杂：英文词与最近的中文（汉字或全角标点）相邻且不在白名单
    seen = set()
    for m in WORD_RE.finditer(line):
        word = m.group(0)
        if word.lower() in rules.whitelist or word in seen:
            continue
        i = m.start() - 1
        while i >= 0 and line[i] in " \t":
            i -= 1
        j = m.end()
        while j < len(line) and line[j] in " \t":
            j += 1
        near_cjk = (i >= 0 and CJK_ADJ_RE.match(line[i])) or (j < len(line) and CJK_ADJ_RE.match(line[j]))
        if near_cjk:
            seen.add(word)
            issues.append(("warn", CAT_MIX, word, "不在白名单：文件名/标识符/命令名可用反引号包裹（行内代码不检查）；术语首次出现时加中文解释，或改用通行中文说法；不要自行加入白名单，确属通行术语请向用户建议"))
    return issues


def check_text(text, rules, max_len):
    """对整段文本执行检查，返回 [(行号, 级别, 类别, 命中, 建议)]。"""
    issues = []
    for no, line in enumerate(preprocess(text.split("\n")), 1):
        for level, cat, hit, advice in check_line(line, rules, max_len):
            issues.append((no, level, cat, hit, advice))
    return issues


def print_stats(stats):
    """打印各类命中统计。stats 为 {(级别, 类别): 数量}。"""
    if not stats:
        print("检查完成: 无命中")
        return
    print("---- 统计 ----")
    block_n = warn_n = 0
    for level in ("block", "warn"):
        for cat in (CAT_TERM, CAT_PAT, CAT_LONG, CAT_MIX):
            n = stats.get((level, cat), 0)
            if n:
                print(f"[{level.upper()}][{cat}] {n}")
            if level == "block":
                block_n += n
            else:
                warn_n += n
    print(f"共 {block_n + warn_n} 条命中: BLOCK {block_n}, WARN {warn_n}")


def run_self_test(script_dir):
    """内置自检：用临时数据目录与样例文本验证四类检查及剔除逻辑。"""
    top_dir = script_dir.parent
    data_dir = top_dir / "data" / ".selftest_tmp"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "banned_terms.tsv").write_text(
        "收束\tblock\t收尾\t自检用生造词\n兜底\twarn\t默认\t自检用口语词\n", encoding="utf-8")
    (data_dir / "banned_patterns.txt").write_text(
        "先给个判断\n如果你需要.{0,4}我还可以\n", encoding="utf-8")
    (data_dir / "en_whitelist.txt").write_text("redis\npid\n", encoding="utf-8")
    sample = "\n".join([
        "第一段先给个判断，这里把流程收束之后封存。",
        "这一句特别长：" + "数" * 70 + "然后结束。",
        "启用 finalizer 兜底，避免对象泄漏。",
        "服务用 redis 和 pid 记录状态。",
        "```text",
        "代码块里的 收束 ghostword 不检查",
        "```",
        "行内 `inlineghost 收束` 与 http://example.com/urlghost 一并跳过。",
    ])
    rules = Rules()
    rules.load(data_dir, quiet=True)
    issues = check_text(sample, rules, 60)

    def has(level, cat, hit=None):
        return any(lv == level and c == cat and (hit is None or h == hit)
                   for _, lv, c, h, _ in issues)

    checks = [
        ("生造词 block 命中「收束」", has("block", CAT_TERM, "收束")),
        ("生造词 warn 命中「兜底」", has("warn", CAT_TERM, "兜底")),
        ("禁用句式命中「先给个判断」", has("block", CAT_PAT, "先给个判断")),
        ("超长句告警", has("warn", CAT_LONG)),
        ("中英混杂命中 finalizer", has("warn", CAT_MIX, "finalizer")),
        ("白名单 redis 不报", not has("warn", CAT_MIX, "redis")),
        ("白名单 pid 不报", not has("warn", CAT_MIX, "pid")),
        ("代码块内英文不报混杂", not has("warn", CAT_MIX, "ghostword")),
        ("行内代码内英文不报混杂", not has("warn", CAT_MIX, "inlineghost")),
        ("URL 中英文不报混杂", not has("warn", CAT_MIX, "urlghost")),
        ("「收束」在代码块/行内代码外只报一次",
         sum(1 for _, lv, c, h, _ in issues
             if lv == "block" and c == CAT_TERM and h == "收束") == 1),
    ]
    failed = 0
    for name, ok in checks:
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
        failed += 0 if ok else 1
    # 清理自检临时目录
    for f in data_dir.iterdir():
        f.unlink()
    data_dir.rmdir()
    if not any((top_dir / "data").iterdir()):
        (top_dir / "data").rmdir()
    print(f"self-test: {len(checks) - failed}/{len(checks)} 项通过")
    return 1 if failed else 0


def build_parser():
    parser = argparse.ArgumentParser(
        description="中文文本「不说人话」检查器：生造词、禁用句式、超长句、中英混杂")
    parser.add_argument("files", nargs="*", help="待检查的文本文件（可多个）")
    parser.add_argument("--stdin", action="store_true", help="从标准输入读取，路径显示为 <stdin>")
    parser.add_argument("--data-dir", type=Path, default=None,
                        help="数据目录（默认为脚本所在目录下 ../data）")
    parser.add_argument("--max-len", type=int, default=60,
                        help="超长句的 CJK 汉字数阈值（默认 60）")
    parser.add_argument("--self-test", action="store_true", help="运行内置自检后退出")
    parser.add_argument("--exit-zero", action="store_true", help="即使有 BLOCK 命中也返回退出码 0")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    script_dir = Path(__file__).resolve().parent
    if args.self_test:
        return run_self_test(script_dir)
    if not args.files and not args.stdin:
        parser.error("请提供待检查文件，或使用 --stdin 读取标准输入")

    rules = Rules()
    rules.load(args.data_dir or script_dir.parent / "data")

    sources, read_fail = [], False
    if args.stdin:
        sources.append(("<stdin>", sys.stdin.read()))
    for p in args.files:
        path = Path(p)
        if not path.is_file():
            print(f"错误: 无法读取文件: {p}", file=sys.stderr)
            read_fail = True
            continue
        sources.append((str(p), path.read_text(encoding="utf-8", errors="replace")))

    stats, block_total = {}, 0
    for path, text in sources:
        for no, level, cat, hit, advice in check_text(text, rules, args.max_len):
            print(f"{path}:{no}: [{level.upper()}][{cat}] {hit} -> {advice}")
            stats[(level, cat)] = stats.get((level, cat), 0) + 1
            if level == "block":
                block_total += 1
    print_stats(stats)

    if read_fail or (block_total and not args.exit_zero):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
