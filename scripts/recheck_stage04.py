"""复验实际模型产物：通过逐项修订接口校正文案，保留父版本并真实重跑所有代码。"""
import asyncio
import json
import os
from pathlib import Path

from accept_stage04 import check_lesson, comparison
from app.agent import Agent
from app.config import PROJECT_ROOT, Settings
from app.domain import dumps, now, sha
from app.education.models import ReviseItem
from app.education.rules import UNIVERSITY_NOTES
from app.storage import Store
from app.verification.runner import RemoteRunner
from verify_stage03 import main

CORRECTIONS = {
    'junior_A': {
        'example-1': {'explanation': 'n=5时，range(1,6)依次产生1、2、3、4、5，循环体执行5次。'
            '迭代器耗尽后for结束，循环变量i仍为5；此代码不会执行i<=n判断，也不会把i更新成6。'
            '追踪问题：n=0与n=1时输出什么？预期观察：range(1,1)为空而无输出；n=1时仅输出1。'},
    },
    'junior_B': {
        'segment-2': {'activity': '教师展示count代码，提问n=5时range(1,6)产生哪些值、print执行几次。'
            '可观察回答：依次为1、2、3、4、5，共执行5次。迭代器耗尽后for结束；'
            'i仍为5，不存在代码中未写出的i<=n条件判断。再预测并运行n=0/1/5核对。'},
        'example-1': {'explanation': 'n=5时，i依次取1、2、3、4、5，共输出5行；range耗尽后结束for，i仍为5。'
            '追踪问题：n=0是否给i赋值、是否有输出？预期观察：range(1,1)为空，循环体不执行，'
            '本次程序没有给i赋值且无输出。n=1仅输出1。不要把for的迭代器耗尽混写为while条件判断。'},
        'example-2': {'explanation': 'n=6时total初值为0；处理i=1至6后依次为0、2、2、6、6、12。'
            '不变量：本轮处理i后，total等于1到当前i的所有正偶数之和。'
            '追踪问题：n=0/1时为何输出0，n=2时何时发生累加？预期观察：n=0没有迭代；'
            'n=1只有奇数，total不变；n=2在i=2时变为2。此示例使用for，不虚构额外while版本。'},
        'segment-6': {'activity': '出口测：n=1时range(1,n)与range(1,n+1)分别产生什么？'
            '可观察回答：前者为空，后者仅产生1；n=0时两者都为空。提交终点是否包含及预计输出的边界表。'},
    },
    'university_A': {
        'example-1': {'explanation': UNIVERSITY_NOTES['sum'] + ' 追踪问题：n=5时第3轮开始和结束的状态？'
            '预期观察：开始i=3,total=3；先累加得到6，再更新i=4。每轮判断前不变量的形式保持为'
            'total等于1到i-1的和。第5轮结束i=6,total=15，第6次判断为假，不执行第6轮循环体。'},
        'example-2': {'explanation': '外层处理第i行之前，count等于前i-1行所有合法整数对数；初始化为空前缀、count=0。'
            '内层j遍历1到i，每轮增加一个整数对，本行完成后覆盖前i行，保持前缀计数性质。'
            '外层range耗尽后已覆盖1到n全部行，结果为n(n+1)/2。n>=1时Python外层变量i停留在n，'
            '不会自动变成n+1；n=0时外层没有迭代。终止性来自两层有限range。'
            '时间为1+2+...+n，即Θ(n²)，额外空间O(1)。追踪n=4应得到10，n=0应得到0。'},
        'segment-5': {'activity': '教师提问约数计数与素数计数的时间、空间复杂度。可观察回答：约数计数O(n)、空间O(1)。'
            '素数计数忽略提前break时，每个候选x至多试除x-2次；n>=2时求和为(n-1)(n-2)/2，'
            '因此O(n²)是保守上界。不能声称每个候选都试满，也不能由n为素数推断此前全部候选都是素数。'
            'n=0/1时没有候选。要求参考论证包含初始化、保持、退出与终止性。'},
        'exercise-1': {'explanation': UNIVERSITY_NOTES['sum']},
        'exercise-2': {'explanation': UNIVERSITY_NOTES['divisors']},
        'exercise-3': {'explanation': UNIVERSITY_NOTES['primes']},
    },
}


