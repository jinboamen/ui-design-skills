# AI → Figma 设计交付

`ai-figma-design-workflow` 帮助设计同学将需求、原型或已有设计转成可继续编辑的 Figma 成稿，适用于网页、后台、移动端、桌面端和跨端产品。

## 能完成什么

- 从零设计、已有产品新增功能、局部改版与规范修正。
- 先从精选设计/UI 平台研究具体优秀案例，实际看图并说明借鉴点。
- 原型用于提取业务、原始文案和流程；独立完成视觉设计。
- 默认先交付完整功能的视觉样张，用户确认后制作 Figma；明确要求“直接生成 Figma”时可跳过样张确认，研究与验收仍需完成。
- 复用并精简组件，设置文字/显隐/替换属性及必要变体，使用真实自动布局。
- 实际拉宽/缩窄画框检查自适应；图片与图标保持比例，配图可使用透明 PNG，其余 UI 尽量使用原生可编辑图层。
- PC 交互控件设计 Default / Hover；移动端不要求 Hover。悬停触发等原型连线按交互需求配置。

设计稿保留原始内容，不自行添加业务入口、虚构数据或提示文案。

## 安装与工具准备

使用仓库已有的 Skills CLI 安装入口：

```sh
npx skills add jinboamen/ui-design-skills --skill ai-figma-design-workflow
```

也可以从 [版本发布](https://github.com/jinboamen/ui-design-skills/releases/tag/ai-figma-design-workflow-v1.0.0) 下载 ZIP，将其中整个 `ai-figma-design-workflow/` 文件夹放入支持的客户端技能目录。入口为 [SKILL.md](SKILL.md)，两个参考文档需一并保留。

该包提供工作流程指令，不附带 Figma 写入服务、访问凭据、字体、私有素材或其他技能。执行需要：

- 能加载本技能的 AI 客户端；
- 联网搜索及实际查看图片/页面的能力；
- 具备目标 Figma 文件访问权限的读取、写入及截图工具；
- 工作流所调用的 Figma 操作技能，如 `figma-use`、`figma-generate-design`、`figma-generate-library`；新建文件时需要对应的新建文件能力；
- 使用 AI 位图生成时，对应的图片生成/编辑能力。

工具不可用时需明确报告限制，不能把本地图片或脚本当作在线 Figma 交付成功。安装技能本身不代表这些工具已配置。

## 使用示例

提供可公开使用或有权限的需求/原型/设计资料后输入：

```text
使用 $ai-figma-design-workflow，为这个功能设计 PC 界面。
原型仅用于业务内容，先研究优秀 UI 参考并独立制作完整功能样张，
确认后再交付有组件和自动布局的 Figma 稿。
```

已确定要直接落稿时：

```text
使用 $ai-figma-design-workflow，根据这些需求直接生成 Figma。
保留原始文案，先完成 UI 参考研究，复用现有规范，
检查组件、自动布局、自适应和 PC Hover 状态。
```

## 目录与验收

```text
ai-figma-design-workflow/
├── SKILL.md
├── README.md
├── LICENSE
├── agents/openai.yaml
└── references/
    ├── design-research.md
    └── figma-delivery.md
```

- [设计研究与原型隔离](references/design-research.md)：参考平台、作品质量、实际看图与独立视觉设计。
- [Figma 制作与验收](references/figma-delivery.md)：内容忠实、组件复用、自动布局、自适应、图片比例及原生图层。

交付需提供当前 Figma 区域链接和实际结构/视觉检查结果。格式校验通过只能证明技能文件格式正确，不能保证某次生成的 UI 已通过验收。

本 Skill 及该目录下文档采用 [MIT License](LICENSE)。第三方参考网站、作品、字体和素材的权利归各自权利人所有，本许可不授予这些第三方内容的使用权。

[返回技能索引](../../README.md)
