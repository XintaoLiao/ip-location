# IP Location

macOS 菜单栏应用，显示当前公网 IP 所属国家的国旗，并提供一个可拖拽的悬浮气泡窗口，实时显示国旗、国家代码和网络上传/下载速度。

![Python](https://img.shields.io/badge/Python-3.12-blue)
![macOS](https://img.shields.io/badge/macOS-12--26-green)
![Architecture](https://img.shields.io/badge/arch-Intel%20%7C%20Apple%20Silicon-orange)

## 功能

- 菜单栏显示国旗 + 国家代码
- 悬浮圆形气泡窗口（可拖拽、右键菜单）
- 实时网络速度监控（每 2 秒刷新）
- 4 个 IP 查询服务自动降级（ipinfo.io → ip-api.com → ifconfig.co → api.myip.com）
- IP 所在国家变更时发送系统通知
- 支持开机自启动（LaunchAgent）
- 中国大陆/香港/澳门/台湾特殊显示

## 安装与运行

```bash
# 安装 Python 3.12（推荐通过 Homebrew）
brew install python@3.12

# 创建虚拟环境并安装依赖
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 运行
./start.sh
```

## 构建分发包

```bash
# 生成 .app + DMG（需要先创建 .venv）
./build_dmg.sh

# 重新生成应用图标
python3 gen_icon.py
```

## 兼容性

### 系统支持矩阵

| macOS 版本 | Intel (x86_64) | Apple Silicon (ARM) | 状态 |
|---|---|---|---|
| 12 Monterey | ✅ | ✅ | 完全支持 |
| 13 Ventura | ✅ | ✅ | 完全支持 |
| 14 Sonoma | ✅ | ✅ | 完全支持 |
| 15 Sequoia | ✅ | ✅ | 完全支持 |
| 26 Tahoe | ✅ | ✅ | 基本支持，有已知风险（见下方） |

> macOS 26 Tahoe 是最后一个支持 Intel 的 macOS 版本。

### 依赖兼容性

| 依赖 | 版本 | 架构 | 备注 |
|---|---|---|---|
| Python | 3.12+ | universal2 | Homebrew 在 macOS 14+ 为 Tier 1；12-13 为 Tier 3（可用 python.org 安装器替代） |
| pyobjc-core | 12.1 | universal2 | wheel 目标 macOS 10.13+，同时包含 Intel 和 ARM 二进制 |
| pyobjc-framework-Cocoa | 12.1 | universal2 | 同上 |
| rumps | 0.4.0 | 纯 Python | 无架构限制 |
| requests | 2.32+ | 纯 Python | 无架构限制 |

### macOS 26 Tahoe 已知风险

1. **TCC 网络权限收紧**：通过 LaunchAgent 自启动时，Python 的网络请求可能被 TCC 阻止（`errno 65: No route to host`）。解决方案：授予 Python 网络权限，或改用 `curl` 子进程替代 `requests`。

2. **菜单栏图标可能被隐藏**：Tahoe 的 Liquid Glass 菜单栏在空间不足时会静默隐藏 `NSStatusItem`，rumps 基于此 API 可能受影响。

3. **无边框窗口回归**：Tahoe 26.3 曾出现无边框窗口不可点击/拖拽的回归（已修复），浮窗气泡使用此类型窗口，需关注后续系统更新。

4. **`launchctl load/unload` 已弃用**：当前仍可使用但会有警告，建议未来迁移至 `launchctl bootstrap gui/<UID> <path>` / `launchctl bootout gui/<UID>/<label>`。
