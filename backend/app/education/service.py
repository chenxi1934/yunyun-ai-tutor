import asyncio
import hashlib
import json

from pydantic import ValidationError

from app.domain import AppError, dumps, now, sha, uid
from app.education.catalog import cases, contract
from app.education.models import ClassProfile, LessonPlan
from app.education.profiles import parse_profile
from app.education.rules import curriculum_risks, strategies, suggested_plan, validate_grounding


class EducationService:
    def __init__(self, store, verification):
        self.store, self.verification = store, verification

    def profiles(self, sid):
        return self.store.find('class_profiles', sid)

    def profile(self, sid, profile_id=None, revision=None):
        matches = [r['profile'] for r in self.profiles(sid)
                   if (profile_id is None or r['profile']['id'] == profile_id)
                   and (revision is None or r['profile']['revision'] == revision)]
        if not matches:
            raise AppError('PROFILE_REQUIRED', '请先导入当前会话的汇总班情。', 409)
        return ClassProfile.model_validate(matches[-1])

    def import_profile(self, session, content, format, *, source: bytes | None = None):
        previous = self.profiles(session['id'])
        last = previous[-1]['profile'] if previous else None
        context = session['context']
        if context.get('topic', '循环结构') != '循环结构':
            raise AppError('TOPIC_NOT_SUPPORTED', '阶段04只支持循环结构。', 422)
        try:
            profile = parse_profile(content, format, context['stage'], context.get('grade', ''),
                                    last['revision'] + 1 if last else 1, last['id'] if last else None)
        except ValidationError:
            raise AppError('INVALID_CLASS_DATA', '班情字段不符合结构协议。', 422) from None
        if source is not None:
            profile.source_hash = hashlib.sha256(source).hexdigest()
        self.store.put('class_profiles', {'id': uid(), 'session_id': session['id'],
                                         'profile': profile.model_dump()})
        self.store.event(session['id'], None, 'class_profile.imported',
                         {'profile_id': profile.id, 'revision': profile.revision, 'source_hash': profile.source_hash})
        return profile.model_dump()

    def context(self, sid):
        profile = self.profile(sid)
        plan = suggested_plan(profile)
        return {'profile': profile.model_dump(), 'strategies': [s.model_dump() for s in strategies(profile)],
                'suggested_plan': plan.model_dump(),
                'contracts': {i.task_id: contract(i.task_id) for i in
                              [*plan.examples, *plan.exercises]},
                'notice': '建议草稿由确定性规则提供，尚未测试/审核；模型可改写教学内容和代码，不能改固定测试。'}

    def tool_result(self, view):
        result = {k: view[k] for k in ('lesson_id', 'revision', 'code_status', 'teacher_review_status',
                                      'candidate_ready', 'delivery_ready', 'curriculum_risks', 'notice')}
        result['items'] = {key: {k: value[k] for k in ('revision', 'review_status', 'verification_status', 'draft_id')
                                if k in value} for key, value in view['items'].items()}
        dids = set(view['bindings'].values())
        # 成功报告持久化可追溯；工具上下文只展开失败，减少整份教案的重复回传。
        result['failures'] = [r for r in self.store.find('reports', view['session_id'])
                              if r['draft_id'] in dids and r['status'] != 'PASS']
        return result

    def latest(self, sid, lesson_id):
        matches = [r for r in self.store.find('lessons', sid) if r['lesson_id'] == lesson_id]
        if not matches:
            raise AppError('NOT_FOUND', '教案不属于当前会话。', 404)
        return matches[-1]

    def propose(self, session, plan, profile_id, profile_revision, base_revision, run_id=None):
        sid = session['id']
        try:
            plan = LessonPlan.model_validate(plan)
        except ValidationError as error:
            raise AppError('INVALID_LESSON', '教案结构不完整，请根据字段位置修订。', 422,
                           details={'fields': [list(e['loc']) for e in error.errors(include_input=False)]}) from None
        profile = self.profile(sid, profile_id, profile_revision)
        if self.profile(sid).revision != profile_revision:
            raise AppError('STALE_PROFILE', '班情已更新，请使用最新依据重新备课。', 409)
        validate_grounding(plan, profile)
        records = self.store.find('lessons', sid)
        parent = records[-1] if records else None
        if (parent['revision'] if parent else 0) != base_revision:
            raise AppError('REVISION_CONFLICT', '教案版本已变化。', 409)
        lesson_id = parent['lesson_id'] if parent else uid()
        return self._save(session, lesson_id, plan, profile, parent, run_id, '生成结构化教案')

    def _save(self, session, lesson_id, plan, profile, parent, run_id, reason):
        sid = session['id']
        bindings, item_revisions = {}, {}
        old_plan = LessonPlan.model_validate(parent['plan']) if parent else None
        old_items = {i.id: i.model_dump() for i in old_plan.items()} if old_plan else {}
        global_change = parent and (parent['profile_ref'] != [profile.id, profile.revision]
                                   or old_plan.prerequisites != plan.prerequisites)
        if parent and set(old_items) != {i.id for i in plan.items()}:
            raise AppError('ITEM_SET_CHANGED', '修订须保留所有稳定ID，不能删除失败或被拒项目。', 422)
        code_items = [*plan.examples, *plan.exercises]
        for item in code_items:
            old_task = old_items.get(item.id, {}).get('task_id')
            if parent and old_task != item.task_id and parent['profile_ref'] == [profile.id, profile.revision]:
                raise AppError('FROZEN_TASK', '同一班情修订不能换题绕过冻结规格；只能修改候选代码。', 422)
            if run_id and parent:
                path = f'lessons/{lesson_id}/{item.id}.py'
                previous = self.store.get('drafts', parent['bindings'][item.id])
                repairs = [r for r in self.store.find('repairs', sid) if r['path'] == path]
                if previous['content'] != item.code and repairs and repairs[-1]['failed']:
                    if sha(item.code) in repairs[-1]['failed_hashes']:
                        raise AppError('NO_PROGRESS', '重复已失败代码，停止自动修复。', 409)
                    if repairs[-1]['count'] >= 2:
                        raise AppError('REPAIR_LIMIT', '两次自动修复已用完。', 409)
        changed = {i.id for i in plan.items() if old_items.get(i.id) != i.model_dump()}
        # 改参考解会使相关错因干预审核失效；其他教学项目保留逐项审核。
        changed |= {m.id for m in plan.misconceptions if set(m.exercise_ids) & changed}
        for item in plan.items():
            previous = parent['item_revisions'].get(item.id, 0) if parent else 0
            item_revisions[item.id] = previous + 1 if item.id in changed or global_change else previous
        for item in code_items:
            path = f'lessons/{lesson_id}/{item.id}.py'
            previous = self.store.get('drafts', parent['bindings'][item.id]) if parent and item.id in parent['bindings'] else None
            old_task = old_items.get(item.id, {}).get('task_id')
            if previous and previous['content'] == item.code and old_task == item.task_id:
                bindings[item.id] = previous['id']
                continue
            if run_id:
                self.verification.repair_guard(sid, path, sha(item.code))
            self.verification.invalidate(sid, path)
            if old_task != item.task_id:
                self.verification.freeze(sid, path, cases(item.task_id))
                spec = self.verification.latest_spec(sid, path)
                spec['source'] = 'baseline'
                self.store.put('test_specs', spec)
            draft = {'id': uid(), 'session_id': sid, 'run_id': run_id, 'call_id': None,
                     'path': path, 'base_hash': None, 'content': item.code, 'content_hash': sha(item.code),
                     'operation': 'write', 'revision': previous['revision'] + 1 if previous else 1,
                     'parent_id': previous['id'] if previous else None, 'status': 'DRAFT',
                     'verification_status': 'NOT_TESTED', 'mock': session['mock'], 'created_at': now(),
                     'diff': '', 'repair_diff': None}
            if previous:
                from app.tools import Registry
                draft['repair_diff'] = Registry._diff(path, previous['content'], item.code)
            self.store.put('drafts', draft)
            bindings[item.id] = draft['id']
        record = {'id': uid(), 'session_id': sid, 'lesson_id': lesson_id,
                  'schema_version': 1, 'revision': parent['revision'] + 1 if parent else 1,
                  'parent_id': parent['id'] if parent else None, 'plan': plan.model_dump(),
                  'profile_ref': [profile.id, profile.revision], 'bindings': bindings,
                  'item_revisions': item_revisions, 'content_hash': sha(dumps(plan.model_dump())),
                  'created_at': now(), 'reason': reason, 'run_id': run_id,
                  'source': 'model' if run_id else 'teacher', 'mock': session['mock']}
        for approval in self.store.find('approvals', sid):
            if approval.get('lesson_id') == lesson_id and approval['status'] == 'PENDING':
                approval['status'] = 'STALE'
                self.store.put('approvals', approval)
        self.store.put('lessons', record)
        self.store.event(sid, run_id, 'lesson.revised', {'lesson_id': lesson_id, 'revision': record['revision'],
                                                      'content_hash': record['content_hash']})
        return self.view(sid, lesson_id)

    def revise(self, session, lesson_id, body, run_id=None):
        record = self.latest(session['id'], lesson_id)
        self.expect(record, body.expected_revision)
        value = json.loads(dumps(record['plan']))
        found = False
        for group in ('goals', 'segments', 'examples', 'exercises', 'misconceptions'):
            for index, item in enumerate(value[group]):
                if item['id'] == body.item_id:
                    if body.replacement.get('id') != body.item_id:
                        raise AppError('STABLE_ID_REQUIRED', '修订必须保留项目ID。', 422)
                    value[group][index], found = body.replacement, True
        if not found:
            raise AppError('NOT_FOUND', '教学项目不存在。', 404)
        try:
            plan = LessonPlan.model_validate(value)
        except ValidationError:
            raise AppError('INVALID_LESSON', '修订破坏结构、时间或评分约束；原版本保留。', 422) from None
        profile = self.profile(session['id'], *record['profile_ref'])
        if profile.revision != self.profile(session['id']).revision:
            raise AppError('STALE_PROFILE', '班情已更新，请先重新备课。', 409)
        validate_grounding(plan, profile)
        return self._save(session, lesson_id, plan, profile, record, run_id, body.reason)

    @staticmethod
    def expect(record, revision):
        if record['revision'] != revision:
            raise AppError('REVISION_CONFLICT', '教案版本已变化，请刷新。', 409)

    def reviews(self, record):
        values = {}
        for review in self.store.find('education_reviews', record['session_id']):
            if (review['lesson_id'] == record['lesson_id'] and
                    review['item_revision'] == record['item_revisions'].get(review['item_id'])):
                values[review['item_id']] = review
        return values

    def review(self, session, lesson_id, body):
        record = self.latest(session['id'], lesson_id)
        self.expect(record, body.expected_revision)
        if body.item_id not in record['item_revisions']:
            raise AppError('NOT_FOUND', '教学项目不存在。', 404)
        if body.decision == 'accept' and self.profile(session['id']).revision != record['profile_ref'][1]:
            raise AppError('STALE_PROFILE', '班情已变化，不能接受旧依据教案。', 409)
        if body.decision == 'accept' and body.item_id in record['bindings']:
            if not self.view(session['id'], lesson_id)['items'][body.item_id]['current_pass']:
                raise AppError('VERIFICATION_REQUIRED', '该代码未通过当前冻结用例，不能接受。', 409)
        review = {'id': uid(), 'session_id': session['id'], 'lesson_id': lesson_id,
                  'lesson_revision': record['revision'], 'item_id': body.item_id,
                  'item_revision': record['item_revisions'][body.item_id], 'decision': body.decision,
                  'note': body.note, 'actor': session['owner'], 'created_at': now()}
        self.store.put('education_reviews', review)
        self.store.event(session['id'], None, 'lesson.item_reviewed', review)
        return self.view(session['id'], lesson_id)

    def view(self, sid, lesson_id):
        record = self.latest(sid, lesson_id)
        plan = LessonPlan.model_validate(record['plan'])
        profile = self.profile(sid, *record['profile_ref'])
        reviews, items = self.reviews(record), {}
        for item in plan.items():
            info = {'revision': record['item_revisions'][item.id], 'review_status':
                    {'accept': 'ACCEPTED', 'reject': 'REJECTED'}.get(reviews.get(item.id, {}).get('decision'), 'PENDING')}
            if item.id in record['bindings']:
                draft = self.store.get('drafts', record['bindings'][item.id])
                spec = self.verification.latest_spec(sid, draft['path'])
                task_contract = contract(item.task_id)
                current = (self.verification.current_pass(draft) and
                           spec['cases'] == task_contract['cases'])
                info.update(draft_id=draft['id'], code_hash=draft['content_hash'],
                            verification_status='STALE' if draft['verification_status'] == 'PASS' and not current else draft['verification_status'],
                            current_pass=current,
                            test_spec=spec, contract=task_contract,
                            report_ids=[r['id'] for r in self.store.find('reports', sid) if r['path'] == draft['path']])
            items[item.id] = info
        risks = curriculum_risks(plan)
        stale = profile.revision != self.profile(sid).revision
        verified = all(items[i]['current_pass'] for i in record['bindings'])
        accepted = all(v['review_status'] == 'ACCEPTED' for v in items.values())
        return {**record, 'profile': profile.model_dump(), 'strategies': [s.model_dump() for s in strategies(profile)],
                'items': items, 'curriculum_risks': risks, 'profile_stale': stale,
                'code_status': 'PASS' if verified else 'NOT_DELIVERABLE',
                'teacher_review_status': 'ACCEPTED' if accepted else 'PENDING',
                'candidate_ready': verified and not risks and not stale,
                'delivery_ready': verified and accepted and not risks and not stale,
                'notice': '代码通过仅覆盖固定用例；教案文字、学段适配、超纲与评分仍须教师逐项确认。正式写入前还须确认文件Diff。'}

    async def verify(self, sid, lesson_id, revision):
        record = self.latest(sid, lesson_id)
        self.expect(record, revision)
        plan = LessonPlan.model_validate(record['plan'])
        code_items = {i.id: i for i in [*plan.examples, *plan.exercises]}
        for item_id, did in record['bindings'].items():
            draft = self.store.get('drafts', did)
            spec = self.verification.latest_spec(sid, draft['path'])
            if spec['cases'] != contract(code_items[item_id].task_id)['cases']:
                raise AppError('FROZEN_TASK', '测试规格偏离固定任务契约；不能用删减/改写用例替代教育验证。', 409)
        try:
            identity = await self.verification.runner.identity()
        except AppError as error:
            with self.store.tx():
                self.verification.refresh(sid, None)
                self.store.put('education_attempts', {'id': uid(), 'session_id': sid,
                    'lesson_id': lesson_id, 'lesson_revision': revision, 'item_id': None,
                    'error': error.payload(), 'report': None, 'created_at': now()})
            raise
        with self.store.tx():
            self.verification.refresh(sid, identity)
        for item_id, did in record['bindings'].items():
            draft = self.store.get('drafts', did)
            if self.verification.current_pass(draft):
                continue
            with self.store.tx():
                self.verification.invalidate(sid, draft['path'])
                draft['verification_status'] = 'NOT_TESTED'
                self.store.put('drafts', draft)
            report = None
            try:
                spec = self.verification.latest_spec(sid, draft['path'])
                report = await self.verification.prepare(sid, did, spec['id'])
                with self.store.tx():
                    self.verification.commit(report)
            except asyncio.CancelledError:
                with self.store.tx():
                    self.store.put('education_attempts', {'id': uid(), 'session_id': sid,
                        'lesson_id': lesson_id, 'lesson_revision': revision, 'item_id': item_id,
                        'error': {'code': 'INTERRUPTED', 'message': '验证中断，没有通过证据。'},
                        'report': report, 'created_at': now()})
                raise
            except AppError as error:
                with self.store.tx():
                    self.store.put('education_attempts', {'id': uid(), 'session_id': sid,
                        'lesson_id': lesson_id, 'lesson_revision': revision, 'item_id': item_id,
                        'error': error.payload(), 'report': report, 'created_at': now()})
                if error.code == 'RUNNER_UNAVAILABLE':
                    raise
        return self.view(sid, lesson_id)

    def export(self, sid, lesson_id):
        view = self.view(sid, lesson_id)
        if not view['delivery_ready']:
            raise AppError('EDUCATION_REVIEW_REQUIRED', '须全部代码通过、无超纲风险且教师逐项接受后才可导出。', 409)
        from app.education.render import render_files
        reports = [r for r in self.store.find('reports', sid) if r['draft_id'] in view['bindings'].values()]
        return render_files(view, reports)
