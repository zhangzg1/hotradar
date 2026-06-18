"""
热点API测试脚本
测试热点相关的所有接口
"""
import asyncio
import httpx
from datetime import datetime
import uuid

# API 基础地址
BASE_URL = "http://localhost:8000/api/v1"

# 测试关键词ID（需要先存在）
# 如果数据库中已有关键词，可以使用已有的；否则需要先创建


class HotspotsAPITester:
    """热点API测试类"""

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        self.keyword_id = None
        self.hotspot_id = None

    async def close(self):
        """关闭客户端"""
        await self.client.aclose()

    async def setup(self):
        """准备测试环境 - 查找或创建关键词"""
        print("\n" + "=" * 60)
        print("0. 准备测试环境 - 查找关键词")
        print("=" * 60)

        # 获取关键词列表
        response = await self.client.get(f"{BASE_URL}/keywords", params={"page_size": 1})
        data = response.json()

        if data.get("total", 0) > 0 and data.get("data"):
            self.keyword_id = data["data"][0]["id"]
            print(f"使用已有关键词ID: {self.keyword_id}")
            return True

        # 如果没有关键词，创建一个
        payload = {"text": f"test_keyword_{uuid.uuid4().hex[:8]}"}
        response = await self.client.post(f"{BASE_URL}/keywords", json=payload)

        if response.status_code == 200:
            self.keyword_id = response.json()["id"]
            print(f"创建关键词ID: {self.keyword_id}")
            return True

        print("无法准备关键词")
        return False

    async def test_list_hotspots(self):
        """测试获取热点列表"""
        print("\n" + "=" * 60)
        print("1. 测试获取热点列表 - GET /hotspots")
        print("=" * 60)

        params = {"page": 1, "page_size": 10, "sort_by": "createdAt", "sort_order": "desc"}
        response = await self.client.get(f"{BASE_URL}/hotspots", params=params)
        data = response.json()

        print(f"状态码: {response.status_code}")
        print(f"总数: {data.get('total', 0)}")
        print(f"页码: {data.get('page', 0)}")

        hotspots = data.get("data", [])
        for hp in hotspots[:5]:
            print(f"  - ID: {hp['id']}, 标题: {hp.get('title', '')[:40]}...")
            print(f"    来源: {hp.get('source')}, 重要程度: {hp.get('importance')}")

        # 保存一个热点ID用于后续测试
        if hotspots:
            self.hotspot_id = hotspots[0]["id"]

        return response.status_code == 200

    async def test_list_hotspots_filter(self):
        """测试筛选热点列表"""
        print("\n" + "=" * 60)
        print("2. 测试筛选热点列表")
        print("=" * 60)

        # 按关键词筛选
        if self.keyword_id:
            params = {"keyword_id": self.keyword_id}
            response = await self.client.get(f"{BASE_URL}/hotspots", params=params)
            data = response.json()

            print(f"关键词筛选 - 状态码: {response.status_code}, 总数: {data.get('total', 0)}")

        # 按重要程度筛选
        params = {"importance": "high"}
        response = await self.client.get(f"{BASE_URL}/hotspots", params=params)
        data = response.json()

        print(f"重要程度筛选 - 状态码: {response.status_code}, 高重要性数量: {data.get('total', 0)}")

        # 按来源筛选
        params = {"source": "twitter"}
        response = await self.client.get(f"{BASE_URL}/hotspots", params=params)
        data = response.json()

        print(f"来源筛选 - 状态码: {response.status_code}, Twitter来源数量: {data.get('total', 0)}")

        return True

    async def test_get_hotspot_stats(self):
        """测试获取热点统计"""
        print("\n" + "=" * 60)
        print("3. 测试获取热点统计 - GET /hotspots/stats")
        print("=" * 60)

        response = await self.client.get(f"{BASE_URL}/hotspots/stats")
        data = response.json()

        print(f"状态码: {response.status_code}")
        print(f"总数: {data.get('total', 0)}")
        print(f"今日新增: {data.get('todayNew', 0)}")
        print(f"真实数量: {data.get('realCount', 0)}")
        print(f"虚假数量: {data.get('fakeCount', 0)}")
        print(f"已邮件通知: {data.get('emailedCount', 0)}")

        print("重要程度分布:")
        for dist in data.get("importanceDistribution", []):
            print(f"  - {dist.get('importance')}: {dist.get('count')}")

        print("来源分布:")
        for dist in data.get("sourceDistribution", []):
            print(f"  - {dist.get('source')}: {dist.get('count')}")

        return response.status_code == 200

    async def test_get_hotspot_detail(self):
        """测试获取热点详情"""
        print("\n" + "=" * 60)
        print("4. 测试获取热点详情 - GET /hotspots/{id}")
        print("=" * 60)

        if not self.hotspot_id:
            print("无热点ID，跳过测试")
            return True

        response = await self.client.get(f"{BASE_URL}/hotspots/{self.hotspot_id}")
        data = response.json()

        print(f"状态码: {response.status_code}")

        if response.status_code == 200:
            print(f"标题: {data.get('title', '')[:50]}...")
            print(f"来源: {data.get('source')}")
            print(f"重要程度: {data.get('importance')}")
            print(f"相关性评分: {data.get('relevance')}")
            print(f"摘要: {data.get('summary', '')[:100]}...")
            print(f"作者: {data.get('author', {}).get('name')}")
            print(f"发布时间: {data.get('publishedAt')}")

        return response.status_code == 200

    async def test_search_hotspots(self):
        """测试搜索热点"""
        print("\n" + "=" * 60)
        print("5. 测试搜索热点 - POST /hotspots/search")
        print("=" * 60)

        # 使用通用搜索词
        payload = {"query": "AI", "limit": 10}
        response = await self.client.post(f"{BASE_URL}/hotspots/search", json=payload)
        data = response.json()

        print(f"状态码: {response.status_code}")
        print(f"搜索词: 'AI'")
        print(f"匹配总数: {data.get('total', 0)}")

        hotspots = data.get("data", [])
        for hp in hotspots[:3]:
            print(f"  - {hp.get('title', '')[:40]}...")

        return response.status_code == 200

    async def test_search_with_filters(self):
        """测试带筛选条件的搜索"""
        print("\n" + "=" * 60)
        print("6. 测试带筛选条件的搜索")
        print("=" * 60)

        payload = {
            "query": "热点",
            "importance": ["high", "medium"],
            "isReal": True,
            "limit": 5,
        }
        response = await self.client.post(f"{BASE_URL}/hotspots/search", json=payload)
        data = response.json()

        print(f"状态码: {response.status_code}")
        print(f"搜索词: '热点', 重要程度: high/medium, 真实: True")
        print(f"匹配总数: {data.get('total', 0)}")

        return response.status_code == 200

    async def test_get_nonexistent_hotspot(self):
        """测试获取不存在的热点"""
        print("\n" + "=" * 60)
        print("7. 测试获取不存在的热点（期望404）")
        print("=" * 60)

        fake_id = "nonexistent_hotspot_id_12345"
        response = await self.client.get(f"{BASE_URL}/hotspots/{fake_id}")

        print(f"状态码: {response.status_code}")

        return response.status_code == 404

    async def test_delete_hotspot(self):
        """测试删除热点"""
        print("\n" + "=" * 60)
        print("8. 测试删除热点 - DELETE /hotspots/{id}")
        print("=" * 60)

        if not self.hotspot_id:
            print("无热点ID，跳过测试")
            return True

        response = await self.client.delete(f"{BASE_URL}/hotspots/{self.hotspot_id}")
        data = response.json()

        print(f"状态码: {response.status_code}")
        print(f"响应: {data}")

        if response.status_code == 200:
            self.hotspot_id = None
            print("热点已删除")
            return True

        return False

    async def test_delete_nonexistent_hotspot(self):
        """测试删除不存在的热点"""
        print("\n" + "=" * 60)
        print("9. 测试删除不存在的热点（期望404）")
        print("=" * 60)

        fake_id = "nonexistent_hotspot_id_12345"
        response = await self.client.delete(f"{BASE_URL}/hotspots/{fake_id}")

        print(f"状态码: {response.status_code}")

        return response.status_code == 404

    async def cleanup(self):
        """清理测试数据"""
        print("\n" + "=" * 60)
        print("清理测试数据")
        print("=" * 60)

        # 删除创建的关键词（如果有）
        if self.keyword_id:
            try:
                await self.client.delete(f"{BASE_URL}/keywords/{self.keyword_id}")
                print(f"已删除关键词: {self.keyword_id}")
            except Exception as e:
                print(f"删除关键词失败: {e}")


