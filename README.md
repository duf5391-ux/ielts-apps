# 雅思学习册四平台入口

固定网址：https://duf5391-ux.github.io/ielts-learning/ 。在线模式自动加载同一网站的内容更新；个人学习记录仍保存在各设备。

构建复用 shiaho777/WebToApp 的 MIT 模板（固定源码 3704633018bfef5fbf2783e3b59870eac8bc109c），独立适配见各平台目录。Android 使用持久签名，私钥只存于本地私有目录和仓库 Secrets，绝不包含在源码及下载中。

## 下载

[四端入口与校验文件](https://github.com/duf5391-ux/ielts-apps/releases/tag/v1.0.0)

| 文件 | 实际类型 |
|---|---|
| android.apk | 签名Android APK，最低Android 6，版本1.0.0 |
| ios.mobileconfig | iPhone/iPad可移除Web Clip描述文件；不是IPA |
| windows.zip | Edge/Chrome应用窗口启动器 |
| macos.zip | 浏览器应用模式入口，附受限WKWebView原生窗口备用 |

下载后按包内说明使用，校验见Release的SHA256SUMS.txt。macOS原生模板缺少文件选择及部分弹窗处理，所以默认使用浏览器入口；不把薄WebView当作完整学习功能已验证。iOS描述文件未CMS签名，Mac未Apple Developer ID公证，暂不处理App Store。

## 验证范围

包内容、固定网址、身份及哈希已核查；Android通过签名/ZIP对齐检查，Windows检查模式找到当前电脑的Edge。平台维护脚本位于Android、DesktopIOS、MacOS目录，固定复用同作者源码；macOS生成步骤见MacOS/README.md。

Android、iPhone/iPad和Mac尚无实机安装与完整功能验收：录音允许/拒绝、完整音频、导入导出、重启恢复、后台返回及同签名升级仍须分别验证。四端入口采用在线模式，GitHub Pages在部分大陆网络仍有连接波动，安装入口不能解决网络可达性。个人记录跨设备或App与浏览器之间不自动同步，迁移使用学习册备份导入，录音单独下载。
