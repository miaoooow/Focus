# Focus Cloud（项目维护者部署）

Focus Cloud 把账户、免费任务规划和宠物卡通化放在服务端。普通用户只需在 Focus 中注册/登录，不需要申请 OpenRouter、Gemini 或 Cloudflare API Key。

服务使用 Cloudflare Workers、D1 和 Workers AI。免费额度适合课程展示与小规模试用；超额后接口会明确返回“今日额度已用完”，Focus 会自动回退本地场景库。

## 首次部署

```powershell
cd focus_cloud
npm install
npx wrangler login
npx wrangler d1 create focus-accounts
```

把命令返回的 `database_id` 写入 `wrangler.toml`，然后执行：

```powershell
npm run db:remote
npm run deploy
```

将部署得到的 HTTPS 地址写入：

- `data/focus_cloud.json`：Windows EXE
- `web_standalone/index.html` 的 `focus-cloud-url` meta：GitHub Pages

这些是发布者的一次性配置，不要求最终用户添加任何文件或密钥。

## 安全约束

- 密码使用随机盐和 PBKDF2-SHA256 派生后存入 D1。
- 登录令牌只以 SHA-256 摘要存储，30 天自动过期。
- 默认每个账户每天 30 次文本规划、2 次宠物生成。
- CORS 仅允许 Focus Pages、localhost 和已安装扩展。
- 不把 Cloudflare 凭据写进网页、扩展或 EXE。
