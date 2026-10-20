# Figma Export、Slice 与正式素材规则

当任务涉及切图、图片、图标、Export 或 Slice 时使用本文件。

## 执行等级与验证复用

本文件中的素材识别、Slice 优先、母版继承、父级原子隔离、位图 2×、PNG 转保留 Alpha 的 WebP 和禁止近似替代规则在所有模式下始终执行。

默认增量精准模式只减少确定性重复，不减少验证覆盖：每份唯一正式素材输出都必须完成候选导出与独立 Figma 画布基准的双源一致性验证。简单显式 SVG 或普通 Export 可以减少父级合成等额外诊断，但不能跳过双源。只有来源/有效设置、格式、物理尺寸、Alpha 摘要、有效内容边界和解码后内容哈希全部一致的重复候选，才可复用同一已通过结果；每个实例 Node ID 与页面引用仍单独保留。

严格 1:1 认证模式使用相同素材准确度门槛，并额外为每个正式素材候选保留独立双源认证记录；即使输出字节相同，也不能只用共享结果引用替代逐候选证据。缓存与指纹规则详见 [高效增量精准工作流](efficient-workflow.md)。后文无模式标注的“每张素材都双源验证”在两种模式都按唯一正式输出完整执行。

## 正式素材入口

正式素材只有两类：

1. 普通节点、Frame、Group、Component 等节点的 Figma 原生 Export。
2. 本次交付范围内的 Slice。Slice 自身就是裁切意图标记，不要求 `exportSettings` 非空。

用户明确说明某个本地文件是从精确 Figma Export/Slice 手动导出的，只是上述正式来源的另一条交付通道，不是第三类素材。只有在 Node ID、Export 配置、统一 2×输出、格式、Alpha 和独立画布基准均可验证时，才可登记为 `figma-manual-export`；仅凭文件名相似不得采信。

不再依赖 `_ic`、`_bt`、`_bg`、`_export` 等图层名后缀。节点类型不能否定设计师的 Export 意图：按钮、卡片、文字和背景只要明确设置 Export，就作为正式切图；没有 Export/Slice 时才默认代码实现。

主组件、当前 Variant、组件集或母版内部 Export 子层仍属于第 1 类，并可作为**组件素材定义**被页面实例继承。设计师只在母版声明一次，不需要给每个实例重复添加 Export；母版只提供导出配方，最终必须渲染页面实际实例。

真实交付根 `implementationRoot` 是唯一例外：任务链接可能指向它本身，也可能指向包住它的展示场景、桌面壁纸、设备壳或审阅画布。必须先锁定交付根，再完成下述意图判定；不能把交付根仅因位于链接根内部就当作普通子节点 Export。

## 链接根与真实交付根

先记录用户 URL 指向的 `linkRoot`，再根据用户要求的交付对象锁定 `implementationRoot`：

- URL 直接指向待实现页面或组件时，两者相同。
- URL 指向展示场景，而内部主 Frame 承载完整页面/组件时，该主 Frame 是 `implementationRoot`；外层场景只提供壁纸、设备壳、阴影或摆放基准。
- “还原为前端页面/组件、保留内容、可交互”是交付根需要真实 DOM 的明确证据；覆盖整个交付根的 Export 不得按普通子节点自动原子化。
- 只有用户明确要求把整个交付根输出为一张图时，整根 Export 才是 `production-atomic`。
- 尺寸、children 数量、节点名称或“看起来像页面”只能作为辅助结构证据，不能单独决定交付根。存在多个同级候选或目标仍不清楚时，标记 `ambiguous` 并询问用户。

一旦确定 `implementationRoot`，后续“根节点”均指它，而不是机械地指 URL 最外层节点。

## 任务根画框 Export 意图判定

在扫描任务根节点的 children 之前，先读取根 Frame/Section 自身的 Export 设置并记录 `isTaskRoot: true`。根节点存在 Export 时，将 `exportIntent` 分类为：

