# Chef Assistant Mobile App

这是一个最小 React Native（Expo）壳应用：

- 主 WebView 加载现有 Web 前端
- 原生层接管“下厨房导入”流程
- App 内 WebView 打开下厨房页面，用户完成人机验证后，App 读取页面 HTML 并调用后端 `/recipes/import/from-html`

## 目录

- `App.js`：主 WebView + 导入 WebView + bridge
- `app.json`：Expo 配置
- `package.json`：依赖与脚本

## 启动

```bash
cd mobile-app
npm install
npm run start
```

## 默认地址

当前默认配置：

- 主前端：`http://10.0.2.2:5173`
- 后端 API：`http://10.0.2.2:8000`

说明：
- `10.0.2.2` 是 Android 模拟器访问宿主机 localhost 的地址
- 如果你用真机或 iOS 模拟器，需要改 `App.js` 里的地址

## Bridge 协议

Web -> Native:

```json
{
  "type": "open_xiachufang_import",
  "payload": {
    "mode": "recipe|homepage",
    "url": "https://www.xiachufang.com/..."
  }
}
```

Native -> Web:

通过 `window.dispatchEvent(new CustomEvent('native-import-result', ...))` 回传导入结果。

## 当前限制

- App 目前没有额外做登录/权限/持久化包装
- 当前 `extractRecipeLinks()` 依赖首页 HTML 中包含完整 recipe URL；如果下厨房未来改成动态渲染，需要改成更稳的抽取策略