async def run_tests():
    """运行所有测试"""
    tester = HotspotsAPITester()

    try:
        print("\n" + "=" * 60)
        print("热点API测试开始")
        print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"基础 URL: {BASE_URL}")
        print("=" * 60)

        # 准备测试环境
        if not await tester.setup():
            print("无法准备测试环境，部分测试可能跳过")

        tests = [
            ("获取热点列表", tester.test_list_hotspots),
            ("筛选热点列表", tester.test_list_hotspots_filter),
            ("获取热点统计", tester.test_get_hotspot_stats),
            ("获取热点详情", tester.test_get_hotspot_detail),
            ("搜索热点", tester.test_search_hotspots),
            ("带筛选条件搜索", tester.test_search_with_filters),
            ("获取不存在热点", tester.test_get_nonexistent_hotspot),
            ("删除热点", tester.test_delete_hotspot),
            ("删除不存在热点", tester.test_delete_nonexistent_hotspot),
        ]

        passed = 0
        failed = 0

        for name, test_func in tests:
            try:
                result = await test_func()
                if result:
                    passed += 1
                    print(f"✓ {name} 通过")
                else:
                    failed += 1
                    print(f"✗ {name} 失败")
            except Exception as e:
                failed += 1
                print(f"✗ {name} 异常: {e}")

        # 清理
        await tester.cleanup()

        print("\n" + "=" * 60)
        print(f"测试完成: 通过 {passed}, 失败 {failed}")
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