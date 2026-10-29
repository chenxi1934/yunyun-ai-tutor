from typing import Literal

from pydantic import Field, model_validator

from app.domain import StrictModel

Stage = Literal['初中', '大学']
FactType = Literal['not_submitted', 'infinite_loop', 'boundary_error']


class Fact(StrictModel):
    id: str
    type: FactType
    count: int = Field(ge=0, le=1000)
    denominator: int | None = Field(default=None, ge=1, le=1000)
    source_ref: str
    observation: str
    status: Literal['observed'] = 'observed'


class ClassProfile(StrictModel):
    schema_version: Literal[1] = 1
    id: str
    revision: int = Field(ge=1)
    stage: Stage
    grade: str
    topic: Literal['循环结构'] = '循环结构'
    class_size: int | None = Field(default=None, ge=1, le=1000)
    prior_knowledge: list[str]
    source_hash: str
    source_format: Literal['text', 'json', 'csv']
    facts: list[Fact] = Field(min_length=1, max_length=3)
    unknowns: list[str]
    created_at: str


class Strategy(StrictModel):
    id: str
    rule_id: str
    evidence_ids: list[str]
    action: str
    target: str


class Item(StrictModel):
    id: str = Field(pattern=r'^[a-z][a-z0-9_-]{0,39}$')
    title: str = Field(min_length=1, max_length=150)


class Goal(Item):
    criterion: str = Field(min_length=1, max_length=500)


class Segment(Item):
    minutes: int = Field(ge=1, le=45)
    activity: str = Field(min_length=1, max_length=1200)
    strategy_ids: list[str] = Field(min_length=1)


class CodeItem(Item):
    task_id: str
    knowledge_points: list[str] = Field(min_length=1, max_length=10)
    explanation: str = Field(min_length=1, max_length=1200)
    code: str = Field(min_length=1, max_length=8000)


class ScoringPoint(StrictModel):
    criterion: str = Field(min_length=1, max_length=500)
    points: int = Field(ge=1, le=100)


class Exercise(CodeItem):
    level: Literal['基础', '进阶', '挑战']
    prompt: str = Field(min_length=1, max_length=1200)
    scaffolding: str = Field(max_length=1000)
    scoring: list[ScoringPoint] = Field(min_length=2, max_length=8)

    @model_validator(mode='after')
    def scoring_total(self):
        if sum(s.points for s in self.scoring) != 100:
            raise ValueError('每题评分点必须合计100分')
        return self


class Misconception(Item):
    misconception_type: FactType
    evidence_ids: list[str]
    basis: Literal['observed', 'predicted']
    trigger: str = Field(min_length=1, max_length=500)
    cause: str = Field(min_length=1, max_length=500)
    cause_status: Literal['hypothesis'] = 'hypothesis'
    teaching_intervention: str = Field(min_length=1, max_length=800)
    exercise_ids: list[str] = Field(min_length=1)
    stage: Stage


class LessonPlan(StrictModel):
    stage: Stage
    topic: Literal['循环结构'] = '循环结构'
    duration_minutes: Literal[45] = 45
    prerequisites: list[str] = Field(min_length=1, max_length=12)
    goals: list[Goal] = Field(min_length=2, max_length=5)
    segments: list[Segment] = Field(min_length=3, max_length=10)
    examples: list[CodeItem] = Field(min_length=2, max_length=3)
    exercises: list[Exercise] = Field(min_length=3, max_length=3)
    misconceptions: list[Misconception] = Field(min_length=1, max_length=5)

    @model_validator(mode='after')
    def integrity(self):
        if sum(s.minutes for s in self.segments) != 45:
            raise ValueError('教学环节总时间必须为45分钟')
        if {e.level for e in self.exercises} != {'基础', '进阶', '挑战'}:
            raise ValueError('必须包含基础/进阶/挑战各一题')
        items = self.items()
        if len({i.id for i in items}) != len(items):
            raise ValueError('所有教学项目ID必须全局唯一')
        exercise_ids = {e.id for e in self.exercises}
        for m in self.misconceptions:
            if m.stage != self.stage or not set(m.exercise_ids) <= exercise_ids:
                raise ValueError('错因学段或练习引用错误')
        return self

    def items(self):
        return [*self.goals, *self.segments, *self.examples, *self.exercises, *self.misconceptions]


class EducationContext(StrictModel):
    pass


class ProposeLesson(StrictModel):
    profile_id: str
    profile_revision: int = Field(ge=1)
    # 工具schema保持精简；服务层仍用LessonPlan严格验证完整结构。
    plan: dict
    base_revision: int = Field(ge=0)


class ReadLesson(StrictModel):
    lesson_id: str


class ImportProfile(StrictModel):
    format: Literal['text', 'json', 'csv']
    content: str = Field(min_length=1, max_length=1048576)
    expected_revision: int = Field(ge=0)


class ReviseItem(StrictModel):
    expected_revision: int = Field(ge=1)
    item_id: str
    replacement: dict
    reason: str = Field(min_length=1, max_length=500)


class ReviewItem(StrictModel):
    expected_revision: int = Field(ge=1)
    item_id: str
    decision: Literal['accept', 'reject']
    note: str = Field(min_length=1, max_length=1000)


class ReviseLessonItem(ReviseItem):
    lesson_id: str


class VerifyLesson(ReadLesson):
    expected_revision: int = Field(ge=1)


class LessonRevision(StrictModel):
    expected_revision: int = Field(ge=1)
