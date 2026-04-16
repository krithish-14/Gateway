"""
Script to fix split Django template tags in profile.html.
These split tags cause 'Invalid block tag: endif' TemplateSyntaxError.
"""
import re

filepath = r'project_review/templates/project_review/profile.html'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

print("Original problematic lines detected:")
for i, line in enumerate(content.splitlines(), 1):
    if '{% if' in line and line.strip().endswith(r'if'):
        print(f"  Line {i}: {repr(line)}")

# Fix pattern: join lines where {% if ... is split across two lines inside an HTML tag
# Pattern: ends with "{% if" (possibly with text) and next line continues it
fixed = re.sub(
    r'(\{%\s*if\b[^%]*?)\r?\n\s+([^{%\n]+?%\})',
    lambda m: m.group(1) + ' ' + m.group(2).strip(),
    content
)

if fixed != content:
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(fixed)
    print("\nFIXED! File written successfully.")
else:
    print("\nNo split tags found - file may already be correct.")

# Show relevant lines for verification
print("\nVerification (lines 596-606):")
for i, line in enumerate(fixed.splitlines()[595:606], 596):
    print(f"  {i}: {line}")
