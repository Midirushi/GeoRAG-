from typing import List, Dict, AsyncGenerator
from anthropic import AsyncAnthropic
from app.config import settings

class LLMGenerator:
    def __init__(self):
        self.client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.model = settings.LLM_MODEL
        self.system_prompt = "你是时空地理知识专家，需基于提供的检索结果准确回答，明确标注信息来源（地点和时间），知识不足时需说明，语气专业友好。"

    async def generate(self, query: str, contexts: List[Dict]) -> str:
        """非流式生成：基于检索上下文生成完整回答"""
        # 1. 构建上下文字符串（格式：文档标题+地点+时间+内容片段）
        context_str = self._build_context(contexts)
        # 2. 构建Prompt
        prompt = f"""
        {self.system_prompt}
        用户问题：{query}
        相关知识：
        {context_str}
        回答要求：
        1. 严格基于上述知识，不添加外部信息；
        2. 每个结论需标注来源（如“[来源：故宫建筑史，北京，明朝(1368-1644)]”）；
        3. 分点说明（若有多个要点），语言简洁易懂。
        """
        # 3. 调用LLM生成回答
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()

    async def generate_stream(self, query: str, contexts: List[Dict]) -> AsyncGenerator[str, None]:
        """流式生成：逐段返回回答（提升用户体验）"""
        context_str = self._build_context(contexts)
        prompt = f"""
        {self.system_prompt}
        用户问题：{query}
        相关知识：
        {context_str}
        回答要求：
        1. 严格基于上述知识，不添加外部信息；
        2. 每个结论需标注来源（如“[来源：故宫建筑史，北京，明朝(1368-1644)]”）；
        3. 分点说明（若有多个要点），语言简洁易懂。
        """
        # 调用Anthropic流式API
        async with self.client.messages.stream(
            model=self.model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}]
        ) as stream:
            async for event in stream:
                if event.type == "content_block_delta":
                    yield event.delta.text  # 逐段返回文本

    def _build_context(self, contexts: List[Dict]) -> str:
        """构建上下文字符串（整理检索到的文档信息）"""
        context_parts = []
        for idx, ctx in enumerate(contexts, 1):
            payload = ctx["payload"]
            # 提取关键信息（标题、地点、时间、内容片段）
            title = payload.get("title", "未知标题")
            address = payload.get("geo_point", {}).get("address", "未知地点")
            display_time = payload.get("metadata", {}).get("display_time", "未知时间")
            content = payload.get("content", "")[:500] + "..." if len(payload.get("content", "")) > 500 else payload.get("content", "")
            # 拼接单个文档上下文
            context_parts.append(
                f"【文档{idx}】\n"
                f"标题：{title}\n"
                f"地点：{address}\n"
                f"时间：{display_time}\n"
                f"内容：{content}\n"
            )
        return "\n\n".join(context_parts)