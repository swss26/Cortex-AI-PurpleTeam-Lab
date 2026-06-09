# 주의: 이 XSIAM 환경에서는 demisto / CommandResults / return_results / return_error 가
# 플랫폼에 의해 자동 주입되므로 'import demistomock' / 'from CommonServerPython import *'
# 를 쓰지 않는다. (쓰면 ModuleNotFoundError: No module named 'demistomock' 발생)
import re
import html as html_lib
import time

# XSIAM Automation Script: markdown-json-change
# ---------------------------------------------
# AI Agent가 반환한 Markdown 텍스트를 메일 본문용 HTML로 변환하고,
# 마크다운의 섹션(## 헤딩) 단위로 잘라 issue 컨텍스트처럼 JSON 구조로 저장한다.
#
# [Inputs]
#   markdown : 변환할 마크다운 텍스트 (예: ${AgentixAnalysis})
#   title    : 메일 상단 제목 (선택, 예: ${issue.name})
#
# [Outputs -> Context: MailHtml]
#   MailHtml.title         : 제목
#   MailHtml.html          : 전체 HTML (필요시 통째로 쓸 때)
#   MailHtml.sections      : [ { id, heading, level, html, text }, ... ]
#   MailHtml.sectionCount  : 섹션 개수
#   MailHtml.generatedAt   : 생성 시각(UTC)


def _esc(text):
    """HTML 특수문자 이스케이프."""
    return html_lib.escape(text, quote=False)


def _inline(text):
    """인라인 마크다운(**bold**, *italic*, `code`, [text](url)) -> HTML."""
    code_style = ('background:#f3f4f6;padding:2px 6px;border-radius:4px;'
                  'font-family:Consolas,Monaco,monospace;font-size:12px;'
                  'color:#b91c1c')
    text = _esc(text)
    text = re.sub(r'`([^`]+)`',
                  r'<code style="%s">\1</code>' % code_style, text)
    text = re.sub(r'\*\*([^*]+)\*\*',
                  r'<strong style="color:#111827">\1</strong>', text)
    text = re.sub(r'__([^_]+)__',
                  r'<strong style="color:#111827">\1</strong>', text)
    text = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<em>\1</em>', text)
    text = re.sub(r'\[([^\]]+)\]\((https?://[^\)]+)\)',
                  r'<a href="\2" style="color:#2563eb">\1</a>', text)
    return text


_P = ('margin:0 0 10px;font-size:14px;line-height:1.6;color:#374151')
_LI = ('margin:0 0 6px;font-size:14px;line-height:1.6;color:#374151')


def _render_block(lines):
    """
    헤딩을 제외한 본문 라인 묶음을 메일 친화적 HTML로 변환.
    목록은 중첩 <ul> 대신 들여쓰기(margin-left) 방식으로 그려 메일 클라이언트
    호환성과 깨짐을 모두 해결한다.
    """
    out = []
    in_code = False
    code_buf = []
    list_counters = {}   # 들여쓰기 깊이별 번호 카운터

    for raw in lines:
        line = raw.rstrip()

        # 코드 블록
        if line.strip().startswith('```'):
            if in_code:
                out.append(
                    '<pre style="background:#1f2937;color:#e5e7eb;padding:12px;'
                    'border-radius:6px;overflow:auto;font-size:13px">'
                    '%s</pre>' % _esc('\n'.join(code_buf)))
                code_buf = []
                in_code = False
            else:
                in_code = True
            continue
        if in_code:
            code_buf.append(raw)
            continue

        if not line.strip():
            list_counters = {}
            continue

        # 구분선
        if re.match(r'^\s*([-*_])\1{2,}\s*$', line):
            list_counters = {}
            out.append('<hr style="border:0;border-top:1px solid #e5e7eb;'
                       'margin:16px 0"/>')
            continue

        # 목록 (순서/비순서, 중첩은 들여쓰기 깊이로 표현)
        m = re.match(r'^(\s*)([-*+]|\d+\.)\s+(.*)$', line)
        if m:
            indent = len(m.group(1).replace('\t', '    '))
            depth = indent // 4           # 0,1,2...
            ordered = bool(re.match(r'^\d+\.$', m.group(2)))
            margin = 4 + depth * 22        # 깊이별 들여쓰기(px)

            if ordered:
                list_counters[depth] = list_counters.get(depth, 0) + 1
                marker = '%d.' % list_counters[depth]
                mark_html = ('<span style="color:#6b7280;font-weight:600;'
                             'min-width:20px;display:inline-block">%s</span>'
                             % marker)
            else:
                list_counters.pop(depth, None)
                mark_html = ('<span style="color:#9ca3af;'
                             'min-width:20px;display:inline-block">&bull;</span>')

            out.append(
                '<div style="%s;margin-left:%dpx;display:flex;'
                'align-items:flex-start">%s<span>%s</span></div>'
                % (_LI, margin, mark_html, _inline(m.group(3))))
            continue

        # 일반 문단
        list_counters = {}
        out.append('<p style="%s">%s</p>' % (_P, _inline(line)))

    if in_code:
        out.append(
            '<pre style="background:#1f2937;color:#e5e7eb;padding:12px;'
            'border-radius:6px;overflow:auto;font-size:13px">%s</pre>'
            % _esc('\n'.join(code_buf)))
    return '\n'.join(out)


