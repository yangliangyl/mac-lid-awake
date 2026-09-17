---
name: mac-lid-awake
description: 从零安装、配置和验收 Mac 合盖不休眠，或检查并修复已有配置。适用于新手搭建 Amphetamine 与 Power Protect、合盖保活、供电切换后失效、合盖后 Codex 或 Claude Code 停跑；用户明确说“只检查”时不修改设置。
---

# Mac 合盖不休眠

目标：让有合盖传感器的 Mac 在合盖后继续运行，屏幕可以熄灭，并用系统状态、供电切换和真实合盖测试分层验收。

按用户意图选择模式：

- “检查、现在状态、自检”：默认检查并修复，运行 `lid_awake.py ensure`。
- “只检查、不要修改”：运行 `lid_awake.py check`。
- “安装、从零配置、新手帮我搞定”：执行完整 onboarding。先运行 `setup_audit.py`，再读取并严格执行 [新机安装与验收](references/onboarding.md)，持续推进到通过或遇到必须由用户完成的系统授权。
- “总失效、彻底解决、自动守护、换方案”：先检查漂移证据和工具冲突，再读取 [稳定性升级与工具迁移](references/stability.md)。未经用户明确选择，不安装守护、Agent Hook 或替代应用。
- “恢复正常合盖休眠”：只执行文末恢复流程，不运行保活修复。

## 执行

脚本仅需 macOS 和 Python 3。将下面路径替换为当前 Skill 的实际安装目录，路径含空格时保留引号。

```bash
python3 "<skill-dir>/scripts/lid_awake.py" ensure
```

只检查：

```bash
python3 "<skill-dir>/scripts/lid_awake.py" check
```

读取 JSON 的 `status`、`before`、`after` 和 `actions`，同时检查退出码。已有合盖不休眠设置时不重复改动。脚本采用以下有限修复流程：

1. 核实是有合盖传感器的 Mac，读取 `SleepDisabled`、电源、合盖状态和休眠阻止项；读取失败时不猜测状态。
2. 若 `SleepDisabled = 0`，优先通过已运行的 Amphetamine 的专用 AppleScript API 重新启用合盖模式；只在警告已关闭时自动调用，避免不可见弹窗。已有会话不替换，没有会话才启动无限时长会话并允许屏幕熄灭。合盖状态下不先关闭合盖保护。
3. 等待应用异步生效，再读取系统状态。仍未生效时，仅在 Power Protect 的既有授权文件存在时尝试 `sudo -n /usr/bin/pmset -a disablesleep 1`。不改写 sudoers，不安装软件，不循环请求权限。
4. 两次复核系统状态；失败或设置又被改回时停止，说明实际错误和当前状态。需要用户完成系统授权时，说明缺的是哪一步，不索要密码。

日常模式不安装常驻服务、不创建定时任务。完整 onboarding 只安装用户目标所需的 Amphetamine 和官方 Power Protect；稳定性升级一次只允许一个组件拥有 `SleepDisabled`，迁移前必须停用旧工具的合盖模式。不擅自安装 Amphetamine Enhancer，不修改现有唤醒计划、网络、锁屏、低电量保护或其他电源参数。App Store 登录、Touch ID、管理员密码和实际合盖动作必须由用户完成；Agent 不索要、代填或记录凭据。

## 判断和交付

- `configured` / `repaired`：只说明“合盖不休眠设置已生效”。`SleepDisabled = 1` 是本流程的系统配置验收项，影响电池和插电两种供电下的系统休眠，不只影响合盖动作。
- `not_configured`：本流程的保活设置未达标；不能仅据此断言所有外接显示器场景一定休眠。
- `unknown` / `blocked`：说明读取失败或修复受阻，不报成功。
- Amphetamine 的勾选、`cdmEnabled` 和普通 `PreventUserIdleSystemSleep` 都不能单独证明合盖保活。`PreventSystemSleep = 0` 也不能推翻已读取的 `SleepDisabled = 1`。
- 任何 `pmset` 电源参数写入都可能重置 `SleepDisabled`；修改电池、屏幕或休眠参数后必须重新检查。

简短报告当前是否达标、做了什么、电源状态，以及是否完成实际合盖验证。无需默认粘贴全部诊断数据。

用户需要实际验收时，记录测试起点，请其合盖约一分钟后打开，再检查相应时间段：

```bash
pmset -g log | rg 'Entering Sleep state|Wake from|DarkWake from' | tail -n 30
```

仅分析测试窗口，旧的 `Clamshell Sleep` 不能算本次修复失败；`DarkWake` 不代表任务持续运行。没有新日志也不能单独证明一直在线，结合用户确认的合盖时段与连续任务/远程连接证据。未完成测试就明确写“尚未实测”，不要为此阻塞设置交付。切换充电器后的可靠性需要单独验证。

仅当用户要求恢复正常休眠时，关闭 Amphetamine 的合盖模式，再执行 `sudo -n /usr/bin/pmset -a disablesleep 0` 并读取 `pmset -g` 验证。普通闲置休眠仍可能被其他应用阻止。

Power Protect 的安装位置与用途见[作者说明](https://github.com/x74353/Amphetamine-Power-Protect)。日常检查不重复下载和安装；仅 onboarding、组件缺失、权限损坏或供电切换回归失败时进入安装/重装流程。
