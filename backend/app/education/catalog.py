"""人工编写的固定任务和用例；模型只提交代码，不能提交或改写expected。"""
from app.verification.models import TestCase

TASKS = {
    'count': ('输入整数n，0≤n≤100；逐行输出1到n，n=0无输出。', [(0, ''), (1, '1\n'), (5, '1\n2\n3\n4\n5\n')],
              'n=int(input())\nfor i in range(1,n+1):\n    print(i)\n'),
    'sum': ('输入整数n，0≤n≤10000；输出1到n的整数和；n=0输出0。', [(0, '0\n'), (1, '1\n'), (5, '15\n')],
            'n=int(input())\ni=1\ntotal=0\nwhile i<=n:\n    total+=i\n    i+=1\nprint(total)\n'),
    'countdown': ('输入整数n，0≤n≤100；逐行输出n到1，n=0无输出。', [(0, ''), (1, '1\n'), (3, '3\n2\n1\n')],
                  'n=int(input())\nwhile n>0:\n    print(n)\n    n-=1\n'),
    'even_sum': ('输入整数n，0≤n≤10000；输出不超过n的正偶数之和；无偶数输出0。', [(0, '0\n'), (1, '0\n'), (2, '2\n'), (6, '12\n')],
                 'n=int(input())\ntotal=0\nfor i in range(1,n+1):\n    if i%2==0:\n        total+=i\nprint(total)\n'),
    'multiples': ('输入整数n，0≤n≤10000；输出1到n中是3或5倍数的数之和，公共倍数只计一次。', [(0, '0\n'), (1, '0\n'), (3, '3\n'), (15, '60\n')],
                  'n=int(input())\ntotal=0\nfor i in range(1,n+1):\n    if i%3==0 or i%5==0:\n        total+=i\nprint(total)\n'),
    'pairs': ('输入整数n，0≤n≤100；用嵌套循环统计1≤j≤i≤n的整数对数并输出。', [(0, '0\n'), (1, '1\n'), (4, '10\n')],
              'n=int(input())\ncount=0\nfor i in range(1,n+1):\n    for j in range(1,i+1):\n        count+=1\nprint(count)\n'),
    'divisors': ('输入正整数n，1≤n≤1000；用循环输出n的正约数个数。', [(1, '1\n'), (7, '2\n'), (12, '6\n')],
                 'n=int(input())\ncount=0\nfor i in range(1,n+1):\n    if n%i==0:\n        count+=1\nprint(count)\n'),
    'primes': ('输入整数n，0≤n≤100；用嵌套循环和break统计不超过n的素数个数。', [(0, '0\n'), (1, '0\n'), (2, '1\n'), (10, '4\n')],
               'n=int(input())\ncount=0\nfor x in range(2,n+1):\n    prime=True\n    for d in range(2,x):\n        if x%d==0:\n            prime=False\n            break\n    if prime:\n        count+=1\nprint(count)\n'),
}


def cases(task_id):
    return [TestCase(id=f'n={n}', input=f'{n}\n', expected=value) for n, value in TASKS[task_id][1]]


def contract(task_id):
    return {'task_id': task_id, 'task_contract': TASKS[task_id][0],
            'cases': [c.model_dump() for c in cases(task_id)], 'source': 'baseline',
            'comparison': 'exact_stdout', 'catalog_version': 1}
