import os
import sys
import io
import re
import wave
from config.logger import setup_logging
from config.config_loader import get_internal_dir
from core.providers.tts.base import TTSProviderBase

try:
    import sherpa_onnx
except ImportError:
    raise ImportError(
        "sherpa-onnx库未安装，请运行: pip install sherpa-onnx"
    )

try:
    import cn2an
    CN2AN_AVAILABLE = True
except ImportError:
    CN2AN_AVAILABLE = False
    logger = setup_logging()
    logger.warning("cn2an库未安装，数字将无法正确转换为中文。建议运行: pip install cn2an")

TAG = __name__
logger = setup_logging()


# 捕获标准输出
class CaptureOutput:
    def __enter__(self):
        self._output = io.StringIO()
        self._original_stdout = sys.stdout
        sys.stdout = self._output

    def __exit__(self, exc_type, exc_value, traceback):
        sys.stdout = self._original_stdout
        self.output = self._output.getvalue()
        self._output.close()

        # 将捕获到的内容通过 logger 输出
        if self.output:
            logger.bind(tag=TAG).debug(self.output.strip())


def convert_numbers_to_chinese(text: str) -> str:
    """
    将文本中的数字和单位转换为中文

    Args:
        text: 输入文本

    Returns:
        转换后的文本

    Examples:
        "温度是28.2℃" -> "温度是二十八点二摄氏度"
        "风速11.0 m/s" -> "风速十一点零米每秒"
        "今天是2025年12月16日" -> "今天是二零二五年十二月十六日"
    """
    if not CN2AN_AVAILABLE:
        logger.bind(tag=TAG).warning("cn2an 库不可用，跳过数字转换")
        return text

    try:
        logger.bind(tag=TAG).debug(f"开始数字转换: {text}")

        # 0. 先处理百分比（必须在其他转换之前，因为需要特殊处理）
        # 匹配 "数字 %" 或 "数字%" 的模式
        def replace_percentage(match):
            num_str = match.group(1).strip()
            try:
                if '.' in num_str:
                    # 小数百分比：65.3% -> 百分之六十五点三
                    parts = num_str.split('.')
                    integer_part = cn2an.an2cn(parts[0], "low")
                    decimal_part = ''.join([cn2an.an2cn(d, "low") for d in parts[1]])
                    return f"百分之{integer_part}点{decimal_part}"
                else:
                    # 整数百分比：80% -> 百分之八十
                    return f"百分之{cn2an.an2cn(num_str, 'low')}"
            except:
                return match.group(0)

        text = re.sub(r'(\d+(?:\.\d+)?)\s*%', replace_percentage, text)

        # 1. 处理单位符号和特殊字符（注意顺序：长的在前，避免被短的先替换）
        unit_map = {
            # 复合单位（必须在单个单位之前处理）
            'W/m²': '瓦每平方米',
            'W/m2': '瓦每平方米',
            'm/s': '米每秒',
            'km/h': '千米每小时',
            # 温度单位
            '℃': '摄氏度',
            '°C': '摄氏度',
            '°F': '华氏度',
            # 压力单位
            'hPa': '百帕',
            'Pa': '帕',
            # 长度单位
            'mm': '毫米',
            'cm': '厘米',
            'km': '千米',
            # 角度
            '°': '度',
            # 标点符号
            '：': ',',  # 中文冒号转为逗号（更自然）
            ':': ',',   # 英文冒号转为逗号
        }

        for symbol, chinese in unit_map.items():
            text = text.replace(symbol, chinese)

        # 处理单独的 "m"（米），但要避免误替换单词中的 m
        # 只替换 "数字 m" 或 "数字m" 的情况
        text = re.sub(r'(\d)\s*m(?=\s|$|[,，。.])', r'\1米', text)

        # 2. 处理小数（如 28.2 -> 二十八点二）
        def replace_decimal(match):
            num_str = match.group(0)
            try:
                parts = num_str.split('.')
                integer_part = cn2an.an2cn(parts[0], "low")
                decimal_part = ''.join([cn2an.an2cn(d, "low") for d in parts[1]])
                return f"{integer_part}点{decimal_part}"
            except:
                return num_str

        text = re.sub(r'\d+\.\d+', replace_decimal, text)

        # 2. 处理年份（如 2025 -> 二零二五）
        def replace_year(match):
            year_str = match.group(1)
            try:
                # 年份按数字逐个读
                return ''.join([cn2an.an2cn(d, "low") for d in year_str]) + '年'
            except:
                return match.group(0)

        text = re.sub(r'(\d{4})年', replace_year, text)

        # 3. 处理长数字串（如电话号码，超过4位的连续数字）
        def replace_long_number(match):
            num_str = match.group(0)
            if len(num_str) > 4:
                # 长数字按位读
                try:
                    return ''.join([cn2an.an2cn(d, "low") for d in num_str])
                except:
                    return num_str
            else:
                # 短数字正常转换
                try:
                    return cn2an.an2cn(num_str, "low")
                except:
                    return num_str

        text = re.sub(r'\d+', replace_long_number, text)

        return text

    except Exception as e:
        logger.bind(tag=TAG).warning(f"数字转换失败: {e}，返回原文本")
        return text


