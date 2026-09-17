# 新机安装与验收

用于用户要求“从零安装”“新手直接帮我搞定”或审计发现依赖缺失。Agent 主动推进；只在系统凭据、物理插拔和合盖动作处让用户接手。

## 1. 审计与边界

先运行：

```bash
python3 "<skill-dir>/scripts/setup_audit.py"
```

必须是带 `AppleClamshellState` 的 macOS 笔记本。台式 Mac、读取失败或不受支持的平台停止，不用 `pmset disablesleep` 猜测修复。

记录但不泄露：机型、芯片、macOS、Amphetamine 是否安装/运行、Power Protect 两个文件、限定的免密 `pmset` 授权、其他已知合盖工具、`SleepDisabled`、当前供电。不要打印 sudoers 内容。检测到两个及以上合盖工具时先停止，确认唯一所有者；不得让多个工具同时控制全局状态。

## 2. 安装 Amphetamine

若 `/Applications/Amphetamine.app` 不存在：

1. 打开官方 Mac App Store 页面：`macappstore://apps.apple.com/app/id937984704`；网页备用地址为 `https://apps.apple.com/app/amphetamine/id937984704?mt=12`。
2. 用 UI 自动化推进到“获取/安装”。实际触发安装新软件前遵守当前环境的确认要求。Apple ID 登录、购买确认或系统凭据由用户接手；Amphetamine 免费，但不要声称无需账户。
3. 安装后核对 bundle id `com.if.Amphetamine`、签名和 `/Applications/Amphetamine.app`，然后打开应用。

若已安装，先核对 App Store 是否提供更新；更新不是完成合盖配置的前提，不因网络或商店问题阻塞对现有兼容版本的检查。

## 3. 安装 Power Protect

Apple Silicon 必须安装官方 Power Protect；Intel Mac 仅在 Amphetamine 明确要求时安装。官方下载地址：

`https://github.com/x74353/Amphetamine-Power-Protect/raw/main/DMG/Power%20Protect%20for%20Amphetamine.dmg`

流程：

1. 下载到用户 Downloads，使用明确文件名 `Power Protect for Amphetamine.dmg`。不要从镜像站下载。
2. 运行 `hdiutil verify`，挂载后只接受名为 `Install Power Protect.pkg` 的包；用 `pkgutil --check-signature` 展示签名结果。GitHub 未发布固定版本哈希，不能把本地计算值冒充官方校验值。
3. 打开安装包前按当前环境要求确认。通过安装器推进；Touch ID/管理员密码由用户完成。
4. 验证以下文件存在且为 root 所有，并验证 `sudo -n -l /usr/bin/pmset` 仅显示预期的 `pmset` 能力：
   - `~/Library/Application Scripts/com.if.Amphetamine/powerProtect.scpt`
   - `/private/etc/sudoers.d/amphetamine_powerProtect`
5. 卸载 DMG。不要删除用户已有安装包，除非用户要求。

## 4. 配置 Amphetamine

优先使用 Amphetamine 官方 AppleScript API；API 不可用时才用 UI。

1. 启动无限时长会话：`start new session with options {duration:0, interval:0, displaySleepAllowed:true}`。
2. 允许显示器休眠，避免合盖保活等同于屏幕常亮。
3. 启用 Closed-Display Mode。若安装 Power Protect 前已有合盖会话，先结束/禁用，再重新开始/启用。
4. 遇到警告或脚本失败弹窗时读取其内容，不盲点；系统授权交给用户。
5. 运行 `lid_awake.py ensure`，必须得到 `SleepDisabled=1` 的两次读数。

Amphetamine 勾选、`cdmEnabled=1`、普通 `PreventUserIdleSystemSleep` 都不是系统级验收。

## 5. 供电切换回归

仅凭一次 `SleepDisabled=1` 不能宣布完成，尤其是 Apple Silicon。按顺序执行：

1. 记录当前供电和 `SleepDisabled`。
2. 请用户从当前供电切换到另一状态；等待系统识别后运行 `lid_awake.py check`。检查模式不能自动修复，否则会污染回归结果。
3. 再切回原供电，重复只检查。
4. 两个方向检查前都为 1 才算通过。任一方向为 0：重启 Closed-Display Mode 后复测；仍失败则最多重装 Power Protect 一次。重装后仍失败或隔夜再次漂移，不继续重复重装，进入 [稳定性升级与工具迁移](stability.md)。

## 6. 真实合盖验收

设置通过后记录精确测试起点，请用户保持一个可观察的连续任务或远程连接，合盖约一分钟再打开。随后只分析测试窗口：

```bash
pmset -g log | rg 'Entering Sleep state|Wake from|DarkWake from' | tail -n 30
```

通过需要同时满足：测试窗口没有新的 `Clamshell Sleep`，且连续任务/远程连接未中断。`DarkWake` 不等于任务持续运行；没有日志也不能单独证明成功。插电与电池合盖场景若用户都依赖，应分别实测。

## 7. 完成交付

分别报告：软件安装、唯一状态所有者、系统配置、双向供电回归、持续稳定性、真实合盖测试。只把实际完成项标为通过；不得用“已配置”替代“已实测”。说明电池消耗和散热风险，建议合盖运行时保持通风。
