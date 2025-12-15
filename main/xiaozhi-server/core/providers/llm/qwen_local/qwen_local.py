import os
import torch
import threading
from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer
from config.logger import setup_logging
from core.providers.llm.base import LLMProviderBase
from config.config_loader import get_project_dir

TAG = __name__
logger = setup_logging()


class LLMProvider(LLMProviderBase):
    def __init__(self, config):
        model_path = config.get("model_path")
        if not model_path:
            raise ValueError("model_path 必须配置，指向本地Qwen模型目录")
        
        # 处理相对路径，转换为绝对路径
        if not os.path.isabs(model_path):
            project_dir = get_project_dir()
            self.model_path = os.path.join(project_dir, model_path)
        else:
            self.model_path = model_path
        
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"模型路径不存在: {self.model_path}")
        
        # 模型参数配置
        self.device = config.get("device", "auto")  # auto, cpu, cuda
        self.torch_dtype = config.get("torch_dtype", "auto")  # auto, float16, bfloat16, float32
        self.max_tokens = config.get("max_tokens", 2048)
        self.temperature = config.get("temperature", 0.7)
        self.top_p = config.get("top_p", 0.8)
        self.load_in_8bit = config.get("load_in_8bit", False)
        self.load_in_4bit = config.get("load_in_4bit", False)
        # 注意力实现方式: eager(稳定), flash_attention_2(快速，需要安装), sdpa(默认，但有警告)
        self.attn_implementation = config.get("attn_implementation", "eager")
        
        logger.bind(tag=TAG).info(f"正在加载本地Qwen模型: {self.model_path}")
        
        try:
            # 加载tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_path,
                trust_remote_code=True
            )
            
            # 确定设备
            if self.device == "auto":
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
            
            # 确定数据类型
            if self.torch_dtype == "auto":
                if self.device == "cuda":
                    self.torch_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
                else:
                    self.torch_dtype = torch.float32
            else:
                dtype_map = {
                    "float16": torch.float16,
                    "bfloat16": torch.bfloat16,
                    "float32": torch.float32
                }
                self.torch_dtype = dtype_map.get(self.torch_dtype, torch.float32)
            
            # 加载模型
            model_kwargs = {
                "trust_remote_code": True,
                "torch_dtype": self.torch_dtype,
                # 设置注意力实现方式，避免SDPA的滑动窗口警告
                # eager: 最稳定，兼容性好
                # flash_attention_2: 更快，但需要安装flash-attn库
                # sdpa: 默认，但Qwen2的滑动窗口功能未实现，会有警告
                "attn_implementation": self.attn_implementation,
            }
            
            if self.device == "cuda":
                model_kwargs["device_map"] = "auto"
            
            if self.load_in_8bit:
                model_kwargs["load_in_8bit"] = True
            elif self.load_in_4bit:
                model_kwargs["load_in_4bit"] = True
                try:
                    from transformers import BitsAndBytesConfig
                    model_kwargs["quantization_config"] = BitsAndBytesConfig(
                        load_in_4bit=True,
                        bnb_4bit_compute_dtype=self.torch_dtype
                    )
                except ImportError:
                    logger.bind(tag=TAG).warning("bitsandbytes未安装，无法使用4bit量化")
            
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_path,
                **model_kwargs
            )
            
            if self.device == "cpu":
                self.model = self.model.to(self.device)
            
            self.model.eval()
            
            logger.bind(tag=TAG).info(
                f"本地Qwen模型加载成功，设备: {self.device}, 数据类型: {self.torch_dtype}"
            )
            
        except Exception as e:
            logger.bind(tag=TAG).error(f"加载本地Qwen模型失败: {e}")
            raise
    
    def _format_dialogue(self, dialogue):
        """将对话格式转换为Qwen的输入格式"""
        messages = []
        for msg in dialogue:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                messages.append({"role": "system", "content": content})
            elif role == "user":
                messages.append({"role": "user", "content": content})
            elif role == "assistant":
                messages.append({"role": "assistant", "content": content})
        
        # 使用apply_chat_template格式化
        text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        return text
    
    def response(self, session_id, dialogue, **kwargs):
        try:
            # 格式化对话
            prompt = self._format_dialogue(dialogue)
            
            # 编码输入
            inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
            
            # 获取生成参数
            max_tokens = kwargs.get("max_tokens", self.max_tokens)
            temperature = kwargs.get("temperature", self.temperature)
            top_p = kwargs.get("top_p", self.top_p)
            
            # 创建流式输出器
            streamer = TextIteratorStreamer(
                self.tokenizer,
                skip_prompt=True,
                skip_special_tokens=True,
                clean_up_tokenization_spaces=True
            )
            
            # 生成参数
            generation_config = {
                "max_new_tokens": max_tokens,
                "temperature": temperature,
                "top_p": top_p,
                "do_sample": temperature > 0,
                "pad_token_id": self.tokenizer.eos_token_id,
                "streamer": streamer,
            }
            
            # 在单独线程中生成
            generation_thread = threading.Thread(
                target=self.model.generate,
                kwargs={
                    **inputs,
                    **generation_config,
                }
            )
            generation_thread.start()
            
            # 流式输出
            buffer = ""
            for new_text in streamer:
                buffer += new_text
                # 当缓冲区积累到一定长度或遇到标点时输出
                if len(buffer) >= 3 or any(p in buffer for p in ["。", "，", "！", "？", "\n", "、"]):
                    yield buffer
                    buffer = ""
            
            # 输出剩余内容
            if buffer:
                yield buffer
            
            # 等待生成线程完成
            generation_thread.join()
                
        except Exception as e:
            logger.bind(tag=TAG).error(f"本地Qwen模型响应生成失败: {e}")
            import traceback
            logger.bind(tag=TAG).error(traceback.format_exc())
            yield "【本地Qwen模型响应异常】"
    
    def response_with_functions(self, session_id, dialogue, functions=None):
        """通过提示词工程实现function calling功能"""
        if not functions:
            logger.bind(tag=TAG).debug("无可用函数，使用普通响应模式")
            for token in self.response(session_id, dialogue):
                yield token, None
            return

        # 先检查是否是气象数据查询（快速路径，不调用LLM）
        user_text = ""
        for msg in reversed(dialogue):
            if msg.get("role") == "user":
                user_text = msg.get("content", "")
                break

        quick_result = self._quick_intent_match(user_text, functions)
        if quick_result:
            logger.bind(tag=TAG).info(f"快速匹配到函数调用: {quick_result}")
            # 返回 <tool_call> 格式，系统会解析
            yield f"<tool_call>{quick_result}</tool_call>", None
            return

        # 如果快速匹配失败，使用普通响应
        logger.bind(tag=TAG).debug("快速匹配失败，使用普通对话模式")
        for token in self.response(session_id, dialogue):
            yield token, None

    def _quick_intent_match(self, text, functions):
        """快速意图匹配，不调用LLM"""
        import json
        import re

        # 气象数据查询关键词映射
        meteo_keywords = {
            "温度": "温度", "多少度": "温度", "气温": "温度", "冷不冷": "温度", "热不热": "温度",
            "湿度": "湿度", "潮不潮": "湿度",
            "气压": "气压", "大气压": "气压",
            "风速": "风速", "风大不大": "风速", "刮风": "风速",
            "风向": "风向",
            "降水": "降水量", "下雨": "降水量", "雨量": "降水量",
            "能见度": "能见度",
            "紫外线": "紫外线",
        }

        # 检查是否有 get_meteo_data 函数
        has_meteo_func = any(
            f.get("function", {}).get("name") == "get_meteo_data"
            for f in functions
        )

        if has_meteo_func:
            for keyword, element in meteo_keywords.items():
                if keyword in text:
                    # 提取时间信息
                    time_query = self._extract_time_query(text)

                    arguments = {"element": element}
                    if time_query:
                        arguments["time_query"] = time_query

                    return json.dumps({
                        "name": "get_meteo_data",
                        "arguments": arguments
                    }, ensure_ascii=False)

        return None

    def _extract_time_query(self, text):
        """
        从文本中提取时间查询表达式

        Returns:
            时间查询字符串，如果没有时间信息则返回None
        """
        import re

        # 时间关键词模式
        time_patterns = [
            # 相对时间
            r'(现在|当前|目前)',
            r'(今天|今日)',
            r'(昨天|昨日)',
            r'(前天)',
            r'(\d+)\s*(小时前|个小时前)',
            r'(\d+)\s*(天前)',
            r'(上周|上星期)([一二三四五六日天])?',
            r'(这周|本周|这星期|本星期)([一二三四五六日天])?',

            # 具体时间
            r'(\d+)\s*月\s*(\d+)\s*(号|日)',
            r'(\d+)\s*点',
            r'(早上|上午|中午|下午|晚上|凌晨)',

            # 组合时间
            r'(今天|昨天|前天)?\s*(早上|上午|中午|下午|晚上|凌晨)?\s*(\d+)\s*点',
            r'(\d+)\s*月\s*(\d+)\s*(号|日)\s*(早上|上午|中午|下午|晚上|凌晨)?\s*(\d+)?\s*点?',
        ]

        # 尝试匹配所有时间模式
        matched_parts = []
        for pattern in time_patterns:
            matches = re.findall(pattern, text)
            if matches:
                # 将匹配到的部分添加到列表
                for match in matches:
                    if isinstance(match, tuple):
                        matched_parts.extend([m for m in match if m])
                    else:
                        matched_parts.append(match)

        # 如果没有匹配到时间关键词，返回None
        if not matched_parts:
            return None

        # 简单策略：返回原始文本（让dateparser去解析）
        # 移除气象要素关键词，只保留时间部分
        time_text = text
        meteo_keywords = ["温度", "多少度", "气温", "冷不冷", "热不热",
                         "湿度", "潮不潮", "气压", "大气压",
                         "风速", "风大不大", "刮风", "风向",
                         "降水", "下雨", "雨量", "能见度", "紫外线",
                         "是多少", "多少", "怎么样", "如何"]

        for keyword in meteo_keywords:
            time_text = time_text.replace(keyword, "")

        # 清理多余的标点和空格
        time_text = re.sub(r'[？?！!，,。.的]', ' ', time_text).strip()

        # 如果清理后为空，返回None
        if not time_text or len(time_text) < 2:
            return None

        return time_text
