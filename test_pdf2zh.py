import json

from pdf2zh import translate
from pdf2zh.config import ConfigManager
from pdf2zh.doclayout import OnnxModel

# 加载配置
with open('pdf2zh_config.json', 'r') as f:
    config = json.load(f)

# 应用配置
for key, value in config.items():
    if key not in ['models', 'fonts']:
        ConfigManager.set(key, value)

# 设置模型
model_path = config['models']['doclayout_path']
model = OnnxModel(model_path)

# 设置字体
font_path = config['fonts']['zh']
ConfigManager.set("NOTO_FONT_PATH", font_path)

# service = silicon
# envs ={
#     "SILICON_API_KEY": "自己的api-key",
#     "SILICON_MODEL": "Qwen/Qwen2.5-7B-Instruct"
# }

# service = ollama
# envs ={
#     "OLLAMA_HOST": "http://127.0.0.1:11434",
#     "OLLAMA_MODEL": "deepseek-r1:1.5b"
# }

# service = google/bing
envs = {}


params = {
    "model": model,
    "lang_in": "en",
    "lang_out": "zh",
    "service": "bing", 
    "thread": 4,
    "vfont": font_path,
    "envs": envs
}

(file_mono, file_dual) = translate(files=["test.pdf"], **params)[0]