- `production-atomic`：用户明确要求把整个根画框作为一张正式图片交付。
- `preview-only`：用户明确说明该 Export 只用于分享、审阅或查看整稿；用户要求把覆盖整个交付根的页面/组件还原成真实前端内容或交互；或团队已定义且当前能力能可靠读取的显式预览标记证明这一点。
- `ambiguous`：没有可靠证据判断其用途。

证据优先级为：用户对本次任务的明确说明；团队已定义且可可靠读取的结构化意图标记；其他上下文。节点尺寸、是否包含 children、画面看起来像整页、文件格式以及节点名称都不能单独作为判定依据。建议把分享用整图放在独立的 `Preview / Share` Page，但 Page 或节点名称本身仍不能覆盖用户意图。

处理矩阵：

| 节点与意图 | 是否正式素材 | 是否原子隔离 | 是否继续遍历 children |
| --- | --- | --- | --- |
| `implementationRoot` 内普通子节点 Export | 是 | 是 | 否 |
| `implementationRoot` 自身 Export | 先判定 | 取决于意图 | 取决于意图 |
| 根节点 `production-atomic` | 是 | 是 | 否 |
| 根节点 `preview-only` | 否 | 否 | 是 |
| 根节点 `ambiguous` | 未确定 | 不执行 | 暂停并询问用户 |

`preview-only` 根导出可以下载到任务临时目录，作为同尺寸叠加或像素差异基准，但不得进入正式素材清单、项目 assets、页面 DOM 或提交记录；不得压制内部 Export/Slice，不得使已收集的后代候选失效。验证完成后删除或忽略临时预览。

`ambiguous` 必须默认拒绝：在读取根节点属性确认歧义后，暂停该根节点的素材提取并向用户确认，禁止静默地整图原子化，也禁止静默忽略根 Export 后继续实现。

## 组件母版一次声明与实例继承

扫描 `implementationRoot` 的实际页面树时，对每个可见 `INSTANCE` 调用 `await instance.getMainComponentAsync()`，并设置 `figma.skipInvisibleInstanceChildren = false` 以获得真实状态结构。按以下优先级解析根导出配方：

1. 实际实例自身 Export。
2. 当前主组件；实例属于 Variant 时即当前 Variant 的 Export。
3. 所属 `COMPONENT_SET` 的默认 Export 配方。

根配方命中时，以页面实际实例作为 `renderNode`，建立整个实例的原子边界并停止扫描该实例后代。不得导出主组件图替代实例，否则会丢失图片替换、文字/颜色覆盖、Variant、嵌套实例交换、可见性和缩放状态。

根配方未命中时，扫描当前主组件内部带 Export 的后代定义节点，并记录从主组件到定义节点的 `relativeChildIndexPath`。用同一路径映射到页面实际实例子层，且必须同时满足：

- 路径完整可达。
- 定义节点与实际节点的 `type`、`name` 一致。
- 实例虚拟子层 ID 包含定义 Node ID 时只作为辅助证据，不能单独决定映射。
- 路径不能跨越 `SLOT` 或未解析的嵌套 `INSTANCE`；嵌套实例回到实际页面树后按其交换后的主组件单独解析。

映射成功后，以实际实例子层作为 `renderNode`。实际子层自身有 Export 时覆盖母版配方，否则继承定义节点配方；子层命中只隔离该实际子层，继续扫描兄弟节点。路径失败、结构不一致、隐藏、零尺寸或不可渲染时标记阻断，禁止按名称、坐标或视觉相似度猜测，也禁止回退导出可见母版。

每个继承候选至少记录 `assetDefinitionNodeId`、`mainComponentId`、`instanceId`、`renderNodeId`、`relativeChildIndexPath` 和 `mappingEvidence`。同一母版的多个实例只有在最终格式、像素尺寸和内容哈希都一致时才可共用文件；内部追溯仍保留每个实例 Node ID。

## Slice 范围审计、优先级和终止递归

执行顺序必须是：

