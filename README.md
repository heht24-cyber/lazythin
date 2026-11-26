# lazythin

> **终端里的 Syncthing:状态一眼可见,冲突一键收拾。**

*lazythin = lazy(lazygit 那个 lazy)+ syncthing。*给全球几十万 Syncthing 用户一个不用开浏览器的日常入口:一个 TUI 实时面板,加一套安全的冲突文件处理命令。**零第三方依赖,纯 Python 标准库。**

## 为什么需要它

Syncthing 很好用,但两件日常小事一直很烦:

1. **看状态要开浏览器。** 同步卡没卡、对方设备在不在线、还差多少没传完,都得开 127.0.0.1:8384 的 web UI。
2. **冲突文件没人管。** 多设备同时改一个文件,Syncthing 会默默生成 `report.sync-conflict-20261125-193000-WKFLOR2.txt` ——不通知、堆着,想收拾又没有趁手工具:哪个是我的?哪边是对的?要不要留?

这不是小众烦恼:Syncthing 官方仓库里仅标题含 sync-conflict 的 issue 就有 29 个,高热度的如 [#2584](https://github.com/syncthing/syncthing/issues/2584)(53 条评论)、[#2282](https://github.com/syncthing/syncthing/issues/2282)、[#8604](https://github.com/syncthing/syncthing/issues/8604)。

已有的 Syncthing 终端工具——Go 写的 [syncthingtui](https://github.com/Evidlo/syncthingtui)、[stc](https://github.com/tenox7/stc),Rust 写的 [stui](https://github.com/corcoran/stui)——以状态监控/配置为主,需要下载对应平台的二进制。lazythin 的差异点:

- **纯 Python 零依赖**:克隆后 `pip install -e .` 即用,任意平台,无需下载或编译平台二进制
- **把冲突文件做成完整工作流**:扫描 → unified diff → 安全解决(默认干跑 + 败方转存 `.lazythin-bak`)
- 中文界面与修复提示

## 快速开始

```console
$ git clone https://github.com/heht24-cyber/lazythin
$ cd lazythin
$ pip install -e .
$ lazythin
```

自动定位本机 Syncthing 的 config.xml,读取 GUI 地址与 API key,连上即用。

TUI 键位:`r` 立即刷新 · `c` 切到冲突面板 · `q` 退出;默认每 2 秒自动刷新(`--interval` 可调)。

一帧真实输出(作者本机,Syncthing v2.1.7):

```console
$ lazythin --once
  lazythin  ·  syncthing v2.1.7 "Hafnium Hornet"  ·  本机 B3B6IYX…  ·  已运行 10h 11m  ·  CPU 0.0%
  ──────────────────────────────────────────────────────────
  文件夹 1
  ● Shared           idle       ▓▓▓▓▓▓▓▓▓▓ 100.0%  需 21.7 KiB
     D:\Share · sendreceive · 错误 4

  设备 1
  ● NixSurface       [fd7a:115c:a1e0::c836:3f27]:35774  v2.1.3
  ──────────────────────────────────────────────────────────
```

同步中的文件夹会显示进度条与实时速率(`↓ 12.3 MiB/s ↑ 1.1 MiB/s`,按两次刷新差计算)。

## 冲突文件:三步收拾

```console
$ lazythin conflicts                       # ① 扫描全部共享文件夹
⚠ D:\Share\docs\report.sync-conflict-20261125-193000-WKFLOR2.txt
   原文件 report.txt · 20261125-193000 · WKFLOR2 · 20 B

$ lazythin conflicts --diff 'D:\Share\docs\report.sync-conflict-20261125-193000-WKFLOR2.txt'
--- report.txt
+++ report.sync-conflict-20261125-193000-WKFLOR2.txt
@@ -1,2 +1,2 @@
 第一行
-旧内容
+新内容

$ lazythin conflicts --resolve keep-conflict --yes
  [完成] 改名 report.txt -> report.txt.lazythin-bak
  [完成] report.txt 的内容替换为冲突副本
```

三种解决方式:

| 方式 | 效果 |
|---|---|
| `keep-orig` | 保留原文件,冲突副本转存 `.lazythin-bak` |
| `keep-conflict` | 冲突副本顶上原位置,原文件转存 `.lazythin-bak` |
| `keep-both` | 冲突副本改名为 `report (conflict 20261125-193000).txt`,两个都留 |

安全设计:**默认只打印计划,加 `--yes` 才执行;败方文件默认转存 `.lazythin-bak` 而不是删除**(`--no-backup` 才真删)。二进制文件自动跳过逐行 diff。

冲突副本命名已对照官方源码核实(`lib/model/folder_sendrecv.go` 的 `conflictName()`):`去扩展名的原名 + .sync-conflict-YYYYMMDD-HHMMSS-<设备ID> + 扩展名`;lazythin 同时兼容把标记放结尾的旧风格。

## 脚本集成

```console
$ lazythin status --json      # 机器可读快照
$ lazythin --once             # 渲染一帧退出(监控/CI/截图)
```

退出码:`conflicts` 发现冲突返回 1(全部解决后 0),连不上 API 返回 2。

## 兼容性与实现

- 实测 **Syncthing v2.1.7**(当前最新 release);所用 5 个 REST 端点均在官方文档中且无弃用标记;v2 的 `deviceID` 字段与 v1 的 `id` 字段均兼容。
- 只调用**只读** REST 端点(`/rest/system/status`、`/rest/config`、`/rest/db/status`、`/rest/system/connections` 等),不改任何同步配置。
- config.xml 自动查找:Windows `%LOCALAPPDATA%\Syncthing`、Linux `~/.config/syncthing` / `~/.local/state/syncthing`、macOS `~/Library/Application Support/Syncthing`,也可 `--config` 指定。API key 只在本机使用。
- TLS GUI(https 自签名)自动处理。

## 局限(v0.1)

- 不监听事件流,刷新靠轮询(默认 2s,本地 API 开销极小)。
- 冲突扫描不进 `.stversions`(版本归档),那本来就是留档。

## 开发与测试

```console
$ python -m unittest discover -s tests -v
```

40 个单元测试;REST 数据形状的测试夹具取自真实 Syncthing v2.1.7 的响应,不打真实网络。

## License

MIT
