# Kaggle 云端原速配音

在已授权的 Kaggle Notebook 中启用 GPU 与互联网，将已有服务凭据作为 Notebook 私有 Secret 授权给本次会话，或在隐藏输入框中输入已有凭据。导入 `kaggle_qwen3_tts_server.ipynb` 后按顺序运行，最后一个单元给出本次会话 HTTPS 地址。会话结束后临时隧道关闭。

本机设置 `KAGGLE_TTS_ENDPOINT_URL` 与相同的 `KAGGLE_TTS_TOKEN`。可先执行 `./install.sh --check` 确认依赖、离线 Whisper 权重和品牌参考音，再用 `kit/scripts/voice.sh script.md --backend kaggle --speed 1.0 --output voice` 生成。

鉴权 `POST /tts_async` 返回 `job_id`，客户端每 2.5 秒查询 `GET /tts_job/{job_id}`，直到 `done` 或 `error`。默认等待 900 秒，可用 `YICE_TTS_TIMEOUT` 调整。仅异步提交 HTTP 404 时回退原有同步 `POST /tts`。私有 `POST /asr` 使用 Whisper large-v3 返回逐词时间，显存推理库不兼容时在该 Kaggle 会话内使用 CPU。长章按声学停顿分段上传，已识别段以音频哈希缓存，词时间回归原始时间轴。参考音频通过 HTTPS 内存直传，同参考音与文本复用克隆提示。

人工复听已锁定一批原音时，可将显式候选清单路径传给 `--reuse-candidates` 或同义环境变量 `YICE_VOICE_REUSE_CANDIDATES`；正式入口逐条核对文本、seed、品牌与 WAV 的 SHA-256，再对相同录音复核。

随后根据语音首字时间完善 `episode-manifest.json`，运行 `kit/scripts/assemble-episode.sh episode-manifest.json --output out`，再执行 `audit-v3.sh --v10`。Modal 端点仅在明确授权时调用。

## 换电脑迁移配音

在本人电脑上运行 `./install.sh --configure-voice 精修参考音.wav 对应原文.txt`。端点配置和声纹都保存在 `~/.config/yice-youtube-video/`。换电脑时只需私下拷贝这个目录，保持文件权限 0600，再运行安装检查。未配置私人参考音时使用工具包品牌配置。
