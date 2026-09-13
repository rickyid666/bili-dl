# bili_dl · B站视频下载器

输入 B站视频地址 → 自动取流 → **ffmpeg 无损合并音视频**（`-c copy`，不重新编码，画质零损失）。

只依赖 Python 标准库 + `tools/ffmpeg.exe`，不需要 pip 装任何东西。

## 安装（从零开始三步）

```bat
git clone <本仓库地址> bili-dl
cd bili-dl
python tools/get_ffmpeg.py      :: 下载 ffmpeg 到 tools/（仓库里不含这个 100MB 的二进制）
```

然后双击 `启动.bat` 即可。ffmpeg 只下一次，之后一直在。

> 已经装过 ffmpeg 的话，把 `ffmpeg.exe` 丢进 `tools/`，或者直接 `--ffmpeg <路径>` 也行。


---

## 一、怎么用

### 方式 A：网页界面（推荐）

双击 **`启动.bat`** → 浏览器自动打开 `http://127.0.0.1:8848` → 粘贴链接 → 点「开始下载」。

关闭那个黑窗口即停止服务。

### 方式 B：命令行

```bat
python bili_dl.py BV1jw8w6yESY                    :: 默认最高清晰度
python bili_dl.py https://www.bilibili.com/video/BV1jw8w6yESY/ -q 1080 -p all
python bili_dl.py BV1jw8w6yESY BV1vyNmzxErv       :: 一次多个
python bili_dl.py BV1jw8w6yESY --cookie "SESSDATA=xxx; bili_jct=yyy"
```

常用参数：

| 参数 | 说明 |
|---|---|
| `-q, --quality` | `best` / `8k` / `4k` / `1080p60` / `1080` / `720p60` / `720` / `480` / `360` |
| `-p, --parts` | `1`（默认）/ `1,3` / `all` |
| `-o, --outdir` | 输出目录，默认 `downloads/` |
| `--cookie` | 登录 cookie，也可用环境变量 `BILI_COOKIE` |
| `--cookie-file` | 从文本文件读 cookie |
| `--threads` | 分片线程数，默认 8 |
| `--ffmpeg` | 手动指定 ffmpeg.exe |
| `--keep-temp` | 保留下载的 `.m4s` 临时流 |

### 方式 C：双击 `命令行下载.bat`

按提示依次输入 **链接 → 清晰度 → 分P**，全程只按回车也能跑（默认 best + 第 1 P）。适合不想开网页的时候。

---

## 二、清晰度能到多高？（重要）

B站把清晰度锁在**登录态**上：

| 身份 | 最高能拿到 |
|---|---|
| 不填 cookie（游客） | **480P** |
| 填了 cookie（普通账号） | **1080P**（部分视频 1080P60） |
| 大会员 cookie | 4K / HDR / 杜比视界 |

**怎么拿 cookie：**

1. 浏览器打开并登录 bilibili.com
2. 按 `F12` → 切到 `Console`（控制台）
3. 输入 `document.cookie` 回车
4. 复制整串（含 `SESSDATA=...; bili_jct=...` 等），粘到网页界面的「登录 cookie」框里（会自动记住），或命令行 `--cookie "..."`

> cookie 只存在本机 `config.json`，不会外发。想清空直接删掉该文件即可。

---

## 三、它是怎么做的

```
链接/BV号
  └─ /x/web-interface/view        拿 cid、标题、分P
  └─ /x/player/playurl (fnval=4048)  拿 DASH 流清单
       ├─ 视频轨：按目标清晰度筛选，同清晰度优先 avc1（兼容性最好）
       └─ 音频轨：取码率最高的一条
  └─ 多线程 Range 分片并发下载（默认 8 线程），失败自动切换备用 CDN
  └─ ffmpeg -c copy -movflags +faststart   无损封装成 mp4
```

几个实现上的讲究：

- **不重新编码**：只是把两条流装进同一个 mp4 容器，秒级完成、画质无损、体积不变。
- **Range 并发**：单文件按段并发拉取，大文件速度提升明显；CDN 不支持 Range 时自动退回单线程。
- **备用地址**：B站会给三条 CDN 地址，主地址失败自动换下一条。
- **签名时效**：B站直链带 `deadline` 签名，过期即失效——所以是"边取边下"，不缓存链接。
- **删除容错**：临时文件清理全部延后且不致命，删除失败不会影响已完成的成品。

---

## 四、目录结构

```
bili-dl/
├── 启动.bat            ← 双击启动网页界面
├── bili_web.py         ← 网页界面（本地 HTTP 服务 + 内嵌前端）
├── bili_dl.py          ← 下载核心（也可单独当命令行工具用）
├── tools/ffmpeg.exe    ← 自带的 ffmpeg（合并用，可替换成新版）
├── downloads/          ← 下载产物
└── config.json         ← 记住的 cookie / 清晰度偏好（自动生成）
```

---

## 五、常见问题

**Q：提示"未找到 ffmpeg"？**
把 `ffmpeg.exe` 放进 `tools/` 目录，或用 `--ffmpeg <路径>` 指定。程序也会自动搜索 PATH。

**Q：只能下到 480P？**
没填 cookie。见上面第二节。

**Q：1080P 视频下载后是分开的两个文件？**
不会。视频轨与音频轨会合并成一个 mp4；只有在你手动 `--keep-temp` 时才会看到 `.m4s` 临时文件。

**Q：下载很慢？**
B站对单连接限速，`--threads 16` 可以再快一些；也可以换清晰度（码率越低越快）。

**Q：能下番剧/付费课程吗？**
不能。那些走不同的接口且需要大会员权限，本工具只处理普通投稿视频。

---

## 六、维护备注（改这个项目前先看）

- **两个 `.bat` 必须用「GBK 编码 + CRLF 行尾」写**，这是踩过的坑：
  - 存成 UTF-8 → cmd 按 GBK 解析文件字节，`echo` 出来的中文全是乱码；
  - 用 LF（Unix）行尾 → cmd 解析 `if (...)` / `goto` 这类多行结构会出错，双击直接失效。
  - 要改 bat，用 `tools/make_bat.py` 重新生成（它按 GBK + CRLF 写），别手动"另存为"。
- **界面没用 tkinter**：本机 pythoncore 版 Python 不带 tkinter，所以走标准库 `http.server`。
- **Python 版本**：只用标准库，3.8+ 都能跑。本机 cmd 里是 3.13（workbuddy），pwsh 里是 3.14，两个都实测通过。
- **端口 8848 被占用**：`set BILI_DL_PORT=8849` 再启动，程序也会给出这个提示。
- 临时文件清理在受限环境下可能被拦截，代码里已做"延后清理 + 失败回退 `cmd /c del`"，绝不影响成品。

---

## 七、安全与免责

### 关于 cookie（重要）

- `config.json` 会保存你填过的 cookie —— 它等价于**账号登录凭据**（含 `SESSDATA`、`bili_jct`）。
- 本仓库 `.gitignore` 已排除 `config.json`、`cookies.txt`、`downloads/`、`tools/ffmpeg.exe`。
- **不要把 `config.json` 发给任何人、不要提交进仓库、不要丢进网盘分享。**
- 怀疑泄露：B站「设置 → 安全隐私 → 退出所有设备」强制下线，旧 cookie 随即失效。

### 免责声明

- 本项目仅供个人学习与技术研究使用，请勿用于商业用途或大规模抓取。
- 下载的视频版权归原作者所有，请遵守B站用户协议，勿二次传播或用于侵权用途。
- 使用本工具产生的一切后果由使用者自行承担。

## 八、许可

MIT License，详见 [LICENSE](LICENSE)。
