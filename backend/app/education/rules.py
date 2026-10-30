import ast

from app.domain import AppError
from app.education.catalog import TASKS
from app.education.models import ClassProfile, LessonPlan, Strategy

UNIVERSITY_NOTES = {
    'sum': '不变量：每次while判断前total等于1到i-1的和。初始化i=1、total=0成立；'
           '先累加i再令i加1，保持该不变量；退出时i=n+1，得到1到n的和。'
           '终止性：非负递减量n-i+1每轮减1。n=0直接退出并输出0。'
           '复杂度：时间O(n)，额外空间O(1)。',
    'divisors': '不变量：处理i前count等于1到i-1中n的约数个数。初始化count=0；'
                '仅在n%i==0时加1，保持对已检查区间的计数；退出时已检查1到n全部整数。'
                '终止性：有限range(1,n+1)每轮前进一步。n=1只有约数1，输出1。'
                '复杂度：时间O(n)，额外空间O(1)。',
    'primes': '外层不变量：处理x前count是区间[2,x)中素数个数。初始化count=0；'
              '内层检查已试除的整数，发现因子则prime=False并break，否则保持无因子的判断；'
              '内层结束后按prime增加count，保持外层不变量；退出后统计完2到n。'
              '终止性：内外层均为有限range，break只退出最内层。x=2时内层为空，仍计为素数；'
              'n=0/1时无候选，输出0。复杂度：最坏时间上界O(n²)，额外空间O(1)。',
}

TASK_LABELS = {'count': '顺序计数', 'sum': '累加求和', 'countdown': '循环倒计数',
               'even_sum': '正偶数求和', 'multiples': '倍数筛选与去重',
               'pairs': '整数对计数', 'divisors': '正约数计数', 'primes': '素数计数'}


def lesson_overview(profile, university):
    facts = '；'.join(f.observation for f in profile.facts) or '暂无已确认的量化观察，不能预设未交或出错人数'
    size = f'班级共{profile.class_size}人' if profile.class_size else '班级人数未知，不计算比例'
    prior = '、'.join(profile.prior_knowledge) or '先修掌握情况未确认，课前需诊断'
    emphasis = ('循环不变量的初始化、保持与退出，终止性论证及时间/空间复杂度' if university else
                '循环条件、循环体与变量更新的对应关系，以及range终点不包含的边界含义')
    actions = '；'.join(s.action for s in strategies(profile))
    return [
        {'id': 'analysis-content', 'kind': 'content', 'title': '本课内容与学习路径',
         'content': f'课程定位：以变量、输入输出和条件判断为基础，学习用重复执行解决计数、累加和筛选任务。\n'
                    f'核心内容：{emphasis}。\n'
                    '学习路径：先预测执行过程，再用追踪表解释变量变化，运行固定用例核对，最后迁移到分层练习。\n'
                    '课堂资源：使用备课产物中的示例与分层题；教师按课堂需要准备零次/一次/正常输入的追踪表和出口反馈单。'},
        {'id': 'analysis-learners', 'kind': 'learners', 'title': '本班依据与教学应对',
         'content': f'已知班情：{size}；{facts}。\n先修依据：{prior}。\n'
                    '判断边界：各类学生集合交集未知，人数不能相加；观察只能提示待诊断问题，不能证明能力或病因。\n'
                    f'教学应对：{actions}\n'
                    '课堂核实：先收集条件判断与变量更新的回答，再调整提示强度；缺失信息继续标为未知。'},
        {'id': 'analysis-focus', 'kind': 'focus', 'title': '重点、难点与解决策略',
         'content': f'教学重点：{emphasis}。\n'
                    '教学难点：把每次条件判断与更新后的状态对应起来，解释为什么终止，以及零次/一次循环的差别。\n'
                    '解决策略：教师示范一轮追踪，学生补齐后续状态；将退出条件和更新方向并列检查，用零次/一次输入核对边界。\n'
                    '评价依据：学生能独立填写追踪记录、解释边界并完成对应层级任务；未达成时回到具体状态追踪，不只重复结论。'},
    ]


