"""Save the user's own request headers locally; never print their values."""
import getpass
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def validate_headers(headers):
    if not isinstance(headers, dict) or not headers:
        raise ValueError('Expected a non-empty JSON object of request headers.')
    if any(not isinstance(k, str) or not isinstance(v, str) or '\n' in k+v or '\r' in k+v for k,v in headers.items()):
        raise ValueError('All header names and values must be single-line strings.')
    if not any(k.lower() in ('token','cookie','authorization') and v.strip() for k,v in headers.items()):
        raise ValueError('No token, cookie or authorization header found.')
    if any(v.strip() in ('YOUR_VALUE','PASTE_HERE','...') for v in headers.values()):
        raise ValueError('Replace example placeholders with your own captured values.')
    # urllib creates transport headers itself. HTTP/2 pseudo headers are not forwarded.
    return {k:v for k,v in headers.items() if not k.startswith(':') and k.lower() not in ('host','content-length','connection','accept-encoding')}

def main():
    print('HoK MetaLab - local camp authorization setup')
    print('Use only headers from YOUR logged-in hero/getdetailranklistbyid request.')
    print('Enter the path to a local headers JSON file, or press Enter to paste one-line JSON privately.')
    source = input('Local JSON path: ').strip().strip('"')
    try:
        raw = Path(source).read_text(encoding='utf-8-sig') if source else getpass.getpass('Headers JSON (hidden): ')
        headers = validate_headers(json.loads(raw))
    except Exception:
        print('Invalid file or headers. Values were not saved or printed. See docs/camp-authorization.md.')
        return 1
    target=ROOT/'private/camp_headers.json'
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(headers,ensure_ascii=False),encoding='utf-8')
    print('Saved locally to private/camp_headers.json. Not included in website or export package.')
    print('Tell the assistant: local camp authorization is configured. No secrets need to be sent in chat.')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
