# mac-lid-awake

一个用于安装、检查、修复和验收 Mac 合盖不休眠配置的 Agent Skill。

它围绕 Amphetamine 与 Power Protect 工作，重点不是“界面上是否已经勾选”，而是读取 macOS 的 `SleepDisabled` 状态，并区分配置完成、供电切换回归和真实合盖测试。

## 能做什么

- 只读检查当前合盖保活状态。
- 在已有 Amphetamine 配置漂移时执行有限修复并复核。
- 引导新 Mac 安装 Amphetamine 与官方 Power Protect。
- 检查供电切换、`pmset` 写入和真实合盖后的可靠性。
- 为反复漂移的配置提供单一所有者、租约和故障安全的升级边界。
- 在用户要求时恢复正常合盖休眠。

## 要求

- 带合盖传感器的 macOS 笔记本。
- Python 3。
- 修复模式需要已安装并运行 Amphetamine；Apple Silicon 通常还需要官方 Power Protect。

本 Skill 不会索要或记录 Apple ID、Touch ID、管理员密码等凭据。系统授权和真实合盖动作必须由用户本人完成。

## 默认行为：检查只读，修复另行确认

自然语言中的“检查”“现在状态”“自检”和“只检查”都路由到只读 `check`。检查可以报告配置未达标，但不会因此自动运行修复。

当用户要求“修复”或“恢复合盖保活”时，Agent 会先确认 Amphetamine 是唯一状态所有者，并说明该设置同时影响电池和插电状态下的系统休眠。启动无限会话与直接 `pmset` 写入分别需要显式参数；仅发现旧 Power Protect 文件不会自动获得写入权。用户确认后才执行 `ensure`。从零安装和恢复正常休眠分别使用独立流程。

## 安装

| 宿主 | 用户级目录 | 显式调用 | 当前验证状态 |
| --- | --- | --- | --- |
| Codex 本地 | `~/.agents/skills/mac-lid-awake/` | `$mac-lid-awake` | 目录和语法按官方文档整理；真实系统流程未复测 |
| Claude Code 本地 | `~/.claude/skills/mac-lid-awake/` | `/mac-lid-awake` | 目录和语法按官方文档整理；真实系统流程未复测 |
| 其他 Agent | 以对应宿主文档为准 | 以对应宿主为准 | 未验证 |

目录与调用语法参考 [OpenAI Codex Skills 文档](https://developers.openai.com/zh-Hans/docs/build-skills)和 [Claude Code Skills 文档](https://code.claude.com/docs/en/skills)。

安装前先确认目标目录不存在；如已有同名目录，请检查来源、版本和未提交改动，不要直接覆盖。克隆仓库本身不会修改电源设置；运行 onboarding、`ensure` 或恢复流程是另外的系统操作，需要单独确认。

```bash
# Codex
git clone https://github.com/yangliangyl/mac-lid-awake.git \
  ~/.agents/skills/mac-lid-awake

# Claude Code
git clone https://github.com/yangliangyl/mac-lid-awake.git \
  ~/.claude/skills/mac-lid-awake
```

在 Codex 中显式调用 `$mac-lid-awake`；在 Claude Code 中使用 `/mac-lid-awake`。其他宿主以自身的 Skill 发现和权限机制为准。

## 使用

对 Agent 直接描述目标，例如：

- “检查目前的合盖不休眠状态。”
- “只检查，不要修改设置。”
- “帮我修复合盖保活；先说明会改什么，等我确认再执行。”
- “帮我从零配置 Mac 合盖后继续运行；安装和系统授权另行确认。”
- “合盖保活总是失效，帮我定位原因。”
- “恢复正常合盖休眠。”

也可以直接运行脚本：

```bash
python3 scripts/lid_awake.py check
python3 scripts/lid_awake.py ensure --owner amphetamine --confirm-repair \
  --allow-start-session --allow-pmset
python3 scripts/lid_awake.py restore --owner amphetamine --confirm-restore \
  --allow-pmset
python3 scripts/setup_audit.py
```

`check` 是所有普通检查请求的默认，且只读。`ensure` 仅用于经确认的修复：`--confirm-repair` 表示用户已理解电池/插电影响，`--owner amphetamine` 声明唯一所有者，另外两个 `--allow-*` 分别授权必要时启动无限会话和使用已验证的受限 Power Protect 权限。无需某项能力时可以不传，对应步骤会停止而不是自动升级权限。`restore` 是独立恢复分支，不会启动保活会话。

## 验收边界

`SleepDisabled = 1` 只代表系统配置验收通过，不等于真实合盖场景已经验证。可靠交付还应按实际使用场景检查：

1. 电池切换到插电后状态保持为 1。
2. 插电切换到电池后状态保持为 1。
3. 合盖约一分钟期间，连续任务或远程连接没有中断。
4. 测试窗口内没有新的 `Clamshell Sleep`。

任何 `pmset` 电源参数写入都可能重置 `SleepDisabled`，修改电池、屏幕或休眠策略后应重新检查。

## 安全设计

- 不自动改写 sudoers，也不安装常驻服务或定时任务。
- 只有同时具备本次显式 `--allow-pmset`、完整 Power Protect 文件和可验证的受限 `sudo -n -l /usr/bin/pmset` 权限时，才尝试限定的 `pmset` 写入。
- 不把普通 idle-sleep assertion 误判为合盖保活成功。
- 不允许多个工具同时拥有全局 `SleepDisabled` 状态。
- 未完成真实合盖测试时，不宣称“彻底稳定”。

详细流程见 [SKILL.md](SKILL.md)、[新机安装与验收](references/onboarding.md) 和 [稳定性升级与工具迁移](references/stability.md)。

## License

[MIT](LICENSE)
