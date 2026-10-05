"""Detect and normalize TXT locally without changing the original file."""
from dataclasses import dataclass
import codecs
from chardet import detect
from fastapi import HTTPException

IMPORT_ENCODINGS = ['auto', 'utf-8', 'gb18030', 'gbk', 'big5', 'big5hkscs',
                    'utf-16-le', 'utf-16-be', 'utf-32-le', 'utf-32-be',
                    'cp1252', 'shift_jis', 'euc_jp', 'euc_kr']
DETECTED_ENCODINGS = {codecs.lookup(e).name for e in IMPORT_ENCODINGS if e != 'auto'}
DETECTED_ENCODINGS.update({'ascii', 'utf-8-sig', 'utf-16', 'utf-32', 'gb2312',
                          'iso8859-1', 'cp1251', 'koi8-r'})
BOMS = [(codecs.BOM_UTF32_LE, 'utf-32'), (codecs.BOM_UTF32_BE, 'utf-32'),
        (codecs.BOM_UTF8, 'utf-8-sig'), (codecs.BOM_UTF16_LE, 'utf-16'),
        (codecs.BOM_UTF16_BE, 'utf-16')]

@dataclass
class DecodedText:
    text: str
    encoding: str
    removed_null_characters: int = 0

def normalize(text, encoding):
    nulls = text.count('\x00')
    # Sparse NUL padding occurs in transferred TXT files. Dense NULs are often binary
    # or an incorrectly decoded UTF-16 file and must not silently become a book.
    if nulls and nulls / max(1, len(text)) > .001:
        raise ValueError('too many nulls')
    sample = text[:16384] + text[len(text)//2:len(text)//2+8192] + text[-8192:]
    controls = sum(ord(c) < 32 and c not in '\n\r\t\0' for c in sample)
    if controls > max(0, len(sample) // 1000):
        raise ValueError('binary controls')
    text = text.lstrip('\ufeff').replace('\x00', '').replace('\r\n', '\n').replace('\r', '\n')
    return DecodedText(text, encoding, nulls)

def attempt(raw, encoding):
    return normalize(raw.decode(encoding, errors='strict'), encoding)

def decode_text_details(raw: bytes, encoding='auto'):
    if encoding not in IMPORT_ENCODINGS:
        raise HTTPException(400, '不支持这个编码选项')
    if raw.startswith((b'PK\x03\x04', b'%PDF-', b'\x89PNG', b'\xff\xd8\xff', b'\x1f\x8b')):
        raise HTTPException(400, '文件实际是压缩包、PDF或图片，请导入真正的TXT或EPUB')
    if encoding != 'auto':
        try:
            return attempt(raw, 'utf-8-sig' if encoding == 'utf-8' else encoding)
        except (UnicodeError, ValueError):
            raise HTTPException(400, '所选编码无法完整读取文件，请换一个导入编码；原文件未修改') from None
    for bom, candidate in BOMS:
        if raw.startswith(bom):
            try:
                return attempt(raw, candidate)
            except (UnicodeError, ValueError):
                raise HTTPException(400, '文件的Unicode编码标记与正文不一致，或正文含损坏数据；原文件未修改') from None
    try:
        return attempt(raw, 'utf-8-sig')
    except (UnicodeError, ValueError):
        pass
    # Bound detection work on large books; always validate the entire file strictly.
    guess = detect(raw[:262144])
    candidate = guess.get('encoding')
    if candidate:
        try:
            candidate = codecs.lookup(candidate).name
        except LookupError:
            candidate = None
    candidates = []
    if candidate in DETECTED_ENCODINGS and guess.get('confidence', 0) >= .5:
        candidates.append(candidate)
    # Unicode without a BOM still has aligned ASCII spaces/newlines in most books.
    # Test only when that alignment is visible, rather than decoding arbitrary binary.
    sample = raw[:65536]
    for codec, width, marker in [('utf-32-le', 4, b'\n\0\0\0'),
                                 ('utf-32-be', 4, b'\0\0\0\n'),
                                 ('utf-16-le', 2, b'\n\0'),
                                 ('utf-16-be', 2, b'\0\n')]:
        if len(raw) % width == 0 and any(sample[i:i+width] == marker for i in range(0,len(sample)-width+1,width)):
            candidates.insert(0, codec)
    candidates.append('gb18030')
    for candidate in dict.fromkeys(candidates):
        try:
            return attempt(raw, candidate)
        except (UnicodeError, ValueError):
            pass
    raise HTTPException(400, '自动检测仍无法完整读取这份TXT，请在导入编码中选择原编码后重试；无需转换原文件')

def decode_text(raw: bytes, encoding='auto'):
    result = decode_text_details(raw, encoding)
    return result.text, result.encoding
