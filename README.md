# Focus

Focus 是一款面向学生和上班族的专注 Agent：输入本轮目标后，它会推荐可能使用的软件与网站，使用浏览器白名单减少误提醒，并通过宠物成长、幽默反馈和自然声景积累长期专注记录。

![Focus 小猫专注场景](pictures/focus.png)

> 图片素材来源：YouTube 博主 **mocha.**；音频作者显示在软件的声音卡片中。

## 开始前只要理解一件事

Focus 的网页与 Windows EXE **都使用同一个 Focus 浏览器扩展**。

- Focus 扩展负责识别当前活动标签页的域名和标题；
- Windows EXE 额外负责识别当前前台软件、窗口标题和本地文件工具；
- GitHub 网页版负责目标、白名单、计时、声音和宠物界面；
- 扩展只传递当前标签页，不读取网页正文，不保存完整浏览历史。

扩展安装一次后，同时服务网页版和 EXE，不再需要分别添加“桥接文件”。

## 选择使用入口

### 1. Windows EXE

[下载 Focus Windows 安装包](https://github.com/miaoooow/Focus/releases/latest/download/Focus-Windows-Setup.exe)

- Windows 10/11 x64；
- 一键安装，可选择安装路径；
- 以独立软件窗口运行，不打开普通浏览器页面；
- 可监督本地软件与窗口；
- 完整识别当前网址需要启用 Focus 扩展；扩展短暂休眠不会阻止开始，未收到域名时不会误扣币。

### 2. Focus 浏览器扩展

[下载 Focus 浏览器扩展](https://github.com/miaoooow/Focus/releases/latest/download/Focus-Browser-Extension.zip)

当前仓库提供的是商店审核前的开发包：

1. 解压 ZIP；
2. 在 Edge 打开 `edge://extensions`，或在 Chrome 打开 `chrome://extensions`；
3. 开启“开发人员模式”；
4. 选择“加载解压缩的扩展”；
5. 以后网页和 EXE 会自动检测该扩展。

浏览器不允许网站静默安装扩展。若要做到真正的一键安装，必须先把同一份扩展提交 Chrome Web Store / Microsoft Edge Add-ons 审核；审核通过后 README 将替换为商店链接。

升级覆盖安装 Focus 后，请在扩展管理页面对开发版扩展点击一次“重新加载”。如果更换了安装目录，需要移除旧扩展，再从新目录的 `browser_extension` 文件夹重新加载。

### 3. 网页版

[打开 Focus 网页版](https://miaoooow.github.io/Focus/)

也可[下载离线网页包](https://github.com/miaoooow/Focus/releases/latest/download/Focus-Web.zip)。

网页版不再提供“能力受限但假装监督”的模式。未连接扩展时可以浏览界面和准备目标，但不能开始白名单监督。

### 校验下载文件

[下载 SHA-256 校验文件](https://github.com/miaoooow/Focus/releases/latest/download/SHA256.txt)

```powershell
Get-FileHash .\Focus-Windows-Setup.exe -Algorithm SHA256
```

## 为什么以前需要 API Key

OpenRouter、Gemini 等托管模型需要识别调用者、统计额度并防止滥用，所以即使模型标注“免费”，直接调用服务商通常仍需要 API Key。把共享 Key 写进网页、扩展或 EXE 会被任何人提取并盗用，因此 Focus 不会这么做。

Focus 4.2 增加了两层账户模式：

```text
默认：本机账户 → 立即注册并保持登录 → 本地场景库
云端：Focus Cloud 账户 → 限流和隐私校验 → Workers AI 免费额度
```

因此，即使项目维护者还没有部署 Focus Cloud，网页和 EXE 也能创建本机账户并在当前设备保持会话；用户不需要申请 OpenRouter、Gemini 或 Cloudflare Key。但这类本机账户只是设备内资料，不具备跨设备同步、找回密码或在线模型额度。

注意：仓库包含 Focus Cloud 的服务端原型，但截至 4.2.1，公开网页和安装包尚未配置可用的 Focus Cloud 地址，`wrangler.toml` 中的 D1 数据库 ID 也仍是占位值。因此当前公开版本不能把本机账户当成真实云账户，也不能承诺注册后即可使用免费在线模型。部署说明见 [focus_cloud/README.md](focus_cloud/README.md)。

高级用户仍可选择：

- 本地场景库：默认、最快、离线；
- Ollama：完全本地，但需要下载模型；
- OpenRouter / Gemini：使用自己的 Key 和额度。

## 账户功能

网页和 EXE 均已接入注册、登录、退出和会话恢复界面，但当前存在两种性质不同的账户：

- 本机账户（当前可用）：密码只保存随机盐和 PBKDF2-SHA256 派生值，登录状态保存在当前浏览器或 Windows 用户目录；
- Focus Cloud 账户（代码原型）：部署 D1、Workers 和模型绑定后，才可提供跨请求身份、30 天登录会话、每日额度与服务端模型凭据隔离。

云端登录令牌在数据库中只保存 SHA-256 摘要。专注历史、白名单、宠物成长和音频偏好仍默认留在用户设备，不会因为登录自动上传。本机账户不等于云端同步账户，也不会凭空获得在线模型额度。

## 当前仍存在的问题

下面按仓库代码和当前公开部署状态区分“已经可用”和“仍需完善”。把问题公开列出，是为了避免把原型写成成品，也方便后续逐项解决。

| 模块 | 当前可用能力 | 尚未完成的问题 |
|---|---|---|
| EXE 与扩展连接 | 4.2.1 增加网页心跳；心跳暂时断开时允许开始，断开期间不扣币 | 开发版扩展升级后仍需在浏览器中手动重新加载；浏览器内置页、扩展页等受浏览器安全限制，不能注入心跳 |
| 扩展分发 | 同一扩展可同时服务网页和 EXE | 尚未上架 Chrome Web Store / Microsoft Edge Add-ons，普通用户仍需下载 ZIP 并开启开发人员模式 |
| 本机账户 | 网页刷新或 EXE 重启后恢复登录；密码不保存明文 | 只在单台设备生效；清除浏览器数据或用户目录后会丢失；没有找回密码、跨设备同步、账户删除和迁移 |
| Focus Cloud 账户 | 已有 Workers + D1 注册、登录、退出、令牌摘要和 30 天会话代码 | 尚无公共服务地址，D1 ID 仍是占位值；没有邮箱验证、密码重置、设备会话管理、登录/注册防暴力限制和过期会话清理 |
| 在线文本模型 | 服务端原型可调用 Workers AI，并设置每日文本额度 | 当前公开版本没有接入在线端点；模型结果还需做更严格的结构校验、软件/域名场景库对齐和真实线上稳定性测试 |
| 本地模型 | 可选 Ollama，失败时自动回退本地场景库 | 最终用户仍需自行安装 Ollama 和下载模型，体积与启动时间不适合作为默认轻量方案 |
| 自定义宠物 AI | 本机可生成轻量动作组；云端图片接口和上传确认流程已有原型 | 公共图片模型未部署验证；还缺少照片保存期限、删除机制、隐私说明和失败重试策略 |
| 额度与运维 | 原型按账户记录每日文本/图片次数 | 并发扣额尚未做原子保护，模型失败也可能消耗次数；缺少月度成本上限、服务监控、告警和可用性说明 |
| Windows 发布 | 安装包可选择路径，并使用独立窗口运行 | 安装包尚未进行商业代码签名，也没有自动更新通道；新版本需要用户手动下载安装 |
| 素材授权 | README 和声音卡片标注了图片与音频来源 | 公开长期分发前仍需逐项确认图片和音频的再分发授权，必要时替换为明确许可的原创素材 |

要把它完善为普通用户无需配置即可使用的在线版本，推荐按以下顺序推进：

1. 部署 Cloudflare D1 与 Worker，绑定实际模型，并在 GitHub Pages 和 Windows 发布包中注入同一个 HTTPS 服务地址。
2. 增加注册与登录限流、验证码或 Turnstile、密码重置、账户删除、设备会话查看与撤销；网页版评估使用更安全的会话 Cookie，减少长期令牌直接存放在 `localStorage`。
3. 为模型网关增加超时、重试、健康检查、结构化输出校验和本地场景库二次过滤；失败调用不应扣除免费额度。
4. 增加真实端到端验收：网页、EXE、扩展分别完成“注册—重启恢复—AI 规划—额度耗尽回退—退出登录”全链路测试。
5. 补充隐私政策、宠物照片删除/保留期限、服务状态页面和费用上限，确认后再把界面中的“免费 AI”作为正式能力宣传。

### 4.2.1 扩展连接修复

此前 EXE 把“最近 6 秒没有收到域名上报”误判成“扩展没有安装”，扩展即使已经启用，也可能因为后台休眠或用户切回 EXE 而无法开始专注。4.2.1 做了三项修复：

- 普通网页每 2 秒唤醒扩展并向本地 EXE 上报当前域名；
- `heartbeat.js` 已加入 Windows 安装包与公开扩展 ZIP，不再出现清单引用文件但打包遗漏的情况；
- EXE 不再用瞬时心跳作为启动硬门槛；连接恢复前只显示等待状态，无法确认网址时不进行扣币。

## 主要功能

### 目标解析与智能白名单

推荐使用“时长 + 具体成果”的写法：

```text
30分钟整理完今天的会议纪要
50分钟完成Python数据分析，并用Excel核对结果
25分钟修改简历，禁止刷B站和微博
```

Focus 优先给出本地即时建议；只有项目维护者部署 Focus Cloud、注入服务地址且用户登录云端账户后，在线模型才会补充任务场景、必要工具和常用域名。监督循环仍使用确定性规则，不在每次窗口切换时调用模型。

### 一个扩展，同时连接网页和 EXE

- 在 GitHub 网页版中，内容脚本建立受限消息桥，只允许开始、暂停、继续、停止、读取当前域名等固定动作；
- 在 EXE 中，扩展把当前活动域名发送给 `127.0.0.1` 的 Focus 本地服务；
- 白名单按域名后缀匹配，例如加入 `github.com` 会允许其子域名；
- 只有在白名单外持续超过宽限时间才扣分并提醒。

### 自定义宠物

- 本机模式：照片不上传，在浏览器或 EXE 本地生成轻量动作组；
- Focus Cloud 模式（待公共服务部署）：用户确认后发送单张宠物照片，由服务端图片模型生成卡通底图；
- Gemini 模式：保留为高级自带 Key 选项；
- 成功时害羞庆祝，轻度走神时摇头扭身，连续走神时生气推杯；
- 可命名、领养、切换和删除自定义宠物。

### 声音花园与成长

EXE、扩展完整专注台和网页版共用四类压缩自然声景：

| 分类 | 显示作者 |
|---|---|
| 雨幕、溪流、鸟鸣 | The Nature Sounds SocietyJapan |
| 海岸 | Echoes of Nature |

音频由本地 `Musics` 原文件压缩为低码率 Opus，总计约 7 MB。专注会累计分钟、猫币、经验、连续天数、成长阶段和徽章。

## 隐私边界

- 不截屏、不录屏、不读取键盘输入；
- 扩展只读取当前活动标签页的域名和标题；
- Windows EXE 只读取当前前台进程和窗口标题；
- 宠物照片只有在用户明确选择云端模式并确认后才上传；
- 普通网页不能监控 Windows 本地程序，必须由 EXE 完成；
- 服务端 Key 不进入客户端；可选个人 Key 在 Windows 上由 DPAPI 加密。

## 项目结构

```text
Focus/
├─ app.py                         Windows 入口
├─ Focus.spec                     PyInstaller 资源清单
├─ focus_agent/                   监测、规划、账户客户端、宠物与本地服务
├─ focus_cloud/                   账户 + 免费模型网关（Workers / D1 / Workers AI）
├─ browser_extension_standalone/  网页与 EXE 共用的唯一扩展源码
├─ web/                           Windows 独立窗口界面
├─ web_standalone/                GitHub Pages 网页界面
├─ data/                          场景、关系、幽默提醒与云端公开配置
├─ assets/                        图标、成长素材与压缩声音
├─ pictures/                      界面图片素材
├─ installer/Focus.iss            Windows 安装器
├─ scripts/                       测试、文档、音频与发布脚本
├─ tests/                         自动化回归测试
└─ docs/迪拉兰-Focus_Agent设计说明书.docx  产品设计与功能图解
```

`Musics` 原文件、虚拟环境、构建缓存和 Release 二进制不会提交到仓库。

## 从源码运行

```powershell
git clone https://github.com/miaoooow/Focus.git
cd Focus
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
.\scripts\start.ps1
```

运行测试：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

构建 4.2.1 发布包：

```powershell
.\scripts\build_public_editions.ps1 -Version 4.2.1
```

输出：

```text
Focus-Windows-Setup.exe
Focus-Browser-Extension.zip
Focus-Web.zip
SHA256.txt
```

GitHub Pages 由 `.github/workflows/pages.yml` 在 `main` 更新后自动部署。Release 必须上传上述四个同名文件，README 的 `releases/latest/download/...` 才会保持长期有效。

## 素材来源

- 图片素材：YouTube 博主 **mocha.**
- 音频来源：界面中显示的作者。

署名用于说明素材来源，不代表获得二次分发授权。公开发布前，项目维护者仍应确认图片和音频的授权范围。

## 欢迎指正与共同解决

Focus 仍处在持续完善阶段。如果你发现扩展误判、白名单识别不准、账户状态丢失、界面交互问题，或对模型接入和宠物动画有更好的方案，欢迎在 [GitHub Issues](https://github.com/miaoooow/Focus/issues) 中提出。

提交问题时建议附上 Focus 版本、Windows 与浏览器版本、复现步骤、预期结果和实际提示；请勿上传密码、API Key、完整浏览记录或未经处理的私人宠物照片。欢迎大家指正，也欢迎一起把上面的问题逐项解决。
