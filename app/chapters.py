import re

HEADING=re.compile(r'^\s*(?:第[零〇一二三四五六七八九十百千万两\d]+[章回卷节部篇]|chapter\s+\d+|序章|楔子|尾声|后记)(?:\s|[：:.、]|$)',re.I)


def parse_chapters(text, maximum=12000):
    sections=[];title='正文';lines=[]
    for line in text.splitlines(keepends=True):
        if len(line.strip())<=100 and HEADING.match(line):
            if ''.join(lines).strip(): sections.append((title,''.join(lines).strip()))
            title=line.strip();lines=[]
        else: lines.append(line)
    if ''.join(lines).strip():sections.append((title,''.join(lines).strip()))
    result=[]
    for title,body in sections:
        parts=[body[i:i+maximum] for i in range(0,len(body),maximum)]
        for index,part in enumerate(parts):
            result.append((title if len(parts)==1 else f'{title} · {index+1}',part))
    return result
