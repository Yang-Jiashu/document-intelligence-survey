# 北京大学技术报告模板 (PKU Technical Report Template)

一个干净、可复用的北京大学风格技术报告 / 白皮书 LaTeX 模板。已对原始论文做脱敏处理：标题、作者、单位团队、项目链接、邮箱、正文与参考文献全部替换为占位内容，仅保留排版框架与北大视觉风格（校徽、品牌红 `#8C1515`、标题框、字体）。

## 目录结构

```
pku-tech-report-template/
├── main.tex              # 主文件：标题/作者/单位/链接 + 各章节 \input
├── main.bib              # 示例参考文献（占位，自行替换）
├── style.cls             # 文档类：北大排版样式（请勿随意改动）
├── .latexmkrc            # 锁定 pdfLaTeX + 自动 bibtex（方便 LaTeX Workshop）
├── 00README.json         # arXiv 构建配置（如不投 arXiv 可忽略）
├── resources/
│   ├── packages.tex      # 宏包与自定义命令
│   ├── pku.png           # 北大校徽（页眉）
│   └── *.ttf / *.tfm     # 标题/正文所用字体
├── figs/
│   ├── icons/            # 页眉小图标（globe / github / mail）
│   ├── 1_overview.tex    # 占位图（example-image-duck）
│   ├── 2_pipeline.tex
│   └── 3_results.tex
├── sec/
│   ├── 0_abstract.tex    # 摘要
│   ├── 1_intro.tex       # 引言
│   ├── 2_related_work.tex# 相关工作
│   ├── 3_method.tex      # 方法
│   ├── 4_experiments.tex # 实验
│   ├── 5_conclusion.tex  # 结论
│   └── 6_broader_impact.tex # 局限与影响
└── tabs/
    └── 0_comparison.tex  # 示例表格
```

## 编译方式

**必须使用 pdfLaTeX**（`style.cls` 用 pdfTeX 的 `\pdfmapline` 加载 TTF 字体，`xelatex` / `lualatex` 无法编译）。

- **VSCode + LaTeX Workshop**：直接打开 `main.tex`，用默认的 `latexmk` recipe 一键编译即可。仓库内 `.latexmkrc` 已把构建锁定为 pdfLaTeX 并自动运行 bibtex；`main.tex` 顶部的 `% !TEX program = pdflatex` 也会提示编辑器选对引擎。
- **命令行**：
  ```bash
  latexmk -pdf main.tex      # 推荐，自动跑 bibtex 与多遍编译
  # 或手动：
  pdflatex main && bibtex main && pdflatex main && pdflatex main
  ```

## 依赖

- **完整版 TeX Live**（建议 2024/2025）。模板用到 `tcolorbox`、`titlesec`、`natbib`、`cleveref`、`nicematrix` 等常见宏包，完整版均自带。
- 占位图用的是 `mwe` 宏包自带的 `example-image-duck`。若报错 `File 'example-image-duck' not found`，安装它：
  ```bash
  tlmgr install mwe
  ```

## 开始撰写：先改这几处

1. `main.tex` — `\title{...}`、`\author{...}`、下方的「Research Group / Lab or Team Name」团队行、`\affiliation{...}`，以及三个 `\checkdata`（项目主页 / 代码仓库 / 联系邮箱）。
2. `sec/0_abstract.tex` — 摘要。
3. `sec/1_intro.tex` … `sec/6_broader_impact.tex` — 各章节正文（已含写作提示）。
4. `figs/*.tex` — 把 `example-image-duck` 换成你自己的图，放到 `figs/` 下并改 `\includegraphics` 路径。
5. `main.bib` — 替换示例文献为你的真实参考文献。

## 小贴士

- 用 `\pkured{...}` 或 `\textcolor{pkured}{...}` 给方法名/关键词上品牌红。
- 章节标题、表格 (`booktabs` + `\rowcolor{RowRed/RowBlue}`)、强调框 (`evolbox`)、公式与 `\cref` 交叉引用均已在示例中演示。
- 单位 `Peking University` 与校徽属于模板品牌，按需保留或替换为你所在院系。
