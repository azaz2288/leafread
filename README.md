# LeafRead · 本地阅读管理器

导入TXT，识别常见中文编码并生成章节；管理书架、搜索正文、保存进度和书签，自定义阅读字号与背景。

**状态：v0.1 可运行基础版，按路线图持续开发。默认只允许本机访问。**

## 已实现

- UTF-8/UTF-16/GB18030 文本导入，10MiB限额与内容去重
- 中文章节和英文Chapter识别，无章节长文本自动分段
- 书架、章节目录、阅读定位、进度、书签
- 正文检索并跳转到对应章节
- 阅读字号与亮/暖/暗主题，本地偏好与进度持久化

## 运行

需要 Python 3.12。Windows PowerShell：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8767
```

浏览器打开 http://127.0.0.1:8767 。其他系统用 `.venv/bin/python`；已安装依赖可直接运行 `run.cmd`。配置 `APP_DATA_DIR` 可改变数据目录。

## 数据

data/app.db 含用户书籍全文和阅读记录，必须备份但不得提交Git。

## 验证

```powershell
python -m unittest discover -s tests -v
python -m compileall -q app tests
```

CI在Linux和Windows运行相同测试。实际执行证据见 [进度](docs/PROGRESS.md)。

## 已知边界

- 第一版只支持TXT，没有EPUB/PDF；章节识别为规则方法
- 正文搜索为SQLite LIKE扫描，大书库全文索引在路线图
- 单用户本地阅读，尚无账户、跨设备同步、离线PWA
- 阅读位置采用章节及比例，字体改变后并非逐字精确定位

## 设计与后续

- [架构设计](docs/DESIGN.md)
- [按顺序开发的里程碑](docs/ROADMAP.md)

MIT License。用户导入内容不随源码发布。
