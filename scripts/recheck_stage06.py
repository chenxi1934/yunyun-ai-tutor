"""在新公网会话复验真实模型原稿，修正已观察的教学文字；不调用模型或绕过审批。"""
import argparse
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--url', default='https://111.229.226.186')
    parser.add_argument('--prefix', default='stage06-content')
    args = parser.parse_args()
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', args.prefix):
        parser.error('证据前缀不合法')
    source = json.loads(args.source.read_text())
    assert source['scenarios'] and all(s['status'] == 'PASS' for s in source['scenarios'])
    output = {'status': 'FAIL', 'model_called': False, 'source_overall_status': source['status'],
              'source_sha256': hashlib.sha256(args.source.read_bytes()).hexdigest(),
              'review_source': '自动审校及合成教师动作，不代表真实教师专业审核', 'scenarios': []}
    destination = Path('.runtime') / (args.prefix + '.json')
    try:
        for saved in source['scenarios']:
            name = saved['name']
            snapshot = json.loads(args.source.with_name(
                args.source.stem.removesuffix('-browser') + '-' + name + '-generated.json').read_text())
            original = snapshot['lessons'][-1]
            with httpx.Client(base_url=args.url, timeout=180) as client:
                def request(method, url, body=None):
                    response = client.request(method, url, json=body)
                    response.raise_for_status()
                    return response.json()

                request('POST', '/api/client', {})
                profile = original['profile']
                session = request('POST', '/api/sessions', {'stage': profile['stage'],
                    'grade': profile['grade'], 'topic': '循环结构'})['session']
                sid = session['id']
                fact_input = {'class_size': profile['class_size'],
                    'prior_knowledge': profile['prior_knowledge'],
                    'facts': [{k: f[k] for k in ('type', 'count', 'denominator')} for f in profile['facts']]}
                profile = request('POST', f'/api/sessions/{sid}/class-profiles',
                    {'format': 'json', 'content': json.dumps(fact_input, ensure_ascii=False),
                     'expected_revision': 0})['profile']
                view = request('POST', f'/api/sessions/{sid}/lessons',
                    {'plan': original['plan'], 'profile_id': profile['id'],
                     'profile_revision': 1, 'base_revision': 0})['lesson']
                lid = view['lesson_id']
                specs = {i: v['test_spec'] for i, v in view['items'].items() if 'test_spec' in v}
                corrections = []
                # 只修订本轮已经观察到的具体错误，不将通用替换当作教学正确性检测器。
                if name == 'web-chrome-B':
                    item = view['plan']['examples'][1]
                    wrong = '预计学生手算得10（漏掉6）'
                    assert wrong in item['explanation'], '源稿已不同，请先人工核对，不能盲目修订'
                    replacement = {**item, 'explanation': item['explanation'].replace(
                        wrong, '预计学生手算得6（2+4=6，漏掉偶数6；正确包含6时为12）')}
                    before = view['revision']
                    request('POST', f'/api/sessions/{sid}/lessons/{lid}/reviews',
                        {'expected_revision': before, 'item_id': item['id'], 'decision': 'reject',
                         'note': '自动审校发现讲解算错；代码通过也不能接受错误文字。'})
                    view = request('PATCH', f'/api/sessions/{sid}/lessons/{lid}/items',
                        {'expected_revision': before, 'item_id': item['id'], 'replacement': replacement,
                         'reason': '纠正range(1,6)中偶数为2、4，其和为6，保持代码及固定用例。'})['lesson']
                    corrections.append({'item_id': item['id'], 'before': item['explanation'],
                        'after': replacement['explanation'], 'from_revision': before,
                        'to_revision': view['revision']})
                assert view['bindings'] and all(view['items'][i]['test_spec'] == spec for i, spec in specs.items())
                assert [e['code'] for e in [*view['plan']['examples'], *view['plan']['exercises']]] == [
                    e['code'] for e in [*original['plan']['examples'], *original['plan']['exercises']]]
                view = request('POST', f'/api/sessions/{sid}/lessons/{lid}/verify',
                    {'expected_revision': view['revision']})['lesson']
                assert view['code_status'] == 'PASS' and view['teacher_review_status'] == 'PENDING'
                for iid in view['items']:
                    view = request('POST', f'/api/sessions/{sid}/lessons/{lid}/reviews',
                        {'expected_revision': view['revision'], 'item_id': iid, 'decision': 'accept',
                         'note': '自动化合成审核，仅用于交付机制验收；不代表教师专业确认。'})['lesson']
                current = request('GET', f'/api/sessions/{sid}')
                approval = request('POST', f'/api/sessions/{sid}/lessons/{lid}/delivery',
                    {'expected_revision': current['session']['revision']})['approval']
                current = request('GET', f'/api/sessions/{sid}')
                request('POST', f'/api/approvals/{approval["id"]}/decision',
                    {'expected_revision': current['session']['revision'], 'decision': 'approve'})
                package = client.get(f'/api/sessions/{sid}/lessons/{lid}/package')
                package.raise_for_status()
                with zipfile.ZipFile(io.BytesIO(package.content)) as archive:
                    manifest = json.loads(archive.read('manifest.json'))
                    assert all(hashlib.sha256(archive.read(p)).hexdigest() == h for p, h in manifest['files'].items())
                    reports = json.loads(archive.read('reports.json'))
                    assert len(reports) == 5 and all(r['status'] == 'PASS' for r in reports)
                destination.with_name(args.prefix + '-' + name + '.zip').write_bytes(package.content)
                current = request('GET', f'/api/sessions/{sid}')
                output['scenarios'].append({'name': name, 'source_model_session': saved['session_id'],
                    'session_id': sid, 'corrections': corrections, 'snapshot': current,
                    'cases': sum(len(r['cases']) for r in reports), 'model_called_this_recheck': False})
                print(json.dumps({'scenario': name, 'status': 'PASS', 'corrections': len(corrections)}), flush=True)
        output['status'] = 'PASS'
    finally:
        destination.write_text(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
