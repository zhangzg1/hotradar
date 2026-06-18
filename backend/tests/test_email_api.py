"""
API 测试脚本
测试热点采集和邮件通知相关的三个 API 接口
"""
import asyncio
import httpx
import websockets
import json
from datetime import datetime

# API 基础地址（根据实际启动端口调整）
BASE_URL = "http://localhost:8000/api/v1"

# WebSocket 地址
WS_URL = "ws://localhost:8000/ws/tasks"

# 测试关键词
TEST_KEYWORD = "Harness Engineer"


class APITester:
    """API 测试类"""

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=300.0)  # 长超时用于采集任务
        self.keyword_id = None
        self.task_id = None

    async def close(self):
        """关闭客户端"""
        await self.client.aclose()

    async def get_keywords(self):
        """获取关键词列表"""
        print("\n" + "=" * 60)
        print("1. 获取关键词列表")
        print("=" * 60)

        response = await self.client.get(f"{BASE_URL}/keywords/")
        data = response.json()

        print(f"状态码: {response.status_code}")
        print(f"关键词总数: {data.get('total', 0)}")

        # 查找测试关键词
        keywords = data.get("data", [])
        for kw in keywords:
            print(f"  - ID: {kw['id']}, 文本: {kw['text']}, 激活: {kw['isActive']}")
            if kw["text"] == TEST_KEYWORD:
                self.keyword_id = kw["id"]
                print(f"\n找到测试关键词 '{TEST_KEYWORD}'，ID: {self.keyword_id}")

        if not self.keyword_id:
            print(f"\n未找到关键词 '{TEST_KEYWORD}'，请先在数据库中添加该关键词")
            return False

        return True

    async def test_collection_no_email(self):
        """测试采集任务（无自动邮件）"""
        print("\n" + "=" * 60)
        print("2. 测试采集任务（无自动邮件） - POST /collections")
        print("=" * 60)

        if not self.keyword_id:
            print("错误: 未找到关键词 ID")
            return False

        # 启动 WebSocket 监听
        ws_task = asyncio.create_task(
            self.listen_websocket("collection_no_email")
        )

        # 发送采集请求
        payload = {"keywordIds": [self.keyword_id]}
        print(f"请求体: {json.dumps(payload, indent=2)}")

        response = await self.client.post(
            f"{BASE_URL}/collections",
            json=payload,
        )
        data = response.json()

        print(f"状态码: {response.status_code}")
        print(f"响应: {json.dumps(data, indent=2)}")

        self.task_id = data.get("taskId")

        if self.task_id:
            print(f"\n任务已启动，taskId: {self.task_id}")
            print("等待 WebSocket 推送...")
            await ws_task
            return True
        else:
            ws_task.cancel()
            return False

    async def test_collection_with_auto_email(self):
        """测试采集任务（含自动邮件）"""
        print("\n" + "=" * 60)
        print("3. 测试采集任务（含自动邮件） - POST /collections/auto-email")
        print("=" * 60)

        if not self.keyword_id:
            print("错误: 未找到关键词 ID")
            return False

        # 启动 WebSocket 监听
        ws_task = asyncio.create_task(
            self.listen_websocket("collection_auto_email")
        )

        # 发送采集请求
        payload = {"keywordIds": [self.keyword_id]}
        print(f"请求体: {json.dumps(payload, indent=2)}")

        response = await self.client.post(
            f"{BASE_URL}/collections/auto-email",
            json=payload,
        )
        data = response.json()

        print(f"状态码: {response.status_code}")
        print(f"响应: {json.dumps(data, indent=2)}")

        self.task_id = data.get("taskId")

        if self.task_id:
            print(f"\n任务已启动，taskId: {self.task_id}")
            print("等待 WebSocket 推送和邮件发送...")
            await ws_task
            return True
        else:
            ws_task.cancel()
            return False

    async def test_manual_email_notification(self):
        """测试手动邮件通知"""
        print("\n" + "=" * 60)
        print("4. 测试手动邮件通知 - POST /email-notifications")
        print("=" * 60)

        payload = {
            "hours": 24,  # 默认 24 小时
            "importance": ["high", "urgent"],  # 默认高重要性
            "keywordIds": [self.keyword_id] if self.keyword_id else None,
        }
        print(f"请求体: {json.dumps(payload, indent=2)}")

        response = await self.client.post(
            f"{BASE_URL}/email-notifications",
            json=payload,
        )
        data = response.json()

        print(f"状态码: {response.status_code}")
        print(f"响应: {json.dumps(data, indent=2)}")

        if response.status_code == 200:
            print(f"\n邮件发送成功，发送数量: {data.get('sentCount', 0)}")
            return True
        else:
            print(f"\n邮件发送失败: {data.get('error', '未知错误')}")
            return False

    async def listen_websocket(self, task_name: str):
        """监听 WebSocket 推送"""
        if not self.task_id:
            print("无 taskId，跳过 WebSocket 监听")
            return

        ws_url = f"{WS_URL}/{self.task_id}"
        print(f"WebSocket 连接: {ws_url}")

        try:
            async with websockets.connect(ws_url) as ws:
                print("WebSocket 已连接")

                message_count = 0
                while True:
                    try:
                        message = await asyncio.wait_for(ws.recv(), timeout=120.0)
                        data = json.loads(message)
                        message_count += 1

                        print(f"\n[WebSocket 消息 #{message_count}]")
                        print(f"类型: {data.get('type')}")

                        if data.get("type") == "hotspot_collected":
                            hotspot_data = data.get("data", {})
                            print(f"关键词: {hotspot_data.get('keyword')}")
                            print(f"热点数量: {len(hotspot_data.get('hotspots', []))}")
                            print(f"自动邮件: {hotspot_data.get('autoEmailTriggered', False)}")

                            for hp in hotspot_data.get("hotspots", [])[:3]:  # 只显示前3条
                                print(f"  - {hp.get('title', '')[:50]}... [{hp.get('importance')}]")

                        elif data.get("type") == "error":
                            print(f"错误: {data.get('data', {}).get('error')}")
                            break

                        elif data.get("type") == "pong":
                            print("心跳响应")

                    except asyncio.TimeoutError:
                        print("WebSocket 超时，任务可能已完成")
                        break

        except Exception as e:
            print(f"WebSocket 连接失败: {e}")

    async def list_hotspots(self):
        """查看热点列表"""
        print("\n" + "=" * 60)
        print("5. 查看热点列表")
        print("=" * 60)

        params = {
            "keyword_id": self.keyword_id,
            "limit": 10,
        }

        response = await self.client.get(
            f"{BASE_URL}/hotspots",
            params=params,
        )
        data = response.json()

        print(f"状态码: {response.status_code}")
        print(f"热点总数: {data.get('total', 0)}")

        hotspots = data.get("data", [])
        for hp in hotspots:
            print(f"  - [{hp.get('importance')}] {hp.get('title', '')[:40]}...")
            print(f"    来源: {hp.get('source')}")
            print(f"    邮件已发送: {hp.get('emailSent', False)}")


