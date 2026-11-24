# v7.2 Kaggle 云端配音

在已授权的 Kaggle Notebook 中启用 GPU 与互联网，添加随机 `KAGGLE_TTS_TOKEN` Secret 并向当前 Notebook 开放访问。导入 `kaggle_qwen3_tts_server.ipynb` 后按顺序运行，最后一个单元给出本次会话 HTTPS 地址。会话结束后临时隧道关闭。

本机设置 `KAGGLE_TTS_ENDPOINT_URL` 与相同的 `KAGGLE_TTS_TOKEN`。可先执行 `./install.sh --check` 确认依赖、离线 Whisper 权重和品牌参考音，再用 `kit/scripts/voice.sh script.md --backend kaggle --speed 1.0 --output voice` 生成。

鉴权 `POST /tts_async` 返回 `job_id`，客户端每 2.5 秒查询 `GET /tts_job/{job_id}`，直到 `done` 或 `error`。默认等待 900 秒，可用 `YICE_TTS_TIMEOUT` 调整。仅异步提交 HTTP 404 时回退原有同步 `POST /tts`。参考音频通过 HTTPS 内存直传，同参考音与文本复用克隆提示。

随后根据语音首字时间完善 `episode-manifest.json`，运行 `kit/scripts/assemble-episode.sh episode-manifest.json --output out`，再执行 `audit-v3.sh --v7`。Modal 端点仅在明确授权时调用。
