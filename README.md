# Focus

Focus 是一款面向学生和上班族的专注工具：输入目标后自动推荐本轮可能使用的软件和网站，用白名单减少误提醒，并通过宠物成长、幽默提醒和自然声景记录长期专注。

![Focus 小猫专注场景](pictures/focus.png)

> 图片素材来源：YouTube 博主 **mocha.**

## 先看清：完整监督需要什么

不是 EXE 和网页都必须安装扩展，实际关系如下：

| 使用方式 | 是否需要浏览器扩展 | 能监督什么 | 适合场景 |
|---|---|---|---|
| Windows EXE | 监督软件时不需要；精确识别域名时需要配套桥接扩展 | Windows 前台软件、进程、窗口标题；连接桥接后可识别活动域名 | 同时使用 Office、VS Code、文件夹和浏览器 |
| 浏览器完整版本 | **需要**安装 Focus 扩展 | 当前活动标签页域名、网站白名单、跨标签页计时 | 主要在 Edge/Chrome 学习或工作 |
| GitHub Pages 网页体验 | 不需要扩展，但能力受限 | 当前页面是否被隐藏，不能读取其他标签页或桌面软件 | 立即体验计时、声音和宠物养成 |

浏览器的安全机制禁止普通网页读取其他标签页地址。因此：

- 想监督桌面软件：使用 Windows EXE。
- 想准确判断当前浏览的网站：安装 Focus 浏览器扩展。
- 只想体验计时和养成：直接打开网页即可。

## 下载与使用

### Windows EXE

