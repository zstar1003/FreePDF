"""FreePDF主程序"""

import multiprocessing
import os
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 全局变量，防止重复加载
_PDF2ZH_MODULES = None
_PDF2ZH_CONFIG = None
_PDF2ZH_LOADED = False

def get_app_dir():
    """获取应用程序目录，兼容开发环境和打包环境"""
    if getattr(sys, 'frozen', False):
        # 打包后的exe环境
        app_dir = os.path.dirname(sys.executable)
        print(f"运行环境: 打包EXE, 应用目录: {app_dir}")
        return app_dir
    else:
        # 开发环境
        app_dir = os.path.dirname(os.path.abspath(__file__))
        print(f"运行环境: 开发环境, 应用目录: {app_dir}")
        return app_dir

def get_resource_path(relative_path):
    """获取资源文件路径，兼容开发环境和打包环境"""
    app_dir = get_app_dir()
    resource_path = os.path.join(app_dir, relative_path)
    print(f"资源文件: {relative_path} -> {resource_path}")
    return resource_path

# 在PyQt6初始化之前预加载pdf2zh模块，避免环境冲突
def _load_pdf2zh_modules():
    """预加载pdf2zh模块"""
    global _PDF2ZH_MODULES, _PDF2ZH_CONFIG, _PDF2ZH_LOADED
    
    if _PDF2ZH_LOADED:
        print("pdf2zh模块已加载，跳过重复加载")
        return
        
    print("正在预加载pdf2zh模块...")
    print(f"Python版本: {sys.version}")
    print(f"当前工作目录: {os.getcwd()}")
    print(f"sys.path: {sys.path[:3]}...")  # 只显示前3个路径避免输出过长
    
    try:
        print("步骤1: 导入标准库...")
        import json
        
        # 在exe环境下设置onnxruntime的DLL路径
        if hasattr(sys, '_MEIPASS'):
            print("步骤1.5: 设置exe环境下的DLL路径...")
            exe_dir = sys._MEIPASS
            internal_dir = os.path.join(exe_dir, '_internal')
            
            # 添加onnxruntime DLL路径
            onnx_paths = [
                os.path.join(internal_dir, 'onnxruntime', 'capi'),
                os.path.join(internal_dir, 'onnxruntime'),
                internal_dir
            ]
            
            for path in onnx_paths:
                if os.path.exists(path):
                    if hasattr(os, 'add_dll_directory'):
                        try:
                            os.add_dll_directory(path)
                            print(f"  - 添加DLL搜索路径: {path}")
                        except Exception as e:
                            print(f"  - 添加DLL路径失败: {e}")
                    
                    # 更新PATH环境变量
                    current_path = os.environ.get('PATH', '')
                    if path not in current_path:
                        os.environ['PATH'] = path + os.pathsep + current_path
                        print(f"  - 更新PATH: {path}")

        print("步骤2: 导入pdf2zh模块...")
        
        # 尝试先导入onnxruntime（使用hook确保兼容性）
        try:
            print("  - 预导入onnxruntime hook...")
            import onnxruntime_hook
            print("  - onnxruntime hook 导入成功")
        except Exception as e:
            print(f"  - onnxruntime hook 导入失败: {e}")
            
        try:
            print("  - 预导入onnxruntime...")
            import onnxruntime
            print(f"  - onnxruntime版本: {onnxruntime.__version__}")
        except Exception as e:
            print(f"  - onnxruntime导入失败: {e}")
            # 继续尝试导入pdf2zh，也许不需要onnxruntime
        
        try:
            from pdf2zh import translate
            print("  - translate 导入成功")
        except Exception as e:
            print(f"  - translate 导入失败: {e}")
            raise
            
        try:
            from pdf2zh.config import ConfigManager
            print("  - ConfigManager 导入成功")
        except Exception as e:
            print(f"  - ConfigManager 导入失败: {e}")
            raise
            
        try:
            from pdf2zh.doclayout import OnnxModel
            print("  - OnnxModel 导入成功")
        except Exception as e:
            print(f"  - OnnxModel 导入失败: {e}")
            raise
        
        print("步骤3: 读取配置文件...")
        # 获取配置文件路径
        config_path = get_resource_path('pdf2zh_config.json')
        
        if not os.path.exists(config_path):
            # 尝试其他可能的位置
            alternative_paths = [
                'pdf2zh_config.json',  # 当前目录
                os.path.join(os.getcwd(), 'pdf2zh_config.json'),  # 工作目录
            ]
            for alt_path in alternative_paths:
                print(f"尝试替代路径: {alt_path}")
                if os.path.exists(alt_path):
                    config_path = alt_path
                    print(f"找到配置文件: {config_path}")
                    break
            else:
                raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
        # 加载配置
        print(f"读取配置文件: {config_path}")
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        print(f"原始配置: {config}")

        print("步骤4: 修正文件路径...")
        # 修正配置中的相对路径为绝对路径
        app_dir = get_app_dir()
        
        # 修正模型路径
        if 'models' in config and 'doclayout_path' in config['models']:
            model_path = config['models']['doclayout_path']
            if not os.path.isabs(model_path):
                new_model_path = os.path.normpath(os.path.join(app_dir, model_path))
                config['models']['doclayout_path'] = new_model_path
                print(f"模型路径: {model_path} -> {new_model_path}")
        
        # 修正字体路径
        if 'fonts' in config:
            for font_key in config['fonts']:
                font_path = config['fonts'][font_key]
                if not os.path.isabs(font_path):
                    new_font_path = os.path.normpath(os.path.join(app_dir, font_path))
                    config['fonts'][font_key] = new_font_path
                    print(f"字体路径 {font_key}: {font_path} -> {new_font_path}")
        
        print("步骤5: 检查文件存在性...")
        # 检查关键文件是否存在
        model_path = config['models']['doclayout_path']
        print(f"检查模型文件: {model_path}")
        if not os.path.exists(model_path):
            print("模型文件不存在！列出模型目录内容:")
            model_dir = os.path.dirname(model_path)
            if os.path.exists(model_dir):
                print(f"模型目录内容: {os.listdir(model_dir)}")
            else:
                print(f"模型目录不存在: {model_dir}")
            raise FileNotFoundError(f"模型文件不存在: {model_path}")
        
        font_path = config['fonts']['zh']
        print(f"检查字体文件: {font_path}")
        if not os.path.exists(font_path):
            print("字体文件不存在！列出字体目录内容:")
            font_dir = os.path.dirname(font_path)
            if os.path.exists(font_dir):
                print(f"字体目录内容: {os.listdir(font_dir)}")
            else:
                print(f"字体目录不存在: {font_dir}")
            raise FileNotFoundError(f"字体文件不存在: {font_path}")
        
        print("步骤6: 应用配置...")
        # 应用配置
        for key, value in config.items():
            if key not in ['models', 'fonts']:
                ConfigManager.set(key, value)
                print(f"设置配置: {key} = {value}")

        # 设置字体
        ConfigManager.set("NOTO_FONT_PATH", font_path)
        print(f"设置字体路径: {font_path}")
        
        print("步骤7: 保存到全局变量...")
        # 将预加载的模块和配置保存到全局变量
        _PDF2ZH_MODULES = {
            'translate': translate,
            'ConfigManager': ConfigManager,
            'OnnxModel': OnnxModel
        }
        _PDF2ZH_CONFIG = config
        _PDF2ZH_LOADED = True
        
        print("✅ pdf2zh模块预加载成功")
        
    except Exception as e:
        print(f"❌ pdf2zh模块预加载失败: {e}")
        import traceback
        traceback.print_exc()
        _PDF2ZH_MODULES = None
        _PDF2ZH_CONFIG = None
        _PDF2ZH_LOADED = True  # 标记为已尝试加载，避免重复尝试

# 预加载模块
_load_pdf2zh_modules()

# 安全地导入PyQt6
from PyQt6.QtWebEngineCore import QWebEngineProfile
from PyQt6.QtWidgets import QApplication

from ui.main_window import MainWindow


def get_pdf2zh_modules():
    """获取预加载的pdf2zh模块"""
    return _PDF2ZH_MODULES, _PDF2ZH_CONFIG


if __name__ == "__main__":
    # 配置多进程支持
    multiprocessing.freeze_support()

    app = QApplication(sys.argv)
    
    # 设置应用程序属性
    app.setApplicationName("FreePDF")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("zstar")
    
    # 预热WebEngine，提前初始化核心组件
    print("正在预热WebEngine...")
    profile = QWebEngineProfile.defaultProfile()
    profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
    profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies)
    print("WebEngine核心组件预热完成")
    
    # 创建主窗口
    window = MainWindow()
    window.showMaximized()
    
    # 运行应用程序
    sys.exit(app.exec())