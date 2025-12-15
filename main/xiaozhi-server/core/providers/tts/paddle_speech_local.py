"""
PaddleSpeech 本地离线 TTS Provider
直接调用 PaddleSpeech 库，无需启动服务器
"""
import os
from pathlib import Path
from config.logger import setup_logging
from core.providers.tts.base import TTSProviderBase

TAG = __name__
logger = setup_logging()


class TTSProvider(TTSProviderBase):
    def __init__(self, config, delete_audio_file):
        super().__init__(config, delete_audio_file)
        
        # 获取配置参数
        self.spk_id = int(config.get("spk_id", 0))
        self.sample_rate = int(config.get("sample_rate", 24000))
        self.speed = float(config.get("speed", 1.0))
        self.volume = float(config.get("volume", 1.0))
        
        # 音频格式
        self.audio_file_type = "wav"
        
        # 初始化 PaddleSpeech TTS
        self._init_tts()
        
        logger.bind(tag=TAG).info("PaddleSpeech 本地 TTS 初始化成功")
    
    def _init_tts(self):
        """初始化 PaddleSpeech TTS 模型"""
        try:
            # 设置模型路径到项目目录
            models_dir = Path(__file__).parent.parent.parent.parent / "models"
            paddle_home = models_dir / ".paddlespeech"
            ppnlp_home = models_dir / ".paddlenlp"

            # 设置环境变量
            os.environ['PADDLE_HOME'] = str(paddle_home)
            os.environ['PPNLP_HOME'] = str(ppnlp_home)

            logger.bind(tag=TAG).info(f"PADDLE_HOME: {paddle_home}")
            logger.bind(tag=TAG).info(f"PPNLP_HOME: {ppnlp_home}")

            from paddlespeech.cli.tts.infer import TTSExecutor

            # 创建 TTS 执行器
            self.tts_executor = TTSExecutor()

            logger.bind(tag=TAG).info("正在加载 PaddleSpeech TTS 模型...")

            # 预热模型（生成一段测试音频）
            # 使用 tmp 目录下的临时文件
            temp_wav = self.generate_filename(".wav")
            try:
                _ = self.tts_executor(
                    text="你好",
                    output=temp_wav
                )
                # 删除临时文件
                if os.path.exists(temp_wav):
                    os.remove(temp_wav)
            except Exception as e:
                logger.bind(tag=TAG).warning(f"预热模型时出现警告（可忽略）: {e}")

            logger.bind(tag=TAG).info("PaddleSpeech TTS 模型加载完成")

        except Exception as e:
            logger.bind(tag=TAG).error(f"PaddleSpeech TTS 初始化失败: {e}")
            raise
    
    async def text_to_speak(self, text, output_file):
        """
        将文本转换为语音

        Args:
            text: 要合成的文本
            output_file: 输出文件路径，如果为 None 则返回音频字节数据

        Returns:
            如果 output_file 为 None，返回音频字节数据；否则返回 None
        """
        try:
            logger.bind(tag=TAG).debug(f"开始合成语音: {text}")

            # PaddleSpeech 必须保存到文件，不能直接返回字节
            # 如果 output_file 为 None，使用临时文件
            if output_file is None:
                # 生成临时文件
                temp_file = self.generate_filename(".wav")

                # 生成音频到临时文件
                _ = self.tts_executor(
                    text=text,
                    output=temp_file
                )

                # 读取文件内容
                with open(temp_file, "rb") as f:
                    audio_bytes = f.read()

                # 删除临时文件
                if os.path.exists(temp_file):
                    os.remove(temp_file)

                logger.bind(tag=TAG).debug(f"音频已生成，大小: {len(audio_bytes)} 字节")
                return audio_bytes
            else:
                # 直接保存到指定文件
                _ = self.tts_executor(
                    text=text,
                    output=output_file
                )
                logger.bind(tag=TAG).debug(f"音频已保存到: {output_file}")
                return None

        except Exception as e:
            error_msg = f"PaddleSpeech TTS 合成失败: {e}"
            logger.bind(tag=TAG).error(error_msg)
            raise Exception(error_msg)


