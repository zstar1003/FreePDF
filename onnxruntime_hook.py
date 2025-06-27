"""
ONNXRuntime Hook for PyInstaller

这个文件用于解决ONNXRuntime在PyInstaller打包环境中的依赖问题。
确保ONNXRuntime能够正确找到其动态链接库和提供者。
"""

import os
import sys
from pathlib import Path


def setup_onnxruntime():
    """设置ONNXRuntime环境"""
    try:
        # 检查是否在PyInstaller打包环境中
        if getattr(sys, 'frozen', False):
            # 在打包环境中
            bundle_dir = Path(sys._MEIPASS)
            
            # 添加ONNXRuntime库路径
            onnx_lib_path = bundle_dir / "onnxruntime" / "capi"
            if onnx_lib_path.exists():
                os.environ['PATH'] = str(onnx_lib_path) + os.pathsep + os.environ.get('PATH', '')
                print(f"ONNXRuntime库路径已添加: {onnx_lib_path}")
            
            # 设置ONNXRuntime提供者路径
            providers_path = bundle_dir / "onnxruntime" / "capi" / "onnxruntime_providers_shared.dll"
            if providers_path.exists():
                os.environ['ONNXRUNTIME_PROVIDERS_PATH'] = str(providers_path.parent)
                print(f"ONNXRuntime提供者路径已设置: {providers_path.parent}")
        
        # 尝试导入ONNXRuntime
        import onnxruntime as ort
        
        # 检查可用的执行提供者
        available_providers = ort.get_available_providers()
        print(f"可用的ONNXRuntime提供者: {available_providers}")
        
        # 优先使用CPU提供者以确保兼容性
        preferred_providers = ['CPUExecutionProvider']
        if 'CUDAExecutionProvider' in available_providers:
            preferred_providers.insert(0, 'CUDAExecutionProvider')
            print("检测到CUDA支持")
        
        return True, preferred_providers
        
    except ImportError as e:
        print(f"ONNXRuntime导入失败: {e}")
        return False, []
    except Exception as e:
        print(f"ONNXRuntime设置出错: {e}")
        return False, []

def create_session_with_fallback(model_path, providers=None):
    """创建ONNXRuntime会话，带有fallback机制"""
    try:
        import onnxruntime as ort
        
        if providers is None:
            providers = ['CPUExecutionProvider']
        
        # 尝试使用指定的提供者创建会话
        for provider in providers:
            try:
                session = ort.InferenceSession(
                    model_path,
                    providers=[provider]
                )
                print(f"成功使用 {provider} 创建ONNXRuntime会话")
                return session
            except Exception as e:
                print(f"使用 {provider} 创建会话失败: {e}")
                continue
        
        # 如果所有指定提供者都失败，尝试使用默认设置
        session = ort.InferenceSession(model_path)
        print("使用默认设置创建ONNXRuntime会话")
        return session
        
    except Exception as e:
        print(f"创建ONNXRuntime会话失败: {e}")
        raise

def get_model_info(session):
    """获取模型信息"""
    try:
        inputs = session.get_inputs()
        outputs = session.get_outputs()
        
        input_info = [(inp.name, inp.shape, inp.type) for inp in inputs]
        output_info = [(out.name, out.shape, out.type) for out in outputs]
        
        print(f"模型输入: {input_info}")
        print(f"模型输出: {output_info}")
        
        return input_info, output_info
    except Exception as e:
        print(f"获取模型信息失败: {e}")
        return [], []

# 在模块导入时自动设置
if __name__ == "__main__":
    # 测试脚本
    success, providers = setup_onnxruntime()
    if success:
        print("ONNXRuntime设置成功")
        print(f"推荐的提供者: {providers}")
    else:
        print("ONNXRuntime设置失败")
else:
    # 作为模块导入时自动设置
    setup_onnxruntime() 