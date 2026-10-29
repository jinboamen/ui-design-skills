# V1 活动页制作

当前发布版本：**v1.1.0**。

`v1-activity-page` 是从用户提供的 KV 制作通用运营静态活动页的技能。页面固定宽 1920px，以当前 KV 确定画风，先展示三套最终背景与轻量前景样张；用户选定后，再完成一套正式前景和分层素材。

## 支持内容

- 头图、套餐售卖、盲盒或跑马灯抽奖、抽奖任务。
- 用户主动启用的礼包领取、平铺活动规则和普通 Banner。
- 默认浮动活动规则入口、独立模块标题、透明业务 PNG 和独立装饰。

默认业务顺序为「套餐售卖 → 盲盒抽奖 → 抽奖任务」。转盘、翻牌、积分兑换与套餐升级不在本技能范围。成品用于静态展示，不包含真实登录、支付、抽奖服务或外部接口。

## 目录结构

```text
v1-activity-page/
├── SKILL.md
├── agents/openai.yaml
├── references/
│   ├── planning-and-references.md
│   ├── art-direction.md
│   ├── design-quality.md
│   ├── shared-assets-workflow.md
│   └── v1-layout.md
└── scripts/
    ├── export_background_slices.py
    ├── normalize_png_ppi.py
    ├── validate_output.py
    └── marquee-preview.js
```

## v1.1.0 更新

- 参考检索按实际设计对象与运营用途展开，游戏名作为补充；识别同结构换皮案例并补足缺失方法。
- 按实际页面比例分别校准纹理密度、装饰占地和前景可见尺寸，保留材质与设计丰富度。
- 按模块区分时使用 KV 内相容的深浅与色面变化，同时保持活动身份与完整交界。
- 完善组件设计完成度、实际文字容量、主体承托及空间融合检查。
- 跑马灯按棋盘和内容高度确定下方间距，增加独立高亮素材与离线轮转预览脚本。
- 平铺规则正文支持选填占位，并按正文动态适配模块高度。

公开版移除真实业务网址、活动标识和具体业务案例，保留制作与验证规则。技能发布 ZIP 用于安装；活动页成品仍按技能要求交付素材文件夹。

## 安装与准备

将完整的 `v1-activity-page/` 文件夹放入所用 AI 客户端的技能目录，按客户端方式加载。入口为 [SKILL.md](v1-activity-page/SKILL.md)。

制作需要本次 KV、必要业务配置、图片生成工具、网页搜索和实际图片查看能力，以及浏览器预览与截图能力。技能本身不包含这些服务。没有真实 KV 时，可以验证布局或脚本，不能交付正式活动素材。

辅助脚本需要 Python 3.10+ 与 Pillow：

```sh
python -m pip install Pillow
```

## 使用示例

上传 KV 后，在支持技能调用的客户端中输入：

```text
使用 $v1-activity-page，根据这张 KV 制作活动页。
保留默认的套餐售卖、盲盒抽奖和抽奖任务，先展示三套背景配轻量前景样张，等我选择后完成正式素材。
```

缺少配置时，技能会每次只询问一项并等待回答，包括模块标题、必要数量与业务文案、背景方式，以及本次头图高度。已提供的信息不重复询问。

## 制作流程

1. 分析 KV，确认模块、必要配置、背景方式和头图高度。
2. 默认搜索并实际查看本轮 2～3 项相容设计参考，在首次生图前展示链接、图片或截图与具体借鉴点；用户本次明确要求不搜索时遵从其要求。
3. 制作 A／B／C 三套最终背景，回填轻量前景形成真实浏览器样张，等待用户手动选择。
4. 复用所选背景，依据所选示意精细制作一套前景、必要状态与独立装饰，完成真实回填。
5. 检查机械规格、视觉、接缝、分层与主体融合，交付唯一素材文件夹和完整页面预览。

“整体衔接”和“按模块区分”两种背景方式均先完成组合母图，再按最终坐标原像素切片；不以分别生成的背景硬拼代替接缝设计。PNG 默认统一为 72 PPI，像素尺寸和真实透明度也须符合规范。

## 辅助工具

| 脚本 | 用途 |
| --- | --- |
| `export_background_slices.py` | 根据 `assets.json` 从已完成的背景母图导出切片，不执行生图或缩放 |
| `normalize_png_ppi.py` | 检查 PNG 分辨率元数据，显式启用写入时规范化 PPI，保持像素与透明度 |
| `marquee-preview.js` | 跑马灯离线预览：单格高亮沿外围轮转，可暂停，不执行真实抽奖 |
| `validate_output.py` | 检查交付目录、素材规格、清单、配置与证据记录，不生成压缩包 |

在素材清单与母图准备好后，可从仓库根目录运行：

```sh
python v1-activity-page/scripts/export_background_slices.py <页面目录>
python v1-activity-page/scripts/normalize_png_ppi.py <页面目录> --recursive
python v1-activity-page/scripts/validate_output.py <页面目录>
```

PPI 工具默认只检查；需要修改时先查看 `--help`，按要求提供 `--apply --backup-dir <备份目录>`。规范化应在最终冻结和记录素材哈希之前完成。配置字段、尺寸和验收要求见 [布局与清单](v1-activity-page/references/v1-layout.md)。

## 交付内容

正式素材文件夹包含可离线打开的 `index.html`、`styles.css`、`assets/`、`assets.json`、设计记录，以及默认启用的 `decorations/` 和其清单、总览。另提供位于页面目录旁的完整 1920px 宽 `<页面目录名>-preview.png`。

校验脚本通过后，仍需查看真实浏览器成品并完成视觉验收。交付只保留一份正式素材文件夹，不额外生成 ZIP 或重复素材目录。

[返回技能索引](https://github.com/jinboamen/ui-design-skills/tree/skill)
