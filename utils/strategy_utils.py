"""Shared follow-up strategy helpers."""

# Strategy Registry - single source of truth
STRATEGY_REGISTRY = [
    {
        "name": "daily_routine",
        "category": "low_risk",
        "selection": "daily_routine：低风险或普通事实扩展时使用，问一天的典型安排、作息规律、工作节奏。侧重时间维度，适合开场破冰或缓和无压力轮次",
        "exec_direction": "一天的典型安排、作息、工作节奏（时间维度）",
        "exec_boundary": "不追问具体工作内容或项目细节",
    },
    {
        "name": "entry_experience",
        "category": "low_risk",
        "selection": "entry_experience：对方提到学习方向、转方向、刚入门时使用，问最初怎么接触、为什么选这个方向、入门阶段做了什么",
        "exec_direction": "怎么接触这个方向、为什么选它、入门阶段做了什么",
        "exec_boundary": "不追问当前工作流程或专业判断",
    },
    {
        "name": "work_style",
        "category": "low_risk",
        "selection": "work_style：对方提到工作、项目、学习内容时使用，问平时用什么工具、跟谁协作、典型的一天怎么推进。侧重工作方式而非时间安排，与 daily_routine 互补",
        "exec_direction": "用什么工具、跟谁协作、典型推进方式（方式维度，非时间维度）",
        "exec_boundary": "不与 daily_routine 混淆——不问作息，问做法",
    },
    {
        "name": "recent_memory",
        "category": "low_risk",
        "selection": "recent_memory：需要更多真实细节但不能深挖专业内容时使用，问最近做过的具体任务、这几天在忙什么、上周有没有遇到什么特别的事。通过近期具体事件验证经验真实性",
        "exec_direction": "最近做过的具体任务、这几天在忙什么、近期具体事件",
        "exec_boundary": "不深挖专业内容，只通过具体事件验证经验真实性",
    },
    {
        "name": "light_clarification",
        "category": "vague_answer",
        "selection": "light_clarification：职业身份粒度过粗、信息模糊或存在轻微不一致时使用，只做温和澄清。适合用户给出了大类职业但缺少具体方向时——例如用户说自己是公务员，就自然问是哪个部门/系统的、偏行政还是业务、大概负责哪块工作；用户说自己是老师，就问是小学/初中/高中/大学、教什么学科、在编还是代课；核心是把职业大类收敛到具体细分方向，为后续深度追问做准备",
        "exec_direction": "对方更偏哪个系统、岗位方向、服务对象或职责类型。把职业大类收敛到细分方向",
        "exec_boundary": "",
        "trigger_keywords": ["职业身份粒度过粗", "职业大类过宽", "岗位性质", "职责方向", "具体职业类型", "具体系统"],
    },
    {
        "name": "experience_probe",
        "category": "broad_probe",
        "selection": "experience_probe：经历型侧面探问。适合对方提到项目、实习、课程实践、自学经历时使用，问过程、卡点、产出、参与方式。例如“这个项目你主要负责哪部分”“中间有没有特别难搞的阶段”",
        "exec_direction": "项目过程、遇到的卡点、具体产出、参与角色和方式",
        "exec_boundary": "不问理论或行业看法，聚焦个人经历",
    },
    {
        "name": "knowledge_probe",
        "category": "broad_probe",
        "selection": "knowledge_probe：知识理解型侧面探问。适合对方提到某个专业方向、行业概念或热门话题时使用，用聊天方式问怎么理解、怎么判断好坏、对新人有什么建议。不限技术方向，也适用于金融、医疗、教育等各行业",
        "exec_direction": "对方怎么理解某概念、怎么判断好坏、对新人有什么建议",
        "exec_boundary": "不限技术方向，适用于各行业。用聊天方式而非考试方式",
    },
    {
        "name": "tool_workflow_probe",
        "category": "broad_probe",
        "selection": "tool_workflow_probe：工具流程习惯侧面探问。适合对方提到学习、写代码、查资料、调模型、做项目时使用，问平时用什么工具、遇到问题去哪里查、哪种方式更管用。侧重日常工具链和解决问题的方法偏好",
        "exec_direction": "平时用什么工具、遇到问题去哪里查、哪种方式更管用。侧重日常工具链和解决问题的方法偏好",
        "exec_boundary": "不要问成技术面试",
    },
    {
        "name": "scenario_judgment_probe",
        "category": "broad_probe",
        "selection": "scenario_judgment_probe：场景判断型侧面探问。适合需要观察真实经验和专业思维时使用，给一个轻量的假设场景，让对方说一般会怎么处理、会优先考虑什么。侧重判断逻辑而非操作步骤",
        "exec_direction": "给一个轻量假设场景，问对方一般会怎么处理、优先考虑什么",
        "exec_boundary": "侧重判断逻辑而非操作步骤。场景要轻量，不要设计成考题",
    },
    {
        "name": "process_sequence",
        "category": "experience_chain",
        "selection": "process_sequence：经验链追问。问真实处理流程、先后顺序、判断节点",
        "exec_direction": "真实处理流程、先后顺序、关键判断节点",
        "exec_boundary": "追问自然融入对话，不写成面试题",
    },
    {
        "name": "boundary_judgment",
        "category": "experience_chain",
        "selection": "boundary_judgment：经验链追问。问边界判断、什么时候继续/暂停/转介/升级",
        "exec_direction": "边界判断——什么情况下继续、暂停、转介或升级",
        "exec_boundary": "追问自然融入对话，不写成面试题",
    },
    {
        "name": "real_constraint",
        "category": "experience_chain",
        "selection": "real_constraint：经验链追问。问真实限制，如记录、时间、流程、协作、规范",
        "exec_direction": "真实限制——记录要求、时间压力、流程规范、协作约束",
        "exec_boundary": "追问自然融入对话，不写成面试题",
    },
    {
        "name": "counterexample",
        "category": "experience_chain",
        "selection": "counterexample：经验链追问。问反例、卡点、常规方法不管用时怎么办",
        "exec_direction": "反例、卡点、常规方法不管用时的处理方式",
        "exec_boundary": "追问自然融入对话，不写成面试题",
    },
    {
        "name": "term_clarification",
        "category": "experience_chain",
        "selection": "term_clarification：经验链追问。追问用户自己说过的关键词在实际场景里具体指什么",
        "exec_direction": "追问用户自己说过的关键词在实际场景里具体指什么",
        "exec_boundary": "追问自然融入对话，不写成面试题",
    },
    {
        "name": "output_evidence",
        "category": "experience_chain",
        "selection": "output_evidence：经验链追问。问产出、留痕、结果、复盘或如何判断有效",
        "exec_direction": "产出、留痕、结果、复盘方式或如何判断有效",
        "exec_boundary": "追问自然融入对话，不写成面试题",
    },
]

