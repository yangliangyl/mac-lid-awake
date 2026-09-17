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

## 安装

### Codex

```bash
git clone https://github.com/yangliangyl/mac-lid-awake.git ~/.codex/skills/mac-lid-awake
```

也可以克隆到其他 Agent 支持的 Skills 目录。重新启动或刷新 Agent 后，调用 `$mac-lid-awake`。

## 使用

对 Agent 直接描述目标，例如：

- “检查目前的合盖不休眠状态。”
- “只检查，不要修改设置。”
- “帮我从零配置 Mac 合盖后继续运行。”
- “合盖保活总是失效，帮我定位原因。”
- “恢复正常合盖休眠。”

也可以直接运行脚本：

```bash
python3 scripts/lid_awake.py check
python3 scripts/lid_awake.py ensure
python3 scripts/setup_audit.py
```

`check` 只读；`ensure` 会在检测到 `SleepDisabled = 0` 时，尝试通过已经运行的 Amphetamine 恢复 Closed-Display Mode，并进行两次状态确认。

## 验收边界

`SleepDisabled = 1` 只代表系统配置验收通过，不等于真实合盖场景已经验证。可靠交付还应按实际使用场景检查：

1. 电池切换到插电后状态保持为 1。
2. 插电切换到电池后状态保持为 1。
3. 合盖约一分钟期间，连续任务或远程连接没有中断。
4. 测试窗口内没有新的 `Clamshell Sleep`。

任何 `pmset` 电源参数写入都可能重置 `SleepDisabled`，修改电池、屏幕或休眠策略后应重新检查。

## 安全设计

- 不自动改写 sudoers，也不安装常驻服务或定时任务。
- 只在既有 Power Protect 授权存在时尝试限定的 `pmset` 修复。
- 不把普通 idle-sleep assertion 误判为合盖保活成功。
- 不允许多个工具同时拥有全局 `SleepDisabled` 状态。
- 未完成真实合盖测试时，不宣称“彻底稳定”。

详细流程见 [SKILL.md](SKILL.md)、[新机安装与验收](references/onboarding.md) 和 [稳定性升级与工具迁移](references/stability.md)。

## License

[MIT](LICENSE)