def strategies(profile: ClassProfile):
    counts = {f.type: f for f in profile.facts}
    result = [Strategy(id='strategy-core', rule_id='R00', evidence_ids=[],
                       action='45分钟循环课，覆盖零次、边界和正常输入；未知班情保留诊断。', target='全班')]
    actions = {
        'not_submitted': ('R01', '先修诊断5分钟；提供补交机会，不据此判定能力差。'),
        'infinite_loop': ('R02', 'while变量逐步追踪10分钟；基础题提供初值/条件/更新追踪表。'),
        'boundary_error': ('R03', '边界对比15分钟；显式比较range终点和n=0/1。'),
    }
    for kind, (rule, action) in actions.items():
        fact = counts.get(kind)
        if fact and fact.count:
            result.append(Strategy(id='strategy-' + kind, rule_id=rule, evidence_ids=[fact.id],
                                   action=action, target=f'观察到{fact.count}人的该类情况，交集未知'))
    return result


def focus(profile):
    facts = {f.type: f.count for f in profile.facts}
    # 多种问题并存时优先安全终止，再处理边界；不相加人数。
    return 'termination' if facts.get('infinite_loop', 0) else (
        'boundary' if facts.get('boundary_error', 0) else 'diagnostic')


def suggested_plan(profile):
    stage, emphasis = profile.stage, focus(profile)
    university = stage == '大学'
    strategy = strategies(profile)
    refs = [s.id for s in strategy]
    minutes = [5, 8, 10, 10, 10, 2] if emphasis == 'termination' else [2, 8, 8, 15, 10, 2]
    if emphasis == 'diagnostic':
        minutes = [5, 8, 8, 12, 10, 2]
    activities = [
        ('先修诊断', '用条件语句与变量更新小题诊断；给未交者补交机会，原因待核实。'),
        ('循环演示', '逐行追踪计数与累加；先预测再运行n=0/1/5。'),
        ('终止追踪', '画初值→条件→循环体→更新表，说明何时退出。'),
        ('边界对比', '比较range(1,n)与range(1,n+1)，手算n=0/1并解释差异。'),
        ('分层练习', '基础独立完成，进阶结合条件，挑战解释去重；教师逐题审核。'),
        ('出口测', '说明零次循环与一次循环的条件，提交一行变量追踪记录。'),
    ]
    not_submitted = next((f.count for f in profile.facts if f.type == 'not_submitted'), None)
    if not_submitted == 0:
        activities[0] = ('先修诊断', '用条件语句与变量更新小题快速诊断；本班上次未交为0，不安排补交环节。')
    elif not_submitted is None:
        activities[0] = ('先修诊断', '用条件语句与变量更新小题诊断；提交状态未知，先核实，不预设存在未交学生。')
    if university:
        activities[1] = ('不变量论证', '追踪累加器；给出循环不变量、初始化/保持/退出论证。')
        activities[2] = ('终止性分析', '用递减量说明终止，辨析break的作用域与嵌套循环。')
        activities[4] = ('复杂度与练习', '完成约数与素数计数；解释最坏时间复杂度和空间复杂度。')
    teaching_moves = [
        ('出示条件判断和变量变化的诊断问题，邀请学生说明判断依据；按回答核实先修掌握情况。',
         '独立作答后与同伴对照，标记不能解释的步骤；有提交障碍时向教师说明。',
         '收集诊断回答；不能解释条件或更新的学生进入带提示的追踪任务，不把未交直接判为能力不足。'),
        ('按当前课堂示例演示一轮执行；先遮住运行结果，让学生预测零次、一次与正常输入。',
         '填写输入、当前变量、条件真假、本轮输出和更新后值，并用实际结果核对预测。',
         '抽查追踪表是否包含循环前的首次判断；发现只记输出不记状态时，补做一轮口头追踪。'),
        ('将初值、进入条件、循环体和更新方向并排展示，追问每一轮状态如何接近退出条件。',
         '两人一组交替说明当前状态与下一轮条件；用自己的话说明循环结束的原因。',
         '学生能指出决定终止的状态变化；不能说明时回到追踪表，不以运行未报错代替理解。'),
        ('并列展示循环终点的两种写法，使用当前示例的零次/一次输入，引导学生逐项比较。',
         '先手算应包含的首项和末项，再填写运行次数与输出，解释遗漏或多算发生在哪里。',
         '检查学生能否解释终点是否包含；仍有混淆者先完成边界表，再进入进阶题。'),
        ('先说明三档任务的输入输出契约和评分点；巡回记录困难发生在条件、更新还是筛选。',
         '完成基础任务后选择进阶或挑战；提交代码、追踪记录和结果解释，保留失败后的修改依据。',
         '按题目评分点反馈；代码依据固定测试，解释与适配由教师审核，公共倍数不得重复计入。'),
        ('收取一条零次循环解释和一条退出条件说明，归纳共性疑问并安排后续练习。',
         '独立提交出口反馈：说明何时不进入循环、状态如何更新，以及下一步需要的帮助。',
         '根据出口回答区分已掌握与需再诊断内容，记录下一课的针对性跟进，不预填达成人数。'),
    ]
    if university:
        teaching_moves[1] = ('示范不变量的初始化、保持和退出三步论证，再讨论计数结果。',
                             '书写不变量并逐条核对三个阶段，用边界输入检查论证是否成立。',
                             '检查论证是否覆盖空循环和最后一次更新；仅写术语不能视为完成证明。')
        teaching_moves[2] = ('用递减量解释终止性，辨析嵌套循环中break退出的范围。',
                             '指出每层循环的有限进展，解释break对内外层的不同作用。',
                             '检查终止论证是否独立于测试结果，并核对复杂度分析的计数范围。')
        teaching_moves[4] = ('讲清约数与素数任务的输入边界和评分要求，追问嵌套循环的计数范围。',
                             '完成代码与初始化/保持/退出论证，分别说明终止性及最坏复杂度。',
                             '分别评价代码测试证据、论证完整性和复杂度；仅输出正确不能代替证明。')
    example_tasks = ['sum', 'pairs'] if university else (['count', 'sum'] if emphasis != 'boundary' else ['count', 'even_sum'])
    exercise_tasks = ['sum', 'divisors', 'primes'] if university else ['countdown', 'even_sum', 'multiples']
    junior_scoring = [('初值与条件正确', 25), ('变量更新与结果正确', 35), ('零次/边界追踪解释', 40 if emphasis == 'boundary' else 20)]
    if emphasis != 'boundary':
        junior_scoring.append(('初值/条件/更新追踪表', 20))
    scoring = [('程序与输出正确', 50), ('循环不变量及终止性论证', 30), ('时间与空间复杂度分析', 20)] if university else junior_scoring
    exercises = []
    for i, (task, level) in enumerate(zip(exercise_tasks, ['基础', '进阶', '挑战'], strict=True), 1):
        exercises.append({'id': f'exercise-{i}', 'title': TASK_LABELS[task], 'task_id': task,
            'knowledge_points': ['循环不变量', '终止性', '复杂度'] if university else ['计数', '累加', '条件更新'],
            'explanation': UNIVERSITY_NOTES[task] if university else '先手算，再填追踪表，最后运行核对。',
            'code': TASKS[task][2], 'level': level, 'prompt': TASKS[task][0],
            'scaffolding': ('请独立论证终止性并给出最坏复杂度。' if university else
                            ('追踪表：初值｜进入条件｜本轮输出｜更新后值。' if emphasis == 'termination'
                             else '边界表：n=0｜n=1｜终点是否包含｜预期输出。')),
            'scoring': [{'criterion': criterion, 'points': points} for criterion, points in scoring]})
    misconceptions = []
    for kind, title, trigger, cause, action, ex in [
        ('not_submitted', '先修掌握待诊断', '要求独立填写循环前置条件', '可能是提交障碍或先修尚未掌握，不能由未交直接推断能力。',
         '先做低压力条件判断诊断，允许补交并核对提交障碍。', 'exercise-1'),
        ('infinite_loop', '循环不终止', 'while条件保持真且状态不变', '可能漏写更新或更新方向错误，需用追踪表确认。',
         '手工跟踪初值/条件/更新；先预测退出点，受限运行后讨论超时。', 'exercise-1'),
        ('boundary_error', '循环边界漏项', '误把range终点当作包含', '可能混淆开闭区间，须用n=0/1和最大项核实。',
         '并列手算零次/一次循环，解释n与n+1；强调边界评分点。', 'exercise-2'),
    ]:
        evidence = [f.id for f in profile.facts if f.type == kind and f.count > 0]
        misconceptions.append({'id': 'risk-' + kind, 'title': title, 'misconception_type': kind,
            'evidence_ids': evidence, 'basis': 'observed' if evidence else 'predicted',
            'trigger': trigger, 'cause': cause, 'cause_status': 'hypothesis',
            'teaching_intervention': action + (' 大学课要求用不变量和递减量说明。' if university else ''),
            'exercise_ids': [ex], 'stage': stage})
    return LessonPlan.model_validate({'stage': stage, 'prerequisites': ['变量', '输入输出', '条件语句'],
        'overview': lesson_overview(profile, university),
        'goals': [{'id': 'goal-1', 'title': '解释循环执行与退出',
                   'criterion': '独立填写n=0/1/5的变量追踪表，正确指出条件更新。'},
                  {'id': 'goal-2', 'title': '循环不变量与复杂度' if university else '完成循环任务',
                   'criterion': '论证不变量与终止性，分析嵌套循环时间/空间复杂度。' if university else
                                '用for/while完成计数与累加；解释零次与边界输入。'}],
        'segments': [{'id': f'segment-{i}', 'title': title, 'minutes': minute, 'activity': activity,
                      'strategy_ids': refs, 'teacher_actions': teaching_moves[i - 1][0],
                      'student_actions': teaching_moves[i - 1][1], 'assessment': teaching_moves[i - 1][2]}
                     for i, ((title, activity), minute) in
                     enumerate(zip(activities, minutes, strict=True), 1)],
        'examples': [{'id': f'example-{i}', 'title': f'演示：{TASK_LABELS[task]}', 'task_id': task,
                      'knowledge_points': ['嵌套循环', '复杂度'] if university and task == 'pairs' else ['循环', '条件更新'],
                      'explanation': '逐轮解释循环不变量和最坏复杂度。' if university else
                                     '逐轮记录变量，比较零次、一次和正常循环。', 'code': TASKS[task][2]}
                     for i, task in enumerate(example_tasks, 1)],
        'exercises': exercises, 'misconceptions': misconceptions})