# ---- 핵심 정보(메타) 추출: "**라벨:** 값" 형태의 줄을 표로 ----
_META_RE = re.compile(r'^\s*\*\*(.+?):\*\*\s*(.*)$')


def _extract_meta(lines):
    """본문 라인에서 '**라벨:** 값' 형태를 (label, value) 리스트로 추출."""
    meta = []
    for raw in lines:
        m = _META_RE.match(raw.strip())
        if m and m.group(2).strip():
            meta.append((m.group(1).strip(), m.group(2).strip()))
    return meta


def _severity_color(text):
    """심각도 문자열 -> (배경색, 표시라벨)."""
    t = (text or '').lower()
    if any(k in t for k in ['critical', '심각', '치명']):
        return '#7f1d1d', 'CRITICAL'
    if any(k in t for k in ['high', '높음']):
        return '#b91c1c', 'HIGH'
    if any(k in t for k in ['medium', '중간', '보통']):
        return '#b45309', 'MEDIUM'
    if any(k in t for k in ['low', '낮음']):
        return '#047857', 'LOW'
    return '#374151', (text or 'INFO').upper()


def _slug(text, idx):
    """헤딩 텍스트로 안정적인 섹션 id 생성."""
    s = re.sub(r'[^0-9A-Za-z가-힣]+', '-', text).strip('-').lower()
    return s or ('section-%d' % idx)


def split_sections(md):
    """
    마크다운을 헤딩(#, ##, ###...) 기준으로 섹션 분리.
    각 헤딩 직전까지를 한 섹션으로 본다. 첫 헤딩 앞 본문은 'intro' 섹션.
    """
    lines = md.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    sections = []
    cur = {'heading': '', 'level': 0, 'lines': []}
    in_code = False

    for raw in lines:
        if raw.strip().startswith('```'):
            in_code = not in_code
            cur['lines'].append(raw)
            continue
        m = re.match(r'^(#{1,6})\s+(.*)$', raw) if not in_code else None
        if m:
            # 직전 섹션 마감
            if cur['heading'] or cur['lines']:
                sections.append(cur)
            cur = {'heading': m.group(2).strip(),
                   'level': len(m.group(1)),
                   'lines': []}
        else:
            cur['lines'].append(raw)
    if cur['heading'] or cur['lines']:
        sections.append(cur)

    result = []
    for i, sec in enumerate(sections):
        body_html = _render_block(sec['lines'])
        text = '\n'.join(l for l in sec['lines'] if l.strip())
        heading = sec['heading']
        level = sec['level'] or 2
        head_html = ('<h%d>%s</h%d>' % (level, _esc(heading), level)
                     if heading else '')
        result.append({
            'id': _slug(heading, i) if heading else 'intro',
            'heading': heading,
            'level': level,
            'lines': sec['lines'],
            'html': head_html + body_html,
            'text': (heading + '\n' + text).strip() if heading else text,
        })
    return result


def _meta_table(meta):
    """(label,value) 리스트 -> 2열 정보 테이블 HTML."""
    if not meta:
        return ''
    rows = []
    for label, value in meta:
        rows.append(
            '<tr>'
            '<td style="padding:7px 12px;background:#f9fafb;border:1px solid '
            '#e5e7eb;font-weight:600;color:#374151;white-space:nowrap;'
            'font-size:13px;width:160px;vertical-align:top">%s</td>'
            '<td style="padding:7px 12px;border:1px solid #e5e7eb;color:#111827;'
            'font-size:13px;word-break:break-all">%s</td>'
            '</tr>' % (_esc(label), _inline(value)))
    return ('<table style="border-collapse:collapse;width:100%;margin:0 0 4px">'
            + ''.join(rows) + '</table>')


def _card(heading, level, inner):
    """섹션을 카드(박스)로 감싼다."""
    color = '#1d4ed8' if level <= 2 else '#374151'
    head = ('<div style="font-size:16px;font-weight:700;color:%s;'
            'margin:0 0 12px;padding-bottom:8px;'
            'border-bottom:2px solid #e5e7eb">%s</div>'
            % (color, _esc(heading))) if heading else ''
    return ('<div style="background:#ffffff;border:1px solid #e5e7eb;'
            'border-radius:8px;padding:18px 20px;margin:0 0 16px">'
            + head + inner + '</div>')


