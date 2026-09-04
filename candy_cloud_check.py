#!/usr/bin/env python3
"""Print missing configuration NAMES only. No state writes or network calls."""
import os
import sys
from candy_cloud import load_campaign

def main():
    load_campaign()
    if os.environ.get('MODE') == 'render-only':
        print('Render-only mode needs no publishing credentials.')
        return 0
    names = ['BUFFER_API_KEY', 'BUFFER_TIKTOK_CHANNEL_ID', 'R2_ACCOUNT_ID',
             'R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY', 'R2_PUBLIC_BASE_URL',
             'CANDY_STATE_ACCESS_KEY_ID', 'CANDY_STATE_SECRET_ACCESS_KEY']
    if os.environ.get('MODE') == 'import-history':
        names.append('CANDY_HISTORY_IMPORT_B64')
    missing = [name for name in names if not os.environ.get(name, '').strip()]
    if missing:
        print('Setup required: missing encrypted GitHub secrets: ' + ', '.join(missing))
        return 1
    print('Required secret names are configured. State and Buffer access will be verified next.')
    return 0

if __name__ == '__main__':
    sys.exit(main())
