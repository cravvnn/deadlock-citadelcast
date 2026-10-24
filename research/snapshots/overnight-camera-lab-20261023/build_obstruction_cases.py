from pathlib import Path
H=Path(__file__).resolve().parent
html=(H/'obstruction_cases_template.html').read_text(encoding='utf-8').replace('__DATA__',(H/'obstruction-cases.json').read_text())
assert len(html.encode())<512000
(H/'obstruction-cases.html').write_text(html,encoding='utf-8')
print('Wrote obstruction-cases.html: '+str(len(html.encode()))+' bytes')
