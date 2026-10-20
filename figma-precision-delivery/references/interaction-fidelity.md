# Figma 页面交互与动效保真规则

当任务涉及页面实现、组件、Prototype、Hover、点击、状态切换或动效时，完整执行本文件。Figma 中可读取的交互是精准还原的默认组成部分，和文字、样式、Export/Slice 同级；只有用户明确要求静态实现时才可省略。

执行等级、签名字段、代表实例条件和失效规则统一见 [增量流程](efficient-workflow.md)。两种模式均完整发现交互并验证每一种唯一状态转换；缓存不能省略发现或移除实例。

## 1. 证据来源与判定边界

必须分开读取三类证据：

1. `get_design_context`：静态结构、样式和素材参考，不能证明是否存在交互。
2. motion context：时间轴、关键帧、duration 和 easing。空结果只表示未发现该类关键帧。
3. Figma Plugin API：节点 `reactions`、trigger、actions、目标 Node ID、transition、组件实例当前 Variant、主组件和组件集全部 Variant。这是 Prototype 与交互组件的主要证据。

禁止把任一静态工具的空结果解释为“页面没有交互”。只有完成 Plugin API reaction 扫描且读取成功后，才能在扫描范围内记录 `no-reaction-found`。工具无权限、不支持属性、响应截断或无法解析组件目标时，状态是 `unverified`。

## 2. 强制发现流程

1. 锁定 `implementationRoot`，设置 `figma.skipInvisibleInstanceChildren = false`，枚举根及全部后代中具有 `reactions` 的节点。
2. 对每个可见 `INSTANCE` 调用 `getMainComponentAsync()`，记录实际实例、当前主组件、`variantProperties` 和 `componentProperties`。
3. 主组件属于 `COMPONENT_SET` 时，枚举组件集的全部 Variant、`componentPropertyDefinitions`、每个 Variant 及其后代的 reactions。不能只读实例当前静态状态。
4. 对每个 `NODE` action 继续读取 `destinationId`，解析目标节点、目标 Variant 及其视觉属性。`CHANGE_TO` 必须形成“当前状态 → 目标状态”的明确边。
5. 收集 `ON_HOVER`、`ON_CLICK`、`ON_PRESS`、`ON_DRAG`、`MOUSE_ENTER/LEAVE`、`MOUSE_DOWN/UP`、`AFTER_TIMEOUT`、`ON_KEY_DOWN` 等全部 trigger，以及 `NAVIGATE`、`CHANGE_TO`、`SWAP`、`OVERLAY`、`SCROLL_TO`、URL、BACK、CLOSE、SET_VARIABLE、SET_VARIABLE_MODE、CONDITIONAL 和媒体动作。
6. 读取 action 的 transition、duration、easing、direction、matchLayers、overlay position 和 reset/preserve 选项。transition 为 `null` 时按无声明过渡实现，不自行添加动画。
7. 页面或相关节点存在时间轴证据时读取 motion context，并把关键帧轨道与 Prototype reaction 分开记录后再组合实现。

组件母版中的 reaction 只需声明一次，但交付映射必须落到页面实际实例。相同组件的多个实例可共用代码实现，内部清单仍保留每个实例 Node ID、边界和当前状态。

## 3. 内部交互清单

清单只保存在任务临时目录，不写入项目、不提交、不向用户展示。每条至少包含：

```text
sourceNodeId / sourceInstanceId / sourceComponentId
sourceVariant / sourceBounds
trigger / triggerParameters
actions[] / navigation
destinationNodeId / destinationVariant
transitionType / direction / duration / easing
stateBefore / stateAfter
implementationRef / implementationMethod
figmaEvidenceStatus / browserValidationStatus
```

按“页面实例 + trigger + actions + destination + transition”去除工具重复返回的同一 reaction；不能按组件名称去重，也不能因为多个实例共用母版而丢掉页面实例记录。多 action、条件分支和变量动作必须保留原始顺序与分支。

## 4. 实现映射

- `ON_HOVER + CHANGE_TO`：实现对应 Variant 的完整视觉变化。简单差异可用 CSS `:hover`；涉及多层切换、素材替换或联动时使用组件状态，不能只加通用阴影或位移猜测效果。
- `ON_PRESS`、`MOUSE_DOWN/UP`：映射为指针按下/释放状态；不能用 Hover 代替 Pressed。
- `ON_CLICK + NAVIGATE/URL`：使用项目现有路由或语义链接，保持目标、滚动和新窗口语义。
- `OVERLAY/CLOSE/BACK`：使用项目现有 Dialog、Popover、Drawer 或路由栈，复现位置、背景、关闭方式和焦点管理。
- `SET_VARIABLE`、`SET_VARIABLE_MODE`、`CONDITIONAL`：建立明确的产品状态和分支，不把它简化成纯 CSS。
- `AFTER_TIMEOUT`、媒体和拖拽：按 Figma 参数实现定时、媒体或手势行为，并提供可清理的状态生命周期。
- SMART_ANIMATE、方向过渡和关键帧：使用项目现有动画能力，严格映射 duration、easing、direction 和属性轨道；没有证据时不发明动画。

语义控件必须可键盘到达并有可见焦点。Hover 的 Figma 视觉可在 `:focus-visible` 下复用作为无额外设计证据时的可访问回退，但要在内部标记为 accessibility fallback，不能冒充 Figma 原生 Focus Variant。尊重 `prefers-reduced-motion`：保留状态结果，缩短或移除非必要位移动画。

## 5. 交互状态中的切图

每个可达 Variant 独立执行素材规则。状态节点自身或可验证的母版/组件集配方命中 Export/Slice 时，按实际状态渲染节点生成素材；普通实例不需要重复添加标记。位图继续强制统一 2×，PNG 中间文件继续真实转换为默认无损、保留 Alpha 的 WebP。

状态没有显式或可继承 Export/Slice 时，按节点样式用代码实现，禁止截图整个状态冒充正式素材。原子切图区域存在 reaction 时，只在素材外增加语义控件和精确热点，不穿透原子边界复用后代视觉数据。

## 6. 浏览器验收

“至少点一个看看”不构成交互验收。必须覆盖交互清单中每一种唯一的状态转换：

- 每个 Default/Hover/Pressed/Disabled/Focus/展开/收起等可达视觉状态。
- 每个导航、Overlay、URL、Back/Close、变量和条件分支结果。
- 每种 transition 的 duration、easing、direction 和最终状态。
- 操作前后截图、计算样式、DOMRect、素材引用和控制台错误；视觉状态按同尺寸规则与对应 Figma Variant 比较。
- 键盘可达性、焦点可见性和 reduced-motion 行为。

相同组件、相同起止 Variant、相同 transition 的重复实例可以选一个做完整像素验收，但其余实例仍要做触发、目标、边界和内容覆盖检查。任一清单项为 `unverified`、`failed` 或缺少目标状态证据时，整体不能声称 1:1 或精准还原完成。