ALLOWED_FOLLOWUP_STRATEGIES = {s["name"] for s in STRATEGY_REGISTRY}

ALLOWED_PROBE_ANGLES = {
    "process_sequence", "boundary_judgment", "real_constraint",
    "counterexample", "term_clarification", "output_evidence",
}

PROBE_ANGLE_ORDER = [
    "process_sequence", "boundary_judgment", "real_constraint",
    "counterexample", "term_clarification", "output_evidence",
]

PROBE_ANGLE_HINTS = {
    "process_sequence": "换到过程顺序角度，问对方一般怎么判断先做什么、后做什么",
    "boundary_judgment": "换到边界判断角度，问哪些情况需要收住、转介、升级或避免继续推进",
    "real_constraint": "换到真实限制角度，问记录、时间、流程、协作、规范或现实约束",
    "counterexample": "换到反例和卡点角度，问遇到常规方法不管用时通常怎么处理",
    "term_clarification": "换到术语澄清角度，问对方自己说的关键词在实际场景里具体指什么",
    "output_evidence": "换到产出证据角度，问工作结束后通常留下什么记录、结果或复盘",
}

CATEGORY_LABELS = {
    "low_risk": "低风险通用场景",
    "vague_answer": "泛泛回答专用",
    "broad_probe": "宽泛探索策略",
    "experience_chain": "经验链追问",
}

CATEGORY_ORDER = ["low_risk", "vague_answer", "broad_probe", "experience_chain"]


def format_strategy_choices():
    """Generate strategy selection text for Routing/Supervisor prompts."""
    lines = []
    for cat in CATEGORY_ORDER:
        lines.append("")
        lines.append("-- " + CATEGORY_LABELS[cat] + " --")
        for s in STRATEGY_REGISTRY:
            if s["category"] == cat:
                lines.append("- " + s["selection"] + "；")
    return "\n".join(lines).strip()


def format_strategy_enum():
    """Generate strategy enum string for output format requirements."""
    return "|".join(s["name"] for s in STRATEGY_REGISTRY)


def format_strategy_exec_guide():
    """Generate strategy execution guide for Follow-up Generator."""
    lines = [
        "【策略执行指引】",
        "当前追问策略方向为：{followup_strategy}",
        "",
        "以下定义了每个策略的话题方向与边界。实际追问句子仍需通过上方「核心生成公式」和「对话包装方式」来自然表达——不要直接照搬下面的方向描述。",
    ]
    for cat in CATEGORY_ORDER:
        lines.append("")
        lines.append("-- " + CATEGORY_LABELS[cat] + " --")
        for s in STRATEGY_REGISTRY:
            if s["category"] == cat:
                lines.append(s["name"] + "：")
                lines.append("  话题方向：" + s["exec_direction"])
                if s["exec_boundary"]:
                    lines.append("  边界：" + s["exec_boundary"])
    return "\n".join(lines)



def get_strategy_field(name: str, field: str) -> str:
    """从 STRATEGY_REGISTRY 提取单个策略的单个字段值。
    用于模板中需要自然嵌入策略描述的场景，避免硬编码重复。"""
    for s in STRATEGY_REGISTRY:
        if s['name'] == name:
            return s[field]
    return ''


def get_experience_chain_strategies_pipe() -> str:
    """返回 experience_chain 类别策略名的管道分隔列表，用于 JSON 示例。"""
    names = [s['name'] for s in STRATEGY_REGISTRY if s['category'] == 'experience_chain']
    return '|'.join(names)

def normalize_followup_strategy(strategy, has_risk=False):
    """Return a valid follow-up strategy with a conservative fallback."""
    if strategy in ALLOWED_FOLLOWUP_STRATEGIES:
        return strategy
    return "light_clarification" if has_risk else "daily_routine"


def normalize_probe_angle(angle, used_angles=None):
    """Return a valid probe angle, rotating away from angles already used."""
    normalized = str(angle or "").strip()
    if normalized not in ALLOWED_PROBE_ANGLES:
        normalized = PROBE_ANGLE_ORDER[0]
    used = [item for item in (used_angles or []) if item in ALLOWED_PROBE_ANGLES]
    if normalized in used and len(set(used)) < len(ALLOWED_PROBE_ANGLES):
        for candidate in PROBE_ANGLE_ORDER:
            if candidate not in used:
                return candidate
    return normalized


def probe_angle_hint(angle):
    """Human-readable generation hint for a probe angle."""
    return PROBE_ANGLE_HINTS.get(str(angle or "").strip(), "换一个新的经验细节角度追问")
