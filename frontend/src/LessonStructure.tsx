import type { Lesson, TeachingItem } from './api'

const taskNames: Record<string, string> = { count: '顺序计数', sum: '累加求和', countdown: '循环倒计数', even_sum: '正偶数求和', multiples: '倍数筛选与去重', pairs: '整数对计数', divisors: '正约数计数', primes: '素数计数' }

export function teachingTitle(item: TeachingItem) {
  return item.task_id && taskNames[item.task_id] && /^(?:(?:演示|基础|进阶|挑战)：)?[a-z_]+$/.test(item.title)
    ? taskNames[item.task_id] : item.title
}

export function lessonSections(plan: Lesson['plan'], tab: string) {
  const overview = plan.overview || []
  if (tab === '教案') return [
    { key: 'content', title: '一、教学内容分析', items: overview.filter(item => item.kind === 'content') },
    { key: 'learners', title: '二、学情分析', items: overview.filter(item => item.kind === 'learners') },
    { key: 'goals', title: '三、教学目标', items: plan.goals },
    { key: 'focus', title: '四、教学重点、难点与解决策略', items: overview.filter(item => item.kind === 'focus') },
    { key: 'segments', title: '五、教学过程', items: plan.segments },
  ]
  const items = tab === '示例代码' ? plan.examples : tab === '分层练习' ? plan.exercises : plan.misconceptions
  return [{ key: tab, title: tab, items }]
}

export function reviewCounts(items: TeachingItem[], states: Lesson['items']) {
  const accepted = items.filter(item => states[item.id]?.review_status === 'ACCEPTED').length
  const rejected = items.filter(item => states[item.id]?.review_status === 'REJECTED').length
  return { accepted, rejected, pending: items.length - accepted - rejected }
}

export function sourceLabel(ref: string) {
  if (ref.startsWith('csv:row=')) return `CSV 第 ${ref.slice(8)} 行`
  const json = /^json:\$\.facts\[(\d+)\]$/.exec(ref)
  if (json) return `JSON 第 ${Number(json[1]) + 1} 条观察`
  if (ref.startsWith('text:')) return '文字班情'
  return '历史班情来源，详见追溯信息'
}

export function MisconceptionReferences({ item, lesson, blocked, onOpen }: {
  item: TeachingItem; lesson: Lesson; blocked: boolean; onOpen: (id: string) => void
}) {
  const facts = (item.evidence_ids || []).map(id => lesson.profile.facts.find(fact => fact.id === id))
  const exercises = (item.exercise_ids || []).map(id => lesson.plan.exercises.find(exercise => exercise.id === id))
  return <>
    <dl className="misconception-detail">
      <dt>依据</dt><dd>{item.basis === 'observed' ? '观察到的班情' : '预测风险，尚无直接观察'}
        {facts.map((fact, index) => <p key={index}>{fact ? `${fact.observation}（${sourceLabel(fact.source_ref)}）` : '此观察在当前班情中缺失，请核对历史依据。'}</p>)}
      </dd>
      <dt>触发情况</dt><dd>{item.trigger}</dd><dt>原因假设（待核实）</dt><dd>{item.cause}</dd><dt>课堂干预</dt><dd>{item.teaching_intervention}</dd>
      <dt>关联练习</dt><dd className="related-exercises">{exercises.map((exercise, index) => exercise
        ? <button type="button" className="subtle" disabled={blocked} title={blocked ? '请先保存或取消当前编辑' : undefined} key={exercise.id} onClick={() => onOpen(exercise.id)}>{exercise.level} · {teachingTitle(exercise)}</button>
        : <span key={index}>关联练习在当前版本中缺失，请核对。</span>)}</dd>
    </dl>
    <details className="trace-details"><summary>查看追溯信息</summary><p>观察标识：{item.evidence_ids?.join('、') || '无直接观察'}；练习标识：{item.exercise_ids?.join('、')}</p>{facts.map(fact => fact && <p key={fact.id}>来源定位：{fact.source_ref}{fact.source_hash && <>；来源 Hash：{fact.source_hash}</>}</p>)}</details>
  </>
}