def validate_grounding(plan, profile):
    if plan.stage != profile.stage:
        raise AppError('STAGE_MISMATCH', '教案学段必须与会话班情一致。', 422)
    facts = {f.id: f for f in profile.facts}
    required = {s.id for s in strategies(profile)}
    used = {r for s in plan.segments for r in s.strategy_ids}
    if used != required:
        raise AppError('INVALID_STRATEGY', '环节必须引用实际班情策略，不能虚构或遗漏。', 422)
    for m in plan.misconceptions:
        if any(i not in facts or facts[i].type != m.misconception_type or facts[i].count == 0
               for i in m.evidence_ids):
            raise AppError('INVALID_EVIDENCE', '错因引用必须指向同类非零真实观察。', 422)
        if (m.basis == 'observed') != bool(m.evidence_ids):
            raise AppError('INVALID_EVIDENCE', '没有依据的结论必须明确标为预测。', 422)
    for fact in profile.facts:
        if fact.count and not any(fact.id in m.evidence_ids for m in plan.misconceptions):
            raise AppError('MISSING_EVIDENCE', '非零班情观察必须有对应预警与干预。', 422)
    allowed = {'count', 'sum', 'countdown', 'even_sum', 'multiples'} if plan.stage == '初中' else set(TASKS)
    if any(i.task_id not in allowed for i in [*plan.examples, *plan.exercises]):
        raise AppError('TASK_NOT_APPROVED', '任务不在本学段固定契约中；新题须另经教师批准测试。', 422)


