# Focus Buddy

一款带有小猫养成、幽默提醒和可选 AI 任务规划的专注工具。

Focus Buddy 提供三种使用方式：功能完整的 Windows 安装版、把完整专注网页与跨标签页监督合在一起的浏览器扩展版，以及无需安装即可体验的网页版。

![Focus Buddy 小猫专注场景](pictures/focus.png)

> 图片素材来源：YouTube 博主 **mocha.**

## 选择适合你的版本

| 版本 | 适合谁 | 能监督什么 | AI | 下载/使用 |
|---|---|---|---|---|
| Windows 安装版 | 希望使用完整功能的学生和上班族 | Windows 软件、窗口标题、浏览器域名 | 内置规则；可选 OpenRouter 或 Ollama | [直接下载 EXE](https://github.com/miaoooow/Focus-Buddy/releases/latest/download/FocusBuddy-Windows-Setup.exe) |
| 浏览器扩展版 | 主要在 Edge/Chrome 学习或工作的人 | 当前活动标签页的域名 | 本地规则，不需要模型 | [下载完整扩展 ZIP](https://github.com/miaoooow/Focus-Buddy/releases/latest/download/FocusBuddy-Browser-Extension.zip) |
| 网页版 | 想立即体验，不希望安装软件的人 | 是否离开当前网页 | 本地场景规则 | [立即打开网页版](https://miaoooow.github.io/Focus-Buddy/) |

### 能力区别

- **Windows 安装版**功能最完整，安装时可以选择位置，启动后显示为独立的 Focus Buddy 窗口。它不要求用户安装 Python、Ollama 或下载模型；需要更强语义理解时，可在软件内连接自己的 OpenRouter Key。
- **浏览器扩展版**独立运行，不依赖 EXE。点击工具栏图标会打开完整专注台，提供场景解析、网站白名单、声音花园、宠物领养和成长记录；后台只读取当前活动标签页的域名，用白名单判断是否偏离任务。
- **网页版**受浏览器安全限制，不能查看其他软件或标签页地址，只能在用户离开当前网页超过宽限时间后记录一次偏航。

三个版本的数据彼此独立，都默认保存在用户自己的设备中。

## 1. Windows 安装版

### 包含的功能

- 使用自然语言输入目标，例如“45 分钟完成高数作业第三章”。
- 默认使用 12 类内置场景数据库解析任务，不需要联网或模型。
- 可选 OpenRouter 免费路由直接解析任务，不需要下载本地模型；已有 Ollama 的用户也能继续使用。
- 应用、进程、页面关键词和网站域名白名单。
- VS Code、终端、文件资源管理器等关联软件智能推荐。
- 小猫走入屏幕、摇头、推翻杯子和完成庆祝动画。
- 上传自家宠物照片，可在本机生成，也可在明确同意后交给 Gemini 卡通化，再在本机生成四个成长阶段。
- 专注分钟、猫币、经验、徽章、连续天数和历史记录。
- 声音花园、分类播放、音量和播放进度记忆。
- 四段精选自然采样采用 48kbps Opus 压缩，总计约 7MB；原始大文件不进入安装包，播放时采用分段流式读取。
- WebView2 独立应用窗口；关闭窗口会一并结束本地服务。

### 安装

点击下面的链接直接下载：

[下载 FocusBuddy-Windows-Setup.exe](https://github.com/miaoooow/Focus-Buddy/releases/latest/download/FocusBuddy-Windows-Setup.exe)

3.5.0 版使用新的 Focus Buddy 图标，默认领养“奶牛警长”，并加入精选压缩声音包和可选云端 AI。

双击安装包后，可以先选择安装目录；随后安装器会完成当前用户安装、创建快捷方式并启动 Focus Buddy。它已经包含运行所需的 Python 环境和程序依赖，不需要管理员权限。应用以独立窗口运行，只在后台监听 `127.0.0.1`，并自动从 8765–8775 中选择空闲端口。

独立窗口使用 Windows WebView2。Windows 11 已包含 WebView2，绝大多数仍受支持的 Windows 10 设备也已经安装；极少数缺少运行时的电脑会安全回退到默认浏览器，不影响计时和监督功能。

当前版本面向 Windows 10/11 的 x64 兼容设备。Windows 可能对未签名安装包显示 SmartScreen 提示；运行前可使用 Release 中的 `SHA256.txt` 核对文件。

### 可选：直接连接 AI

这不是首次使用的必要步骤。未安装模型时，目标解析、计时、白名单、提醒、声音和养成功能都能正常工作。

Focus Buddy 不会把 Ollama 和大型模型强行塞进安装包，因为这会增加数 GB 体积和显著提高内存要求。

点击目标区的“连接云端 AI”可以选择：

- **本地场景库**：最快、完全离线，也是默认模式。
- **OpenRouter**：使用用户自己的 Key，默认模型为 `openrouter/free`，不需要下载模型；免费路由仍受服务商限额与可用模型变化影响。
- **Ollama**：适合已经装好本地模型、希望数据完全不出电脑的用户。

软件不内置或共享任何 API Key。Windows 版使用当前用户的 DPAPI 加密保存 Key，页面接口只返回“是否已配置”，不会返回明文。Gemini 图片模型是单独的可选功能，可能产生服务商费用；每次发送宠物照片前都会再次要求用户确认。

服务与用量以官方说明为准：[OpenRouter 免费模型路由](https://openrouter.ai/docs/guides/routing/routers/free-router) · [Gemini 图片生成](https://ai.google.dev/gemini-api/docs/image-generation)。

### 精确识别网站

Windows 程序不能直接读取浏览器地址栏，因此安装目录中附带一个本地网址桥接：

1. Edge 打开 `edge://extensions`，Chrome 打开 `chrome://extensions`。
2. 开启“开发人员模式”。
3. 点击“加载解压缩的扩展”。
4. 选择 Windows 安装目录中的 `browser_extension` 文件夹。
5. 刷新 Focus Buddy，确认“网址识别桥接”显示已连接。

这个桥接是 Windows 版的配套组件，不是下面的独立浏览器扩展版。

## 2. 浏览器扩展版

浏览器扩展版适合所有工作都在浏览器中完成的用户，不需要运行 Windows EXE。扩展会打开与网页版同一套完整专注台，同时由后台持续监督当前标签页。

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

1. 点击工具栏中的 Focus Buddy，再点击“打开完整专注台”。
2. 输入这一轮目标和专注分钟数；页面会从本地场景数据库推荐可能用到的工具和网站。
3. 确认自动填入的网站白名单，也可一键加入当前网站或手动增删域名。
4. 点击“开始这一轮”。完整专注台可以保持打开，也可以切换到白名单网站工作。
5. 在白名单外连续停留 8 秒后，Luna 会发送浏览器通知并记录一次走神。
6. 完成后累计专注分钟、猫币、轮次和宠物成长进度。

工具栏小窗用于快速查看计时、当前域名以及暂停/继续；完整页面用于目标、白名单、声音、宠物和长期成长。两者通过扩展本机存储共享同一份会话状态。

扩展只保存目标、允许域名、计时状态和成长数据，不保存完整 URL 或浏览历史。它不申请全站内容读取权限，也不会读取网页正文。

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

网页版与扩展完整版共用“目标规划 → 倒计时 → 偏航记录 → 奖励成长 → 声音花园 → 宠物领养”的主要界面。普通网页受浏览器安全限制，不能读取其他标签页域名或 Windows 前台软件；安装扩展后，同一界面会连接扩展后台，实现跨标签页域名监督。需要监督桌面软件时仍应使用 Windows 版。

### 网页与扩展如何协作

```text
完整专注台（目标、白名单、宠物、声音）
                ↓ 消息通信
扩展后台（计时、活动标签域名、8 秒宽限、奖励）
                ↓ 本机存储
工具栏小窗（状态、暂停/继续、快速返回完整页面）
```

GitHub Pages 地址是免安装体验版，不能自行突破浏览器权限读取其他标签页。下载扩展 ZIP 后打开的完整专注台，才会启用上图中的跨标签页监督。

## 目标怎么写更准确

推荐使用“时长 + 具体成果”的格式：

```text
30分钟整理完今天的会议纪要
50分钟完成Python数据分析，并用Excel核对结果
25分钟修改简历，禁止刷B站和微博
```

Windows 版默认使用内置规则；只有用户主动选择并开启 AI 增强时才调用对应服务。扩展版和网页版不会把目标发送到模型服务。

## 隐私说明

- 不截屏、不录屏、不读取键盘输入。
- Windows 版只读取当前前台窗口的进程名和窗口标题。
- 独立扩展版只读取当前活动标签页的域名。
- Windows 网址桥接只在内存中短暂保留活动域名和标题。
- 宠物照片、成长记录、白名单和专注历史默认保存在本机。
- 只有用户选择 OpenRouter 后，任务目标才会发送给 OpenRouter；失败时自动回退本地场景库。
- 只有用户选择 Gemini、配置个人 Key 并对本次上传勾选同意后，宠物照片才会发送给 Gemini。
- 云端 Key 由 Windows DPAPI 加密保存在当前用户数据目录，API 不向前端回传明文。
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
├─ assets/branding/               EXE、安装器与网页共用品牌图标
├─ assets/soundscapes/            约7MB的精选Opus离线声音包
├─ assets/cat-story-skins/        三种内置小猫及幼年/成年形态
├─ web/                           Windows 版控制台页面
├─ browser_extension/             Windows 版网址识别桥接
├─ browser_extension_standalone/  扩展后台、工具栏小窗与会话桥接
├─ web_standalone/                网页/PWA及扩展完整专注台的共享界面
├─ data/                          场景、软件关系和提醒语句数据库
├─ assets/                        小猫成长素材
├─ pictures/                      Windows 版猫咪剧情图片
├─ installer/                     Windows 安装器配置
├─ scripts/                       启动、声音压缩、测试和三版本打包脚本
├─ tests/                         自动化回归测试
├─ FocusBuddy.spec                Windows EXE资源清单
└─ README.md                      用户说明
```

开发测试文件只保留在源码仓库，不会进入用户下载的 EXE、扩展 ZIP 或网页 ZIP。

## 从源码运行 Windows 版

需要 Windows、Python 3.11+、PowerShell；Ollama 仅为可选项：

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
.\scripts\build_public_editions.ps1 -Version 3.5.0
```

脚本只会生成：

```text
FocusBuddy-Windows-Setup.exe
FocusBuddy-Browser-Extension.zip
FocusBuddy-Web.zip
SHA256.txt
```

构建脚本会把 `web_standalone` 的完整页面和 `pictures` 中所需图片复制进扩展发布目录，再压缩为扩展 ZIP；源码目录和最终用户包因此都不会保存两套容易失去同步的页面代码。
