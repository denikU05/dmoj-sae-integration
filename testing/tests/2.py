cache = {}
def solve(n):
    if n < 0: return 0
    if n == 0: return 1
    if n in cache: return cache[n]
    res = solve(n-1) + solve(n-2) + solve(n-3)
    cache[n] = res
    return res
n = int(input())
print(solve(n))

"""
комментарии
"""