def curriculum_risks(plan):
    risks = []
    if plan.stage == '初中':
        for item in [*plan.examples, *plan.exercises]:
            try:
                tree = ast.parse(item.code)
            except SyntaxError:
                continue  # 语法错误交给Runner生成真实失败报告。
            loops = (ast.For, ast.While)
            if any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                                  ast.Import, ast.ImportFrom, ast.ListComp, ast.DictComp))
                   or (isinstance(n, loops) and any(isinstance(c, loops) for c in ast.walk(n) if c is not n))
                   for n in ast.walk(tree)):
                risks.append({'item_id': item.id, 'reason': '初中默认范围外的函数/类/导入/推导式/嵌套循环，须修改或调整课程契约。'})
    else:
        goals = ' '.join(g.title + g.criterion for g in plan.goals)
        if not all(term in goals for term in ['不变量', '终止', '复杂度']):
            risks.append({'item_id': 'goal-2', 'reason': '大学目标须覆盖不变量、终止性与复杂度。'})
        for item in plan.exercises:
            criteria = ' '.join(s.criterion for s in item.scoring)
            if not all(term in criteria for term in ['终止', '复杂度']):
                risks.append({'item_id': item.id, 'reason': '大学评分须包含终止论证和复杂度分析。'})
            if not all(term in item.explanation for term in ['不变量', '初始化', '保持', '退出', '终止', '复杂度', 'O(']):
                risks.append({'item_id': item.id, 'reason': '大学参考解须给出不变量的初始化/保持/退出、终止性和复杂度，不能只列评分术语。'})
    return risks