[下载 Focus-Windows-Setup.exe](https://github.com/miaoooow/Focus-Buddy/releases/latest/download/Focus-Windows-Setup.exe)

- 一键安装，安装时可以选择路径。
- 以独立软件窗口运行，不要求安装 Python、Ollama 或模型。
- 默认使用本地场景数据库；也可在软件内选择 OpenRouter、Ollama 或 Gemini。
- 默认领养“奶牛警长”。
- 安装目录内附带 `browser_extension`。只有需要精确识别浏览器域名时，才需要在 Edge/Chrome 中加载它。

连接网址桥接：

1. Edge 打开 `edge://extensions`，Chrome 打开 `chrome://extensions`。
2. 开启“开发人员模式”。
3. 点击“加载解压缩的扩展”。
4. 选择 Focus 安装目录中的 `browser_extension`。
5. 回到 Focus，确认“网址识别桥接”已连接。

Windows 版支持 Windows 10/11 x64。安装包没有代码签名时，SmartScreen 可能显示提示；可使用 Release 中的 `SHA256.txt` 核验文件。

### 浏览器完整版本

[下载 Focus-Browser-Extension.zip](https://github.com/miaoooow/Focus-Buddy/releases/latest/download/Focus-Browser-Extension.zip)

1. 解压 ZIP。
2. 打开 Edge/Chrome 扩展管理页并开启“开发人员模式”。
3. 点击“加载解压缩的扩展”，选择解压后的文件夹。
4. 点击工具栏中的 Focus，再选择“打开完整专注台”。

完整专注台负责目标、白名单、声音、宠物与成长；扩展后台负责活动标签页域名和计时。它不依赖 Windows EXE。

### 网页体验

[打开 Focus 网页版](https://miaoooow.github.io/Focus-Buddy/)

也可以[下载 Focus-Web.zip](https://github.com/miaoooow/Focus-Buddy/releases/latest/download/Focus-Web.zip)离线打开。

网页包含目标建议、倒计时、自然声景、宠物领养和成长记录。它只能判断当前 Focus 页面是否被隐藏，不能准确监督其他标签页；这是浏览器权限限制，不是白名单故障。

## 主要功能

### 目标与白名单

推荐使用“时长 + 具体成果”的写法：

```text
30分钟整理完今天的会议纪要
50分钟完成Python数据分析，并用Excel核对结果
25分钟修改简历，禁止刷B站和微博
```

Focus 默认从本地场景和软件关系数据库中推荐白名单，不联网也能运行。Windows 版可选 OpenRouter 或 Ollama 增强语义解析；服务不可用时自动回退本地规则。

### 自定义宠物动画

- Windows 本机模式：从照片生成待机、害羞、扭身和生气四种动作，并生成幼年、少年、成年和守护者四段成长形态。
- Windows AI 模式：用户明确同意后，Gemini 先根据照片生成同一角色的 2×2 四动作设定图；Focus 再在本机切分动作、生成透明素材和成长阶段。
- 网页/扩展模式：浏览器在本机将照片转成轻量卡通动作组，不上传照片。
- 运行时会按场景切换动作：成功时害羞庆祝，轻度走神时摇头扭身，连续走神时生气提醒。
- 自定义宠物可以领养、切换和删除。

AI 图片生成不是首次使用的必要步骤，也不内置共享 Key。Windows 会使用当前用户的 DPAPI 加密保存个人 Key；前端接口不会返回明文。

### 声音花园

EXE、浏览器扩展和网页版使用同一组自然声景：

| 分类 | 显示作者 |
|---|---|
| 雨幕、溪流、鸟鸣 | The Nature Sounds SocietyJapan |
| 海岸 | Echoes of Nature |

发布音频由本地 `Musics` 目录中的原始文件压缩生成，转换为 48 kbps Opus，总计约 7 MB。原始大文件和歌词不会进入安装包或网页包，作者信息会显示在界面中。

重新生成压缩声音：

```powershell
.\.venv\Scripts\python.exe .\scripts\build_soundscapes.py
```

### 奖励与提醒

- 累计专注分钟、猫币、经验、连续天数和徽章。
- 白名单外停留超过宽限时间才提醒，避免短暂切换造成误扣。
- 关联软件可在本轮放行，也可写入本地关系数据库供以后自动推荐。
- 提醒语句来自本地分类数据库，会结合当前页面或软件生成简短幽默反馈。

## AI 连接说明

Windows 版可以选择：

- **本地场景库**：默认、最快、完全离线。
- **OpenRouter**：使用用户自己的 Key，默认免费路由，不下载模型。
- **Ollama**：适合已安装本地模型、希望数据不离开电脑的用户。
- **Gemini 图片模型**：只用于用户主动选择的宠物动作设定图生成。

OpenRouter/Gemini 的免费额度和可用模型由服务商决定，Focus 不承诺永久免费，也不会隐藏潜在费用。

## 隐私

- 不截屏、不录屏、不读取键盘输入。
- Windows 版只读取当前前台进程和窗口标题。
- 浏览器扩展只读取当前活动标签页的域名和标题，不读取网页正文。
- 普通网页版不能读取其他标签页。
- 专注历史、白名单、宠物和成长记录默认保存在用户设备。
- 只有用户主动启用云端 AI 时，目标或宠物照片才会发送给对应服务商。

## 素材来源

- 图片素材：YouTube 博主 **mocha.**
- 音频来源：界面中显示的作者。

素材署名仅用于说明来源，不改变原作者享有的权利。公开分发或二次使用前，应确认相应授权范围。

## 项目结构

```text
Focus-Buddy/
├─ app.py                         Windows 入口
├─ Focus.spec                     Windows 打包资源清单
├─ focus_agent/                   监测、解析、AI、宠物和本地服务
├─ assets/branding/               Focus 图标
├─ assets/soundscapes/            从 Musics 压缩生成的 Opus 声音
├─ assets/cat-story-skins/        内置宠物成长素材
├─ browser_extension/             Windows 网址桥接
├─ browser_extension_standalone/  浏览器完整版本后台与工具栏
├─ web/                           Windows 独立窗口界面
├─ web_standalone/                网页与浏览器完整专注台
├─ data/                          场景、软件关系和提醒数据库
├─ pictures/                      界面图片素材
├─ installer/Focus.iss            Windows 安装器配置
├─ scripts/                       音频、测试与三版本构建脚本
└─ tests/                         自动化回归测试
```

`Musics`、`.runtime`、`.venv`、构建缓存和设计文档不会进入用户发布包。

## 从源码运行

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

构建 4.0.0 三端发布包：

```powershell
.\scripts\build_public_editions.ps1 -Version 4.0.0
```

输出：

```text
Focus-Windows-Setup.exe
Focus-Browser-Extension.zip
Focus-Web.zip
SHA256.txt
```

GitHub Pages 由 `.github/workflows/pages.yml` 在 `main` 更新后自动发布。
