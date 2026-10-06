# LeafRead · 本地阅读管理器

**v0.2.1 可运行功能版**。默认只允许本机访问。

## 已实现

- TXT默认128MiB（LEAFREAD_MAX_UPLOAD_MIB可配1–1024）、页面上传进度、常见中文编码识别、章节拆分、按账户去重；EPUB安全归档解析、spine顺序与纯文本阅读
- TXT导入在本机自动识别UTF-8、GBK/GB18030、Big5及UTF-16/32（含无BOM），转换后保存；稀疏空字符自动移除并显示数量，原文件保留。编码猜测有歧义时可在导入下拉框指定原编码，无需另存文件；损坏字节不会静默替换。
- 书架、章节目录、进度、书签备注编辑、字体主题、键盘左右翻章
- FTS5正文索引、命中高亮跳转、选段批注、笔记编辑删除和Markdown导出
- TXT导出、回收站恢复、JSON书库备份与校验后事务恢复
- 账户书库隔离、PWA壳缓存、整书IndexedDB离线副本、账户专属离线进度队列
- 版本化进度同步、409冲突检测与用户选择本机/服务器进度；登出清除离线副本
- 按屏分页/滚动、触摸与键盘翻页、目录收起/筛选、字号/行距/正文宽度、专注和全屏；同Wi-Fi手机访问说明见运行文档。

## 运行

EPUB 的 manifest 内 PNG/JPEG/WebP 插图已支持：阅读设置 → “本章插图”。图片先实际解码并转为不含原始元数据的 PNG；集中展示，不运行 EPUB HTML/SVG，也不请求外部图片。含插图的书库备份可恢复图片，旧版无插图备份仍可导入。

Python 3.12，Windows PowerShell：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8767
```

打开 http://127.0.0.1:8767 。已有依赖时可用 `run.cmd`。其他系统使用 `.venv/bin/python`。`APP_DATA_DIR`覆盖数据目录。

## 数据与备份

数据位于data/，已排除Git；不要提交数据库、导入内容、磁盘清单或密钥。详细启动、备份和部署边界见 [运行说明](docs/OPERATIONS.md)。

## 验证

```powershell
python -m unittest discover -s tests -v
python -m compileall -q app tests tools
```

46项本地回归全部通过，包含此前29项及17项插图测试：真实PNG/JPEG/WebP解码、元数据移除、格式/动画/路径/容量边界、账户隔离、图片去重与备份像素恢复、旧备份兼容、上传与整份恢复故障回滚。测试默认使用独立临时数据目录；不读取已有data/。所有浏览器脚本另做Node语法检查。跨平台结果以GitHub当前提交CI为准。

合成演示：`.venv\Scripts\python.exe tools/illustrations_demo.py`，在独立临时目录启动127.0.0.1:8894；回车停止并清理，不打开已有书库。

## 已知边界

- 插图仅PNG/JPEG/WebP，拒绝动画；单张输入/规范化后各≤2MiB、边长≤4096、≤800万像素，每份EPUB≤200张/规范化后32MiB；整份恢复备份也有200张/32MiB总限额。超限拒绝，外部/SVG等引用跳过并提示。
- 不是原始版式：插图单独画廊而非行内位置，长章节拆分后图片归第一节；旧版已导入的EPUB需重新导入原文件才能获得插图。复杂排版、PDF和离线插图仍不支持，TXT导出只有正文。
- JSON备份version=1新增illustrations字段；旧客户端可能忽略图片并导致再次备份丢图，含图片备份应使用v0.2.1或更新版本。单书可正常导出，书库多书合计超过恢复插图限额时整份恢复拒绝，需分批书库迁移。
- 离线前需点“保存整本离线副本”；离线支持已缓存正文和进度，批注/导入/书签修改需联网。
- 进度按章节和正文字符比例定位；反复缩放窗口会按各次页首量化，可能逐步回退。原文字符偏移字段与跨版本精确迁移仍待实现。
- 同步面向同一后端的多个客户端，不是已部署的跨设备云服务；没有原生桌面安装器。
- 默认回环访问，访客local是本机共享空间；账户可隔离内容，但不是公网多租户安全承诺。Cookie为本机HTTP设置，公网需TLS、安全Cookie、关闭访客、限流与部署审计。

[架构设计](docs/DESIGN.md) · [路线图](docs/ROADMAP.md) · [验收记录](docs/PROGRESS.md)

MIT License。用户导入内容不随源码发布。
