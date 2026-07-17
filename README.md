# Focus Buddy

一款带有小猫养成、幽默提醒和本地 AI 任务规划的专注工具。

Focus Buddy 提供三种使用方式：功能完整的 Windows 安装版、只监督浏览器标签页的扩展版，以及无需安装即可使用的网页版。

![Focus Buddy 小猫专注场景](pictures/focus.png)

> 图片素材来源：YouTube 博主 **mocha.**

## 选择适合你的版本

| 版本 | 适合谁 | 能监督什么 | AI | 下载/使用 |
|---|---|---|---|---|
| Windows 安装版 | 希望使用完整功能的学生和上班族 | Windows 软件、窗口标题、浏览器域名 | 内置规则；可选本机 AI | [直接下载 EXE](https://github.com/miaoooow/Focus-Buddy/releases/latest/download/FocusBuddy-Windows-Setup.exe) |
| 浏览器扩展版 | 主要在 Edge/Chrome 学习或工作的人 | 当前活动标签页的域名 | 本地规则，不需要模型 | [直接下载扩展 ZIP](https://github.com/miaoooow/Focus-Buddy/releases/latest/download/FocusBuddy-Browser-Extension.zip) |
| 网页版 | 想立即体验，不希望安装软件的人 | 是否离开当前网页 | 本地场景规则 | [立即打开网页版](https://miaoooow.github.io/Focus-Buddy/) |

### 能力区别

- **Windows 安装版**功能最完整，安装时可以选择位置，启动后显示为独立的 Focus Buddy 窗口，不再占用普通浏览器标签页。它不要求用户安装 Python、Ollama 或下载模型，可以识别 VS Code、Office、文件资源管理器等桌面软件，显示原生小猫提醒，并支持上传宠物照片。
- **浏览器扩展版**独立运行，不依赖 EXE；它只读取当前活动标签页的域名，用域名白名单判断是否偏离任务。
- **网页版**受浏览器安全限制，不能查看其他软件或标签页地址，只能在用户离开当前网页超过宽限时间后记录一次偏航。

三个版本的数据彼此独立，都默认保存在用户自己的设备中。

## 1. Windows 安装版

### 包含的功能

- 使用自然语言输入目标，例如“45 分钟完成高数作业第三章”。
- 默认使用 12 类内置场景数据库解析任务，不需要联网或模型。
- 如果电脑已经有 Ollama，可由用户主动开启本机 AI 增强。
- 应用、进程、页面关键词和网站域名白名单。
- VS Code、终端、文件资源管理器等关联软件智能推荐。
- 小猫走入屏幕、摇头、推翻杯子和完成庆祝动画。
- 上传自家宠物照片，在本机生成四个成长阶段。
- 专注分钟、猫币、经验、徽章、连续天数和历史记录。
- 声音花园、分类播放、音量和播放进度记忆。
- 四种实时合成声景，不再把数百 MB 的原始音频塞进安装包；用户自己的本地音频仍可按需加入。
- WebView2 独立应用窗口；关闭窗口会一并结束本地服务。

### 安装

点击下面的链接直接下载：

[下载 FocusBuddy-Windows-Setup.exe](https://github.com/miaoooow/Focus-Buddy/releases/latest/download/FocusBuddy-Windows-Setup.exe)

3.3.0 版安装包实测约 **22.1 MiB**，不包含大型模型或数百 MB 的原始音频。

双击安装包后，可以先选择安装目录；随后安装器会完成当前用户安装、创建快捷方式并启动 Focus Buddy。它已经包含运行所需的 Python 环境和程序依赖，不需要管理员权限。应用以独立窗口运行，只在后台监听 `127.0.0.1`，并自动从 8765–8775 中选择空闲端口。

独立窗口使用 Windows WebView2。Windows 11 已包含 WebView2，绝大多数仍受支持的 Windows 10 设备也已经安装；极少数缺少运行时的电脑会安全回退到默认浏览器，不影响计时和监督功能。

当前版本面向 Windows 10/11 的 x64 兼容设备。Windows 可能对未签名安装包显示 SmartScreen 提示；运行前可使用 Release 中的 `SHA256.txt` 核对文件。

### 可选：启用本机 AI 增强

这不是首次使用的必要步骤。未安装模型时，目标解析、计时、白名单、提醒、声音和养成功能都能正常工作。

Focus Buddy 没有把 Ollama 和 `qwen3.5:9b` 强行塞进安装包，原因是该模型会让安装包增加约 6–7 GB，并显著提高内存要求，不适合做成面向所有电脑的默认版本。GitHub 也要求单个 Release 文件小于 2 GiB。

已经安装 Ollama 的用户可以在页面中打开“本机 AI 增强（可选）”；程序会自动检测可用模型，不会把目标发送到收费 API。

### 精确识别网站

Windows 程序不能直接读取浏览器地址栏，因此安装目录中附带一个本地网址桥接：

1. Edge 打开 `edge://extensions`，Chrome 打开 `chrome://extensions`。
2. 开启“开发人员模式”。
3. 点击“加载解压缩的扩展”。
4. 选择 Windows 安装目录中的 `browser_extension` 文件夹。
5. 刷新 Focus Buddy，确认“网址识别桥接”显示已连接。

这个桥接是 Windows 版的配套组件，不是下面的独立浏览器扩展版。

## 2. 浏览器扩展版

浏览器扩展版适合所有工作都在浏览器中完成的用户，不需要运行 Windows EXE。

### 安装

点击下面的链接直接下载：

[下载 FocusBuddy-Browser-Extension.zip](https://github.com/miaoooow/Focus-Buddy/releases/latest/download/FocusBuddy-Browser-Extension.zip)

解压后：

1. Edge 打开 `edge://extensions`，Chrome 打开 `chrome://extensions`。
2. 开启“开发人员模式”。
3. 点击“加载解压缩的扩展”。
4. 选择刚刚解压的文件夹。
5. 将 Focus Buddy 固定到浏览器工具栏。

### 使用

1. 输入这一轮目标和专注分钟数。
2. 每行填写一个允许访问的域名，例如 `github.com`。
3. 点击“开始专注”。
4. 离开允许网站 8 秒后，Luna 会显示浏览器通知。
5. 完成后累计专注分钟、猫币和轮次。

扩展只保存目标、允许域名、计时状态和成长数据，不保存完整 URL 或浏览历史。

## 3. 网页版

打开：

<https://miaoooow.github.io/Focus-Buddy/>

需要离线保存时，也可以[直接下载网页版 ZIP](https://github.com/miaoooow/Focus-Buddy/releases/latest/download/FocusBuddy-Web.zip)。

如果该地址显示 404，请先确认仓库管理员已在 `Settings → Pages → Build and deployment → Source` 中选择 **GitHub Actions**，然后到 Actions 页面手动运行一次 `Deploy Focus Buddy Web`。这是 GitHub Pages 第一次发布必须完成的仓库设置。

网页版支持：

- 根据目标推荐本地任务场景和准备工具。
- 专注倒计时、暂停和提前结束。
- 离开当前页面超过 8 秒后记录偏航。
- 清醒值、猫币、完成轮次和宠物成长。
- 自定义宠物名字，上传自家宠物照片并保存在当前浏览器。
- 由浏览器实时合成的雨幕、溪流和夜风环境声。
- PWA 离线缓存；浏览器支持时可安装到桌面。

网页版现已与 EXE 版共用“目标规划 → 倒计时 → 偏航记录 → 奖励成长 → 声音花园 → 宠物领养”的主要体验。浏览器安全机制不允许网页读取其他标签页域名或 Windows 前台软件，因此严格的跨软件监督仍需使用 Windows 版；仅监督网站时也可使用浏览器扩展版。

## 目标怎么写更准确

推荐使用“时长 + 具体成果”的格式：

```text
30分钟整理完今天的会议纪要
50分钟完成Python数据分析，并用Excel核对结果
25分钟修改简历，禁止刷B站和微博
```

Windows 版默认也使用内置规则；只有用户主动打开“本机 AI 增强”时才会调用已经安装在本机的模型。扩展版和网页版不会把目标发送到网络。

## 隐私说明

- 不截屏、不录屏、不读取键盘输入。
- Windows 版只读取当前前台窗口的进程名和窗口标题。
- 独立扩展版只读取当前活动标签页的域名。
- Windows 网址桥接只在内存中短暂保留活动域名和标题。
- 宠物照片、成长记录、白名单和专注历史保存在本机。
- AI 请求只发送给本机 Ollama。
- 关闭 Windows 程序或结束扩展会话后即停止监督。

## 素材来源

- **图片素材**：YouTube 博主 **mocha.**
- **音频来源**：以 Windows 版“声音花园”中显示的作者信息为准。

素材署名仅用于说明来源，不改变原作者享有的权利。公开分发或二次使用前，应确认对应素材的授权范围。

## 项目文件结构

```text
Focus-Buddy/
├─ app.py                         Windows 版启动入口
├─ focus_agent/                   计时、监测、AI规划、养成和本地服务
├─ web/                           Windows 版控制台页面
├─ browser_extension/             Windows 版网址识别桥接
├─ browser_extension_standalone/  独立浏览器扩展版
├─ web_standalone/                独立网页/PWA版
├─ data/                          场景、软件关系和提醒语句数据库
├─ assets/                        小猫成长素材
├─ pictures/                      Windows 版猫咪剧情图片
├─ installer/                     Windows 安装器配置
├─ scripts/                       启动、测试和三版本打包脚本
├─ tests/                         自动化回归测试
├─ FocusBuddy.spec                Windows EXE资源清单
└─ README.md                      用户说明
```

开发测试文件只保留在源码仓库，不会进入用户下载的 EXE、扩展 ZIP 或网页 ZIP。

## 从源码运行 Windows 版

需要 Windows、Python 3.11+、PowerShell，以及可选的 Ollama：

```powershell
git clone https://github.com/miaoooow/Focus-Buddy.git
cd Focus-Buddy
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
.\scripts\start.ps1
```

运行测试：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

## 构建三个发布版本

```powershell
.\scripts\build_public_editions.ps1 -Version 3.3.0
```

脚本只会生成：

```text
FocusBuddy-Windows-Setup.exe
FocusBuddy-Browser-Extension.zip
FocusBuddy-Web.zip
SHA256.txt
```
