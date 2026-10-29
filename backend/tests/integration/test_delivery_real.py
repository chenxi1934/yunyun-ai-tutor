"""真实容器执行与正式交付；合成审核动作仅检验机制，不代替教师教育判断。"""
import io
import json
import zipfile

import pytest
from app.domain import AppError, sha
from app.education.models import ReviewItem, ReviseItem
from app.education.rules import suggested_plan
from test_education import A, B, prepare


@pytest.mark.parametrize('stage,text,format', [('初中', A, 'text'), ('初中', B, 'csv'), ('大学', A, 'text')])
async def test_real_verified_lesson_commit_package_reject_and_restore(setup_agent, stage, text, format, record_property):
    agent, store, session, root, view = prepare(setup_agent, stage, text, format)
    sid, lid = session['id'], view['lesson_id']
    view = await agent.education.verify(sid, lid, 1)
    with store.tx():
        for iid in view['items']:
            agent.education.review(session, lid, ReviewItem(expected_revision=1, item_id=iid,
                decision='accept', note='自动化合成审核，仅验证交付协议'))
        files = agent.education.export(sid, lid)['files']
        pending = agent.delivery.prepare(session, {f'published/{lid}/{p}': c for p, c in files.items()},
            lesson_id=lid, lesson_revision=1, lesson_hash=view['content_hash'])
    original = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    agent.delivery.decide(pending['id'], 0, False)
    assert original == {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    with store.tx():
        pending = agent.delivery.prepare(session, {f'published/{lid}/{p}': c for p, c in files.items()},
            lesson_id=lid, lesson_revision=1, lesson_hash=view['content_hash'])
    agent.delivery.decide(pending['id'], 1, True)
    archive = zipfile.ZipFile(io.BytesIO(agent.delivery.archive(session, lid)))
    assert len([p for p in archive.namelist() if p.endswith('.py')]) == 5
    assert {'lesson.json', 'lesson.md', 'reports.json', 'manifest.json'} <= set(archive.namelist())
    manifest = json.loads(archive.read('manifest.json'))
    assert all(sha(archive.read(p).decode()) == h for p, h in manifest['files'].items())
    assert '分：' in archive.read('lesson.md').decode()
    assert all(r['status'] == 'PASS' for r in json.loads(archive.read('reports.json')))
    # 第二次正式覆盖被拒绝，逐文件字节不变。
    before = {e['path']: (root / e['path']).read_bytes() for e in pending['entries']}
    with store.tx():
        again = agent.delivery.prepare(session, {f'published/{lid}/{p}': c for p, c in files.items()},
            lesson_id=lid, lesson_revision=1, lesson_hash=view['content_hash'])
    agent.delivery.decide(again['id'], 2, False)
    assert all((root / p).read_bytes() == data for p, data in before.items())
    commit = store.find('commits', sid)[-1]
    with store.tx():
        restore = agent.delivery.restore(session, commit)
    assert (root / f'published/{lid}/lesson.md').exists()
    agent.delivery.decide(restore['id'], 3, True)
    assert not (root / f'published/{lid}/lesson.md').exists()
    with pytest.raises(AppError):
        agent.delivery.archive(session, lid)
    record_property('delivery_evidence', json.dumps({'stage': stage, 'profile': view['profile'],
        'files': list(files), 'reports': store.find('reports', sid), 'commits': store.find('commits', sid)}, ensure_ascii=False))


async def test_real_failure_repair_invalidates_approval_and_blocks_export(setup_agent):
    agent, store, session, root, view = prepare(setup_agent, bad_code='print("wrong")\n')
    sid, lid = session['id'], view['lesson_id']
    view = await agent.education.verify(sid, lid, 1)
    assert view['items']['exercise-1']['verification_status'] == 'OUTPUT_MISMATCH'
    with pytest.raises(AppError):
        agent.education.export(sid, lid)
    with store.tx():
        fixed = suggested_plan(agent.education.profile(sid)).exercises[0].model_dump()
        agent.education.revise(session, lid, ReviseItem(expected_revision=1, item_id='exercise-1',
                               replacement=fixed, reason='修复真实失败'))
    view = await agent.education.verify(sid, lid, 2)
    assert view['code_status'] == 'PASS'
    assert len(store.find('reports', sid)) == 6
    assert not view['delivery_ready']
    assert sorted(p.name for p in root.iterdir()) == ['fixture.md']


async def test_edit_after_pending_package_expires_approval_and_requires_reverification(setup_agent):
    agent, store, session, _, view = prepare(setup_agent)
    sid, lid = session['id'], view['lesson_id']
    view = await agent.education.verify(sid, lid, 1)
    with store.tx():
        for iid in view['items']:
            agent.education.review(session, lid, ReviewItem(expected_revision=1, item_id=iid,
                decision='accept', note='合成审核'))
        files = agent.education.export(sid, lid)['files']
        approval = agent.delivery.prepare(session, {f'published/{lid}/{p}': c for p, c in files.items()},
            lesson_id=lid, lesson_revision=1, lesson_hash=view['content_hash'])
        item = {**view['plan']['examples'][0]}
        item['code'] += '\n# 教师修订后需要新执行证据\n'
        changed = agent.education.revise(session, lid, ReviseItem(expected_revision=1,
            item_id=item['id'], replacement=item, reason='验证待审整包自动过期'))
    assert changed['items'][item['id']]['verification_status'] == 'NOT_TESTED'
    assert store.get('approvals', approval['id'])['status'] == 'STALE'
    with pytest.raises(AppError):
        agent.delivery.decide(approval['id'], 0, True)
    assert not store.find('commits', sid)
