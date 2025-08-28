# Fix the _get_current_count method properly
with open('api/core/tenancy/rate_limiter.py', 'r') as f:
    lines = f.readlines()

# Find and fix the indentation issue around line 96-97
for i, line in enumerate(lines):
    if i == 95 and 'if count' in line:  # Line 96 (0-indexed)
        # Ensure next line is properly indented
        if i + 1 < len(lines):
            lines[i + 1] = '        return int(count) if count else 0\n'

with open('api/core/tenancy/rate_limiter.py', 'w') as f:
    f.writelines(lines)
