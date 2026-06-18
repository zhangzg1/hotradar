"""
关键词API测试脚本
测试关键词相关的所有接口
"""
import asyncio
import httpx
from datetime import datetime
import uuid

# API 基础地址
BASE_URL = "http://localhost:8000/api/v1"

# 测试关键词文本
TEST_KEYWORD_TEXT = f"test_keyword_{uuid.uuid4().hex[:8]}"
TEST_CATEGORY = "test_category"


class KeywordsAPITester:
    """关键词API测试类"""

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        self.created_keyword_ids = []

    async def close(self):
        """关闭客户端"""
        await self.client.aclose()

    async def test_create_keyword(self):
        """测试创建关键词"""
        print("\n" + "=" * 60)
        print("1. 测试创建关键词 - POST /keywords")
        print("=" * 60)

        payload = {
            "text": TEST_KEYWORD_TEXT,
            "category": TEST_CATEGORY,
        }
        print(f"请求体: {payload}")

        response = await self.client.post(f"{BASE_URL}/keywords", json=payload)
        data = response.json()

        print(f"状态码: {response.status_code}")
        print(f"响应: {data}")

        if response.status_code == 200:
            self.created_keyword_ids.append(data["id"])
            print(f"\n关键词创建成功，ID: {data['id']}")
            return True
        else:
            print(f"\n创建失败: {data.get('detail', data)}")
            return False

    async def test_create_duplicate_keyword(self):
        """测试创建重复关键词（应失败）"""
        print("\n" + "=" * 60)
        print("2. 测试创建重复关键词（期望409冲突）")
        print("=" * 60)

        payload = {"text": TEST_KEYWORD_TEXT}
        response = await self.client.post(f"{BASE_URL}/keywords", json=payload)
        data = response.json()

        print(f"状态码: {response.status_code}")
        print(f"响应: {data}")

        if response.status_code == 409:
            print("正确返回409冲突")
            return True
        else:
            print(f"预期409，实际{response.status_code}")
            return False

    async def test_list_keywords(self):
        """测试获取关键词列表"""
        print("\n" + "=" * 60)
        print("3. 测试获取关键词列表 - GET /keywords")
        print("=" * 60)

        params = {"page": 1, "page_size": 10, "sort_by": "createdAt", "sort_order": "desc"}
        response = await self.client.get(f"{BASE_URL}/keywords", params=params)
        data = response.json()

        print(f"状态码: {response.status_code}")
        print(f"总数: {data.get('total', 0)}")
        print(f"页码: {data.get('page', 0)}")

        keywords = data.get("data", [])
        for kw in keywords[:5]:
            print(f"  - ID: {kw['id']}, 文本: {kw['text']}, 激活: {kw['isActive']}, 热点数: {kw.get('hotspotCount', 0)}")

        return response.status_code == 200

    async def test_list_keywords_filter(self):
        """测试筛选关键词列表"""
        print("\n" + "=" * 60)
        print("4. 测试筛选关键词列表 - 激活状态筛选")
        print("=" * 60)

        params = {"is_active": True, "category": TEST_CATEGORY}
        response = await self.client.get(f"{BASE_URL}/keywords", params=params)
        data = response.json()

        print(f"状态码: {response.status_code}")
        print(f"筛选后总数: {data.get('total', 0)}")

        return response.status_code == 200

    async def test_get_keyword_detail(self):
        """测试获取关键词详情"""
        print("\n" + "=" * 60)
        print("5. 测试获取关键词详情 - GET /keywords/{id}")
        print("=" * 60)

        if not self.created_keyword_ids:
            print("未创建关键词，跳过测试")
            return False

        keyword_id = self.created_keyword_ids[0]
        response = await self.client.get(f"{BASE_URL}/keywords/{keyword_id}")
        data = response.json()

        print(f"状态码: {response.status_code}")
        print(f"关键词文本: {data.get('text')}")
        print(f"分类: {data.get('category')}")
        print(f"热点数量: {data.get('hotspotCount', 0)}")

        return response.status_code == 200

    async def test_get_keyword_stats(self):
        """测试获取关键词统计"""
        print("\n" + "=" * 60)
        print("6. 测试获取关键词统计 - GET /keywords/stats")
        print("=" * 60)

        response = await self.client.get(f"{BASE_URL}/keywords/stats")
        data = response.json()

        print(f"状态码: {response.status_code}")
        print(f"总数: {data.get('total', 0)}")
        print(f"活跃数: {data.get('active', 0)}")
        print(f"暂停数: {data.get('inactive', 0)}")
        print(f"分类统计: {data.get('categories', [])}")

        return response.status_code == 200

    async def test_update_keyword(self):
        """测试更新关键词"""
        print("\n" + "=" * 60)
        print("7. 测试更新关键词 - PUT /keywords/{id}")
        print("=" * 60)

        if not self.created_keyword_ids:
            print("未创建关键词，跳过测试")
            return False

        keyword_id = self.created_keyword_ids[0]
        new_text = f"updated_{TEST_KEYWORD_TEXT}"
        payload = {"text": new_text, "category": "updated_category"}

        response = await self.client.put(f"{BASE_URL}/keywords/{keyword_id}", json=payload)
        data = response.json()

        print(f"状态码: {response.status_code}")
        print(f"更新后文本: {data.get('text')}")
        print(f"更新后分类: {data.get('category')}")

        return response.status_code == 200

    async def test_toggle_keyword(self):
        """测试激活/暂停关键词"""
        print("\n" + "=" * 60)
        print("8. 测试激活/暂停关键词 - PATCH /keywords/{id}/toggle")
        print("=" * 60)

        if not self.created_keyword_ids:
            print("未创建关键词，跳过测试")
            return False

        keyword_id = self.created_keyword_ids[0]

        # 先暂停
        response = await self.client.patch(f"{BASE_URL}/keywords/{keyword_id}/toggle")
        data = response.json()
        print(f"第一次切换状态码: {response.status_code}")
        print(f"当前激活状态: {data.get('isActive')}")

        # 再激活
        response = await self.client.patch(f"{BASE_URL}/keywords/{keyword_id}/toggle")
        data = response.json()
        print(f"第二次切换状态码: {response.status_code}")
        print(f"当前激活状态: {data.get('isActive')}")

        return response.status_code == 200

    async def test_batch_operation(self):
        """测试批量操作"""
        print("\n" + "=" * 60)
        print("9. 测试批量操作 - POST /keywords/batch")
        print("=" * 60)

        if not self.created_keyword_ids:
            print("未创建关键词，跳过测试")
            return False

        # 批量暂停
        payload = {"action": "deactivate", "keywordIds": self.created_keyword_ids}
        response = await self.client.post(f"{BASE_URL}/keywords/batch", json=payload)
        data = response.json()

        print(f"批量暂停状态码: {response.status_code}")
        print(f"影响数量: {data.get('affectedCount', 0)}")

        # 批量激活
        payload = {"action": "activate", "keywordIds": self.created_keyword_ids}
        response = await self.client.post(f"{BASE_URL}/keywords/batch", json=payload)
        data = response.json()

        print(f"批量激活状态码: {response.status_code}")
        print(f"影响数量: {data.get('affectedCount', 0)}")

        return response.status_code == 200

    async def test_delete_keyword(self):
        """测试删除关键词"""
        print("\n" + "=" * 60)
        print("10. 测试删除关键词 - DELETE /keywords/{id}")
        print("=" * 60)

        if not self.created_keyword_ids:
            print("未创建关键词，跳过测试")
            return False

        keyword_id = self.created_keyword_ids[0]
        response = await self.client.delete(f"{BASE_URL}/keywords/{keyword_id}")
        data = response.json()

        print(f"状态码: {response.status_code}")
        print(f"响应: {data}")

        if response.status_code == 200:
            self.created_keyword_ids.remove(keyword_id)
            print("关键词已删除")
            return True
        return False

    async def test_batch_delete(self):
        """测试批量删除"""
        print("\n" + "=" * 60)
        print("11. 测试批量删除 - POST /keywords/batch (delete)")
        print("=" * 60)

        # 先创建几个关键词用于批量删除
        for i in range(3):
            payload = {"text": f"batch_delete_test_{i}_{uuid.uuid4().hex[:4]}"}
            response = await self.client.post(f"{BASE_URL}/keywords", json=payload)
            if response.status_code == 200:
                self.created_keyword_ids.append(response.json()["id"])

        if len(self.created_keyword_ids) < 3:
            print("创建关键词不足，跳过批量删除测试")
            return True

        ids_to_delete = self.created_keyword_ids[:3]
        payload = {"action": "delete", "keywordIds": ids_to_delete}
        response = await self.client.post(f"{BASE_URL}/keywords/batch", json=payload)
        data = response.json()

        print(f"状态码: {response.status_code}")
        print(f"影响数量: {data.get('affectedCount', 0)}")

        # 清理测试数据
        for id in ids_to_delete:
            if id in self.created_keyword_ids:
                self.created_keyword_ids.remove(id)

        return response.status_code == 200

    async def test_get_nonexistent_keyword(self):
        """测试获取不存在的关键词"""
        print("\n" + "=" * 60)
        print("12. 测试获取不存在的关键词（期望404）")
        print("=" * 60)

        fake_id = "nonexistent_id_12345"
        response = await self.client.get(f"{BASE_URL}/keywords/{fake_id}")

        print(f"状态码: {response.status_code}")

        return response.status_code == 404

    async def cleanup(self):
        """清理测试数据"""
        print("\n" + "=" * 60)
        print("清理测试数据")
        print("=" * 60)

        for keyword_id in self.created_keyword_ids:
            try:
                await self.client.delete(f"{BASE_URL}/keywords/{keyword_id}")
                print(f"已删除: {keyword_id}")
            except Exception as e:
                print(f"删除失败: {keyword_id} - {e}")


async def run_tests():
    """运行所有测试"""
    tester = KeywordsAPITester()

    try:
        print("\n" + "=" * 60)
        print("关键词API测试开始")
        print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"基础 URL: {BASE_URL}")
        print("=" * 60)

        tests = [
            ("创建关键词", tester.test_create_keyword),
            ("创建重复关键词", tester.test_create_duplicate_keyword),
            ("获取关键词列表", tester.test_list_keywords),
            ("筛选关键词列表", tester.test_list_keywords_filter),
            ("获取关键词详情", tester.test_get_keyword_detail),
            ("获取关键词统计", tester.test_get_keyword_stats),
            ("更新关键词", tester.test_update_keyword),
            ("激活/暂停关键词", tester.test_toggle_keyword),
            ("批量操作", tester.test_batch_operation),
            ("删除关键词", tester.test_delete_keyword),
            ("批量删除", tester.test_batch_delete),
            ("获取不存在关键词", tester.test_get_nonexistent_keyword),
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