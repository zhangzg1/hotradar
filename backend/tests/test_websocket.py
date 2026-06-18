"""
WebSocket 监听测试
单独测试 WebSocket 连接和消息接收
"""
import asyncio
import websockets
import json
from datetime import datetime


async def listen_task(task_id: str):
    """监听指定任务 ID 的 WebSocket 推送"""
    ws_url = f"ws://localhost:8000/ws/tasks/{task_id}"

    print(f"连接 WebSocket: {ws_url}")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        async with websockets.connect(ws_url) as ws:
            print("已连接，等待消息...")

            while True:
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=300.0)
                    data = json.loads(message)

                    print(f"\n收到消息:")
                    print(json.dumps(data, indent=2, ensure_ascii=False))

                    if data.get("type") == "error":
                        print("任务出错，退出监听")
                        break

                except asyncio.TimeoutError:
                    print("\n超时（300秒无消息），退出监听")
                    break

    except Exception as e:
        print(f"连接失败: {e}")


def main():
    """主函数"""
    print("\nWebSocket 监听测试")
    print("=" * 60)

    task_id = input("请输入任务 ID（或按回车使用测试 ID）: ").strip()

    if not task_id:
        task_id = "test-task-001"
        print(f"使用测试 ID: {task_id}")

    asyncio.run(listen_task(task_id))


if __name__ == "__main__":
    main()