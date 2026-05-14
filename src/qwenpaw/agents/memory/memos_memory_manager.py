# -*- coding: utf-8 -*-
"""MemOS-backed memory manager for agents."""
import asyncio
import json
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from agentscope.message import Msg, TextBlock
from agentscope.tool import ToolResponse

from .base_memory_manager import BaseMemoryManager, memory_registry
from .memos_client import MemOSClient, MemOSError
from .prompts import (
    MEMORY_GUIDANCE_ZH,
    MEMORY_GUIDANCE_EN,
)
from ...config.config import MemosMemoryConfig, load_agent_config

logger = logging.getLogger(__name__)


@memory_registry.register("memos")
class MemosMemoryManager(BaseMemoryManager):
    """MemOS-backed memory manager for agents.

    实现功能:
    1. 完整实现 BaseMemoryManager 抽象接口
    2. 通过 MemOSClient 调用 MemOS REST API
    3. 支持 fallback 到 ReMeLight (由工厂层处理)
    4. 工具签名与 ReMeLight 兼容

    Integration strategy:
    - retrieve() -> POST /product/search
    - summarize() -> POST /product/add (store summary)
    - list_memory_tools() -> [memos_memory_search, memos_add_memory]
    - start() -> health_check + ensure cube exists
    - close() -> cleanup client session
    """

    def __init__(self, working_dir: str, agent_id: str):
        super().__init__(working_dir=working_dir, agent_id=agent_id)
        self._client: MemOSClient | None = None
        self._config: MemosMemoryConfig | None = None
        self._cube_id: str | None = None
        self._health_monitor_started: bool = False  # 添加标记

        logger.info(
            f"MemosMemoryManager init: "
            f"agent_id={agent_id}, working_dir={working_dir}",
        )

    def _load_config(self) -> MemosMemoryConfig:
        """从 AgentProfile 加载 MemOS 配置.

        如果无法加载配置，返回默认配置.
        """
        try:
            agent_config = load_agent_config(self.agent_id)
            return agent_config.running.memos_memory_config
        except Exception as e:
            logger.warning(
                f"Failed to load MemOS config for agent {self.agent_id}: {e}. "
                f"Using default config.",
            )
            return MemosMemoryConfig()

    async def start(self) -> None:
        """初始化: 加载配置, 连接 MemOS, 验证/创建 Cube.

        即使 MemOS 不可用也不会阻塞 Agent 启动，会静默降级到只读模式。
        用户仍然可以进入配置页面切换到 ReMeLight。
        """
        # Step 1: 加载配置
        self._config = self._load_config()
        logger.info(
            f"MemosMemoryManager starting: "
            f"url={self._config.memos_url}, "
            f"user_id={self._config.user_id}, "
            f"cube_name={self._config.cube_name}",
        )

        # Step 2: 创建客户端
        self._client = MemOSClient(
            base_url=self._config.memos_url,
            api_key=self._config.api_key,
            timeout=self._config.timeout_seconds,
        )

        try:
            await self._client.__aenter__()
        except Exception as e:
            logger.warning(f"MemOS client init failed: {e}")
            self._client = None
            self._initialized = False
            return

        # Step 3: 健康检查 - 失败则静默降级
        try:
            if not await self._client.health_check():
                logger.warning(
                    f"MemOS health check failed at {self._config.memos_url}. "
                    f"Running in degraded mode. "
                    f"User can still access config page to switch to ReMeLight."
                )
                await self._graceful_degrade("健康检查失败")
                return
        except Exception as e:
            logger.warning(f"MemOS health check error: {e}")
            await self._graceful_degrade(f"健康检查异常: {str(e)[:100]}")
            return

        logger.info("MemOS health check passed")

        # Step 4: 验证 Cube
        try:
            cube_exists = await self._client.exist_cube(self._config.cube_name)
            if not cube_exists:
                if self._config.create_cube_if_not_exists:
                    logger.warning(
                        f"Cube '{self._config.cube_name}' does not exist. "
                        f"Auto-creation not fully implemented yet."
                    )
                    self._cube_id = self._config.cube_name
                else:
                    logger.warning(
                        f"Cube '{self._config.cube_name}' does not exist. "
                        f"Running in degraded mode."
                    )
                    await self._graceful_degrade("Cube 不存在")
                    return
            else:
                self._cube_id = self._config.cube_name
                logger.info(f"Cube '{self._cube_id}' verified")
        except Exception as e:
            logger.warning(f"MemOS cube validation error: {e}")
            await self._graceful_degrade(f"Cube 验证失败: {str(e)[:100]}")
            return

        self._initialized = True
        self._update_status("healthy")
        
        logger.info(
            f"MemosMemoryManager started successfully: "
            f"cube_id={self._cube_id}",
        )
        
        # 启动后台健康检查
        self.start_health_monitor()

    async def _graceful_degrade(self, error_msg: str = "") -> None:
        """优雅降级：关闭客户端，设置未初始化标记."""
        if self._client:
            try:
                await self._client.__aexit__(None, None, None)
            except:
                pass
        self._client = None
        self._initialized = False
        
        # 更新状态
        self._update_status("degraded", error_msg or "MemOS 连接失败")
        
        logger.warning(
            "MemOS degraded to read-only mode. "
            "Memory read/write operations will return friendly errors. "
            "You can still access config page."
        )
        
        # 启动/重启后台健康检查（会在降级时尝试重建连接）
        self.start_health_monitor()

    def _update_status(self, status: str, error_msg: str | None = None) -> None:
        """更新 MemOS 状态到配置文件."""
        if not self._config:
            return
        
        self._config.memos_status = status
        self._config.memos_error_msg = error_msg
        self._config.memos_last_check = datetime.now(timezone.utc).isoformat()
        
        try:
            # 读取当前配置文件
            agent_json_path = Path(self.working_dir) / "agent.json"
            if agent_json_path.exists():
                with open(agent_json_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                
                # 更新 memos_memory_config 下的状态
                if "running" in config and "memos_memory_config" in config["running"]:
                    config["running"]["memos_memory_config"]["memos_status"] = status
                    config["running"]["memos_memory_config"]["memos_error_msg"] = error_msg
                    config["running"]["memos_memory_config"]["memos_last_check"] = self._config.memos_last_check
                    
                    with open(agent_json_path, "w", encoding="utf-8") as f:
                        json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to update memos status: {e}")

    async def _health_check_loop(self) -> None:
        """后台定时健康检查，降级时尝试重建连接."""
        import time
        while True:
            await asyncio.sleep(30)  # 每 30 秒检查一次
            
            if not self._config:
                continue
            
            # 如果客户端存在，直接做健康检查
            if self._client:
                try:
                    if await self._client.health_check():
                        self._update_status("healthy")
                    else:
                        self._update_status("degraded", "健康检查返回 false")
                except Exception as e:
                    self._update_status("error", str(e)[:200])
            else:
                # 客户端不存在（降级状态），尝试重建连接
                try:
                    new_client = MemOSClient(
                        base_url=self._config.memos_url,
                        api_key=self._config.api_key,
                        timeout=self._config.timeout_seconds,
                    )
                    await new_client.__aenter__()
                    if await new_client.health_check():
                        # 重建成功！
                        self._client = new_client
                        self._initialized = True
                        self._update_status("healthy")
                        logger.info("MemOS reconnected successfully!")
                    else:
                        await new_client.__aexit__(None, None, None)
                        self._update_status("degraded", "重建连接后健康检查仍失败")
                except Exception as e:
                    self._update_status("error", f"重建连接失败: {str(e)[:100]}")

    def start_health_monitor(self) -> None:
        """启动健康检查后台任务（防重复启动）."""
        if self._health_monitor_started:
            return
        self._health_monitor_started = True
        asyncio.create_task(self._health_check_loop())

    async def close(self) -> bool:
        """关闭 MemOS 连接."""
        if self._client:
            await self._client.__aexit__(None, None, None)
            self._client = None
            logger.info("MemosMemoryManager closed")
        return True

    def get_memory_prompt(self, language: str = "zh") -> str:
        """返回记忆引导提示词."""
        visible = self._config.memory_tool_visible if self._config else False

        if language.startswith("zh"):
            if visible:
                return (
                    "你拥有一个由 MemOS 驱动的长期记忆系统。\n"
                    "你可以使用 memos_memory_search 工具来检索过去的对话记忆和知识。\n"
                    "你可以使用 memos_add_memory 工具来保存重要信息到记忆中。\n"
                    "主动检索与你当前任务相关的历史记忆，以提供更连贯的回答。\n"
                    "注意：记忆操作结果会以通知形式返回（带 🔍💾 等图标），请将这些通知"
                    "自然地展示给用户。"
                )
            return (
                "你拥有一个由 MemOS 驱动的长期记忆系统。\n"
                "你可以使用 memos_memory_search 工具来检索过去的对话记忆和知识。\n"
                "你可以使用 memos_add_memory 工具来保存重要信息到记忆中。\n"
                "主动检索与你当前任务相关的历史记忆，以提供更连贯的回答。"
            )
        if visible:
            return (
                "You have a long-term memory system powered by MemOS.\n"
                "Use memos_memory_search to retrieve past conversation memories.\n"
                "Use memos_add_memory to save important information to memory.\n"
                "Proactively search for memories relevant to your current task.\n"
                "Note: Memory operation results will be returned with notification "
                "icons (🔍💾). Present these notifications naturally to the user."
            )
        return (
            "You have a long-term memory system powered by MemOS.\n"
            "Use memos_memory_search to retrieve past conversation memories.\n"
            "Use memos_add_memory to save important information to memory.\n"
            "Proactively search for memories relevant to your current task."
        )

    def list_memory_tools(self) -> list[Callable[..., ToolResponse]]:
        """返回可用的记忆工具.

        与 ReMeLight 保持一致: 暴露 memory_search 和 add_memory 工具.
        """
        return [self.memos_memory_search, self.memos_add_memory]

    async def retrieve(
        self,
        messages: list[Msg] | Msg,
        **kwargs,
    ) -> dict | None:
        """语义检索记忆.

        使用 MemOS /product/search API.
        """
        if not self._client or not self._config:
            logger.warning("MemosMemoryManager not initialized, skip retrieve")
            return None

        # 构建查询
        query = self._build_query_from_messages(messages)
        if not query:
            return None

        try:
            results = await self._client.search(
                query=query,
                user_id=self._config.user_id,
                readable_cube_ids=[self._cube_id],
                top_k=self._config.top_k,
                relativity=self._config.relativity_threshold,
                mode=self._config.search_mode,
            )

            if not results or not results.get("text_mem"):
                return None

            # 格式化结果，与 ReMeLight 输出一致
            return self._format_retrieve_results(results, messages)

        except MemOSError as e:
            logger.error(f"MemOS search error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in retrieve: {e}")
            return None

    async def summarize(
        self,
        messages: list[Msg],
        **kwargs,
    ) -> str:
        """总结对话消息并存储到 MemOS."""
        if not self._client or not self._config:
            logger.warning("MemosMemoryManager not initialized, skip summarize")
            return ""

        # 构建摘要内容
        summary_content = self._build_summary_from_messages(messages)
        if not summary_content:
            return ""

        try:
            await self._client.add(
                user_id=self._config.user_id,
                writable_cube_ids=[self._cube_id],
                messages=[{"role": "system", "content": summary_content}],
                async_mode="sync",
                info={
                    "source": "qwenpaw_summarize",
                    "agent_id": self.agent_id,
                },
            )
            return summary_content
        except MemOSError as e:
            logger.error(f"MemOS add error: {e}")
            return ""
        except Exception as e:
            logger.error(f"Unexpected error in summarize: {e}")
            return ""

    # ==================== Agent Tool Functions ====================

    async def memos_memory_search(
        self,
        query: str,
        max_results: int = 5,
        min_score: float = 0.1,
    ) -> ToolResponse:
        """搜索代理的长期记忆 (通过 MemOS).

        与 ReMeLight 的 memory_search 签名兼容.

        Args:
            query: 搜索查询
            max_results: 最大返回结果数
            min_score: 最小相关性分数

        Returns:
            ToolResponse: 搜索结果
        """
        # 检查是否降级模式
        if not self._initialized or not self._client or not self._config:
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text="⚠️ MemOS 当前不可用（降级模式）\n\n"
                             "可能原因：\n"
                             "• 网络连接失败\n"
                             "• MemOS 服务不可用\n"
                             "• API 认证失败\n\n"
                             "解决方案：\n"
                             "1. 进入配置页面检查 MemOS 设置\n"
                             "2. 将 Memory Manager 切换为 ReMeLight\n"
                             "3. 修复后重启服务",
                    ),
                ],
            )

        try:
            results = await self._client.search(
                query=query,
                user_id=self._config.user_id,
                readable_cube_ids=[self._cube_id],
                top_k=max_results,
                relativity=min_score,
                mode=self._config.search_mode,
            )

            if not results or not results.get("text_mem"):
                return ToolResponse(
                    content=[
                        TextBlock(
                            type="text",
                            text="No relevant memories found.",
                        ),
                    ],
                )

            # 格式化输出 - text_mem 是 cube 列表，需展平为 memories
            text_mems = results["text_mem"]
            all_memories = []
            for cube in text_mems:
                for mem in cube.get("memories", []):
                    all_memories.append(mem)

            if not all_memories:
                return ToolResponse(
                    content=[
                        TextBlock(
                            type="text",
                            text="No relevant memories found.",
                        ),
                    ],
                )

            visible = self._config.memory_tool_visible if self._config else False
            logger.info(
                f"[MEMOS_DEBUG] search: visible={visible}, "
                f"raw={self._config.memory_tool_visible if self._config else 'N/A'}"
            )

            if visible:
                # 通知模式：带 emoji 和标签摘要
                tags = set()
                lines = [
                    f"🔍 检索到 {len(all_memories)} 条相关记忆\n",
                ]
                for i, mem in enumerate(all_memories, 1):
                    content = mem.get("memory", "")[:200]
                    metadata = mem.get("metadata", {})
                    score = metadata.get("relativity", 0)
                    mem_tags = metadata.get("tags", [])
                    tags.update(mem_tags)
                    lines.append(f"{i}. [score={score:.2f}] {content}...")
                if tags:
                    lines.append(f"\n🏷️ 标签: {'、'.join(list(tags)[:8])}")

                return ToolResponse(
                    content=[
                        TextBlock(
                            type="text",
                            text="\n".join(lines),
                        ),
                    ],
                )
            else:
                # 简洁模式（默认）：只返回核心数据供 agent 自己处理
                lines = [f"Found {len(all_memories)} relevant memories:\n"]
                for i, mem in enumerate(all_memories, 1):
                    content = mem.get("memory", "")[:200]
                    metadata = mem.get("metadata", {})
                    score = metadata.get("relativity", 0)
                    lines.append(f"{i}. [score={score:.2f}] {content}...")

                return ToolResponse(
                    content=[
                        TextBlock(
                            type="text",
                            text="\n".join(lines),
                        ),
                    ],
                )

        except Exception as e:
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=f"Search error: {e}",
                    ),
                ],
            )

    async def memos_add_memory(
        self,
        content: str,
        memory_type: str = "text_mem",
        info: dict | None = None,
    ) -> ToolResponse:
        """手动添加记忆到 MemOS.

        Args:
            content: 要存储的记忆内容
            memory_type: 记忆类型 (text_mem/act_mem/param_mem)
            info: 额外信息

        Returns:
            ToolResponse with add result
        """
        # 检查是否降级模式
        if not self._initialized or not self._client or not self._config:
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text="⚠️ MemOS 当前不可用，无法保存记忆\n\n"
                             "请进入配置页面将 Memory Manager 切换为 ReMeLight",
                    ),
                ],
            )

        try:
            # 构建消息格式
            messages = [{"role": "user", "content": content}]

            # 添加记忆
            result = await self._client.add(
                user_id=self._config.user_id,
                writable_cube_ids=[self._cube_id],
                messages=messages,
                async_mode="sync",
                info=info or {
                    "source": "qwenpaw_manual_add",
                    "agent_id": self.agent_id,
                },
            )

            visible = self._config.memory_tool_visible if self._config else False
            logger.info(
                f"[MEMOS_DEBUG] search: visible={visible}, "
                f"raw={self._config.memory_tool_visible if self._config else 'N/A'}"
            )
            if visible:
                memory_id = ""
                if result and isinstance(result, list) and len(result) > 0:
                    memory_id = result[0].get("memory_id", "")
                summary = content[:60] + ("..." if len(content) > 60 else "")
                text = f"💾 记忆已保存（{memory_id[:8]}）\n📝 {summary}"
            else:
                text = f"Memory added successfully. Result: {result}"

            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=text,
                    )
                ],
            )
        except MemOSError as e:
            return ToolResponse(
                content=[
                    TextBlock(type="text", text=f"Add memory error: {e}"),
                ],
            )
        except Exception as e:
            return ToolResponse(
                content=[
                    TextBlock(type="text", text=f"Unexpected error: {e}"),
                ],
            )

    # ==================== Internal Helpers ====================

    def _build_query_from_messages(
        self,
        messages: list[Msg] | Msg,
    ) -> str:
        """从消息列表构建搜索查询.

        与 ReMeLight 逻辑类似: 取最新消息, 反向构建约 100 字符的查询.
        """
        if isinstance(messages, Msg):
            messages = [messages]

        if not messages:
            return ""

        # 取最近 3 条消息
        recent = messages[-3:] if len(messages) > 3 else messages

        # 构建查询文本
        query_parts = []
        for msg in reversed(recent):
            if hasattr(msg, "content"):
                if isinstance(msg.content, str):
                    query_parts.append(msg.content)
                elif isinstance(msg.content, list):
                    for block in msg.content:
                        if hasattr(block, "text"):
                            query_parts.append(block.text)
                        elif isinstance(block, dict):
                            query_parts.append(block.get("text", ""))

        query = " ".join(query_parts)
        # 限制长度
        return query[:200] if len(query) > 200 else query

    def _format_retrieve_results(
        self,
        raw_results: dict,
        original_messages: list[Msg] | Msg,
    ) -> dict:
        """格式化 MemOS 搜索输出以匹配预期的 retrieve() 格式.

        构建类似 ReMeLight 的 synthetic assistant_msg + tool_result_msg.
        """
        text_mems = raw_results.get("text_mem", [])

        if not text_mems:
            return {"memories": [], "status": "no_results"}

        # 格式化每条记忆
        formatted_memories = []
        for cube in text_mems:
            for mem in cube.get("memories", []):
                metadata = mem.get("metadata", {})
                formatted_memories.append({
                    "memory_id": mem.get("id", ""),
                    "content": mem.get("memory", ""),
                    "score": metadata.get("relativity", 0),
                    "created_at": metadata.get("created_at", ""),
                })

        # 构建响应格式，与 ReMeLight 兼容
        return {
            "memories": formatted_memories,
            "status": "success",
            "count": len(formatted_memories),
        }

    def _build_summary_from_messages(self, messages: list[Msg]) -> str:
        """从对话消息构建摘要文本.

        简单的拼接 + 时间戳，实际生产环境可调用 LLM 进行摘要.
        """
        if not messages:
            return ""

        lines = ["Conversation Summary:"]

        for msg in messages:
            role = getattr(msg, "role", "unknown")
            name = getattr(msg, "name", "")
            name_part = f" ({name})" if name else ""

            if hasattr(msg, "content"):
                if isinstance(msg.content, str):
                    lines.append(f"{role}{name_part}: {msg.content}")
                elif isinstance(msg.content, list):
                    for block in msg.content:
                        if hasattr(block, "text"):
                            lines.append(f"{role}{name_part}: {block.text}")
                        elif isinstance(block, dict):
                            lines.append(
                                f"{role}{name_part}: {block.get('text', '')}",
                            )

        return "\n".join(lines)