# 云端配音

在 Kaggle Notebook 中启用 GPU 和互联网。在 Secrets 中设置随机生成的 KAGGLE_TTS_TOKEN，并向当前 Notebook 开放读取权限。导入本目录的 Notebook 后顺序运行全部单元。最后一个单元会显示本次临时 HTTPS 地址；会话结束后隧道关闭。

本机设置同一 KAGGLE_TTS_TOKEN 和显示的 KAGGLE_TTS_ENDPOINT_URL。使用 `voice.sh 稿件.md --stage draft --output 草稿目录` 进行排演。正式配音使用 `--stage master --speed 1.0` 并配置 MODAL_QWEN3_TTS_ENDPOINT_URL。音频随 HTTPS 请求直传，服务在内存中读取参考音频。
