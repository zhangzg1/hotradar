"""
测试抖音视频转录功能

抖音无原生字幕，直接使用 Qwen ASR 转录

运行方式：
    conda activate ai-hotspot-monitor
    python scripts/test_douyin_subtitle.py                    # 使用默认URL测试
    python scripts/test_douyin_subtitle.py <URL>              # 测试指定URL
"""
import asyncio
import sys
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.video_transcribe import (
    transcribe_video,
    fetch_video_content,
    detect_platform,
)


DEFAULT_TEST_URLS = [
    ("https://www.douyin.com/video/7632653615152352564", "抖音"),
]


async def test_transcribe(url: str, show_details: bool = True):
    """测试视频转录"""
    print("\n" + "=" * 60)
    print("🎵 抖音视频转录测试")
    print("=" * 60)

    platform = detect_platform(url)
    print(f"平台: {platform}")
    print(f"URL: {url}")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    print("\n" + "-" * 40)
    print("[转录流程]")
    print("-" * 40)
    print("抖音无原生字幕，使用 Qwen ASR 转录...")

    text = await transcribe_video(url)

    if text:
        print(f"\n✅ 转录成功！文本长度: {len(text)} 字符")
        print("\n" + "=" * 60)
        print("📄 转录结果:")
        print("=" * 60)
        print(text)
    else:
        print("\n❌ 未获取到转录内容")

    return text


async def test_with_fallback(url: str, fallback: str = "这是备用内容"):
    """测试带 fallback 的接口"""
    print("\n" + "=" * 60)
    print("🧪 测试 fetch_video_content (带 fallback)")
    print("=" * 60)

    platform = detect_platform(url)
    print(f"平台: {platform}")
    print(f"URL: {url}")
    print(f"Fallback: {fallback}")

    text = await fetch_video_content(url, fallback)

    print("\n结果:")
    print("-" * 40)
    if text == fallback:
        print("⚠️ 使用了 fallback 内容")
    else:
        print("✅ 成功获取转录内容")
    print(text[:500] if len(text) > 500 else text)

    return text


def main():
    parser = argparse.ArgumentParser(description="测试抖音视频音频转录")
    parser.add_argument("url", nargs="?", help="视频URL (可选)")
    parser.add_argument("-v", "--verbose", action="store_true", help="显示详细过程")
    parser.add_argument("-f", "--fallback", action="store_true", help="测试带fallback的接口")
    args = parser.parse_args()

    # 使用用户URL或默认列表
    if args.url:
        if args.fallback:
            asyncio.run(test_with_fallback(args.url))
        else:
            asyncio.run(test_transcribe(args.url, show_details=True))
    else:
        for url, name in DEFAULT_TEST_URLS:
            print(f"\n>>> 测试 {name} 平台")
            asyncio.run(test_transcribe(url, show_details=args.verbose))

    print("\n" + "=" * 60)
    print("🎉 测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()