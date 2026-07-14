path = r'C:\Users\kumex\OneDrive\Desktop\Jarvis\Server\app\static\index.html'

with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the comment line before the section
comment_start = None
sec_start = None
sec_end = None

for i, line in enumerate(lines):
    if '<!-- Digitale Speisekarte -->' in line and comment_start is None:
        comment_start = i
    if 'id="speisekarte"' in line and sec_start is None:
        sec_start = i

# Walk forward from sec_start counting <section> depth
depth = 0
for i in range(sec_start, len(lines)):
    if '<section' in lines[i]:
        depth += 1
    if '</section>' in lines[i]:
        depth -= 1
        if depth == 0:
            sec_end = i
            break

print(f'Comment at line {comment_start+1}')
print(f'Section start at line {sec_start+1}')
print(f'Section end at line {sec_end+1}')

# Remove from comment_start to sec_end (inclusive)
# Keep a blank line separator
new_lines = lines[:comment_start] + lines[sec_end+1:]

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print(f'Removed {sec_end - comment_start + 1} lines')
print('Done.')
