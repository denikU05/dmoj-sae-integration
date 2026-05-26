def solve(n):
    if n < 0: return 0
    if n == 0: return 1
    return solve(n-1) + solve(n-2) + solve(n-3)
n = int(input())
print(solve(n))

# 1