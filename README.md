# UI Design Skills

**从需求生成 Figma 设计稿，把 Figma 还原成前端，把一张 KV 扩展成完整活动页。**

面向设计师与前端开发者的 AI Agent Skills，提供 AI → Figma 设计、Figma 精准还原、运营活动页制作、素材检查和交付验收流程。

AI skills for **Figma-to-code**, **UI design**, and **campaign landing pages**, with asset validation and delivery workflows.

[查看技能](#选择技能) · [一键安装](#一键安装) · [直接下载 ZIP](#直接下载-zip) · [版本发布](https://github.com/jinboamen/ui-design-skills/releases)

## 选择技能

| 你想完成的工作 | Skill | 输入与交付 | 详细说明 |
| --- | --- | --- | --- |
| 从需求、原型或已有设计生成可编辑 Figma 稿 | `ai-figma-design-workflow` | 需求与设计资料 → 独立 UI 样张、组件化 Figma、自动布局与自适应验收 | [AI → Figma 设计交付](skills/ai-figma-design-workflow/README.md) |
| 把设计稿还原成前端，或排查还原偏差 | `figma-precision-delivery` | Figma 文件与节点、目标项目 → 页面实现、原生素材、交互和视觉验收结果 | [Figma 精准还原](skills/figma-precision-delivery/README.md) |
| 从一张主视觉 KV 制作完整活动页 | `v1-activity-page` | KV 与活动配置 → 三套样张选一套、1920px 静态页面、分层 PNG、独立装饰和整页预览 | [V1 活动页制作](skills/v1-activity-page/README.md) |

三个技能均包含完整规则、专题参考文档和入口配置；设计还原与活动页技能另附适用的辅助脚本。

## 一键安装

已安装 Node.js、可使用 `npx` 时，在终端运行以下命令，按提示选择技能及目标客户端：

```sh
npx skills add jinboamen/ui-design-skills
```

只安装其中一个技能：

```sh
npx skills add jinboamen/ui-design-skills --skill ai-figma-design-workflow
npx skills add jinboamen/ui-design-skills --skill figma-precision-delivery
npx skills add jinboamen/ui-design-skills --skill v1-activity-page
```

先查看可发现的技能，不进行安装：

```sh
npx skills add jinboamen/ui-design-skills --list
```

以上使用 [Skills CLI](https://github.com/vercel-labs/skills)。命令安装的是技能文件；执行具体工作还需要下面列出的工具和输入。

## 直接下载 ZIP

不熟悉命令行，可以直接下载发布包：

| 技能 | 最新已发布版本 | 下载 | 发布说明 |
| --- | --- | --- | --- |
| AI → Figma 设计交付 | v1.0.0 | [下载 ZIP](https://github.com/jinboamen/ui-design-skills/releases/download/ai-figma-design-workflow-v1.0.0/ai-figma-design-workflow-v1.0.0.zip) | [查看 Release](https://github.com/jinboamen/ui-design-skills/releases/tag/ai-figma-design-workflow-v1.0.0) |
| Figma 精准还原交付 | v1.0.0 | [下载 ZIP](https://github.com/jinboamen/ui-design-skills/releases/download/figma-precision-delivery-v1.0.0/figma-precision-delivery-v1.0.0.zip) | [查看 Release](https://github.com/jinboamen/ui-design-skills/releases/tag/figma-precision-delivery-v1.0.0) |
| V1 活动页制作 | v1.2.0 | [下载 ZIP](https://github.com/jinboamen/ui-design-skills/releases/download/v1-activity-page-v1.2.0/v1-activity-page-v1.2.0.zip) | [查看 Release](https://github.com/jinboamen/ui-design-skills/releases/tag/v1-activity-page-v1.2.0) |

解压后，打开版本文件夹，将里面与技能同名的**整个文件夹**放入所用 AI 客户端的技能目录，并按客户端方式加载。只复制 `SKILL.md` 会缺少参考文档和脚本。

每个 Release 附 `SHA256SUMS.txt`，可用于核对下载包完整性。

## 复制提示词开始使用

### AI → Figma 设计

附上本轮需求、原型或正式设计资料：

```text
使用 $ai-figma-design-workflow，根据这些需求完成 UI 设计。
先从精选设计/UI 平台研究参考，原型只提取业务内容，
独立制作完整功能样张，确认后交付有组件、自动布局与自适应的 Figma 稿。
```

明确要求“直接生成 Figma”时可跳过样张确认；联网研究、独立设计和验收仍需完成。PC 交互控件设计 Hover，移动端不要求 Hover。

### Figma 设计还原

附上你有访问权限的 Figma 链接，并指定目标前端项目：

```text
使用 $figma-precision-delivery，把这个 Figma 页面还原到当前前端项目。
按原生 Export/Slice 获取素材，保留组件状态、交互和动效，完成浏览器验收。
```

技能会锁定真实交付根、检查素材与组件继承，再进行实现和验收；只做诊断时，可明确要求“只读检查还原偏差”。

### KV 活动页制作

上传本次 KV 后输入：

```text
使用 $v1-activity-page，根据这张 KV 制作活动页。
保留默认的套餐售卖、盲盒抽奖和抽奖任务，先展示三套背景配轻量前景样张，
等我选择后完成正式素材。
```

技能会逐项补齐必要配置，搜索并展示相容参考，再制作三套样张。用户选定后复用所选背景，完成一套正式前景、静态页面与完整预览。

## 使用前准备

| 项目 | 需要准备 |
| --- | --- |
| AI → Figma 设计 | 本轮需求与内容、搜索及看图能力、目标 Figma 读写/截图权限与对应操作技能；需生成位图时准备图片生成能力 |
| Figma 还原 | 设计文件与精确节点的访问权限、必要的 Figma 读取和导出工具、目标前端项目、浏览器验收能力 |
| 活动页制作 | 本次 KV 和业务配置、图片生成、网页搜索与图片查看、浏览器预览和截图能力 |
| Python 辅助脚本 | Python 3.10+、Pillow |

```sh
python -m pip install Pillow
```

安装工具支持某个客户端，不代表该客户端已经具备所有执行能力；需要按实际任务核对。活动页交付为静态展示，不包含真实登录、支付或抽奖服务。脚本检查也不能代替真实视觉验收。

## 仓库结构

默认分支为 `skill`，集中提供三套完整技能，便于浏览、下载和安装工具发现：

```text
README.md
skills/
├── ai-figma-design-workflow/
│   ├── README.md
│   ├── SKILL.md
│   ├── LICENSE
│   ├── agents/
│   └── references/
├── figma-precision-delivery/
│   ├── README.md
│   ├── SKILL.md
│   ├── agents/
│   ├── references/
│   └── scripts/
└── v1-activity-page/
    ├── README.md
    ├── SKILL.md
    ├── agents/
    ├── references/
    └── scripts/
```

已有技能另保留同名独立分支，各技能提供固定版本 Release；默认 `skill` 分支提供集中的安装入口。AI → Figma 技能目录采用 MIT 许可，许可范围以其目录内 LICENSE 为准。

## 反馈与维护

遇到问题可 [提交 Issue](https://github.com/jinboamen/ui-design-skills/issues)，说明使用的技能、客户端、预期结果与实际问题。请附上可公开的示例和截图。

更新技能时同步主分支目录、对应技能分支及相关说明；发布新版本时重新生成下载包并检查。

如果这些流程对你有帮助，欢迎 Star 收藏，或将仓库分享给需要设计还原与活动页制作的同学。
