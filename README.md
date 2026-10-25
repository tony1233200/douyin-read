# douyin-read

抖音分享链接解析下载 + 视频语音转文字，全部在本地运行。

Resolve a Douyin share link, download its video/images, and transcribe the
speech to text — everything runs locally on your machine.

## 功能 / Features

- 输入抖音分享链接（或整段分享文案，自动提取链接），下载无水印视频或图文作品的全部图片
- 解析走可配置的第三方公开接口列表，逐个尝试、自动切换备用端点，**无需登录、无需 cookie**
- 下载的视频自动调用本地 SenseVoice-Small 模型转写成逐字稿（纯 CPU、离线运行）
- 每次运行输出 `meta.json`（标题、作者、耗时）方便二次处理

- Paste a Douyin share link (or the whole share text — the link is extracted
  automatically) and get the watermark-free video or all images of a post.
- Parsing uses a configurable list of third-party public endpoints, tried in
  order with automatic fallback. **No login, no cookies.**
- Downloaded videos are transcribed locally with SenseVoice-Small (CPU-only,
  fully offline).
- Each run writes a `meta.json` (title, author, timings) for further use.

## 安装 / Installation

需要 Python 3.10+ 和 ffmpeg。Requires Python 3.10+ and ffmpeg.

```bash
pip install -r requirements.txt
# ffmpeg: macOS `brew install ffmpeg`, Debian/Ubuntu `sudo apt install ffmpeg`
```

转写模型（SenseVoice-Small，约 230 MB）会在首次运行转写时自动下载到
`./models/`；也可以把已有模型目录通过环境变量 `SENSEVOICE_MODEL_DIR` 指定。
模型来源：SenseVoice-Small 由阿里巴巴 FunAudioLLM 发布，此处使用 sherpa-onnx
（k2-fsa）打包的 int8 ONNX 版本（GitHub Releases 提供下载，ModelScope 有镜像）。

The speech model (~230 MB) is downloaded automatically on first use into
`./models/`, or point `SENSEVOICE_MODEL_DIR` at an existing copy. Model:
SenseVoice-Small by Alibaba FunAudioLLM, int8 ONNX build packaged by
sherpa-onnx (k2-fsa), also mirrored on ModelScope.

## 用法 / Usage

```bash
# 下载视频 + 转写
python douyin_read.py "https://v.douyin.com/xxxxxx/"

# 粘贴整段分享文案也可以
python douyin_read.py "8.46 复制打开抖音，看看这个视频 https://v.douyin.com/xxxxxx/ ..."

# 指定输出目录、只下载不转写
python douyin_read.py "https://v.douyin.com/xxxxxx/" ./out --no-transcribe

# 单独转写任意音/视频文件
python transcribe.py video.mp4 transcript.txt
```

输出目录（默认 `./output/<作品ID>/`）：

```
output/<aweme_id>/
├── meta.json          # 标题 / 作者 / 解析端点 / 耗时
├── video-<id>.mp4     # 视频作品
├── img-<id>-1.jpg     # 图文作品图片（多张依次编号）
└── transcript.txt     # 逐字稿
```

## 解析端点说明 / About the parsing endpoints

抖音没有提供面向分享链接的公开 API，本工具通过代码内 `PARSE_ENDPOINTS`
列表中的第三方公开解析接口获取媒体直链，接口由社区第三方运营：

- 任意端点都可能变更、限流或下线，失效时编辑 `douyin_read.py` 里的
  `PARSE_ENDPOINTS` 换新即可（GET 请求、分享链接作为 `url` 参数）；
- 本工具自身不收集、不上传任何账号信息；分享链接会发送给所选解析端点，
  这是解析的必要步骤。

Douyin offers no public API for share links, so media URLs are obtained
through third-party public parsing endpoints listed in `PARSE_ENDPOINTS`
in `douyin_read.py`. They are community-run: any of them may change or go
offline, in which case edit the list (GET, share link as the `url`
parameter). This tool collects no account data; the share link is sent to
the chosen endpoint, which is required for parsing.

## 目录结构 / Layout

```
douyin-read/
├── douyin_read.py     # 主脚本：解析 -> 下载 -> 转写
├── transcribe.py      # SenseVoice-Small 离线转写封装
├── requirements.txt
├── LICENSE
└── README.md
```

## 免责声明 / Disclaimer

本项目仅供个人学习与技术研究使用。下载内容的版权归原作者及平台所有，
请勿用于商业用途或二次分发；使用时请遵守抖音平台的用户条款与当地法律法规。
因使用本工具产生的任何后果由使用者自行承担。

For personal learning and research only. Downloaded content belongs to its
original authors and the platform; do not use it commercially or redistribute
it. Comply with Douyin's terms of service and applicable laws. Use at your
own risk.

## License

MIT — see [LICENSE](LICENSE).
