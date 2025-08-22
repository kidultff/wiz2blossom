## 功能

使用python将为知笔记中的所有笔记都导出到本地, 包括历史修订版本，转化为纯markdown文本文件. 支持私有Docker部署的为知笔记和为知盒子. 

## 前置准备

- 将所有加密笔记取消加密
- 在可执行文件同级目录下创建 `.env` 文件, 参考: [.env.example](.env.example)
  - 配置为知笔记的用户名和密码
  - 如果是私有部署版本, 需修改AS_URL为你私有部署的访问地址
  - 配置是否保存历史版本编辑记录, 如果保存, 会在每个笔记同目录下生成`{笔记名}__version_{编辑时间}.md`的版本文件
- 安装依赖`pip install -r requirements.txt`
- 运行`python main.py`


## 注意

- ** 笔记标题中的特殊字符（如 `/`, `\`, `:`, `*`, `?`, `"`, `<`, `>`, `|` 等）会自动替换为下划线 `_`，确保跨平台兼容性
- 为知笔记应用不要打开协作笔记tab页, 否则影响程序读取读取该笔记的数据.


## 输出内容

```
├── output
│   ├── db
│   │   └── sync.db // sqlite3 记录笔记同步记录和笔记图片同步记录
│   ├── note         // 所有导出 markdown 笔记, 图片和附件
│   └── log
│       └── log.log // 日志
```


## 相关问题

### 协作笔记如何处理

协作笔记使用ws通信, 返回特定的数据格式, 需要写解析器将其解析为markdown纯文本.
[GitHub - websocket-client/websocket-client: WebSocket client for Python](https://github.com/websocket-client/websocket-client)

因为使用ws通信, 为知笔记应用不要打开协作笔记, 否则影响程序读取读取该笔记的数据.

### 如何处理笔记中的附件和图片

程序将笔记中的图片下载到本地, 放到笔记同级目录中 `./attachments` 目录中.

程序将笔记中的图片下载到本地, 放到笔记同级目录中 `./images` 目录中.

之前导出方案使用 picgo 配置图床. 考虑到上手难度太高, 遂直接放弃, 导出到本地, 用户自行处理


### 如何处理加密笔记

将所有加密笔记取消加密, 当作常规笔记处理, 避免处理加密笔记的复杂性.
[WizNote 加密笔记](https://www.wiz.cn/ziw-format.html)

### 如何处理笔记的tag

忽略原先为知笔记中的tag, 将笔记的目录作为tag.


## 不同笔记类型处理方式

随着为知笔记的发展, 有如下类型的笔记
- HTML 笔记. 最初的, 使用富文本编辑器编辑的笔记
- Lite 笔记. 依旧使用富文本编辑器, 标题名需要以`.md` 结尾, 需要在富文本编辑器中写 markdown 文本, 进入预览模式才会进行md渲染.
- 协作笔记. 现在最新的笔记格式, 支持多人协作.

项目支持处理以下几种类型的笔记：

- HTML 笔记（document）
   - 使用 `html2text` 库直接将 HTML 转换为 Markdown. 解析后的markdown文本, 差强人意, 完全取决于富文本的格式.(可以尝试使用大模型 reader-lm-v2 这个转换效果好)

- Lite 笔记（lite/markdown）
   - 通过 BeautifulSoup 库解析 HTML 内容
   - 提取 pre 标签中的原始 Markdown 文本

- 协作笔记（collaboration）
   - 通过自定义解析器处理, 手动解析拼装.
   - 支持解析文本、列表、代码块、表格、图片等多种格式
   - 支持解析笔记双链, 块链接,块快照,关键字
   - 支持解析数学公式（LaTeX格式转换为Markdown行内公式）
   - 支持解析内嵌网页（转换为链接格式）
   - 支持解析流程图和附件（使用统一的附件链接格式）
   - 支持解析评论内容（包括用户信息、时间戳和@提及）
   - 自动忽略加密文本、上标下标、文本对齐等格式
   - 使用 WebSocket 通信获取笔记数据

所有类型的笔记在解析后都会经过以下处理：
- 提取并下载笔记中的图片到同级目录 `./images`下
- 替换笔记中的图片链接
- 添加笔记属性（创建时间、更新时间、标签等）
- 进行 Markdown 格式优化（标题、代码块、列表等的格式修正）


## 参考文章

[WizNote 为知笔记 macOS 本地文件夹分析 | ZRONG's BLOG](https://blog.zengrong.net/post/analysis-of-wiznote/)

[server-architecture.md](https://github.com/WizTeam/wiz-editor/blob/main/docs/zh-CN/server-architecture.md)

[GitHub - WizTeam/wiz-editor](https://github.com/WizTeam/wiz-editor)

[为知笔记API文档](https://www.wiz.cn/wapp/pages/book/bb8f0f10-48ca-11ea-b27a-ef51fb9d4bb4/475c9ef0-4e1a-11ea-8f5c-a7618da01da2)
