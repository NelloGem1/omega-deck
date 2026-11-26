#!/usr/bin/env python3
"""MARSHAL-UTF8 — fleet codec. UTF-8 that never fails.
Auto-registered system-wide via sitecustomize.py.
Usage: 'text'.encode('marshal-utf8') / b'...'.decode('marshal-utf8')"""
import codecs

class MarshalCodec(codecs.Codec):
    def encode(self, input, errors='strict'):
        return input.encode('utf-8', 'backslashreplace'), len(input)
    def decode(self, input, errors='strict'):
        if isinstance(input, str):
            input = input.encode('utf-8')
        else:
            input = bytes(input)
        return input.decode('utf-8', 'backslashreplace'), len(input)

def search(name):
    if name and name.replace('_', '-').lower() in ('marshal-utf8', 'marshalutf8', 'fm-utf8'):
        return codecs.CodecInfo(name='marshal-utf8',
                                encode=MarshalCodec().encode,
                                decode=MarshalCodec().decode)
    return None

codecs.register(search)

if __name__ == '__main__':
    # self-test
    s = 'FIELD MARSHAL ⚔️ 👑 🎓 — codec live'
    enc = s.encode('marshal-utf8')
    dec = enc.decode('marshal-utf8')
    print('marshal-utf8 roundtrip:', 'PASS' if dec == s else 'FAIL')
    print('direct:', s.encode('marshal-utf8')[:20], '...')
