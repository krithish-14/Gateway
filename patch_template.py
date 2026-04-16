
import os

filepath = r'c:\Users\krithish.B.R\Desktop\final project\myworld\final_year_project\project_review\templates\project_review\portal_validation_success.html'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Target multiline tag
target = """<span>Analyzing integrity for <strong>{{ reg_obj.startup_name|default:reg_obj.company_name
                            }}</strong></span>"""

replacement = """<span>Analyzing integrity for <strong>{{ reg_obj.startup_name|default:reg_obj.company_name }}</strong></span>"""

if target in content:
    new_content = content.replace(target, replacement)
    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        f.write(new_content)
    print("Successfully patched multiline tag.")
else:
    # Try with different whitespace if it's not exact
    import re
    # Match {{ ... }} across lines
    pattern = r'\{\{\s*reg_obj\.startup_name\|default:reg_obj\.company_name\s*\}\}'
    if re.search(pattern, content, re.MULTILINE):
        new_content = re.sub(pattern, '{{ reg_obj.startup_name|default:reg_obj.company_name }}', content, flags=re.MULTILINE)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("Successfully patched using regex.")
    else:
        print("Target tag not found.")
