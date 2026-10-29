"""复用阶段03临时隔离器；真实模型全教案生成，费用沿用现有SQLite账本。"""
import asyncio

from app.agent import Agent
from app.config import Settings
from app.domain import dumps, now, uid
from app.education.rules import suggested_plan
from app.storage import Store
from app.verification.runner import RemoteRunner
from verify_stage03 import main


def live_education(socket, token, output):
    async def run():
        settings = Settings(runner_socket=socket, runner_token=token, yunyun_mode='web')
        if settings.llm_provider != 'bailian':
            raise RuntimeError('真实教育验收必须使用百炼')
        store = Store(settings.yunyun_data_dir / 'state.sqlite3')
        session = None
        try:
            agent = Agent(settings, store)
            agent.verification.runner = RemoteRunner(socket, token)
            session = agent.create_session('stage04-live-probe', {'stage': '初中', 'grade': '初二', 'topic': '循环结构'})
            with store.tx():
                agent.education.import_profile(session,
                    '合成班情：班级共40人，刚学完条件语句；5人未交、3人把while写成了死循环，交集未知。', 'text')
            run = agent.new_run(session['id'], '请为初二生成完整45分钟《循环结构》备课草稿。'
                '先读取education_context的班情与规则，按suggested_plan结构调用propose_lesson提交完整plan。'
                '可以保留固定任务与代码；不要原样复制建议内容。必须重新撰写至少两个教学环节activity，'
                '加入具体教师提问与学生可观察回答，并重新撰写两个示例explanation的逐轮追踪问题与预期观察。'
                '不得直接声称已审核；保留稳定ID、字段、45分钟和100分评分结构。文字简洁，确保工具参数不截断。'
                '随后必须调用verify_lesson，让全部课堂示例和三档参考解真实运行；失败只改代码后重测。'
                '结束时明确代码结果与仍需教师逐项教学审核。不要请求正式发布，也不要读取无关文件。', 0, 'education-live-' + uid())
            await agent.run(run['id'])
            data = {'timestamp': now(), 'mock': False, 'synthetic_class_data': True,
                    'session_id': session['id'], 'run': store.get('runs', run['id']),
                    'profiles': store.find('class_profiles', session['id']),
                    'lessons': store.find('lessons', session['id']),
                    'reports': store.find('reports', session['id']),
                    'calls': store.find('calls', session['id']),
                    'attempts': store.find('education_attempts', session['id']),
                    'usage': store.find('usage', session['id']), 'events': store.events(session['id']),
                    'messages': store.messages(session['id'])}
            if data['lessons']:
                data['lesson'] = agent.education.view(session['id'], data['lessons'][-1]['lesson_id'])
            output.write_text(dumps(data), encoding='utf-8')
            assert data['run']['status'] == 'COMPLETED', data['run']
            assert data['lessons'] and all(x['source'] == 'model' and not x['mock'] for x in data['lessons'])
            baseline = suggested_plan(agent.education.profile(session['id'])).model_dump()
            generated = data['lesson']['plan']
            assert sum(a['activity'] != b['activity'] for a, b in
                       zip(generated['segments'], baseline['segments'], strict=True)) >= 2, '模型只复制规则草稿，不能冒充内容生成'
            assert all(a['explanation'] != b['explanation'] for a, b in
                       zip(generated['examples'], baseline['examples'], strict=True)), '示例讲解须有真实模型改写'
            assert data['lesson']['candidate_ready'] and not data['lesson']['delivery_ready']
            assert len(data['lesson']['bindings']) == 5
            assert all(data['lesson']['items'][i]['current_pass'] for i in data['lesson']['bindings'])
            assert len(data['reports']) >= 5
            assert all(u['provider_request_id'] for u in data['usage'] if u['status'] == 'USAGE_ESTIMATE')
            data['status'] = 'PASS'
            data['cny_estimate'] = sum(u['cny'] for u in data['usage'])
            output.write_text(dumps(data), encoding='utf-8')
            return {k: data[k] for k in ('status', 'session_id', 'cny_estimate')}
        finally:
            store.close()
    return asyncio.run(run())


if __name__ == '__main__':
    main(['backend/tests/integration/test_verification.py', 'backend/tests/integration/test_education.py'],
         live_education, 'stage04')
