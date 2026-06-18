import os
import subprocess
import dashscope
from llm.utils import QWEN_ASR_BASE_URL, QWEN_API_KEY

# ====== 配置 ======
dashscope.base_http_api_url = QWEN_ASR_BASE_URL
API_KEY = QWEN_API_KEY

# 原始音频（支持 m4a，本地音频绝对路径）
input_path = "/Users/zigen/Desktop/ai-hotspot-monitor/models/audio_2e21965d.m4a"

# 转换后的 mp3
output_path = input_path.replace(".m4a", ".mp3")


# ====== 1. 检查文件 ======
if not os.path.exists(input_path):
    raise FileNotFoundError(f"文件不存在: {input_path}")


# ====== 2. 转码函数 ======
def convert_to_mp3(input_file, output_file):
    print("🎧 正在转换音频格式 (m4a → mp3)...")

    command = [
        "ffmpeg",
        "-y",  # 覆盖输出文件
        "-i", input_file,
        "-ac", "1",          # 单声道（提高识别稳定性）
        "-ar", "16000",      # 采样率
        "-codec:a", "libmp3lame",
        output_file
    ]

    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("✅ 转换完成:", output_file)
    except subprocess.CalledProcessError as e:
        print("❌ ffmpeg 转换失败")
        print(e.stderr.decode())
        raise


# ====== 3. 如果是 m4a 就转 ======
if input_path.endswith(".m4a"):
    convert_to_mp3(input_path, output_path)
    final_audio = output_path
else:
    final_audio = input_path


# ====== 4. 构造 file URL ======
audio_file_url = f"file:///{final_audio}"

messages = [
    {
        "role": "user",
        "content": [
            {"audio": audio_file_url}
        ]
    }
]


# ====== 5. 调用 ASR ======
print("🚀 开始识别...")

response = dashscope.MultiModalConversation.call(
    api_key=API_KEY,
    model="qwen3-asr-flash",
    messages=messages,
    result_format="message",
    asr_options={
        "enable_itn": False
    }
)

print("\n📝 识别结果：")
print(response)