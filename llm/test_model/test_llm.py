"""
LLM API 问答测试
"""

from llm.models import gpt_llm, qwen_llm, glm_llm, deepseek_llm, ollama_llm, local_llm


def test_llm(llm, name: str, question: str = "你好，请用一句话介绍你自己。"):
    """测试单个 LLM 模型"""
    print("=" * 50)
    print(f"测试模型: {name}")
    print("=" * 50)

    try:
        response = llm.invoke(question)
        print(f"问题: {question}")
        print(f"回答: {response.content}")
        print("✓ 测试成功\n")
        return True
    except Exception as e:
        print(f"问题: {question}")
        print(f"✗ 测试失败: {e}\n")
        return False


def main():
    """主测试函数"""
    print("\n开始测试 LLM API 服务...\n")

    # 测试问题
    question = "什么是 AI 热点监控？请简单解释。"

    # 定义要测试的模型
    models = [
        (gpt_llm, "GPT-4o-mini"),
        (qwen_llm, "通义千问 Qwen-Plus"),
        (glm_llm, "智谱 GLM-4.6"),
        (deepseek_llm, "DeepSeek"),
    ]

    # 运行测试
    results = {}
    for llm, name in models:
        results[name] = test_llm(llm, name, question)

    # 汇总结果
    print("=" * 50)
    print("测试结果汇总")
    print("=" * 50)
    for name, success in results.items():
        status = "✓ 成功" if success else "✗ 失败"
        print(f"{name}: {status}")

    # 统计
    success_count = sum(results.values())
    total_count = len(results)
    print(f"\n总计: {success_count}/{total_count} 模型测试成功")


if __name__ == "__main__":
    main()