1. 先锁定 `linkRoot → implementationRoot`，再判定交付根的 `exportIntent`；交付根没有 Export 时直接继续。
2. 用完整节点能力枚举交付 Page 的 Slice 总数，并单独枚举 `implementationRoot` 子树中的全部 `SLICE` 节点；禁止先按 `exportSettings.length` 过滤。内部 Slice 审计至少记录 Page 总数、根内数量、相交同级数量、显式/隐式数量和最终 Node ID。
3. 正式 Slice 范围只包括：交付根后代 Slice、用户明确传入的 Slice，以及位于同一交付 Page 且边界与交付根相交的同级 Slice。同一 Page 其他画板、旧稿或远离交付根的 Slice 一律排除，不能因其带 Export 就自动进入本次任务。
4. 将正式 Slice 分为 `slice-explicit` 与 `slice-implicit`：前者逐条保留来源设置并应用统一位图 2×输出；后者在 `exportSettings` 为空时按 PNG、SCALE 2 且保留绝对画布边界导出。Plugin API 使用 `useAbsoluteBounds: true`，确保 Slice 中设计师保留的透明留白不因内容边界而被裁掉。
5. 组件实例内部 Slice 常以 `I父实例;主组件后代...` 形式暴露虚拟 Node ID。若 `download_assets` 的 Node ID schema 或 `getNodeByIdAsync` 拒绝该 ID，必须在同一次 `use_figma` 脚本里通过交付 Page 遍历取得 Slice 对象并调用该对象的 `exportAsync`。不要把虚拟 ID 截短，不要改导出主组件，也不要使用名称相同的近似素材。
6. 再从目标 Frame/Section 对显式普通 Export 与组件继承 Export 执行同一套父级优先收集；`preview-only` 根节点自身不参与收集，但继续扫描其 children。
7. Slice 使用精确 Slice 对象的 Figma 最终渲染，禁止分析、拆解或重新拼装覆盖区域内的 Image Fill、Vector 和其他图层。
8. `implementationRoot` 内的普通子节点 Export、继承 Export，或 `production-atomic` 交付根命中后作为原子素材，立即停止遍历对应 `renderNode` 的 children。
9. 隐藏、零尺寸或不可渲染节点不能进入正式素材清单。

## Slice 对普通 Export 的抑制

使用 `absoluteBoundingBox` 判断普通 Export 是否完整落入 Slice。边界比较允许约 `0.5px` 浮点误差：

```text
inner.left   >= outer.left   - 0.5
inner.top    >= outer.top    - 0.5
inner.right  <= outer.right  + 0.5
inner.bottom <= outer.bottom + 0.5
```

- 完整包含：普通 Export 记录 `suppressedBySliceId`，不下载、不生成文件。
- 部分相交：普通 Export 仍独立导出，避免丢失 Slice 外内容。
- Slice 与 Slice 之间不互相抑制。
- Slice 是否为正式素材由其与 `implementationRoot` 的层级关系、用户传入的 Node ID，或同级 Slice 与交付根的边界相交关系确定；名称只用于输出命名，不能决定有效性。几何关系只用于限定本次交付范围和抑制普通 Export，不用于猜测 Slice 内部内容。

## 父级 Export 原子隔离边界

“停止遍历 children”不仅表示不再递归收集，还表示父级 Export 成为一道不可穿透的视觉隔离边界。Figma 工具仍可能在父级响应中附带整个子树的参考代码、文字样式、Raw Images 和 SVG Assets；这些返回值只能视为工具附带数据，不能进入候选清单或页面实现。

一旦完整节点属性确认普通子节点存在显式/继承 Export，或任务根节点已被判定为 `production-atomic`，必须按顺序执行：

1. 立即设置 `atomicExport: true`，把当前节点登记为唯一视觉候选。
2. 建立该节点的后代拒绝集合；禁止继续对后代调用 `get_design_context`、视觉属性或素材工具；仅允许覆盖索引与交互所需的最小结构、边界和 reaction 读取，不重建后代视觉。
3. 丢弃父级工具响应中属于后代的参考代码、文字、填充、效果、`rawImages`、`svgAssets` 和下载 URL，不得据此生成 DOM、CSS 或本地素材。
4. 从内部清单移除先前收集的全部后代候选，并记录 `supersededByAtomicExportId`。父级后来新增 Export 时，同样必须让旧任务或本轮早期产生的后代候选和引用失效。
5. 对普通节点使用自身配方；对继承 Export 使用母版定义配方，但一律在页面实际 `renderNode` 上导出。资产工具即使同时返回子树原图或矢量，也只消费当前原子节点的 Export render。
6. 页面默认只使用一个父级 `<img>`、`<picture>` 或等价视觉节点，不重新实现图片内部的文字、图标、阴影和装饰。