class TTSProvider(TTSProviderBase):
    def __init__(self, config, delete_audio_file):
        super().__init__(config, delete_audio_file)
        
        # 获取模型目录路径
        model_dir = config.get("model_dir", "models/sherpa-onnx-vits-zh-ll")
        
        # 处理相对路径，转换为绝对路径（使用内部资源目录）
        if not os.path.isabs(model_dir):
            internal_dir = get_internal_dir()
            self.model_dir = os.path.join(internal_dir, model_dir)
        else:
            self.model_dir = model_dir
        
        # 检查模型目录是否存在
        if not os.path.exists(self.model_dir):
            raise FileNotFoundError(f"模型目录不存在: {self.model_dir}")
        
        # 获取说话人ID，默认为0
        if config.get("private_voice"):
            self.speaker_id = int(config.get("private_voice"))
        else:
            self.speaker_id = int(config.get("sid", 0))
        
        # 获取音频格式，默认为wav
        self.audio_file_type = config.get("format", "wav")
        
        # 构建模型文件路径
        model_file = os.path.join(self.model_dir, "model.onnx")
        lexicon_file = os.path.join(self.model_dir, "lexicon.txt")
        tokens_file = os.path.join(self.model_dir, "tokens.txt")
        dict_dir = os.path.join(self.model_dir, "dict")
        
        # 检查必需的文件是否存在
        required_files = {
            "model.onnx": model_file,
            "lexicon.txt": lexicon_file,
            "tokens.txt": tokens_file,
        }
        
        for file_name, file_path in required_files.items():
            if not os.path.exists(file_path):
                raise FileNotFoundError(
                    f"模型文件不存在: {file_path}，请确保模型文件完整"
                )
        
        # 检查dict目录
        if not os.path.exists(dict_dir):
            logger.bind(tag=TAG).warning(
                f"字典目录不存在: {dict_dir}，将不使用字典目录"
            )
            dict_dir = ""
        
        # 获取规则FST文件（可选）
        rule_fsts = []
        rule_fst_files = [
            "number.fst",
            "phone.fst",
            "date.fst",
            "new_heteronym.fst",
        ]
        
        for fst_file in rule_fst_files:
            fst_path = os.path.join(self.model_dir, fst_file)
            if os.path.exists(fst_path):
                rule_fsts.append(fst_path)
        
        # 初始化TTS模型
        logger.bind(tag=TAG).info(f"正在加载sherpa-onnx-vits-zh-ll模型: {self.model_dir}")
        
        try:
            with CaptureOutput():
                # 构建OfflineTts配置
                # 注意：当前版本的sherpa-onnx不支持rule_fsts属性，因此不设置FST规则文件
                tts_config = sherpa_onnx.OfflineTtsConfig(
                    model=sherpa_onnx.OfflineTtsModelConfig(
                        vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                            model=model_file,
                            lexicon=lexicon_file,
                            tokens=tokens_file,
                            dict_dir=dict_dir if dict_dir else "",
                            data_dir="",  # 不使用data_dir
                            length_scale=1.0,
                            noise_scale=0.667,
                            noise_scale_w=0.8,
                        ),
                        num_threads=config.get("num_threads", 2),
                        debug=config.get("debug", False),
                        provider=config.get("provider", "cpu"),  # cpu 或 cuda
                    ),
                    max_num_sentences=config.get("max_num_sentences", 2),
                )
                
                self.tts = sherpa_onnx.OfflineTts(tts_config)
                
                # 记录FST文件信息（仅用于日志，不实际使用）
                if rule_fsts:
                    logger.bind(tag=TAG).debug(
                        f"检测到FST规则文件: {', '.join(os.path.basename(f) for f in rule_fsts)}（当前版本不支持）"
                    )
                logger.bind(tag=TAG).info(
                    f"sherpa-onnx-vits-zh-ll模型加载成功，说话人ID: {self.speaker_id}"
                )
        
        except Exception as e:
            logger.bind(tag=TAG).error(f"加载sherpa-onnx-vits-zh-ll模型失败: {e}")
            raise
    
    async def text_to_speak(self, text, output_file):
        """
        将文本转换为语音

        Args:
            text: 要合成的文本
            output_file: 输出文件路径，如果为None则返回音频字节数据

        Returns:
            如果output_file为None，返回音频字节数据；否则返回None
        """
        try:
            # 将数字转换为中文
            processed_text = convert_numbers_to_chinese(text)
            if processed_text != text:
                logger.bind(tag=TAG).info(f"数字转换: {text} -> {processed_text}")

            # 使用sherpa-onnx进行语音合成
            audio = self.tts.generate(processed_text, sid=self.speaker_id, speed=1.0)
            
            # 获取音频数据
            import numpy as np
            
            # audio.samples 可能是列表或numpy数组，统一转换为numpy数组
            samples = audio.samples
            if isinstance(samples, list):
                samples = np.array(samples, dtype=np.float32)
            else:
                samples = np.asarray(samples, dtype=np.float32)
            
            sample_rate = audio.sample_rate  # 采样率
            
            # 确保数据是一维数组
            if len(samples.shape) > 1:
                samples = samples.flatten()
            
            # 将[-1, 1]范围的float32转换为[-32768, 32767]范围的int16
            # 使用clip确保值在有效范围内
            samples_int16 = np.clip(samples * 32767, -32768, 32767).astype(np.int16)
            
            # 创建WAV格式的字节数据
            wav_bytes = io.BytesIO()
            with wave.open(wav_bytes, "wb") as wav_file:
                wav_file.setnchannels(1)  # 单声道
                wav_file.setsampwidth(2)  # 16位采样
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(samples_int16.tobytes())
            
            # 获取WAV字节数据
            wav_bytes.seek(0)  # 确保指针在开始位置
            wav_data = wav_bytes.getvalue()
            
            # 保存到文件或返回字节数据
            if output_file:
                # 确保输出目录存在
                os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else ".", exist_ok=True)
                with open(output_file, "wb") as f:
                    f.write(wav_data)
                logger.bind(tag=TAG).debug(f"音频文件已保存: {output_file}")
            else:
                return wav_data
        
        except Exception as e:
            error_msg = f"sherpa-onnx-vits-zh-ll TTS合成失败: {e}"
            logger.bind(tag=TAG).error(error_msg)
            raise Exception(error_msg)

