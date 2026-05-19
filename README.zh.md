# ops-doc-maintainer

> 让 AI 编码助手能持续维护的主机清单。只记热点 —— 端口、服务、VPN/代理、已装 CLI ——
> 不记噪音 —— CPU、内存、磁盘。Linux + Windows 通吃，一个 skill 搞定。

[English version →](README.md)

---

## 为什么要做这个

如果你让 AI 编码助手在某台机器上装软件、改配置、起服务，几周之后
**没人记得到底动了哪些东西、动在哪里、为什么动**。每开一个新会话都
让 agent 重新跑一遍 `lsof`、`systemctl`、`Get-NetTCPConnection`……
浪费 token，结果还不一致。

`ops-doc-maintainer` 是一个跟在 agent 旁边（Claude Code、Codex、OpenClaw…）
的 skill。它为**当前主机**维护一组小型 Markdown 文件，记录
**当下的热点状态** + **只追加的变更日志**。

它**刻意忽略**低信号信息（OS 版本、CPU、内存、完整磁盘布局、完整进程列表）。
这些东西基本派不上用场，只会让 diff 难读。

## 你最终会得到什么

每台主机一个目录，位于 `~/.ops-doc-maintainer-docs/hosts/<hostname>/`
（Windows 下是另一个路径），大致长这样：

```
hosts/
└── my-workstation/
    ├── index.md          # 入口，附带各文件最近更新时间
    ├── network.md        # 网卡、监听端口、VPN/代理摘要
    ├── services.md       # docker / nginx（Linux）或 services / iis（Windows）
    ├── software.md       # 手工安装的全局 CLI 工具
    ├── postgres.md       # （仅 Linux）连接方式提示，不含数据库内容
    └── changes.md        # 仅追加的有意义变更
```

某次 agent 跑完 `--reason "Configured Clash proxy"` 后，`network.md`
里大概会出现这样的内容：

```markdown
## Listening ports

| Proto | Local | PID | Process |
|---|---|---|---|
| TCP  | 0.0.0.0:7890 | 18412 | clash-windows.exe |
| TCP  | 0.0.0.0:7891 | 18412 | clash-windows.exe |
| TCP  | 127.0.0.1:9090 | 18412 | clash-windows.exe |

## Proxy state

- System proxy: `127.0.0.1:7890` (HTTP + HTTPS)
- TUN adapter: `Mihomo` (10.0.0.1/24)
```

`changes.md` 则追加一行：

```markdown
- 2026-05-19 14:32 — Configured Clash proxy (network)
```

整个产品就这些。

## 安装

### 作为 Claude Code skill

把仓库（或它的 clone）放到 Claude Code 的 skills 目录：

```bash
git clone https://github.com/JasonJarvan/ops-doc-maintainer.git \
  ~/.claude/skills/ops-doc-maintainer
```

`SKILL.md` 的 description 里已经写了平台检测相关的触发词，agent 在你
让它"更新主机文档"时会自动识别并调用。

### 作为 Codex skill

放到你的 `agents/` 或 skills 目录下，引用 `agents/<platform>/openai.yaml`。

### 不接 agent，单独使用

直接跑 dispatcher 就行：

```bash
git clone https://github.com/JasonJarvan/ops-doc-maintainer.git
cd ops-doc-maintainer
python3 scripts/update_ops_docs.py
```

Dispatcher 会自动判断 Linux / macOS / Windows，然后走对应的子目录。

## 平台覆盖

| 领域       | Linux                                  | Windows                                                       |
|------------|----------------------------------------|---------------------------------------------------------------|
| Shell      | bash                                   | Python + PowerShell 子进程                                    |
| 网络       | `ss`、`ip`、`iptables`                 | `Get-NetTCPConnection`、`Get-NetAdapter`、`netsh`             |
| 服务       | `systemctl`                            | `Get-Service`、`Win32_StartupCommand`、计划任务               |
| 包管理     | `apt`、`snap`、`pip`、`uv`             | `winget`、`scoop`、`chocolatey`                               |
| VPN / 代理 | —                                      | Clash、Mihomo、WireGuard、V2Ray 进程 + TUN 适配器检测         |
| 容器       | Docker                                 | Docker Desktop                                                |
| Web 服务器 | Nginx                                  | IIS（可选）                                                   |
| 远程       | SSH                                    | WinRM                                                         |
| SQL        | PostgreSQL（仅连接方式，不含内容）     | **默认不收录**（SQL Server 不在范围内）                       |

## 工作原理

1. `scripts/update_ops_docs.py` 是跨平台入口。它调用 `platform.system()`
   判断系统，然后分别走 `scripts/linux/update_ops_docs.py` 或
   `scripts/windows/update_ops_docs.py`。
2. 平台 updater 按"领域"（network / services / software / …）
   **只读**地采集，每个领域产出结构化数据。
3. 所有领域合并后，根据 docs home 下的 `watchlist.txt` /
   `ignorelist.txt` / `manual-software.txt` 做噪音过滤，写入当前状态
   Markdown 文件。
4. 和上一次相比有**有意义的变化**时，追加一行带时间戳和 `--reason`
   的记录到 `changes.md`。

### 常用命令

```bash
# 全量刷新
python3 scripts/update_ops_docs.py

# 装完软件、只看 software 域
python3 scripts/update_ops_docs.py --reason "Installed PowerToys" --focus software

# 改完代理、只看 network 域
python3 scripts/update_ops_docs.py --reason "Configured Clash proxy" --focus network
```

`--focus` 的合法取值：

- Linux：`network`、`services`、`software`、`postgresql`
- Windows：`network`、`services`、`software`

## 依赖

- Python 3.8+
- Linux：bash 和常见 core utils
- Windows：PowerShell 5.1+（系统自带）或 pwsh；可选 `winget` / `scoop`
  / `choco` 在 `PATH` 里，软件清单会更完整

## 边界（贡献前务必看一下）

- **只读。** 采集脚本绝不写系统配置或注册表。
- **不收密钥。** 连接串、代理凭证、私钥等会被脱敏或忽略，绝不会原样落盘。
- **缺工具 = 数据不全，不是崩溃。** 没装 `winget` 的机器照样能出有用文档。
- **不收 DB 内容。** PostgreSQL / SQL Server 的用户、表、连接列表
  明确不在范围内。

逐平台细节见 `references/<platform>/safety-and-boundaries.md`。

## 贡献

这个 skill 故意做得小。建议扩展方向：

- 更多 VPN/代理客户端识别（Linux 端目前空缺）。
- macOS 子树（当前 macOS 走 Linux 路径，部分采集会静默降级）。
- `adapters/<platform>/` 下加更多 agent 运行时适配。

欢迎 Issue / PR。若改动涉及新增采集逻辑，请同步更新对应
`references/<platform>/collection-rules.md`，让范围边界保持显式。

## 许可

MIT —— 见 `LICENSE`（若仓库中暂未添加，默认按 MIT 使用）。

## 相关项目

- 作为 git submodule 集成在 [`awesome_agent_tools`](https://github.com/JasonJarvan/awesome_agent_tools) 里。
- 姐妹 skill：`skill-orchestrator`（在动手做新 skill 之前，先判断是否真的需要做）。
