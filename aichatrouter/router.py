"""
智能模型路由引擎 - 根据任务类型自动选择最优 AI 模型。

核心组件:
    - TaskClassifier: 任务分类器（基于关键词 + 启发式规则）
    - ModelRouter: 模型路由器（根据任务类型、成本、偏好选择模型）
    - CostOptimizer: 成本优化器（在保证质量的前提下最小化成本）

支持的任务类型:
    - coding: 编程/代码相关
    - creative: 创意写作
    - analysis: 分析/推理
    - qa: 问答/知识查询
    - translation: 翻译
    - math: 数学计算
    - summarization: 摘要/总结

路由策略:
    1. 分类用户输入的任务类型
    2. 根据路由规则选择首选模型
    3. 检查模型可用性和预算
    4. 如不可用则沿回退链选择替代模型
    5. 可选：应用成本优化策略
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from aichatrouter.config import ChatRouterConfig


# =============================================================================
# 任务类型定义
# =============================================================================

TASK_TYPES = [
    "coding",
    "creative",
    "analysis",
    "qa",
    "translation",
    "math",
    "summarization",
]

# 任务类型中文描述
TASK_TYPE_LABELS: Dict[str, str] = {
    "coding": "编程",
    "creative": "创意写作",
    "analysis": "分析推理",
    "qa": "问答",
    "translation": "翻译",
    "math": "数学",
    "summarization": "摘要总结",
}


# =============================================================================
# 任务分类器
# =============================================================================

class TaskClassifier:
    """基于关键词 + 启发式规则的任务分类器。

    分析用户输入文本，判断其任务类型。
    使用多级匹配策略：精确模式匹配 > 关键词权重 > 默认类型。

    不依赖任何 ML 模型，纯规则驱动。

    Attributes:
        default_task: 默认任务类型（当无法判断时使用）。

    Examples:
        >>> classifier = TaskClassifier()
        >>> result = classifier.classify("写一个 Python 快速排序")
        >>> result.task_type
        'coding'
        >>> result.confidence
        0.9
    """

    def __init__(self, default_task: str = "qa") -> None:
        """初始化任务分类器。

        Args:
            default_task: 默认任务类型。
        """
        self.default_task = default_task
        self._patterns = self._build_patterns()

    def _build_patterns(self) -> Dict[str, List[Dict[str, Any]]]:
        """构建任务分类模式。

        Returns:
            任务类型到模式列表的映射。
            每个模式包含:
                - pattern: 正则表达式
                - weight: 匹配权重 (0-1)
                - keywords: 关键词列表
        """
        return {
            "coding": [
                {
                    "pattern": r"(写|实现|开发|编写|创建|构建)\s*(一个|一段|一个)?\s*(Python|Java|JavaScript|C\+\+|Go|Rust|TypeScript|Ruby|PHP|Swift|Kotlin|SQL|HTML|CSS|Shell|Bash|函数|程序|脚本|代码|类|接口|模块|组件|服务|API|应用|网站|网页|工具|算法)",
                    "weight": 0.95,
                    "keywords": [],
                },
                {
                    "pattern": r"(code|program|function|class|method|algorithm|bug|debug|compile|run|execute|import|export|variable|loop|condition|recursive|async|thread|database|API|REST|HTTP|JSON|XML|HTML|CSS|SQL|git|docker|kubernetes|deploy|test|unit.test|integration)",
                    "weight": 0.85,
                    "keywords": [],
                },
                {
                    "pattern": r"(代码|函数|方法|类|接口|模块|组件|变量|循环|条件|递归|异步|线程|数据库|调试|编译|运行|部署|测试|算法|数据结构|排序|查找|遍历|正则|解析|序列化|反序列化|框架|库|包|依赖|配置|环境|构建|打包|发布)",
                    "weight": 0.9,
                    "keywords": [],
                },
                {
                    "pattern": r"(how\s+to|怎么|如何)\s*(implement|write|code|build|create|make|fix|solve|debug|optimize|refactor|deploy|install|setup|configure)\s*",
                    "weight": 0.75,
                    "keywords": [],
                },
                {
                    "keywords": ["def ", "class ", "import ", "return ", "print(", "console.log", "func ", "pub fn", "fn ", "public ", "private ", "async ", "await "],
                    "weight": 0.95,
                    "pattern": None,
                },
            ],
            "creative": [
                {
                    "pattern": r"(写|创作|编|构思|想象|设计|虚构)\s*(一首|一篇|一个|一段|一部|一个故事|一首诗|一篇小说|一个剧本|一篇文章|一段文案|一个广告|一个标题|一个口号|一个品牌|一个角色|一个场景|一个对话|一个歌词|一段歌词)",
                    "weight": 0.95,
                    "keywords": [],
                },
                {
                    "pattern": r"(write|create|compose|draft|craft|design|imagine|invent|story|poem|novel|song|lyrics|script|plot|character|dialogue|creative|fiction|fantasy|sci-fi|romance|thriller|comedy|drama)",
                    "weight": 0.85,
                    "keywords": [],
                },
                {
                    "pattern": r"(故事|小说|诗歌|散文|剧本|歌词|文案|广告|品牌|角色|场景|对话|情节|开头|结尾|标题|口号|标语|营销|创意|灵感|想象|虚构|科幻|奇幻|悬疑|爱情|喜剧|悲剧|童话|寓言)",
                    "weight": 0.9,
                    "keywords": [],
                },
                {
                    "keywords": ["请帮我写", "帮我创作", "请编一个", "写一首", "写一篇", "构思一个", "设计一个"],
                    "weight": 0.8,
                    "pattern": None,
                },
            ],
            "analysis": [
                {
                    "pattern": r"(分析|评估|比较|对比|研究|调查|探讨|论述|论证|批判|评价|判断|权衡|利弊|优缺点|可行性|影响|原因|结果|趋势|预测|推断|归纳|演绎|逻辑|因果|关联|因素)",
                    "weight": 0.9,
                    "keywords": [],
                },
                {
                    "pattern": r"(analyze|evaluate|compare|assess|investigate|examine|discuss|argue|critique|review|study|research|explore|pros\s+and\s+cons|trade-off|impact|cause|effect|trend|predict|infer|deduce|correlation|factor|SWOT|PEST|ROI|KPI)",
                    "weight": 0.85,
                    "keywords": [],
                },
                {
                    "pattern": r"(为什么|why|what\s+if|假设|如果.*会怎样|原因是什么|根本原因|深层原因|本质|核心|关键|主要|次要|直接|间接)",
                    "weight": 0.8,
                    "keywords": [],
                },
                {
                    "keywords": ["分析一下", "帮我分析", "请分析", "对比一下", "比较一下", "评估一下", "研究一下"],
                    "weight": 0.85,
                    "pattern": None,
                },
            ],
            "qa": [
                {
                    "pattern": r"(是什么|什么是|谁是|哪里|什么时候|怎么|如何|为什么|能不能|可不可以|有没有|是否|请问|想知道|了解|解释|说明|介绍|描述|定义|概念|含义|意思)",
                    "weight": 0.7,
                    "keywords": [],
                },
                {
                    "pattern": r"(what\s+is|who\s+is|where|when|how|why|can\s+you|could\s+you|please\s+explain|tell\s+me|define|describe|meaning|concept|introduction)",
                    "weight": 0.7,
                    "keywords": [],
                },
                {
                    "pattern": r"^(你好|hello|hi|hey|嗨|您好|早上好|下午好|晚上好|谢谢|感谢|再见|拜拜)",
                    "weight": 0.6,
                    "keywords": [],
                },
            ],
            "translation": [
                {
                    "pattern": r"(翻译|translate|把.*翻译|将.*翻译|translate.*to|翻译成|译为|译成|中译英|英译中|日译中|中译日|韩译中|中译韩|法译中|中译法|德译中|中译德)",
                    "weight": 0.95,
                    "keywords": [],
                },
                {
                    "pattern": r"(English|Chinese|Japanese|Korean|French|German|Spanish|Russian|Arabic|Portuguese|Italian|Hindi|Thai|Vietnamese|Indonesian)\s*(to|into|翻译|译)",
                    "weight": 0.9,
                    "keywords": [],
                },
                {
                    "keywords": ["翻译", "translate", "译成", "翻成", "翻译成"],
                    "weight": 0.9,
                    "pattern": None,
                },
            ],
            "math": [
                {
                    "pattern": r"(计算|算|求解|方程|公式|推导|证明|积分|微分|极限|矩阵|向量|概率|统计|回归|拟合|优化|线性|非线性|函数|导数|极值|最值|方差|标准差|均值|中位数|众数|排列|组合|阶乘|对数|指数|三角|几何|代数|微积分|数论|图论)",
                    "weight": 0.95,
                    "keywords": [],
                },
                {
                    "pattern": r"(calculate|compute|solve|equation|formula|derive|prove|integral|derivative|limit|matrix|vector|probability|statistics|regression|optimize|linear|nonlinear|function|gradient|variance|standard.deviation|mean|median|mode|permutation|combination|logarithm|exponential|trigonometry|geometry|algebra|calculus|number.theory|graph.theory)",
                    "weight": 0.9,
                    "keywords": [],
                },
                {
                    "pattern": r"[\d\+\-\*\/\^\(\)\[\]\{\}\=\<\>]+",
                    "weight": 0.6,
                    "keywords": [],
                },
                {
                    "keywords": ["计算", "求解", "算一下", "等于多少", "结果是", "多少"],
                    "weight": 0.85,
                    "pattern": None,
                },
            ],
            "summarization": [
                {
                    "pattern": r"(总结|摘要|概括|归纳|提炼|浓缩|简述|概述|综述|摘要|要点|核心内容|主要观点|key\s+points|summary|summarize|tldr|tl;dr|brief|outline|recap|digest|abstract)",
                    "weight": 0.95,
                    "keywords": [],
                },
                {
                    "pattern": r"(用.*句话|用.*概括|简单说|简要|简短|精简|压缩|缩写|缩略)",
                    "weight": 0.85,
                    "keywords": [],
                },
                {
                    "keywords": ["总结一下", "帮我总结", "请总结", "概括一下", "摘要一下", "归纳一下", "提炼一下"],
                    "weight": 0.9,
                    "pattern": None,
                },
            ],
        }

    def classify(self, text: str) -> "ClassificationResult":
        """分类用户输入文本。

        Args:
            text: 用户输入文本。

        Returns:
            ClassificationResult 包含任务类型和置信度。
        """
        if not text or not text.strip():
            return ClassificationResult(self.default_task, 0.0)

        text_lower = text.lower().strip()
        scores: Dict[str, float] = {}

        for task_type, patterns in self._patterns.items():
            total_score = 0.0
            matched_count = 0

            for pattern_config in patterns:
                # 关键词匹配
                if pattern_config.get("keywords"):
                    for keyword in pattern_config["keywords"]:
                        if keyword.lower() in text_lower:
                            total_score += pattern_config["weight"]
                            matched_count += 1

                # 正则模式匹配
                pattern = pattern_config.get("pattern")
                if pattern:
                    try:
                        if re.search(pattern, text_lower, re.IGNORECASE | re.DOTALL):
                            total_score += pattern_config["weight"]
                            matched_count += 1
                    except re.error:
                        pass

            if matched_count > 0:
                # 归一化分数，但保留匹配数量加成
                scores[task_type] = min(total_score / (matched_count * 0.5), 1.0)

        if not scores:
            return ClassificationResult(self.default_task, 0.3)

        # 找到最高分
        best_task = max(scores, key=scores.get)  # type: ignore
        best_score = scores[best_task]

        return ClassificationResult(best_task, best_score, scores)


class ClassificationResult:
    """任务分类结果。

    Attributes:
        task_type: 分类得到的任务类型。
        confidence: 置信度 (0-1)。
        all_scores: 所有任务类型的分数。
    """

    def __init__(
        self,
        task_type: str,
        confidence: float,
        all_scores: Optional[Dict[str, float]] = None,
    ) -> None:
        """初始化分类结果。

        Args:
            task_type: 任务类型。
            confidence: 置信度。
            all_scores: 所有任务类型的分数。
        """
        self.task_type = task_type
        self.confidence = confidence
        self.all_scores = all_scores or {}

    @property
    def label(self) -> str:
        """获取任务类型的中文标签。"""
        return TASK_TYPE_LABELS.get(self.task_type, self.task_type)

    def __repr__(self) -> str:
        return f"ClassificationResult(task_type={self.task_type!r}, confidence={self.confidence:.2f})"


# =============================================================================
# 模型路由器
# =============================================================================

class ModelRouter:
    """智能模型路由器。

    根据任务分类结果、模型可用性、用户偏好和成本预算，
    选择最优的 AI 模型来处理用户请求。

    路由流程:
        1. 获取任务分类结果
        2. 查找对应路由规则
        3. 按优先级尝试首选模型列表
        4. 检查模型可用性（API 密钥、启用状态）
        5. 检查预算限制
        6. 首选不可用时尝试回退模型
        7. 所有模型不可用时使用默认模型

    Attributes:
        config: 配置管理器。
        classifier: 任务分类器。
        cost_optimizer: 成本优化器。
        user_preferences: 用户偏好设置。

    Examples:
        >>> router = ModelRouter(config)
        >>> result = router.route("写一个 Python 快速排序")
        >>> result.provider
        'anthropic'
        >>> result.model
        'claude-sonnet-4-20250514'
    """

    def __init__(
        self,
        config: ChatRouterConfig,
        classifier: Optional[TaskClassifier] = None,
        cost_optimizer: Optional["CostOptimizer"] = None,
    ) -> None:
        """初始化模型路由器。

        Args:
            config: 配置管理器。
            classifier: 任务分类器（可选，默认创建新实例）。
            cost_optimizer: 成本优化器（可选，默认创建新实例）。
        """
        self.config = config
        self.classifier = classifier or TaskClassifier(
            default_task=config.get_default_task()
        )
        self.cost_optimizer = cost_optimizer or CostOptimizer(config)
        self.user_preferences: Dict[str, str] = {}

    def route(self, user_input: str) -> "RoutingResult":
        """路由用户输入到最优模型。

        Args:
            user_input: 用户输入文本。

        Returns:
            RoutingResult 包含供应商、模型和路由信息。
        """
        # 1. 分类任务
        classification = self.classifier.classify(user_input)

        # 2. 检查用户是否有指定偏好
        preferred_model = self.user_preferences.get("model")
        preferred_provider = self.user_preferences.get("provider")

        if preferred_model and preferred_provider:
            # 验证偏好模型是否可用
            model_config = self.config.get_model(preferred_provider, preferred_model)
            if model_config and model_config.get("enabled", True):
                return RoutingResult(
                    provider=preferred_provider,
                    model=preferred_model,
                    task_type=classification.task_type,
                    confidence=classification.confidence,
                    reason="user_preference",
                    fallback_chain=[],
                )

        # 3. 如果禁用自动路由，使用默认模型
        if not self.config.auto_route:
            return RoutingResult(
                provider=self.config.default_provider,
                model=self.config.default_model,
                task_type=classification.task_type,
                confidence=classification.confidence,
                reason="default",
                fallback_chain=[],
            )

        # 4. 获取路由规则
        rule = self.config.get_routing_rule(classification.task_type)
        if not rule:
            return RoutingResult(
                provider=self.config.default_provider,
                model=self.config.default_model,
                task_type=classification.task_type,
                confidence=classification.confidence,
                reason="no_rule",
                fallback_chain=[],
            )

        # 5. 尝试首选模型
        primary_models = rule.get("primary", [])
        selected = self._select_available_model(primary_models)

        if selected:
            # 应用成本优化
            optimized = self.cost_optimizer.optimize(
                selected[0], selected[1], classification.task_type
            )
            if optimized:
                selected = optimized

            return RoutingResult(
                provider=selected[0],
                model=selected[1],
                task_type=classification.task_type,
                confidence=classification.confidence,
                reason="auto_route",
                fallback_chain=self._build_fallback_chain(primary_models, rule.get("fallback", [])),
            )

        # 6. 尝试回退模型
        fallback_models = rule.get("fallback", [])
        selected = self._select_available_model(fallback_models)

        if selected:
            return RoutingResult(
                provider=selected[0],
                model=selected[1],
                task_type=classification.task_type,
                confidence=classification.confidence,
                reason="fallback",
                fallback_chain=self._build_fallback_chain(fallback_models, []),
            )

        # 7. 最终回退到默认模型
        return RoutingResult(
            provider=self.config.default_provider,
            model=self.config.default_model,
            task_type=classification.task_type,
            confidence=classification.confidence,
            reason="default_fallback",
            fallback_chain=[],
        )

    def _select_available_model(
        self, model_list: List[str]
    ) -> Optional[Tuple[str, str]]:
        """从模型列表中选择第一个可用的模型。

        Args:
            model_list: 格式为 ["provider/model", ...] 的模型列表。

        Returns:
            (provider, model) 元组，无可用模型则返回 None。
        """
        for model_ref in model_list:
            if "/" not in model_ref:
                continue
            provider, model = model_ref.split("/", 1)

            # 检查供应商是否启用且有 API 密钥
            provider_config = self.config.get_provider(provider)
            if not provider_config:
                continue
            if not provider_config.get("enabled", True):
                continue
            if provider != "ollama" and not provider_config.get("api_key", ""):
                continue

            # 检查模型是否启用
            model_config = self.config.get_model(provider, model)
            if not model_config:
                continue
            if not model_config.get("enabled", True):
                continue

            return (provider, model)

        return None

    def _build_fallback_chain(
        self, primary: List[str], fallback: List[str]
    ) -> List[Tuple[str, str]]:
        """构建完整的回退链。

        Args:
            primary: 首选模型列表。
            fallback: 回退模型列表。

        Returns:
            可用模型回退链。
        """
        chain: List[Tuple[str, str]] = []
        for model_ref in primary + fallback:
            if "/" not in model_ref:
                continue
            provider, model = model_ref.split("/", 1)
            provider_config = self.config.get_provider(provider)
            if not provider_config or not provider_config.get("enabled", True):
                continue
            if provider != "ollama" and not provider_config.get("api_key", ""):
                continue
            model_config = self.config.get_model(provider, model)
            if model_config and model_config.get("enabled", True):
                chain.append((provider, model))
        return chain

    def set_preference(self, key: str, value: str) -> None:
        """设置用户偏好。

        Args:
            key: 偏好键（model/provider）。
            value: 偏好值。
        """
        self.user_preferences[key] = value

    def clear_preference(self, key: Optional[str] = None) -> None:
        """清除用户偏好。

        Args:
            key: 偏好键，None 则清除所有。
        """
        if key:
            self.user_preferences.pop(key, None)
        else:
            self.user_preferences.clear()


class RoutingResult:
    """模型路由结果。

    Attributes:
        provider: 选中的供应商名称。
        model: 选中的模型名称。
        task_type: 任务类型。
        confidence: 分类置信度。
        reason: 选择原因。
        fallback_chain: 回退模型链。
    """

    def __init__(
        self,
        provider: str,
        model: str,
        task_type: str,
        confidence: float,
        reason: str,
        fallback_chain: List[Tuple[str, str]],
    ) -> None:
        """初始化路由结果。

        Args:
            provider: 供应商名称。
            model: 模型名称。
            task_type: 任务类型。
            confidence: 分类置信度。
            reason: 选择原因。
            fallback_chain: 回退模型链。
        """
        self.provider = provider
        self.model = model
        self.task_type = task_type
        self.confidence = confidence
        self.reason = reason
        self.fallback_chain = fallback_chain

    @property
    def model_ref(self) -> str:
        """获取模型引用字符串（provider/model 格式）。"""
        return f"{self.provider}/{self.model}"

    @property
    def task_label(self) -> str:
        """获取任务类型中文标签。"""
        return TASK_TYPE_LABELS.get(self.task_type, self.task_type)

    @property
    def reason_label(self) -> str:
        """获取选择原因的中文描述。"""
        reason_map = {
            "user_preference": "用户偏好",
            "default": "默认模型",
            "auto_route": "智能路由",
            "fallback": "回退选择",
            "no_rule": "无路由规则",
            "default_fallback": "默认回退",
            "cost_optimized": "成本优化",
        }
        return reason_map.get(self.reason, self.reason)

    def __repr__(self) -> str:
        return (
            f"RoutingResult(provider={self.provider!r}, model={self.model!r}, "
            f"task={self.task_type!r}, reason={self.reason!r})"
        )


# =============================================================================
# 成本优化器
# =============================================================================

class CostOptimizer:
    """成本优化器。

    在保证质量的前提下，选择成本更低的模型替代方案。
    当首选模型成本过高时，建议使用同等能力但更便宜的替代模型。

    优化策略:
        1. 对于偏好低成本的任务类型（如 QA、翻译），优先选择低成本模型
        2. 检查预算限制，超出预算时建议降级
        3. 比较同能力模型的价格，选择最优

    Attributes:
        config: 配置管理器。
    """

    def __init__(self, config: ChatRouterConfig) -> None:
        """初始化成本优化器。

        Args:
            config: 配置管理器。
        """
        self.config = config

    def optimize(
        self,
        provider: str,
        model: str,
        task_type: str,
    ) -> Optional[Tuple[str, str]]:
        """优化模型选择以降低成本。

        如果当前选择不是最优的，返回更便宜的替代方案。

        Args:
            provider: 当前选择的供应商。
            model: 当前选择的模型。
            task_type: 任务类型。

        Returns:
            优化后的 (provider, model)，无需优化则返回 None。
        """
        # 获取路由规则
        rule = self.config.get_routing_rule(task_type)
        if not rule:
            return None

        # 如果规则不偏好低成本，不优化
        if not rule.get("prefer_low_cost", False):
            return None

        # 获取当前模型成本
        current_model_config = self.config.get_model(provider, model)
        if not current_model_config:
            return None

        current_cost = (
            current_model_config.get("input_cost_per_1k", 0)
            + current_model_config.get("output_cost_per_1k", 0)
        )

        # 获取所有可用模型
        all_models = self.config.get_all_enabled_models()

        # 寻找更便宜的替代方案
        best_alternative: Optional[Tuple[str, str]] = None
        best_cost = current_cost

        for p, m, m_config in all_models:
            # 检查模型是否支持当前任务类型
            capabilities = m_config.get("capabilities", [])
            if task_type not in capabilities:
                continue

            alt_cost = (
                m_config.get("input_cost_per_1k", 0)
                + m_config.get("output_cost_per_1k", 0)
            )

            if alt_cost < best_cost:
                best_cost = alt_cost
                best_alternative = (p, m)

        if best_alternative and best_cost < current_cost:
            return best_alternative

        return None

    def estimate_request_cost(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """估算请求成本。

        Args:
            provider: 供应商名称。
            model: 模型名称。
            input_tokens: 输入 Token 数。
            output_tokens: 输出 Token 数。

        Returns:
            估算成本（美元）。
        """
        model_config = self.config.get_model(provider, model)
        if not model_config:
            return 0.0

        input_cost = model_config.get("input_cost_per_1k", 0)
        output_cost = model_config.get("output_cost_per_1k", 0)

        return (input_tokens / 1000.0) * input_cost + (output_tokens / 1000.0) * output_cost

    def find_cheapest_model(
        self,
        task_type: str,
        min_capability: bool = True,
    ) -> Optional[Tuple[str, str]]:
        """查找支持指定任务类型的最便宜模型。

        Args:
            task_type: 任务类型。
            min_capability: 是否要求模型具备该任务能力。

        Returns:
            (provider, model) 元组。
        """
        all_models = self.config.get_all_enabled_models()
        cheapest: Optional[Tuple[str, str]] = None
        cheapest_cost = float("inf")

        for p, m, m_config in all_models:
            if min_capability:
                capabilities = m_config.get("capabilities", [])
                if task_type not in capabilities:
                    continue

            total_cost = (
                m_config.get("input_cost_per_1k", 0)
                + m_config.get("output_cost_per_1k", 0)
            )

            if total_cost < cheapest_cost:
                cheapest_cost = total_cost
                cheapest = (p, m)

        return cheapest

    def compare_models(
        self,
        models: List[Tuple[str, str]],
        input_tokens: int = 1000,
        output_tokens: int = 1000,
    ) -> List[Dict[str, Any]]:
        """比较多个模型的成本。

        Args:
            models: 模型列表 [(provider, model), ...]。
            input_tokens: 估算输入 Token 数。
            output_tokens: 估算输出 Token 数。

        Returns:
            成本比较结果列表，按成本升序排列。
        """
        results = []
        for provider, model in models:
            cost = self.estimate_request_cost(provider, model, input_tokens, output_tokens)
            model_config = self.config.get_model(provider, model)
            results.append({
                "provider": provider,
                "model": model,
                "estimated_cost": cost,
                "input_cost_per_1k": model_config.get("input_cost_per_1k", 0) if model_config else 0,
                "output_cost_per_1k": model_config.get("output_cost_per_1k", 0) if model_config else 0,
            })

        results.sort(key=lambda x: x["estimated_cost"])
        return results
