# cishanjia-huitu

在 Codex 中把医学、细胞和机制参考图临摹为 **Adobe Illustrator 可编辑矢量图**。

这是已提速的 `2026-10-08-speed-1` 技能的独立开源发行版，包含后续箭头连接和整组导出修复。保留完整质量检查，同时缓存完全相同的诊断渲染、复用已检查的完整组件、仅修复存在问题的对象。

## 让 Codex 安装

把下面一句话发送给 Codex：

```text
请使用 skill-installer 从 https://github.com/cyifan-agent/cishanjia-huitu 安装 skills/cishanjia-huitu。按照技能内 references/installation.md 检查并配置本地依赖。
```

安装后，上传参考图，打开 Illustrator 和目标文档，再对 Codex 说：

```text
使用 $cishanjia-huitu 临摹这张图，保留现有内容。请先完成全图设计与检查，再在 Illustrator 中按完整对象显示绘制过程。
```

Codex 的 GitHub 技能安装流程见 [官方技能说明](https://learn.chatgpt.com/docs/build-skills)。如果安装后没有识别到新技能，重新打开 Codex。仅说技能名称不能保证首次自动找到这个仓库，首次安装请附上链接。

## 使用条件

- Windows 10/11，用户已安装并打开 Adobe Illustrator 和一个目标文档。
- Codex 能读取参考图、执行本地脚本；Python 3.11+，建议 3.12。
- 初次配置从 PyPI 安装技能内列出的开源依赖；之后绘图工具不调用收费图片 API，不需要绘图 API 密钥。
- 对应字体须在使用者自己的 Windows 和 Illustrator 中可用；缺失字体会报错，避免静默替换。
- Node.js 仅用于开发者的模拟 Illustrator 回归测试，实际绘图不需要。

技能本身不是本地神经网络模型。参考理解和矢量设计由调用技能的 Codex 模型完成；Codex 自身可能有订阅或调用成本。Illustrator 的授权由使用者自行提供。当前原生桥接仅支持 Windows；不宣称 macOS 原生导入已验证。

## 编辑方式

线粒体、细胞核、动物、坏死细胞、断裂 DNA 和箭头各自拥有完整内部矢量部分。默认使用 Illustrator 原生符号实例，外层取消编组及重复取消编组后仍可整体拖动；双击对象进入内部编辑。光晕使用单个原生渐变形状。文字保持可编辑。

交付检查包含：参考图布局与关键区域、独立箭头、对象整体移动、相邻对象保持原位、原生文字与渐变，以及实际 Illustrator 导出。禁止把截图、像素色块或自动全图描摹冒充临摹结果。复杂图仍需逐项设计和人工视觉检查，提速不代表所有图片都能一键准确重建。

## 项目结构

`skills/cishanjia-huitu/` 是完整可安装技能，包含说明、工具、质量检查和测试。全部路径由技能所在位置及使用者自己的环境解析，不要求安装另一个绘图技能。

个人 `runtime.local.json`、下载依赖、用户参考图、AI 成品和缓存不会随项目发布。请在独立工作目录保存绘图结果。开发说明见 [CONTRIBUTING.md](CONTRIBUTING.md)，已提速版本来源见 [CHANGELOG.md](CHANGELOG.md)。

## 许可

项目代码和技能说明采用 [MIT License](LICENSE)。不附带 Adobe 软件、字体、模型权重、第三方参考图或用户绘图资料；这些材料的权利不受本项目许可影响。
