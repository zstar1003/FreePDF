import json

from pdf2zh_next.high_level import SettingsModel, do_translate_file

if __name__ == '__main__':
    # 加载配置
    with open('pdf2zh_config.json', 'r') as f:
        config = json.load(f)

    # ConfigManager 不支持动态设置配置，它从配置文件读取
    # 这里我们只需要读取配置内容，不需要手动设置
    print("从配置文件读取配置...")
    for key, value in config.items():
        if key not in ['models', 'fonts']:
            print(f"配置项: {key} = {value}")

    # 设置模型路径 - 新API不需要手动加载模型
    model_path = config['models']['doclayout_path']
    print(f"模型路径: {model_path}")

    # 设置字体
    font_path = config['fonts']['zh']
    print(f"字体路径: {font_path}")

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


    # 创建配置对象
    translate_engine_settings = config.get('translation', {})
    # 将服务名转换为正确的格式（首字母大写）
    service_name = translate_engine_settings.get('service', 'bing')
    service_mapping = {
        'bing': 'Bing',
        'google': 'Google',
        'openai': 'OpenAI',
        'deepl': 'DeepL',
        'deepseek': 'DeepSeek',
        'ollama': 'Ollama',
        'xinference': 'Xinference',
        'azureopenai': 'AzureOpenAI',
        'modelscope': 'ModelScope',
        'zhipu': 'Zhipu',
        'siliconflow': 'SiliconFlow',
        'tencentmechinetranslation': 'TencentMechineTranslation',
        'gemini': 'Gemini',
        'azure': 'Azure',
        'anythingllm': 'AnythingLLM',
        'dify': 'Dify',
        'grok': 'Grok',
        'groq': 'Groq',
        'qwenmt': 'QwenMt',
        'openaicompatible': 'OpenAICompatible'
    }
    translate_engine_settings['translate_engine_type'] = service_mapping.get(service_name.lower(), 'Bing')

    # 根据 SettingsModel 的结构创建配置
    settings = SettingsModel(
        basic={
            "input_files": ["test.pdf"],
            "lang_in": "en",
            "lang_out": "zh", 
            "service": "bing",
            "thread_count": 1  # 减少线程数，避免并发问题
        },
        translation={
            "font_path": font_path,
            "envs": envs
        },
        translate_engine_settings=translate_engine_settings
    )

    # 执行翻译
    # 只传递 settings，因为输入文件已经在 settings 中指定
    error_count = do_translate_file(settings)
    print(f"翻译完成，错误数量: {error_count}")