清理旧结果时，只能删除或替换能够通过 Node ID/内部清单证明由 AI 为这些后代生成的文件；不得删除来源不明或属于用户的现有素材。无法安全清理时，至少停止引用并报告遗留文件，不得继续复用。

原子切图内存在 reaction 时，默认在素材外保留语义按钮、链接或精确热点，只有用户明确要求静态实现时才省略。按交互规则读取所需边界、状态和 reaction，不恢复使用后代视觉素材、文字样式或 CSS。覆盖记录可保留最小节点索引，不构成拆解视觉。

原子隔离验收必须同时满足：

- 内部清单中没有该父级的后代素材候选或输出。
- 项目代码没有引用后代 Node ID、后代下载文件或根据后代样式生成的视觉节点。
- 最终 DOM 中父级 Export 对应一个视觉素材节点；按交互规则生成的语义覆盖层除外。
- 父级导出文件与 Figma 父节点标准渲染一致。

## 原始 Export、统一 2×与 PNG 转 WebP

每个普通 Export、继承 Export 或 `slice-explicit` 节点的每一条 `exportSettings` 都是正式交付要求，必须分别记录为 `sourceExportSetting`：

- `format`：PNG、JPG、SVG、PDF 等。
- `suffix`：设计师配置的文件名后缀。
- `constraint.type`：`SCALE`、`WIDTH`、`HEIGHT`。
- `constraint.value`：倍率或目标宽高。
- `contentsOnly`、`colorProfile`、`useAbsoluteBounds` 以及当前 Figma 能力提供的其他属性。

原始记录不得改写或丢失；实际导出另生成 `effectiveExportSetting`，按以下项目规则确定性转换：

- PNG、JPG 等位图统一输出 2×。`SCALE` 统一设为 `2`；`WIDTH`/`HEIGHT` 设为原标记目标值的 `2` 倍；没有尺寸约束时按节点或 Slice 布局边界的 2 倍像素尺寸导出。禁止先低倍率导出后插值放大。
- SVG、PDF 等矢量或文档格式保持格式，不做无意义的倍率转换。
- `suffix` 和除尺寸约束外的原始属性完整继承。多条来源设置必须全部保留追溯；若统一 2×后输出路径冲突，使用包含原 constraint/条目序号的稳定区分名，禁止静默覆盖。
- 来源格式为 PNG 时，先用 `effectiveExportSetting` 得到中间 PNG，再执行 `outputTransformation: {type: 'png-to-webp', lossless: true, preserveAlpha: true}`。项目只保存并引用最终 WebP；来源记录仍保留 `format: PNG`。
- JPG 及其他非 PNG 格式不擅自转换为 WebP。

PNG → WebP 必须真实编码，禁止只改扩展名。使用 `cwebp -lossless -exact -z 9` 或能保留透明像素隐藏 RGB 的等价无损编码；严格准入要求完整解码 RGBA 一致，不提供以包体敏感或标注有损为由的放行路径。用户另行要求有损交付时属于标准变更，不能继续报告满足本 Skill 的无损门槛。中间 PNG 只存在任务临时目录，最终 WebP 必须与中间 PNG 的完整解码 RGBA、像素尺寸、Alpha 分布和有效内容边界一致。

`slice-implicit` 没有原始设置时，使用 `{format: PNG, constraint: {type: SCALE, value: 2}, useAbsoluteBounds: true}`，记录 `implicitSliceFallback: true`，并按同一 PNG → WebP 流程输出。其最终像素尺寸必须是 Slice 绝对画布宽高的 2 倍，不能裁成非透明内容边界。