def recheck(socket, token, output):
    async def run():
        source = Path(os.environ.get('YUNYUN_ACCEPT_SOURCE', str(
            PROJECT_ROOT / '.runtime/stage04-acceptance-final2-live-model.json')))
        original = json.loads(source.read_text())
        assert original['mock'] is False and original['status'] == 'PASS'
        settings = Settings(runner_socket=socket, runner_token=token, yunyun_mode='web')
        store = Store(settings.yunyun_data_dir / 'state.sqlite3')
        result = {'status': 'FAIL', 'timestamp': now(), 'model_called_this_recheck': False,
            'generation_source': str(source), 'generation_source_hash': sha(source.read_text()),
            'script_hash': sha(Path(__file__).read_text()), 'real_teacher_review': 'NOT_TESTED',
            'scenarios': {}, 'corrections': []}
        try:
            for key, saved in original['scenarios'].items():
                agent = Agent(settings, store)
                agent.verification.runner = RemoteRunner(socket, token)
                sid, lid = saved['session_id'], saved['lesson']['lesson_id']
                session = store.get('sessions', sid)
                assert session['owner'] == 'stage04-acceptance' and not session['mock']
                current = agent.education.latest(sid, lid)
                assert current['id'] == saved['lesson']['id'], '已有更新，不能覆盖后续修订'
                for item_id, patch in CORRECTIONS[key].items():
                    record = agent.education.latest(sid, lid)
                    item = next(i for group in ('segments', 'examples', 'exercises')
                                for i in record['plan'][group] if i['id'] == item_id)
                    replacement = {**item, **patch}
                    with store.tx():
                        revised = agent.education.revise(session, lid, ReviseItem(
                            expected_revision=record['revision'], item_id=item_id, replacement=replacement,
                            reason='自动验收校正教学说明；未进行真实教师审核，不改代码或冻结用例。'))
                    result['corrections'].append({'scenario': key, 'item_id': item_id,
                        'from_revision': record['revision'], 'to_revision': revised['revision'],
                        'before': {field: item[field] for field in patch}, 'after': patch})
                current = agent.education.latest(sid, lid)
                assert current['bindings'] == saved['lesson']['bindings']
                old_ids = {r['id'] for r in saved['reports']}
                # 文本改动不修改代码；本次验收仍主动重跑，新增报告不冒充原报告。
                with store.tx():
                    for did in current['bindings'].values():
                        draft = store.get('drafts', did)
                        agent.verification.invalidate(sid, draft['path'])
                view = await agent.education.verify(sid, lid, current['revision'])
                data = {**saved, 'lesson': view, 'lessons': store.find('lessons', sid),
                        'reports': store.find('reports', sid), 'events': store.events(sid),
                        'execution_trigger': 'acceptance service recheck; no model call',
                        'automatic_content_revision': True, 'real_teacher_review': 'NOT_TESTED'}
                data['checks'] = check_lesson(agent, session, data)
                assert all(r['report_id'] not in old_ids for r in data['checks']['execution'])
                assert all(view['items'][i]['code_hash'] == saved['lesson']['items'][i]['code_hash']
                           for i in view['bindings'])
                result['scenarios'][key] = data
                output.with_name(output.stem + '-' + key + '.json').write_text(dumps(data))
                output.with_name(output.stem + '-' + key + '-lesson.json').write_text(
                    json.dumps(view, ensure_ascii=False, indent=2))
                output.write_text(dumps(result))
                print(dumps({'scenario': key, 'revision': view['revision'], 'status': 'PASS',
                             'cases': data['checks']['case_count']}), flush=True)
            result['comparison'] = comparison(result['scenarios'])
            result['comparison']['reference_explanations'] = {k: [
                {'id': e['id'], 'explanation': e['explanation']} for e in d['lesson']['plan']['exercises']]
                for k, d in result['scenarios'].items()}
            result['status'] = 'PASS'
            output.write_text(dumps(result))
            output.with_name(output.stem + '-comparison.json').write_text(json.dumps(
                result['comparison'], ensure_ascii=False, indent=2))
            return {'status': 'PASS', 'source_generation': str(source), 'model_called': False,
                    'program_count': 15, 'case_count': sum(d['checks']['case_count'] for d in result['scenarios'].values())}
        finally:
            store.close()
    return asyncio.run(run())


if __name__ == '__main__':
    main(['backend/tests/integration/test_education.py'], recheck, 'stage04-acceptance-corrected')
