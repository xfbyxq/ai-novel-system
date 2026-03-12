import json
import sys
from typing import Optional
from datetime import datetime
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.models.novel_creation_flow import NovelCreationFlow
from backend.schemas.novel_creation_flow import (
    CreationFlowStep,
    NovelCreationContext,
    NovelCreationFlowState,
    WorldSettingDetails,
    NovelSynopsis,
    NovelDialogueScene
)
from llm.qwen_client import QwenClient


class FlowResponse:
    """流程响应"""
    def __init__(self, message: str, context: NovelCreationContext, next_step: CreationFlowStep):
        self.message = message
        self.context = context
        self.next_step = next_step


class NovelCreationFlowManager:
    """小说创建对话流程管理器"""
    
    def __init__(self, db: AsyncSession, qwen_client: Optional[QwenClient] = None):
        self.db = db
        self.qwen_client = qwen_client or QwenClient()
        self._context_cache: dict[str, NovelCreationContext] = {}
    
    async def initialize_flow(self, session_id: str, scene: NovelDialogueScene = NovelDialogueScene.CREATE) -> NovelCreationFlowState:
        """初始化创建流程"""
        # 创建数据库记录
        flow = NovelCreationFlow(session_id=session_id, scene=scene.value)
        self.db.add(flow)
        await self.db.commit()
        
        # 初始化上下文
        context = NovelCreationContext(scene=scene)
        self._context_cache[session_id] = context
        
        return NovelCreationFlowState(
            session_id=session_id,
            context=context,
            conversation_history=[],
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
    
    async def process_message(self, session_id: str, user_input: str) -> FlowResponse:
        """处理用户消息"""
        # 获取或创建上下文
        context = await self._get_or_create_context(session_id)
        
        # 根据当前步骤处理消息
        current_step = CreationFlowStep(context.current_step)
        
        # 场景选择
        if current_step == CreationFlowStep.SCENE_SELECTION:
            return await self._handle_scene_selection(session_id, user_input, context)
        # 创建流程
        elif current_step == CreationFlowStep.INITIAL:
            return await self._handle_initial_step(session_id, user_input, context)
        elif current_step == CreationFlowStep.GENRE_CONFIRMATION:
            return await self._handle_genre_step(session_id, user_input, context)
        elif current_step in [CreationFlowStep.WORLD_SETTING_DETAIL, CreationFlowStep.WORLD_SETTING_CLARIFY]:
            return await self._handle_world_setting_step(session_id, user_input, context)
        elif current_step in [CreationFlowStep.SYNOPSIS_EXTRACTION, CreationFlowStep.SYNOPSIS_REFINEMENT]:
            return await self._handle_synopsis_step(session_id, user_input, context)
        elif current_step == CreationFlowStep.FINAL_CONFIRMATION:
            return await self._handle_final_step(session_id, user_input, context)
        # 查询流程
        elif current_step == CreationFlowStep.NOVEL_SELECTION:
            return await self._handle_novel_selection(session_id, user_input, context)
        elif current_step == CreationFlowStep.CONTENT_QUERY:
            return await self._handle_content_query(session_id, user_input, context)
        # 修改流程
        elif current_step == CreationFlowStep.REVISION_TARGET_SELECTION:
            return await self._handle_revision_target_selection(session_id, user_input, context)
        elif current_step == CreationFlowStep.REVISION_DETAIL_COLLECTION:
            return await self._handle_revision_detail_collection(session_id, user_input, context)
        elif current_step == CreationFlowStep.REVISION_CONFIRMATION:
            return await self._handle_revision_confirmation(session_id, user_input, context)
        else:
            return FlowResponse(
                message="当前流程状态异常，请重新开始",
                context=context,
                next_step=CreationFlowStep.SCENE_SELECTION
            )
    
    async def _handle_scene_selection(self, session_id: str, user_input: str, context: NovelCreationContext) -> FlowResponse:
        """处理场景选择"""
        # 使用 AI 识别用户意图
        prompt = f"""分析用户想要进行的操作：
用户输入：{user_input}

返回 JSON:
{{
    "scene": "create/query/revise",
    "confidence": 0.9
}}"""
        
        ai_response = await self.qwen_client.chat(prompt)
        
        try:
            scene_info = json.loads(ai_response)
            scene = scene_info.get("scene", "create")
            
            if scene == "create":
                context.scene = NovelDialogueScene.CREATE
                context.current_step = CreationFlowStep.INITIAL.value
                return await self._handle_initial_step(session_id, user_input, context)
            elif scene == "query":
                context.scene = NovelDialogueScene.QUERY
                context.current_step = CreationFlowStep.NOVEL_SELECTION.value
                return FlowResponse(
                    message="好的！请告诉我您想查询哪部小说？您可以提供小说 ID、名称或关键词。",
                    context=context,
                    next_step=CreationFlowStep.NOVEL_SELECTION
                )
            elif scene == "revise":
                context.scene = NovelDialogueScene.REVISE
                context.current_step = CreationFlowStep.NOVEL_SELECTION.value
                return FlowResponse(
                    message="好的！请告诉我您想修改哪部小说？",
                    context=context,
                    next_step=CreationFlowStep.NOVEL_SELECTION
                )
            else:
                return self._get_scene_selection_message()
        except:
            return self._get_scene_selection_message()
    
    def _get_scene_selection_message(self) -> FlowResponse:
        """获取场景选择消息"""
        return FlowResponse(
            message="""您好！我是您的小说创作助手📚

我可以帮您：
1️⃣ **创作新小说** - 通过对话引导您完成小说创建
2️⃣ **查询已有小说** - 查看小说的世界观、角色、剧情等信息
3️⃣ **修改小说内容** - 通过对话修改小说的设定和内容

请告诉我您想做什么？""",
            context=NovelCreationContext(),
            next_step=CreationFlowStep.SCENE_SELECTION
        )
    
    async def _handle_initial_step(self, session_id: str, user_input: str, context: NovelCreationContext) -> FlowResponse:
        """处理初始步骤"""
        # 使用 AI 分析用户意图，提取小说类型
        prompt = f"""请分析用户的小说创作意图，提取以下信息：
1. 小说类型（如玄幻、科幻、言情、都市、历史等）
2. 用户提到的任何世界观元素
3. 用户提到的任何情节或主角信息

用户输入：{user_input}

请以 JSON 格式返回：
{{
    "genre": "类型",
    "world_elements": ["元素 1", "元素 2"],
    "plot_hints": ["情节提示"],
    "confidence": 0.9
}}"""
        
        ai_response = await self.qwen_client.chat(prompt)
        
        # 解析 AI 响应
        try:
            extracted_info = json.loads(ai_response)
            if extracted_info.get("genre"):
                context.genre = extracted_info["genre"]
                context.current_step = CreationFlowStep.GENRE_CONFIRMATION.value
                
                response_message = f"""我了解到您想创作一部**{extracted_info['genre']}**类型的小说。

这个类型非常受欢迎！让我确认一下：您确定要创作{extracted_info['genre']}类型的小说吗？

如果您想调整类型，请告诉我具体的类型名称。"""
            else:
                response_message = self._get_genre_selection_message()
                context.current_step = CreationFlowStep.GENRE_CONFIRMATION.value
        except:
            response_message = self._get_genre_selection_message()
            context.current_step = CreationFlowStep.GENRE_CONFIRMATION.value
        
        return FlowResponse(
            message=response_message,
            context=context,
            next_step=CreationFlowStep(context.current_step)
        )
    
    def _get_genre_selection_message(self) -> str:
        """获取类型选择消息"""
        return """您好！我是您的小说创作助手。

在开始创作之前，让我先了解一下：您想创作什么类型的小说呢？

常见的类型有：
- 📚 **玄幻**：修真、魔法、异世大陆
- 🚀 **科幻**：未来科技、星际文明
- 💕 **言情**：现代言情、古代言情
- 🏙️ **都市**：都市生活、职场商战
- 📜 **历史**：历史穿越、朝代更替
- 🎭 **悬疑**：侦探推理、惊悚恐怖

请告诉我您想创作的类型，或者描述您的创作想法！"""
    
    async def _handle_genre_step(self, session_id: str, user_input: str, context: NovelCreationContext) -> FlowResponse:
        """处理类型确认步骤"""
        # 检查用户是否确认
        if any(word in user_input for word in ["确认", "确定", "是的", "好的", "对"]):
            context.genre_confirmed = True
            context.current_step = CreationFlowStep.WORLD_SETTING_DETAIL.value
            
            response_message = f"""太好了！**{context.genre}**类型是个很棒的选择！

现在让我帮您构建这个精彩的世界观背景。请详细描述一下您小说的世界观设定，包括：

🌍 **时代背景**：古代、现代、未来、架空时代？
🗺️ **地理环境**：大陆、星球、多个世界？
🏛️ **社会结构**：宗门、帝国、联邦、部落？
⚡ **特殊规则**：修炼体系、魔法系统、科技水平？
🎯 **力量体系**：等级划分、能力来源？

您可以尽可能详细地描述，或者只说个大概，我会帮您完善！"""
        else:
            # 用户想修改类型
            context.genre = user_input.strip()
            response_message = f"""明白了！那我们将创作一部**{context.genre}**类型的小说。

您对这个类型有什么特别的想法或设定吗？或者我们直接进入世界观设定的讨论？"""
        
        return FlowResponse(
            message=response_message,
            context=context,
            next_step=CreationFlowStep(context.current_step)
        )
    
    async def _handle_world_setting_step(self, session_id: str, user_input: str, context: NovelCreationContext) -> FlowResponse:
        """处理世界观设定步骤"""
        # 使用 AI 提取世界观信息
        prompt = f"""请从用户的描述中提取世界观设定的详细信息：

用户输入：{user_input}

请提取以下信息（如果用户没有提到某项，可以留空或合理推测）：
{{
    "era_background": "时代背景（古代/现代/未来/架空等）",
    "geographical_environment": "地理环境（大陆/星球/世界等）",
    "social_structure": "社会结构（宗门/帝国/组织等）",
    "special_rules": "特殊规则（修炼/魔法/科技等）",
    "power_system": "力量体系（等级划分/能力来源等）",
    "other_elements": "其他重要元素"
}}"""
        
        ai_response = await self.qwen_client.chat(prompt)
        
        try:
            world_setting_data = json.loads(ai_response)
            context.world_setting = WorldSettingDetails(**world_setting_data)
        except:
            context.world_setting = WorldSettingDetails(
                era_background="待定",
                geographical_environment=user_input[:100]
            )
        
        # 检查信息是否完整
        is_complete = self._check_world_setting_completeness(context.world_setting)
        
        if is_complete:
            context.world_setting_confirmed = True
            context.current_step = CreationFlowStep.SYNOPSIS_EXTRACTION.value
            
            response_message = f"""非常精彩的世界观设定！让我总结一下：

📖 **世界观概览**：
- 时代：{context.world_setting.era_background or '未设定'}
- 地理：{context.world_setting.geographical_environment or '未设定'}
- 社会：{context.world_setting.social_structure or '未设定'}
- 规则：{context.world_setting.special_rules or '未设定'}
- 力量：{context.world_setting.power_system or '未设定'}

接下来，让我们提炼一下小说的核心简介。请告诉我：

📝 **主要情节脉络**：主角的目标和成长历程是什么？
⚔️ **核心冲突**：主要的矛盾和对抗是什么？
👥 **目标读者**：您希望吸引哪类读者群体？

您可以简单描述，我会帮您整理成专业的简介！"""
        else:
            # 需要追问
            missing_elements = self._get_missing_world_setting_elements(context.world_setting)
            
            response_message = f"""很好的设定基础！为了让世界观更加完整，让我再了解一些细节：

{missing_elements}

请补充这些信息，或者告诉我您希望我帮您构思这些元素？"""
            
            context.current_step = CreationFlowStep.WORLD_SETTING_CLARIFY.value
        
        return FlowResponse(
            message=response_message,
            context=context,
            next_step=CreationFlowStep(context.current_step)
        )
    
    async def _handle_synopsis_step(self, session_id: str, user_input: str, context: NovelCreationContext) -> FlowResponse:
        """处理简介提炼步骤"""
        # 使用 AI 提炼简介
        prompt = f"""请从用户的描述中提炼小说的核心简介：

用户输入：{user_input}
小说类型：{context.genre}

请提炼以下信息：
{{
    "main_plot": "用 1-2 句话概括主要情节脉络",
    "core_conflict": "用 1 句话概括核心冲突",
    "target_audience": "目标读者群体",
    "unique_selling_point": "独特卖点或亮点（可选）"
}}"""
        
        ai_response = await self.qwen_client.chat(prompt)
        
        try:
            synopsis_data = json.loads(ai_response)
            context.synopsis = NovelSynopsis(**synopsis_data)
        except:
            context.synopsis = NovelSynopsis(
                main_plot=user_input[:200],
                core_conflict="待完善",
                target_audience="广泛读者"
            )
        
        context.synopsis_confirmed = True
        context.current_step = CreationFlowStep.FINAL_CONFIRMATION.value
        
        # 生成小说标题建议
        title_prompt = f"""根据以下信息，生成 3 个吸引人的小说标题建议：
- 类型：{context.genre}
- 世界观：{context.world_setting.era_background or ''} {context.world_setting.geographical_environment or ''}
- 情节：{context.synopsis.main_plot}

请以 JSON 数组格式返回：["标题 1", "标题 2", "标题 3"]"""
        
        title_response = await self.qwen_client.chat(title_prompt)
        
        try:
            title_suggestions = json.loads(title_response)
            titles_text = "、".join(title_suggestions)
        except:
            titles_text = f"《{context.genre}传奇》"
        
        response_message = f"""太棒了！我已经为您提炼了小说的核心简介：

📖 **故事简介**：
{context.synopsis.main_plot}

⚔️ **核心冲突**：
{context.synopsis.core_conflict}

🎯 **目标读者**：
{context.synopsis.target_audience}

现在让我们进行最后的确认！

📝 **完整信息汇总**：
- 类型：{context.genre}
- 世界观：{context.world_setting.era_background or '未设定'} 背景
- 标题建议：{titles_text}
- 篇幅类型：中篇（默认，可调整）
- 目标平台：番茄小说（默认，可调整）

如果您对以上信息满意，请回复"确认创建"或"好的，创建吧"。

如需调整任何内容，请告诉我具体要修改的部分！"""
        
        return FlowResponse(
            message=response_message,
            context=context,
            next_step=CreationFlowStep.FINAL_CONFIRMATION
        )
    
    async def _handle_final_step(self, session_id: str, user_input: str, context: NovelCreationContext) -> FlowResponse:
        """处理最终确认步骤"""
        # 检查用户是否确认创建
        if any(word in user_input for word in ["确认", "创建", "好的", "可以", "开始"]):
            context.final_confirmed = True
            context.current_step = CreationFlowStep.COMPLETED.value
            
            # 调用小说创建服务
            novel_id = await self._create_novel_from_context(session_id, context)
            
            response_message = f"""🎉 恭喜！您的小说已成功创建！

📚 **小说信息**：
- ID: {novel_id}
- 标题：{context.novel_title or '未命名'}
- 类型：{context.genre}
- 篇幅：{context.length_type}
- 平台：{context.target_platform}

接下来，您可以：
1. 开始生成章节大纲
2. 进一步完善角色设定
3. 直接开始创作第一章

祝您创作愉快！有任何需要随时找我！✨"""
            
            # 保存最终状态
            await self._save_flow_state(session_id, context)
        else:
            # 用户想修改某些内容
            response_message = await self._handle_modification_request(user_input, context)
        
        return FlowResponse(
            message=response_message,
            context=context,
            next_step=CreationFlowStep(context.current_step)
        )
    
    def _check_world_setting_completeness(self, world_setting: WorldSettingDetails) -> bool:
        """检查世界观信息完整性"""
        required_fields = ['era_background', 'geographical_environment']
        filled_fields = [
            field for field in required_fields
            if getattr(world_setting, field) and getattr(world_setting, field) != "待定"
        ]
        return len(filled_fields) >= len(required_fields)
    
    def _get_missing_world_setting_elements(self, world_setting: WorldSettingDetails) -> str:
        """获取缺失的世界观元素"""
        missing = []
        
        if not world_setting.era_background or world_setting.era_background == "待定":
            missing.append("- 时代背景（古代/现代/未来/架空？）")
        if not world_setting.geographical_environment:
            missing.append("- 地理环境（大陆/星球/世界？）")
        if not world_setting.social_structure:
            missing.append("- 社会结构（宗门/帝国/组织？）")
        
        return "\n".join(missing) if missing else ""
    
    async def _get_or_create_context(self, session_id: str) -> NovelCreationContext:
        """获取或创建上下文"""
        if session_id in self._context_cache:
            return self._context_cache[session_id]
        
        # 从数据库加载
        stmt = select(NovelCreationFlow).where(NovelCreationFlow.session_id == session_id)
        result = await self.db.execute(stmt)
        flow = result.scalar_one_or_none()
        
        if flow:
            context = NovelCreationContext(
                scene=NovelDialogueScene(flow.scene) if flow.scene else NovelDialogueScene.CREATE,
                current_step=CreationFlowStep(flow.current_step),
                genre=flow.genre,
                world_setting=WorldSettingDetails(**flow.world_setting_data) if flow.world_setting_data else None,
                synopsis=NovelSynopsis(**flow.synopsis_data) if flow.synopsis_data else None,
                novel_title=flow.novel_title,
                tags=flow.tags or [],
                target_platform=flow.target_platform or "番茄小说",
                length_type=flow.length_type or "medium",
                selected_novel_id=flow.selected_novel_id,
                revision_target=flow.revision_target,
                revision_details=flow.revision_details
            )
            self._context_cache[session_id] = context
            return context
        
        # 创建新的
        return NovelCreationContext()
    
    async def _save_flow_state(self, session_id: str, context: NovelCreationContext):
        """保存流程状态到数据库"""
        stmt = select(NovelCreationFlow).where(NovelCreationFlow.session_id == session_id)
        result = await self.db.execute(stmt)
        flow = result.scalar_one_or_none()
        
        if flow:
            flow.current_step = context.current_step
            flow.scene = context.scene.value
            flow.genre = context.genre
            flow.world_setting_data = context.world_setting.dict() if context.world_setting else {}
            flow.synopsis_data = context.synopsis.dict() if context.synopsis else {}
            flow.novel_title = context.novel_title
            flow.tags = context.tags
            flow.genre_confirmed = context.genre_confirmed
            flow.world_setting_confirmed = context.world_setting_confirmed
            flow.synopsis_confirmed = context.synopsis_confirmed
            flow.final_confirmed = context.final_confirmed
            flow.selected_novel_id = context.selected_novel_id
            flow.revision_target = context.revision_target
            flow.revision_details = context.revision_details
            
            await self.db.commit()
    
    async def _create_novel_from_context(self, session_id: str, context: NovelCreationContext) -> str:
        """从上下文创建小说"""
        # 这里调用小说创建服务
        # 简化实现，实际应该调用 NovelService
        import uuid
        novel_id = str(uuid.uuid4())
        
        # 更新 flow 记录关联 novel_id
        stmt = select(NovelCreationFlow).where(NovelCreationFlow.session_id == session_id)
        result = await self.db.execute(stmt)
        flow = result.scalar_one_or_none()
        
        if flow:
            flow.novel_id = novel_id
            await self.db.commit()
        
        return novel_id
    
    async def _handle_modification_request(self, user_input: str, context: NovelCreationContext) -> str:
        """处理修改请求"""
        # 智能识别用户想修改的内容
        if any(word in user_input for word in ["类型", "题材"]):
            context.genre_confirmed = False
            context.current_step = CreationFlowStep.GENRE_CONFIRMATION.value
            return "好的，请问您想将类型修改为什么呢？"
        elif any(word in user_input for word in ["世界观", "设定", "背景"]):
            context.world_setting_confirmed = False
            context.current_step = CreationFlowStep.WORLD_SETTING_DETAIL.value
            return "好的，请重新描述您希望的世界观设定！"
        elif any(word in user_input for word in ["简介", "故事", "情节"]):
            context.synopsis_confirmed = False
            context.current_step = CreationFlowStep.SYNOPSIS_EXTRACTION.value
            return "好的，请重新描述您的故事简介！"
        elif any(word in user_input for word in ["标题", "名字"]):
            return f"好的，请问您希望将标题修改为什么？（当前：{context.novel_title or '未命名'}）"
        else:
            return "请告诉我您具体想修改哪个部分：类型、世界观、简介还是标题？"
    
    # 以下方法将在 Task 5 和 Task 6 中实现
    # ==================== 查询流程方法 ====================
    
    async def _handle_novel_selection(self, session_id: str, user_input: str, context: NovelCreationContext) -> FlowResponse:
        """处理小说选择"""
        from backend.services.novel_query_service import NovelQueryService
        
        # 使用 AI 提取小说搜索关键词
        prompt = f"""从用户输入中提取搜索关键词：
用户输入：{user_input}

返回 JSON:
{{
    "keyword": "搜索关键词",
    "novel_id": "如果有明确 ID"
}}"""
        
        ai_response = await self.qwen_client.chat(prompt)
        
        try:
            extracted = json.loads(ai_response)
            keyword = extracted.get("keyword", user_input)
            novel_id = extracted.get("novel_id")
            
            query_service = NovelQueryService(self.db)
            
            if novel_id:
                # 直接通过 ID 查询
                novel = await query_service.get_novel_by_id(novel_id)
                if novel:
                    context.selected_novel_id = novel_id
                    context.current_step = CreationFlowStep.CONTENT_QUERY.value
                    
                    return FlowResponse(
                        message=f"找到小说《{novel['title']}》。您想查询什么内容？\n\n可选择：\n- 世界观设定\n- 角色列表\n- 剧情大纲\n- 章节列表\n- 基本信息",
                        context=context,
                        next_step=CreationFlowStep.CONTENT_QUERY
                    )
            else:
                # 搜索小说
                novels = await query_service.search_novels(keyword)
                
                if novels:
                    # 显示搜索结果
                    result_text = f"找到 {len(novels)} 部相关小说：\n\n"
                    for i, n in enumerate(novels[:5], 1):
                        result_text += f"{i}. 《{n['title']}》- {n['genre']} ({n['chapter_count']}章)\n"
                    
                    result_text += "\n请告诉我您想查询哪部小说？可以说序号或书名。"
                    
                    return FlowResponse(
                        message=result_text,
                        context=context,
                        next_step=CreationFlowStep.NOVEL_SELECTION
                    )
                else:
                    return FlowResponse(
                        message=f"抱歉，没有找到与'{keyword}'相关的小说。请尝试其他关键词或提供小说 ID。",
                        context=context,
                        next_step=CreationFlowStep.NOVEL_SELECTION
                    )
        except Exception as e:
            return FlowResponse(
                message=f"搜索失败：{str(e)}",
                context=context,
                next_step=CreationFlowStep.NOVEL_SELECTION
            )
    
    async def _handle_content_query(self, session_id: str, user_input: str, context: NovelCreationContext) -> FlowResponse:
        """处理内容查询"""
        from backend.services.novel_query_service import NovelQueryService
        
        if not context.selected_novel_id:
            return FlowResponse(
                message="请先选择要查询的小说",
                context=context,
                next_step=CreationFlowStep.NOVEL_SELECTION
            )
        
        query_service = NovelQueryService(self.db)
        
        # 使用 AI 识别查询目标
        prompt = f"""分析用户想查询的内容类型：
用户输入：{user_input}

返回 JSON:
{{
    "query_target": "world_setting/character/plot/chapter/basic",
    "specific_request": "具体查询要求"
}}"""
        
        ai_response = await self.qwen_client.chat(prompt)
        
        try:
            query_info = json.loads(ai_response)
            query_target = query_info.get("query_target", "basic")
            
            # 执行查询
            if query_target == "world_setting":
                result = await query_service.get_world_setting(context.selected_novel_id)
                result_text = self._format_world_setting_display(result)
            elif query_target == "character":
                # 检查是否有特定角色类型
                role_type = None
                if "主角" in user_input:
                    role_type = "protagonist"
                elif "配角" in user_input:
                    role_type = "supporting"
                elif "反派" in user_input:
                    role_type = "antagonist"
                
                result = await query_service.get_characters(context.selected_novel_id, role_type)
                result_text = self._format_characters_display(result)
            elif query_target == "plot":
                result = await query_service.get_plot_outline(context.selected_novel_id)
                result_text = self._format_plot_display(result)
            elif query_target == "chapter":
                # 检查是否查询特定章节
                if "第" in user_input and "章" in user_input:
                    import re
                    match = re.search(r'第 (\d+) 章', user_input)
                    if match:
                        chapter_num = int(match.group(1))
                        result = await query_service.get_chapter_content(context.selected_novel_id, chapter_num)
                        result_text = self._format_chapter_content_display(result)
                    else:
                        result = await query_service.get_chapter_list(context.selected_novel_id)
                        result_text = self._format_chapter_list_display(result)
                else:
                    result = await query_service.get_chapter_list(context.selected_novel_id)
                    result_text = self._format_chapter_list_display(result)
            else:
                result = await query_service.get_novel_by_id(context.selected_novel_id)
                result_text = self._format_basic_info_display(result)
            
            context.query_result = result
            context.query_target = query_target
            context.current_step = CreationFlowStep.QUERY_RESULT_DISPLAY.value
            
            return FlowResponse(
                message=result_text,
                context=context,
                next_step=CreationFlowStep.QUERY_RESULT_DISPLAY
            )
        except Exception as e:
            return FlowResponse(
                message=f"查询失败：{str(e)}",
                context=context,
                next_step=CreationFlowStep.CONTENT_QUERY
            )
    
    def _format_world_setting_display(self, ws: dict) -> str:
        """格式化世界观显示"""
        if "error" in ws:
            return f"❌ {ws['error']}"
        
        text = f"""📖 **世界观设定**

🌍 **世界名称**: {ws.get('world_name', '未命名')}
🏷️ **世界类型**: {ws.get('world_type', '未知')}

"""
        
        if ws.get('power_system'):
            power = ws['power_system']
            if isinstance(power, dict) and power.get('description'):
                text += f"⚡ **力量体系**:\n{power['description']}\n\n"
        
        if ws.get('geography'):
            geo = ws['geography']
            if isinstance(geo, dict) and geo.get('description'):
                text += f"🗺️ **地理环境**:\n{geo['description']}\n\n"
        
        if ws.get('factions'):
            fac = ws['factions']
            if isinstance(fac, dict) and fac.get('description'):
                text += f"🏛️ **势力划分**:\n{fac['description']}\n\n"
        
        if ws.get('rules'):
            rules = ws['rules']
            if isinstance(rules, dict) and rules.get('description'):
                text += f"📜 **世界规则**:\n{rules['description']}\n\n"
        
        return text.strip()
    
    def _format_characters_display(self, characters: list) -> str:
        """格式化角色列表显示"""
        if not characters:
            return "暂无角色信息"
        
        result = f"👥 **角色列表** (共{len(characters)}个)\n\n"
        for c in characters[:5]:  # 只显示最新 5 个
            result += f"""**{c['name']}** ({c['role_type']})
- 性别：{c['gender']}
- 外貌：{c['appearance'][:50] if c['appearance'] else '暂无'}...
- 性格：{c['personality'][:50] if c['personality'] else '暂无'}...

"""
        if len(characters) > 5:
            result += f"\n... 还有 {len(characters) - 5} 个角色"
        
        return result
    
    def _format_plot_display(self, plot: dict) -> str:
        """格式化剧情大纲显示"""
        if "error" in plot:
            return f"❌ {plot['error']}"
        
        main_plot = plot.get('main_plot_detailed', {})
        text = """📖 **剧情大纲**

"""
        
        if main_plot.get('core_conflict'):
            text += f"🎯 **核心冲突**: {main_plot['core_conflict']}\n"
        if main_plot.get('protagonist_goal'):
            text += f"👤 **主角目标**: {main_plot['protagonist_goal']}\n"
        if main_plot.get('antagonist_force'):
            text += f"👿 **反派力量**: {main_plot['antagonist_force']}\n"
        
        if main_plot.get('escalation_path'):
            text += "\n📈 **冲突升级**:\n"
            for i, stage in enumerate(main_plot['escalation_path'], 1):
                text += f"{i}. {stage}\n"
        
        return text
    
    def _format_chapter_list_display(self, chapters: list) -> str:
        """格式化章节列表显示"""
        if not chapters:
            return "暂无章节"
        
        result = f"📚 **章节列表** (共{len(chapters)}章)\n\n"
        for c in chapters:
            result += f"第{c['chapter_number']}章：{c['title']} ({c['word_count']}字)\n"
        
        return result
    
    def _format_chapter_content_display(self, chapter: dict) -> str:
        """格式化章节内容显示"""
        if "error" in chapter:
            return f"❌ {chapter['error']}"
        
        return f"""📖 **第{chapter['chapter_number']}章：{chapter['title']}**

字数：{chapter['word_count']}

{chapter['content'][:500]}...

(内容过长，仅显示前 500 字)"""
    
    def _format_basic_info_display(self, novel: dict) -> str:
        """格式化基本信息显示"""
        if not novel:
            return "❌ 小说不存在"
        
        tags_text = ", ".join(novel.get('tags', [])) if novel.get('tags') else "无"
        
        return f"""📖 **{novel.get('title', '未命名')}**

✍️ **作者**: {novel.get('author', '未知')}
🏷️ **类型**: {novel.get('genre', '未知')}
📊 **状态**: {novel.get('status', '未知')}
📈 **字数**: {novel.get('word_count', 0):,}
📚 **章节**: {novel.get('chapter_count', 0)}
🎯 **平台**: {novel.get('target_platform', '未设定')}
🏷️ **标签**: {tags_text}

📝 **简介**:
{novel.get('synopsis', '暂无简介')}"""
    
    # ==================== 修改流程方法 ====================
    
    async def _handle_revision_target_selection(self, session_id: str, user_input: str, context: NovelCreationContext) -> FlowResponse:
        """处理修改目标选择"""
        # 使用 AI 识别修改目标
        prompt = f"""分析用户想修改的内容：
用户输入：{user_input}

返回 JSON:
{{
    "revision_target": "world_setting/character/plot/novel_info",
    "target_name": "具体目标名称 (如角色名)",
    "confidence": 0.9
}}"""
        
        ai_response = await self.qwen_client.chat(prompt)
        
        try:
            revision_info = json.loads(ai_response)
            context.revision_target = revision_info.get("revision_target")
            target_name = revision_info.get("target_name")
            
            context.current_step = CreationFlowStep.REVISION_DETAIL_COLLECTION.value
            
            target_display = self._get_target_display_name(context.revision_target)
            if target_name:
                target_display += f" - {target_name}"
            
            return FlowResponse(
                message=f"""好的，您想修改**{target_display}**。

请详细描述您想如何修改？例如：
- 如果要修改世界观，请描述新的设定
- 如果要修改角色，请说明修改哪些方面（外貌、性格、背景等）
- 如果要修改剧情，请说明具体的修改内容""",
                context=context,
                next_step=CreationFlowStep.REVISION_DETAIL_COLLECTION
            )
        except:
            return FlowResponse(
                message="抱歉，我没有理解您的修改意图。请明确说明想修改什么内容？",
                context=context,
                next_step=CreationFlowStep.REVISION_TARGET_SELECTION
            )
    
    async def _handle_revision_detail_collection(self, session_id: str, user_input: str, context: NovelCreationContext) -> FlowResponse:
        """处理修改详情收集"""
        # 使用 AI 提取修改内容
        prompt = f"""从用户输入中提取修改详情：
用户输入：{user_input}
修改目标：{context.revision_target}

返回 JSON 格式的修改内容，字段与目标对象匹配。"""
        
        ai_response = await self.qwen_client.chat(prompt)
        
        try:
            revision_details = json.loads(ai_response)
            context.revision_details = revision_details
            
            context.current_step = CreationFlowStep.REVISION_CONFIRMATION.value
            
            # 生成修改预览
            preview = self._generate_revision_preview(context)
            
            return FlowResponse(
                message=f"""📝 **修改预览**

{preview}

如果您确认以上修改，请回复"确认修改"或"好的，修改"。
如需调整，请告诉我具体要修改的内容。""",
                context=context,
                next_step=CreationFlowStep.REVISION_CONFIRMATION
            )
        except Exception as e:
            return FlowResponse(
                message=f"提取修改内容失败：{str(e)}",
                context=context,
                next_step=CreationFlowStep.REVISION_DETAIL_COLLECTION
            )
    
    async def _handle_revision_confirmation(self, session_id: str, user_input: str, context: NovelCreationContext) -> FlowResponse:
        """处理修改确认"""
        if any(word in user_input for word in ["确认", "好的", "可以", "修改"]):
            # 执行修改
            from backend.services.novel_revision_service import NovelRevisionService
            revision_service = NovelRevisionService(self.db)
            
            if not context.selected_novel_id:
                return FlowResponse(
                    message="❌ 未选择要修改的小说",
                    context=context,
                    next_step=CreationFlowStep.REVISION_CONFIRMATION
                )
            
            try:
                if context.revision_target == "world_setting":
                    result = await revision_service.update_world_setting(
                        context.selected_novel_id,
                        context.revision_details
                    )
                elif context.revision_target == "character":
                    # TODO: 需要从对话中提取 character_id
                    result = {"error": "角色修改功能待完善"}
                elif context.revision_target == "plot":
                    result = await revision_service.update_plot_outline(
                        context.selected_novel_id,
                        context.revision_details
                    )
                else:
                    result = await revision_service.update_novel_info(
                        context.selected_novel_id,
                        context.revision_details
                    )
                
                if result.get("success"):
                    context.revision_confirmed = True
                    context.current_step = CreationFlowStep.COMPLETED.value
                    
                    return FlowResponse(
                        message=f"✅ {result['message']}\n\n修改已生效！您还需要其他修改吗？",
                        context=context,
                        next_step=CreationFlowStep.COMPLETED
                    )
                else:
                    return FlowResponse(
                        message=f"❌ 修改失败：{result.get('error', '未知错误')}",
                        context=context,
                        next_step=CreationFlowStep.REVISION_CONFIRMATION
                    )
            except Exception as e:
                return FlowResponse(
                    message=f"❌ 修改失败：{str(e)}",
                    context=context,
                    next_step=CreationFlowStep.REVISION_CONFIRMATION
                )
        else:
            # 用户想调整修改内容
            return FlowResponse(
                message="好的，请告诉我具体需要调整什么内容？",
                context=context,
                next_step=CreationFlowStep.REVISION_DETAIL_COLLECTION
            )
    
    def _get_target_display_name(self, target: str) -> str:
        """获取目标的显示名称"""
        mapping = {
            "world_setting": "世界观设定",
            "character": "角色",
            "plot": "剧情大纲",
            "novel_info": "小说基本信息"
        }
        return mapping.get(target, target)
    
    def _generate_revision_preview(self, context: NovelCreationContext) -> str:
        """生成修改预览"""
        if not context.revision_details:
            return "暂无修改内容"
        
        preview = f"**修改目标**: {self._get_target_display_name(context.revision_target)}\n\n"
        
        for field, value in context.revision_details.items():
            # 字段名映射
            field_names = {
                "era_background": "时代背景",
                "geographical_environment": "地理环境",
                "social_structure": "社会结构",
                "special_rules": "特殊规则",
                "power_system": "力量体系",
                "main_plot": "主要情节",
                "core_conflict": "核心冲突"
            }
            
            display_field = field_names.get(field, field)
            preview += f"- **{display_field}**: {value}\n"
        
        return preview