## MCP 资产过滤

- 普通 Export 与 Slice 都只使用当前节点的 Export render。
- 父级普通 Export 命中时，只消费父级响应的 `export`；同一次响应中的后代 `rawImages`、`svgAssets`、参考代码和样式全部丢弃。
- Raw source images 是节点子树内部原始上传图，不自动成为独立页面素材。
- 不使用 Slice 返回的内部原图重新拼装 Slice。
- 只有精确识别为独立 Image Fill 且任务确实需要原图时，才允许使用 Raw source image。
- 临时资产 URL 有时效，先保存到项目外暂存区，全部准入通过后再保存为项目中的稳定本地文件。
- 不得用 `get_screenshot`、浏览器截图或整页截图替代正式透明切图。

## 导入前双源一致性闸门

候选素材只能先写入任务临时目录。每份唯一正式输出在复制到项目 assets、生成代码引用或进入 DOM/CSS 之前，必须取得两个相互独立的证据：

1. **候选导出**：精确普通/继承 Export 或 Slice 在页面实际 `renderNode` 上按有效 2×设置导出的文件，或用户明确提供并可追溯的 `figma-manual-export`。
2. **独立画布基准**：没有复用候选字节、URL 或同一次工具响应，能反映 Figma 编辑器当前可见合成结果的官方画布渲染、同设置手动导出或精确区域截图。截图只用于验证，不能成为项目素材。

不得把候选自身、同一 Export 响应附带的预览、同一 URL 重复下载或候选重新解码后的图当成第二来源。重复候选只有在完整素材指纹一致时才能引用同一双源结果；相同母版、相同名称或肉眼相似都不是复用依据。`contentsOnly`、实例、实例 Slice、父级 Fill/Effect/Opacity/Blend Mode/Mask/Blur、跨父级裁切范围全部视为高风险，并增加诊断但不改变所有唯一输出均需双源的要求。

比较前统一为相同尺寸 RGBA。PNG 来源先比较 2×中间 PNG 与独立基准，再比较最终 WebP 与中间 PNG；SVG/PDF 只为校验无损栅格化，不替换原格式。阈值必须预先固定：

```text
2×输出尺寸与有效 Export 约束：必须完全一致
changedPixelRatioAt16 <= 0.25%
RGBA meanAbsoluteError <= 1.0
Alpha meanAbsoluteError <= 1.0
有效内容边界每边误差 <= 1px
```

任一指标超限即标记 `export-render-conflict`。先重新读取精确实例、设置、边界和父级合成属性，再换一条官方 Figma 导出路径重试；可追溯且通过独立基准的手动 Figma 导出可以替代错误 API 候选。仍失败则禁止接入，已引用时停止引用并安全移除本任务生成的错误文件；禁止用 CSS、滤镜或其他图片补偿。页面级截图接近不能覆盖素材级失败。

## 可执行透明素材准入闸门

预期透明的 PNG 来源不能依靠文字清单或人工目测放行。必须使用本 Skill 的 `scripts/transparent_asset_gate.py` 完成检测和原子复制；禁止先把候选文件放进项目，再补做验证。脚本输入的 2×中间 PNG、最终 WebP、独立 Figma 基准和报告路径必须位于项目目录之外，目标文件必须位于项目目录之内。

依照 [工具接入](tool-access.md) 定位并核验 Python 与 Pillow，不要假设 PATH 中的 `python` 可用。运行方式：

```text
<workspace-python> scripts/transparent_asset_gate.py \
  --project-root <project-root> \
  --intermediate-png <temporary-2x.png> \
  --candidate-webp <temporary-lossless.webp> \
  --reference <independent-figma-reference.png> \
  --destination <project-root/assets/final.webp> \
  --report <temporary-report.json> \
  --expected-width <physical-pixels> \
  --expected-height <physical-pixels> \
  --node-id <asset-definition-node-id> \
  --render-node-id <actual-instance-node-id> \
  --reference-kind official-canvas-render
```

