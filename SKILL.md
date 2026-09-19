---
name: mac-lid-awake
description: 检查、配置和验收 Mac 合盖不休眠，或恢复正常合盖休眠。适用于 Amphetamine 与 Power Protect 搭建、合盖保活、供电切换后失效、合盖后 Codex 或 Claude Code 停跑。“检查”、“现在状态”和“自检”始终使用只读 check；只有用户选择修复或安装，并在了解影响后确认，才可执行 ensure、onboarding 或系统设置变更。
---

# Mac 合盖不休眠

目标：让有合盖传感器的 Mac 在合盖后继续运行，屏幕可以熄灭，并用系统状态、供电切换和真实合盖测试分层验收。

按用户意图选择模式：

- “检查、现在状态、自检”和“只检查、不要修改”：运行 `lid_awake.py check`，不运行修复命令。
- “修复、恢复合盖保活”：先确认 Amphetamine 是唯一状态所有者，说明保活会同时影响电池和插电状态下的系统休眠，并分别说明无限时长会话与受限 `pmset` 写入；获得用户确认后才带对应授权参数运行 `lid_awake.py ensure`。
- “安装、从零配置、新手帮我搞定”：将 onboarding 作为独立安装操作，先说明将读取的状态、可能安装的软件与需要的系统授权，得到确认后再运行 `setup_audit.py` 并读取 [新机安装与验收](references/onboarding.md)。
- “总失效、彻底解决、自动守护、换方案”：先检查漂移证据和工具冲突，再读取 [稳定性升级与工具迁移](references/stability.md)。未经用户明确选择，不安装守护、Agent Hook 或替代应用。
- “恢复正常合盖休眠”：只执行文末恢复流程，不运行保活修复。

## 执行

脚本仅需 macOS 和 Python 3。将下面路径替换为当前 Skill 的实际安装目录，路径含空格时保留引号。

默认检查（只读）：

```bash
python3 "<skill-dir>/scripts/lid_awake.py" check
```

用户了解上述影响并确认修复后：

```bash
python3 "<skill-dir>/scripts/lid_awake.py" ensure \
  --owner amphetamine --confirm-repair \
  --allow-start-session --allow-pmset
```

`--allow-start-session` 与 `--allow-pmset` 是两项独立授权；用户未同意其中一项时删去相应参数，脚本会在需要该能力时停止，不会自动补权。`--confirm-repair` 仅在已经向用户说明电池/插电影响后使用。

读取 JSON 的 `status`、`before`、`after` 和 `actions`，同时检查退出码。`check` 只读；下列有限修复流程只适用于获得确认后的 `ensure`：

1. 核实是有合盖传感器的 Mac，读取 `SleepDisabled`、电源、合盖状态和休眠阻止项；读取失败时不猜测状态。
2. 若 `SleepDisabled = 0`，先核实 Amphetamine 已安装、正在运行且没有其他已知合盖工具造成所有权歧义，再通过专用 AppleScript API 重新启用合盖模式；只在警告已关闭时自动调用，避免不可见弹窗。已有会话不替换；没有会话时，只有本次带 `--allow-start-session` 才启动无限时长会话并允许屏幕熄灭。合盖状态下不先关闭合盖保护。
3. 等待应用异步生效，再读取系统状态。仍未生效时，只有本次带 `--allow-pmset`，且 Power Protect 脚本、sudoers 规则和 `sudo -n -l /usr/bin/pmset` 三项均验证通过，才尝试 `sudo -n /usr/bin/pmset -a disablesleep 1`。旧授权文件单独存在不构成写入许可；不改写 sudoers，不安装软件，不循环请求权限。
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

仅当用户要求恢复正常休眠，并已说明电池/插电影响后，运行独立恢复分支；它只会关闭合盖模式，绝不会启动保活会话：

```bash
python3 "<skill-dir>/scripts/lid_awake.py" restore \
  --owner amphetamine --confirm-restore --allow-pmset
```

恢复分支同样要求唯一所有者和已验证的受限 Power Protect 权限；完成后两次读取 `SleepDisabled=0`。普通闲置休眠仍可能被其他应用阻止。

Power Protect 的安装位置与用途见[作者说明](https://github.com/x74353/Amphetamine-Power-Protect)。日常检查不重复下载和安装；仅 onboarding、组件缺失、权限损坏或供电切换回归失败时进入安装/重装流程。
