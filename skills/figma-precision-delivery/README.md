# Figma 精准还原交付

`figma-precision-delivery` 是面向设计师与前端开发者的通用技能：根据 Figma 的真实结构、原生切图、组件、交互和动效完成页面实现，并以浏览器证据验收还原结果。

## 适用场景

- 将指定 Figma 页面或组件实现到已有前端项目。
- 排查布局、间距、字体、图片裁切、组件状态和动效的还原偏差。
- 只读诊断设计与实现的差异，或维护统一的设计交付规则。

该技能面向设计稿到前端的交付；不会因为还原任务自动扩展业务 API、认证、路由或构建系统。

## 目录结构

```text
figma-precision-delivery/
├── SKILL.md
├── agents/openai.yaml
├── references/
│   ├── efficient-workflow.md
│   ├── tool-access.md
│   ├── asset-extraction.md
│   ├── interaction-fidelity.md
│   ├── visual-fidelity.md
│   ├── project-integration.md
│   └── asset-bridge.md
└── scripts/transparent_asset_gate.py
```

## 安装与准备

将完整的 `figma-precision-delivery/` 文件夹放入所用 AI 客户端的技能目录，按客户端方式加载。入口为 [SKILL.md](SKILL.md)。

执行还原需要：可访问的 Figma 文件及精确节点、具备必要属性读取和原生导出能力的 Figma 工具、目标前端项目，以及可采集真实页面证据的浏览器。能力缺失时按规则记录未验证项。

透明素材校验脚本需要 Python 3.10+ 与 Pillow。从本仓库根目录运行：

```sh
python -m pip install Pillow
python skills/figma-precision-delivery/scripts/transparent_asset_gate.py --help
```

本技能不附带或自动安装本地 Figma 桥接服务；`asset-bridge.md` 仅用于用户明确启用已有桥接时的适配。

## 使用示例

在支持技能调用的客户端中输入，并附上实际设计链接和目标项目：

```text
使用 $figma-precision-delivery，把这个 Figma 页面还原到当前前端项目。
按原生 Export/Slice 获取素材，保留组件状态、交互和动效，完成浏览器验收。
```

只做诊断时可输入：

```text
使用 $figma-precision-delivery，只读检查设计稿与当前页面的还原偏差，给出证据和修正建议。
```

## 执行与验收

1. 锁定交付范围、根节点和工具能力，建立设计快照。
2. 识别 Export/Slice 与组件继承，导出页面实际实例并完成素材准入。
3. 按结构、几何、文字、素材、交互的顺序实现；修改时局部复验。
4. 检查全部可见节点、整页及一级模块像素差、计算样式、间距、交互与构建结果。

默认增量模式与严格认证模式具有相同精度底线；缓存仅减少重复工作。严格认证还有附加证据要求，具体见 [执行等级](references/efficient-workflow.md) 和 [视觉验收](references/visual-fidelity.md)。

`transparent_asset_gate.py` 检查透明 PNG 来源、候选 WebP 与独立基准的一致性，通过后才将素材原子写入目标位置。完整参数以 `--help` 和 [素材准入规则](references/asset-extraction.md) 为准。

最终应提供实现或诊断结果、修改位置、预览位置、验收指标及失败或未验证项。脚本通过、截图通过或构建通过中的任一项，均不能单独证明整个页面完成还原。

[返回技能索引](../../README.md)