独立基准来自可验证的 Figma 官方画布渲染时使用 `official-canvas-render`；来自另一条可追溯的 Figma 手动导出通道时使用 `figma-manual-export`。参数只记录来源声明，不能把同一候选文件复制一份冒充独立基准。

脚本必须以非零退出码阻断以下情况：

- 任一输入无法解码、格式错误或物理尺寸不等于有效 2×设置。
- 中间 PNG、最终 WebP 或独立基准没有真实透明/半透明像素。
- 四角都是相同的不透明 RGB，表明黑、白、灰或画布底色可能被烘焙。
- 中间 PNG 与独立基准超过固定双源阈值。
- 最终 WebP 与中间 PNG 的解码像素、Alpha 分布或有效内容边界不是完全一致，不能证明无损。
- 候选、基准或报告被放进项目目录，或目标路径逃逸项目目录。

只有脚本退出码为 `0`、报告 `status = passed` 且 `promoted = true` 时，目标文件才算正式进入项目。代码中的 `<img>`、CSS `url()`、资源清单和预加载引用必须在此之后添加。报告只放任务临时目录，不写入项目。

脚本失败时不得修改目标文件。若项目已有一份通过认证的旧素材，继续保留旧文件；若没有已认证版本，保留所需布局尺寸但不渲染图片，也不使用带底版本、截图、Raw Image、近似 SVG 或临时透明候选填空。已经引用失败素材时必须先停止引用；不允许以“页面尚未最终验收”为理由把错误素材继续留在运行预览中。

## AI 内部临时清单

任务内部维护以下字段即可；不得写入项目、提交 Git 或在最终答复中展示：

```json
{
  "nodeId": "123:456",
  "renderNodeId": "123:456",
  "assetDefinitionNodeId": "20:30",
  "mainComponentId": "20:30",
  "instanceId": "123:456",
  "relativeChildIndexPath": [],
  "mappingEvidence": null,
  "sourceFrameId": "123:100",
  "sourceType": "node-export | component-instance-export | slice-explicit | slice-implicit | root-preview-export",
  "isTaskRoot": false,
  "exportIntent": "production-atomic | preview-only | ambiguous",
  "sourceExportSettings": [],
  "effectiveExportSettings": [],
  "outputTransformations": [],
  "outputs": [],
  "atomic": true,
  "atomicExport": true,
  "supersededByAtomicExportId": null,
  "suppressedBySliceId": null,
  "implicitSliceFallback": false,
  "provenance": "figma-api-export | figma-manual-export",
  "independentReference": null,
  "assetParityMetrics": null,
  "failureCode": null,
  "validation": "pending | passed | failed"
}
```

`root-preview-export` 只允许出现在任务临时视觉基准记录中，不能进入正式素材候选或项目输出；`ambiguous` 不得产生 outputs。

历史稿中父子同时设置 Export 时，选择距离页面根最近的 Export 父节点，忽略其 Export 子节点，并只在内部记录重复。

## 素材关闭条件

完成识别、来源映射、有效设置、格式与尺寸、独立双源、透明准入后，逐项确认对应记录 passed。还需检查文件能正常解码、有有效内容而非空白/全透明；SVG 可渲染；重复路径没有覆盖；每条来源配置均有输出或可追溯的确定性合并记录。最终网页中的裁切与显示仍由视觉规则单独验收。

预期透明素材记录 minAlpha/maxAlpha、全透明/半透明/不透明像素数、四角与有效内容边界；在明暗两种临时底色上检查边缘光晕。节点属性证明有不透明背景时不误套透明条件，但全部素材仍需双源验证。不得抠图、颜色容差删底或 AI 修图伪造透明度。

异常先重新读取精确实例、设置、边界和合成属性，再换独立正式路径重试；仍失败记录 failed/unverified，不能接入预览。停止引用失败素材，保留上一份已认证版本；没有旧版本时保留布局但不渲染该图。只清理有来源证明的本任务产物，不删除未知或用户文件。

通过后的目录、命名、SVG 引用与代码集成统一见 [开发集成](project-integration.md)。
