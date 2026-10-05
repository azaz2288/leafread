# LeafRead · 本地阅读管理器

**v0.2 可运行功能版**。默认只允许本机访问。

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
python -m compileall -q app tests
```

29项全部通过，包含LAN账户/Host/Origin边界、UTF编码有无BOM、GBK/GB18030与Big5、夹带空字符、二进制与损坏Unicode拒绝、恶意EPUB、账户隔离、同步冲突和备份恢复。真实31MiB合成TXT导入和末章搜索不截断。实际约23MiB UTF-8文件夹带512空字符的导入问题已复现并修复。Linux/Windows CI使用同一提交验证。

## 已知边界

- EPUB仅提取文本，未保留图片、复杂排版和原始版式；不支持PDF阅读。
- 离线前需点“保存整本离线副本”；离线支持已缓存正文和进度，批注/导入/书签修改需联网。
- 进度按章节和滚动比例定位；字体变化后不是逐字精确定位。
- 同步面向同一后端的多个客户端，不是已部署的跨设备云服务；没有原生桌面安装器。
- 默认回环访问，访客local是本机共享空间；账户可隔离内容，但不是公网多租户安全承诺。Cookie为本机HTTP设置，公网需TLS、安全Cookie、关闭访客、限流与部署审计。

[架构设计](docs/DESIGN.md) · [路线图](docs/ROADMAP.md) · [验收记录](docs/PROGRESS.md)

MIT License。用户导入内容不随源码发布。
