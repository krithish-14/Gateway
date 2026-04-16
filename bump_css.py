import os
import re

templates_dir = r"c:\Users\krithish.B.R\Desktop\final project\myworld\final_year_project\project_review\templates\project_review"
# This pattern matches any variant of styles1.css followed by ?v=number
pattern = re.compile(r'styles1\.css[\'\"\s\%\}]*\?v=\d+')

for root, dirs, files in os.walk(templates_dir):
    for file in files:
        if file.endswith('.html'):
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Use a lambda to keep the prefix and only replace the version
            def replacer(match):
                text = match.group(0)
                # Keep everything up to the 'v='
                return re.sub(r'v=\d+', 'v=40', text)

            new_content = pattern.sub(replacer, content)
            
            if new_content != content:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"Bumped version in {file}")
