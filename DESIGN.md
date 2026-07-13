---
name: FinDSL Forge
description: 金融选股 DSL 的确定性编译、诊断与 Doris 证据工作台
colors:
  primary: "#0F766E"
  primary-deep: "#0B4F4A"
  secondary: "#1D4F73"
  background: "#F4F7F8"
  surface: "#FFFFFF"
  surface-muted: "#F8FBFB"
  ink: "#162124"
  muted: "#526469"
  line: "#CAD7DA"
  success: "#137333"
  warning: "#8A5100"
  danger: "#B42318"
  code: "#101820"
typography:
  title:
    fontFamily: "Segoe UI, Microsoft YaHei, system-ui, sans-serif"
    fontSize: "20px"
    fontWeight: 800
    lineHeight: 1.25
    letterSpacing: "0"
  body:
    fontFamily: "Segoe UI, Microsoft YaHei, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: "0"
  label:
    fontFamily: "Segoe UI, Microsoft YaHei, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "0"
  mono:
    fontFamily: "Cascadia Mono, Consolas, monospace"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: "0"
rounded:
  sm: "6px"
  md: "8px"
  panel: "10px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.surface}"
    rounded: "{rounded.md}"
    height: "36px"
    padding: "0 14px"
  button-secondary:
    backgroundColor: "{colors.secondary}"
    textColor: "{colors.surface}"
    rounded: "{rounded.md}"
    height: "36px"
    padding: "0 14px"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "10px"
---

# Design System: FinDSL Forge

## Overview

**Creative North Star: “审计型投研工作台”**

界面服务于高密度的编译与核验任务。它借鉴研究终端清楚、紧凑、状态明确的特点，但不复制行情大屏的深色背景和高饱和涨跌色。视觉层级主要来自线框、表头、留白和字体粗细，主色仅用于模式选择、主操作和通过状态。

页面首先回答“当前运行哪条管线”，然后展示输入、执行状态与阶段结果。成功和失败都属于正式输出；诊断面板不能像临时错误弹窗，证据面板也不能退化成宣传指标卡。

**Key Characteristics:**
- 双管线身份清楚，内部验证与官方 ANTLR/IR 不混用。
- 白色与中性灰承担主体面积，深青色承担有限操作强调。
- 数据、SQL 和 IR 使用等宽字体，中文说明使用系统无衬线字体。
- 桌面保持双栏工作流，窄屏转为单栏且保留完整操作顺序。

## Colors

颜色体系采用中性工作表面、深青主色、蓝色次操作和完整语义状态色。

### Primary
- **审计青**（#0F766E）：当前模式、主操作、焦点和通过状态。
- **深审计青**（#0B4F4A）：主操作悬停与高对比文字。

### Secondary
- **数据蓝**（#1D4F73）：次级执行动作和信息状态。

### Neutral
- **工作台背景**（#F4F7F8）：页面底色。
- **主表面**（#FFFFFF）：输入、输出和导航表面。
- **弱表面**（#F8FBFB）：表头、工具栏和只读摘要。
- **正文墨色**（#162124）：正文与标题。
- **说明灰**（#526469）：次要说明，保持 AA 对比度。
- **边界灰**（#CAD7DA）：分隔线和控件轮廓。

**稀缺强调规则。** 审计青不超过单屏面积的 10%，只标记当前选择和可执行动作。

## Typography

**Display Font:** Segoe UI / Microsoft YaHei / system-ui
**Body Font:** Segoe UI / Microsoft YaHei / system-ui
**Label/Mono Font:** Cascadia Mono / Consolas / monospace

单一无衬线字体承担产品界面，等宽字体只用于 DSL、SQL、标识符和指标值。标题保持紧凑，不使用落地页式大字号。

### Hierarchy
- **Title**（800，20px，1.25）：产品名称。
- **Headline**（700，15–16px，1.35）：面板标题与关键分组。
- **Body**（400，14px，1.55）：说明与操作文本，长段落不超过 75ch。
- **Label**（600，12px，1.4）：字段名、状态标签和表头。
- **Mono**（400，12px，1.55）：DSL、SQL、IR 和键值数据。

**零字距规则。** 所有界面文字使用 `letter-spacing: 0`，不通过压缩字距制造技术感。

## Elevation

系统默认使用扁平线框和表面色区分层级。常驻面板不同时叠加边框与宽模糊阴影；阴影仅用于真正浮于内容之上的菜单、提示或拖拽状态。

**扁平默认规则。** 面板使用 1px 边界，常态不使用装饰性投影。

## Components

### Buttons
- **Shape:** 8px 圆角，36px 固定高度。
- **Primary:** 审计青背景、白色文字，14px 水平内边距。
- **Hover / Focus:** 深青背景；3px 半透明焦点环并保留 2px 外偏移。
- **Secondary / Ghost:** 数据蓝用于次执行动作；Ghost 使用弱表面和完整边框。

### Chips
- **Style:** 仅用于短状态或当前模式，采用浅语义背景和对应深色文字。
- **State:** 必须同时显示 PASS、失败、待核验等文字，不以颜色单独传达含义。

### Cards / Containers
- **Corner Style:** 面板 10px，重复项 8px。
- **Background:** 主表面或弱表面。
- **Shadow Strategy:** 常态无阴影。
- **Border:** 1px 边界灰。
- **Internal Padding:** 12–16px。

### Inputs / Fields
- **Style:** 白色背景、1px 边界、8px 圆角；DSL 输入使用等宽字体。
- **Focus:** 审计青边框与可见焦点环。
- **Error / Disabled:** 错误同时显示诊断码和中文说明；禁用状态降低饱和度但保持文字可读。

### Navigation
- 管线模式使用分段控件，结果阶段使用可横向滚动标签。活动项同时使用背景、文字和 `aria-selected` 表达状态；移动端保持标签可见，不把关键阶段藏进菜单。

### 编译阶段轨迹
- 每个阶段显示名称、状态、耗时和可展开的结构化数据。阶段顺序来自真实后端，不通过前端写死伪造。

## Do's and Don'ts

### Do:
- **Do** 在执行按钮附近明确显示当前管线与目标接口。
- **Do** 使用 #162124 正文和 #526469 说明文字保证对比度。
- **Do** 为加载、成功、失败、空结果和数据缺失提供完整状态。
- **Do** 在 360px、768px、1440px 三种宽度验证文字、标签和固定控件尺寸。

### Don't:
- **Don't** 制作营销落地页、大标题 Hero 或装饰性插画。
- **Don't** 使用紫色渐变、玻璃拟态、发光效果或大面积深色终端皮肤。
- **Don't** 堆叠彩色指标卡、圆角卡片嵌套或边框加宽模糊阴影。
- **Don't** 混用内部 DSL 与官方七槽 DSL，或隐藏失败阶段。
- **Don't** 使用占位 SQL、恒真/恒假谓词或前端写死结果冒充成功。
