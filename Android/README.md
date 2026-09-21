# IELTS Android 构建

复用用户指定作者的多平台工具 `shiaho777/WebToApp`，固定源码提交 `3704633018bfef5fbf2783e3b59870eac8bc109c`（MIT）。原 `shiaho777/web-to-app` 是在 Android 设备运行的打包工作台；当前电脑没有 Android 设备及 JDK/SDK，所以选择同作者现有 Java 模板并交 GitHub Actions 构建真实 APK。

## 交给统一应用仓库的接口

- `build_android.py` → `Android/build_android.py`
- `android-build.yml` → `.github/workflows/android-build.yml`
- 统一 PNG 图标 → `config/icon.png`
- 仓库 Secrets：`IELTS_ANDROID_KEYSTORE_B64`、`IELTS_ANDROID_KEY_METADATA_B64`。

第一个 Secret 是持久 `ieltsstudy.keystore` 的 Base64，文件格式必须为 **PKCS12**；第二个是持久 `ieltsstudy.json` 的 Base64，其 JSON 为 `{"alias":"固定别名","password":"固定共同密码"}`。可附加公开指纹字段 `certificate_sha256`（十六进制 SHA-256，校验时允许冒号），以后每次构建沿用同一对文件。私钥、密码及其 Base64 都不能进入代码仓库、普通构建日志或下载产物。构建器缺少这些文件时直接失败，不生成替代密钥。

固定入口 `https://duf5391-ux.github.io/ielts-learning/`，应用名「雅思学习册」，app_id `ieltsstudy`，包名 `app.ielts.ieltsstudy`，版本 `1 / 1.0.0`，主题 `#356c57`，最低 Android 6.0（API 23，避开模板旧版存储权限 API 缺口）。绕开 Distiller 默认 `a` 前缀直接使用 ApkBuilder；不能再从另一入口生成不同包名。

构建机使用 ubuntu-24.04 已安装的 JDK 17、Android SDK platform 36 / build-tools 36.0.0。缺失就失败；不运行 SDK 下载、安装或 `--licenses`。运行时用上游存储、音频授权、文件选择、下载和 Blob 导出桥，独立脚本在内存适配 HTTPS、本站麦克风授权、外链到系统浏览器、原生 UA、主题与最少权限，不修改上游跟踪文件。最终用 Android SDK 官方 apksigner 签名和验签。

产物仅 `android.apk`、`report.json`、`apksigner-verify.txt`、`apk-badging.txt`。报告包含签名证书、APK、图标及源码 SHA-256；检查包名、版本、中文名称、入口、签名一致和 ZIP 对齐。没有 ZIP 回退；成功构建也不代表真机验收完成。

## 设备验收剩余项

Android 安装、首次启动、后退／外链、完整音频播放、麦克风允许和拒绝、录音导出、备份导出和文件导入、重启后本地记录、后台返回及后续同签名升级保留数据。在线壳会获取网站的后续更新；个人记录存在该 App WebView 内，与普通浏览器记录不自动互通，也没有跨设备云同步。

官方环境证据：[GitHub Ubuntu 24.04 runner image](https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2404-Readme.md)。未使用需要自动同意 SDK 条款的上游安装脚本。