async def run_tests():
    """运行所有测试"""
    tester = APITester()

    try:
        print("\n" + "=" * 60)
        print("API 测试开始")
        print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"基础 URL: {BASE_URL}")
        print(f"测试关键词: {TEST_KEYWORD}")
        print("=" * 60)

        # 1. 获取关键词
        if not await tester.get_keywords():
            print("\n测试终止: 未找到关键词")
            return

        # 2. 测试采集任务（无自动邮件）
        await tester.test_collection_no_email()

        # 3. 查看热点列表
        await tester.list_hotspots()

        # 4. 测试手动邮件通知
        await tester.test_manual_email_notification()

        # 5. 再次查看热点列表（检查邮件状态）
        await tester.list_hotspots()

        # 6. 测试采集任务（含自动邮件）
        # await tester.test_collection_with_auto_email()  # 可选，需要等待采集完成

        print("\n" + "=" * 60)
        print("测试完成")
        print("=" * 60)

    except httpx.ConnectError:
        print("\n错误: 无法连接服务器")
        print("请确保 FastAPI 服务已启动:")
        print("  cd /Users/zigen/Desktop/ai-hotspot-monitor")
        print("  conda activate ai-hotspot-monitor")
        print("  uvicorn backend.core.server:create_app --factory --reload --port 8000")

    except Exception as e:
        print(f"\n测试异常: {e}")

    finally:
        await tester.close()


if __name__ == "__main__":
    asyncio.run(run_tests())