def build_full_html(title, sections, decision=None):
    # 1) 전체 메타(핵심 정보) + 심각도 수집
    all_meta = []
    severity = ''
    alert_name = ''
    for sec in sections:
        for label, value in _extract_meta(sec.get('lines', [])):
            all_meta.append((label, value))
            low = label.replace(' ', '').lower()
            if '심각도' in label or 'severity' in low:
                severity = value
            if '경고이름' in label.replace(' ', '') or '이름' in label or 'name' in low:
                alert_name = value

    sev_bg, sev_label = _severity_color(severity)
    banner_title = _esc(title or alert_name or '보안 위협 분석 리포트')

    # 2) 상단 배너
    banner = (
        '<div style="background:#111827;border-radius:8px;padding:20px 24px;'
        'margin:0 0 16px">'
        '<div style="font-size:12px;color:#9ca3af;letter-spacing:1px;'
        'margin:0 0 6px">CORTEX XSIAM · 보안 위협 분석</div>'
        '<div style="font-size:20px;font-weight:700;color:#ffffff;'
        'line-height:1.35">%s</div>'
        '<div style="margin-top:12px">'
        '<span style="display:inline-block;background:%s;color:#fff;'
        'font-size:12px;font-weight:700;padding:4px 12px;border-radius:14px;'
        'letter-spacing:.5px">심각도 %s</span></div>'
        '</div>' % (banner_title, sev_bg, sev_label)
    )

    # 3) 핵심 정보 요약 카드 (메타 표)
    summary = ''
    if all_meta:
        summary = _card('핵심 정보 요약', 2, _meta_table(all_meta))

    # 4) 각 섹션을 카드로 (메타 줄은 위 표로 이미 보여줬으므로 본문에서 제외)
    body_cards = []
    for sec in sections:
        non_meta = [ln for ln in sec.get('lines', [])
                    if not _META_RE.match(ln.strip())]
        inner = _render_block(non_meta).strip()
        if not inner and not sec['heading']:
            continue
        # 첫 섹션이 메타만 있던 경우(본문 비어있고 제목만) 건너뜀
        if not inner:
            continue
        body_cards.append(_card(sec['heading'], sec['level'], inner))

    # 5) 결정 요청 CTA (메일 하단 자동 생성 Yes/No 링크로 시선 유도)
    cta = ''
    if decision:
        cta = (
            '<div style="background:#fffbeb;border:1px solid #fcd34d;'
            'border-left:5px solid #f59e0b;border-radius:8px;'
            'padding:18px 20px;margin:0 0 16px">'
            '<div style="font-size:15px;font-weight:700;color:#92400e;'
            'margin:0 0 6px">⚠ 관리자 조치 필요</div>'
            '<div style="font-size:14px;color:#78350f;line-height:1.6">%s</div>'
            '<div style="margin-top:14px;font-size:13px;color:#92400e;'
            'font-weight:600">▼ 아래 <span style="color:#1d4ed8">Yes</span> '
            '(승인·격리 진행) 또는 <span style="color:#b91c1c">No</span> '
            '(종료) 링크를 클릭해 결정해 주세요.</div>'
            '</div>' % _inline(decision)
        )

    footer = (
        '<div style="text-align:center;color:#9ca3af;font-size:11px;'
        'margin-top:8px">본 리포트는 Cortex XSIAM 플레이북에 의해 자동 생성되었습니다.</div>'
    )

    return (
        '<div style="background:#f3f4f6;padding:20px;'
        'font-family:Segoe UI,Apple SD Gothic Neo,Malgun Gothic,Arial,'
        'sans-serif">'
        '<div style="max-width:760px;margin:0 auto">'
        + banner + summary + ''.join(body_cards) + cta + footer +
        '</div></div>'
    )


def convert(md, title=None, decision=None):
    sections = split_sections(md)
    return {
        'title': title or '',
        'html': build_full_html(title, sections, decision),
        'sections': sections,
        'sectionCount': len(sections),
        'generatedAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    }


def main():
    args = demisto.args()
    md = args.get('markdown', '') or ''
    title = args.get('title', '') or None
    decision = args.get('decision', '') or None

    if not md.strip():
        return_error('markdown 입력이 비어 있습니다. (예: ${AgentixAnalysis})')
        return

    result = convert(md, title, decision)

    return_results(CommandResults(
        outputs_prefix='MailHtml',
        outputs=result,
        readable_output='HTML 변환 완료: %d개 섹션' % result['sectionCount'],
        raw_response=result,
    ))


if __name__ in ('__main__', '__builtin__', 'builtins'):
    main()
