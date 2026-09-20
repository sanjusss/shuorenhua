# 说人话（`shuorenhua`）

给 `AI` 编程助手用的中文写作 `skill`：约束用词、句式和检查流程，让说明、注释、文档第一次读就能看懂。

## 解决什么问题

模型写中文时容易出现这些问题：

- 生造词、比喻过头的说法（例如「`收束`」「`封账`」「`掐死`」）
- 表演式句型（「`先给个判断`」「`真正的问题不在`……」）
- 把代码拟人化（「参数被吃掉」「预算把任务`掐死`」）
- 超长句、中英混杂、指代不清

本 `skill` 提供：

1. `SKILL.md`：写作规则、改写原则、写完后的检查清单  
2. `data/`：禁用词表、禁用句式、英文术语白名单  
3. `scripts/check_text.py`：对 Markdown 等文本做机械检查（可接 hook / CI）

## 目录结构

```text
shuorenhua/
├── SKILL.md                 # skill 主说明（agent 加载这份）
├── README.md                # 本文件
├── data/
│   ├── banned_terms.tsv     # 生造词对照（含建议替换）
│   ├── banned_patterns.txt  # 禁用句式正则
│   └── en_whitelist.txt     # 允许直接写在中文里的通行英文词
└── scripts/
    └── check_text.py        # 机械检查脚本（依赖 Python 3 标准库）
```

## 安装

需要本机已安装 Git。检查脚本需要 Python 3，无第三方依赖。

把整个仓库克隆到 `~/.agents/skills/shuorenhua/`，并保证该目录内直接有 `SKILL.md`（不要多套一层文件夹）。

### 个人全局（推荐）

```bash
mkdir -p ~/.agents/skills
git clone https://github.com/sanjusss/shuorenhua.git ~/.agents/skills/shuorenhua
```

兼容从 `~/.agents/skills/` 加载 `skill` 的各类 `agent`（不限于某一家产品）。

### 仅当前项目

```bash
# 在仓库根目录执行
mkdir -p .agents/skills
git clone https://github.com/sanjusss/shuorenhua.git .agents/skills/shuorenhua
```

把项目里的 `.agents/skills/shuorenhua` 提交进 Git 后，同事克隆仓库即可共用，无需各自再装。

### 安装后自检

确认路径正确：

```bash
ls ~/.agents/skills/shuorenhua/SKILL.md
# 项目安装则检查：
# ls .agents/skills/shuorenhua/SKILL.md
```

运行脚本自检：

```bash
python3 ~/.agents/skills/shuorenhua/scripts/check_text.py --self-test
```

然后重启或重新打开你的 `agent`，使 `skill` 被重新发现。

## 使用方式

### 让 `agent` 遵守规则

在对话里点名加载，例如：

- 「按 `shuorenhua` 写」
- 「说人话」
- 「检查文风」

也可以在项目的 `AGENTS.md` 或同类规则文件里写明：写中文前必须加载 `shuorenhua`。

规则全文见 `SKILL.md`。要点是：先写清楚发生了什么，再用直白动词和具体对象；写完后先跑脚本，再做人能判断的语义检查。

### 手动检查文档

```bash
python3 /path/to/shuorenhua/scripts/check_text.py 文档.md 另一份.md
```

输出格式示例：`路径:行号: [LEVEL][类别] 命中 -> 建议`。有 `BLOCK` 时退出码为 1，便于接 CI。

常用参数：

| 参数 | 含义 |
|------|------|
| `--stdin` | 从标准输入读入 |
| `--max-len N` | 超长句汉字数阈值（默认 60） |
| `--exit-zero` | 即使有 `BLOCK` 也返回 0 |
| `--data-dir DIR` | 自定义数据目录 |

## 维护词表

| 文件 | 谁可以改 | 说明 |
|------|----------|------|
| `data/banned_terms.tsv` | 可直接追加 | 四列：词、级别（`block`/`warn`）、建议替换、说明（对应英文等） |
| `data/banned_patterns.txt` | 需使用者同意 | 与 `SKILL.md`「禁止句式」同步 |
| `data/en_whitelist.txt` | 需使用者同意 | 只收通行技术词和知名产品名；人名、项目代号用反引号包裹，不进白名单 |

## 许可

若仓库根目录未附带许可证文件，使用前请与作者确认授权方式。
