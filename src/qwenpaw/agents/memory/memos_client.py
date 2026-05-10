# -*- coding: utf-8 -*-
"""MemOS REST API Client Wrapper.

提供统一的 HTTP 客户端封装:
- 统一认证 (Bearer token)
- 自动错误码检查
- 可配置超时 + 重试
- 结构化请求/响应日志
"""
import asyncio
import logging
from typing import Any, AsyncIterator

import aiohttp

logger = logging.getLogger(__name__)


class MemOSError(Exception):
    """MemOS API 返回错误."""

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"MemOS error [{code}]: {message}")


class MemOSClient:
    """MemOS REST API client wrapper."""

    BASE_RESPONSE_KEYS = ("code", "message", "data")

    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        timeout: int = 30,
        max_retries: int = 1,
    ):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._max_retries = max_retries
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self):
        self._session = aiohttp.ClientSession(timeout=self._timeout)
        return self

    async def __aexit__(self, *args):
        if self._session:
            await self._session.close()
            self._session = None

    async def _request(
        self,
        method: str,
        path: str,
        json_body: dict | None = None,
    ) -> dict:
        """统一的请求方法，带认证、错误处理、重试."""
        if not self._session:
            raise RuntimeError("MemOSClient not initialized. Use async context manager.")

        url = f"{self._base_url}{path}"
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                async with self._session.request(
                    method,
                    url,
                    json=json_body,
                    headers=headers,
                ) as resp:
                    # 尝试解析 JSON
                    try:
                        data = await resp.json()
                    except Exception:
                        # 非 JSON 响应（如 health check）
                        if resp.status == 200:
                            return {"status": "ok"}
                        raise

                    # 验证 BaseResponse 格式
                    if isinstance(data, dict) and "code" in data:
                        # MemOS 成功码是 200，不是 0
                        if data["code"] not in (0, 200):
                            raise MemOSError(
                                data.get("code", -1),
                                data.get("message", "Unknown error"),
                            )
                        return data.get("data", {})
                    # 非标准响应
                    return data

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_error = e
                if attempt < self._max_retries:
                    logger.warning(
                        f"MemOS request to {path} failed (attempt {attempt + 1}), "
                        f"retrying: {e}",
                    )
                    await asyncio.sleep(0.5 * (attempt + 1))  # 指数退避
                    continue
                raise

        raise last_error or RuntimeError("Request failed unexpectedly")

    async def _post(self, path: str, json_body: dict | None = None) -> dict:
        """POST 请求."""
        return await self._request("POST", path, json_body)

    async def _get(self, path: str) -> dict:
        """GET 请求."""
        return await self._request("GET", path, None)

    # ==================== P0 Core APIs ====================

    async def search(
        self,
        query: str,
        user_id: str,
        readable_cube_ids: list[str],
        top_k: int = 5,
        relativity: float = 0.45,
        mode: str = "fast",
        session_id: str | None = None,
    ) -> dict:
        """语义搜索记忆.

        Args:
            query: 搜索查询
            user_id: 用户 ID
            readable_cube_ids: 可读的 Cube ID 列表 (必须传!)
            top_k: 返回结果数量
            relativity: 相关性阈值 (0-1)
            mode: 搜索模式 fast/fine/mixture
            session_id: 会话 ID (可选)

        Returns:
            搜索结果 dict，包含 text_mem 列表
        """
        body = {
            "query": query,
            "user_id": user_id,
            "readable_cube_ids": readable_cube_ids,
            "top_k": top_k,
            "relativity": relativity,
            "mode": mode,
        }
        if session_id:
            body["session_id"] = session_id

        return await self._post("/product/search", body)

    async def health_check(self) -> bool:
        """健康检查 - 验证 MemOS 服务是否可用.

        Returns:
            True: 服务可用
            False: 服务不可用
        """
        try:
            if not self._session:
                return False

            url = f"{self._base_url}/health"
            headers = {}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"

            async with self._session.get(url, headers=headers, timeout=5) as resp:
                return resp.status == 200
        except Exception:
            return False

    async def add(
        self,
        user_id: str,
        writable_cube_ids: list[str],
        messages: list[dict],
        async_mode: str = "async",
        info: dict | None = None,
    ) -> dict:
        """添加记忆.

        Args:
            user_id: 用户 ID
            writable_cube_ids: 可写的 Cube ID 列表
            messages: 消息列表 [{"role": "user", "content": "..."}, ...]
            async_mode: async/sync
            info: 额外信息

        Returns:
            添加结果，包含 task_id 或 memory_ids
        """
        body = {
            "user_id": user_id,
            "writable_cube_ids": writable_cube_ids,
            "messages": messages,
            "async_mode": async_mode,
        }
        if info:
            body["info"] = info

        return await self._post("/product/add", body)

    async def list_cubes(self, user_id: str) -> list[dict]:
        """列出用户的所有 Cube.

        Args:
            user_id: 用户 ID

        Returns:
            Cube 列表
        """
        return await self._post("/product/list_cubes", {"user_id": user_id})

    async def create_cube(
        self,
        user_id: str,
        cube_name: str,
        description: str = "",
    ) -> dict:
        """创建新的 Cube.

        Args:
            user_id: 用户 ID
            cube_name: Cube 名称
            description: Cube 描述

        Returns:
            创建结果，包含 cube_id
        """
        return await self._post("/product/create_cube", {
            "user_id": user_id,
            "cube_name": cube_name,
            "description": description,
        })

    async def chat_complete(
        self,
        query: str,
        user_id: str,
        readable_cube_ids: list[str],
        system_prompt: str | None = None,
        history: list[dict] | None = None,
    ) -> dict:
        """Chat 对话 (完整响应).

        Args:
            query: 用户查询
            user_id: 用户 ID
            readable_cube_ids: 可读的 Cube ID 列表
            system_prompt: 系统提示词
            history: 历史消息

        Returns:
            对话结果，包含 response 和 reasoning
        """
        body = {
            "query": query,
            "user_id": user_id,
            "readable_cube_ids": readable_cube_ids,
        }
        if system_prompt:
            body["system_prompt"] = system_prompt
        if history:
            body["history"] = history

        return await self._post("/product/chat/complete", body)

    async def chat_stream(
        self,
        query: str,
        user_id: str,
        readable_cube_ids: list[str],
        system_prompt: str | None = None,
        history: list[dict] | None = None,
    ) -> AsyncIterator[str]:
        """Chat 对话 (流式响应).

        Yields:
            流式响应文本片段
        """
        if not self._session:
            raise RuntimeError("MemOSClient not initialized")

        url = f"{self._base_url}/product/chat/stream"
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        body = {
            "query": query,
            "user_id": user_id,
            "readable_cube_ids": readable_cube_ids,
        }
        if system_prompt:
            body["system_prompt"] = system_prompt
        if history:
            body["history"] = history

        async with self._session.post(url, json=body, headers=headers) as resp:
            resp.raise_for_status()
            async for line in resp.content:
                if line:
                    yield line.decode("utf-8")

    # ==================== P1 Memory CRUD ====================

    async def get_memory(
        self,
        user_id: str,
        cube_id: str | None = None,
        limit: int = 50,
    ) -> dict:
        """获取记忆列表.

        Args:
            user_id: 用户 ID
            cube_id: Cube ID (可选)
            limit: 返回数量限制

        Returns:
            记忆列表
        """
        body = {
            "user_id": user_id,
            "limit": limit,
        }
        if cube_id:
            body["mem_cube_id"] = cube_id

        return await self._post("/product/get_memory", body)

    async def get_all_memories(self, user_id: str) -> dict:
        """获取用户全部记忆."""
        return await self._post("/product/get_all", {"user_id": user_id})

    async def delete_memory(
        self,
        user_id: str,
        memory_id: str,
        cube_id: str,
    ) -> dict:
        """删除记忆.

        Args:
            user_id: 用户 ID
            memory_id: 记忆 ID
            cube_id: Cube ID

        Returns:
            删除结果
        """
        body = {
            "user_id": user_id,
            "memory_id": memory_id,
            "mem_cube_id": cube_id,
        }
        return await self._post("/product/delete_memory", body)

    async def recover_memory(
        self,
        user_id: str,
        record_id: str,
    ) -> dict:
        """恢复记忆.

        Args:
            user_id: 用户 ID
            record_id: 记录 ID

        Returns:
            恢复结果
        """
        body = {
            "user_id": user_id,
            "record_id": record_id,
        }
        return await self._post("/product/recover_memory_by_record_id", body)

    async def feedback(
        self,
        user_id: str,
        memory_id: str,
        feedback_type: str,
        score: float | None = None,
    ) -> dict:
        """用户反馈.

        Args:
            user_id: 用户 ID
            memory_id: 记忆 ID
            feedback_type: 反馈类型 (like/dislike)
            score: 评分 (可选)

        Returns:
            反馈结果
        """
        body = {
            "user_id": user_id,
            "memory_id": memory_id,
            "type": feedback_type,
        }
        if score is not None:
            body["score"] = score

        return await self._post("/product/feedback", body)

    async def suggestions(
        self,
        user_id: str,
        query: str | None = None,
    ) -> list[str]:
        """获取建议查询.

        Args:
            user_id: 用户 ID
            query: 当前查询 (可选)

        Returns:
            建议查询列表
        """
        body = {"user_id": user_id}
        if query:
            body["query"] = query

        data = await self._post("/product/suggestions", body)
        return data.get("suggestions", [])

    # ==================== P2 Cube & Scheduler ====================

    async def exist_cube(self, cube_id: str) -> bool:
        """检查 Cube 是否存在.

        Args:
            cube_id: Cube ID

        Returns:
            是否存在
        """
        data = await self._post(
            "/product/exist_mem_cube_id",
            {"mem_cube_id": cube_id},
        )
        return bool(data.get(cube_id, False))

    async def scheduler_status(self, user_id: str) -> dict:
        """获取调度器状态.

        Args:
            user_id: 用户 ID

        Returns:
            调度器状态
        """
        return await self._get(f"/product/scheduler/status?user_id={user_id}")

    async def scheduler_all_status(self, user_id: str) -> dict:
        """获取详细调度器状态.

        Args:
            user_id: 用户 ID

        Returns:
            详细调度器状态
        """
        return await self._get(f"/product/scheduler/allstatus?user_id={user_id}")

    async def wait_idle(self, user_id: str, timeout: int = 30) -> bool:
        """等待调度器空闲.

        Args:
            user_id: 用户 ID
            timeout: 超时时间(秒)

        Returns:
            是否成功等待
        """
        body = {
            "user_id": user_id,
            "timeout": timeout,
        }
        data = await self._post("/product/scheduler/wait", body)
        return data.get("idle", False)

