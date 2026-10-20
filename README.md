# UI Skills & Tools

通用 UI 设计与前端交付技能集合，涵盖 Figma 设计还原、运营活动页制作及素材校验工具。

## 分支导航

`skill` 为默认主分支，用于维护仓库说明和技能索引。每个技能在独立的同名分支中维护。

| 分支 | 用途 | 使用文档 |
| --- | --- | --- |
| `figma-precision-delivery` | 将 Figma 设计还原为前端，检查素材、交互与视觉精度 | [查看 README](../../tree/figma-precision-delivery) |
| `v1-activity-page` | 从 KV 制作 1920px 静态活动页，交付分层素材与整页预览 | [查看 README](../../tree/v1-activity-page) |

两个技能均包含 `SKILL.md`、`agents/openai.yaml`、专题参考文档与 Python 辅助脚本。请先切换到对应分支，再阅读其 README 和技能入口。

## 获取技能

在本仓库页面选择目标分支后，通过 **Code → Download ZIP** 下载，或复制仓库地址后运行：

```sh
git clone --branch figma-precision-delivery --single-branch <仓库地址> ui-figma-skill
git clone --branch v1-activity-page --single-branch <仓库地址> ui-activity-skill
```

将下载内容中与分支同名的整个技能文件夹放入所用 AI 客户端的技能目录，保留文件结构。具体安装路径与加载方式以客户端为准；只复制 `SKILL.md` 会缺少参考规则和校验工具。

## 使用前准备

- Figma 还原需要设计文件访问权限、支持必要读取与导出的 Figma 工具、目标前端项目和浏览器验收能力。
- 活动页制作需要本次 KV、活动配置、图片生成、网页搜索和图片查看、浏览器预览能力。
- 辅助脚本需要 Python 3.10 或更高版本及 Pillow；技能文档和脚本不代替这些运行环境。

## 维护约定

- 在对应技能分支修改规则、脚本和 README，保持入口与专题引用一致。
- 公开内容使用通用示例，不提交真实客户资料、业务页面地址、访问凭据、本机路径或工作缓存。
- `__pycache__`、编译缓存和环境文件由 `.gitignore` 排除。

使用能力、流程边界及验收条件以各技能的 `SKILL.md` 和专题文档为准。
