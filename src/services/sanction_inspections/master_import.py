"""Validate/convert locally by default. Register and activate only with explicit flags."""
import argparse
import json
from pathlib import Path

from .duty_master import convert_workbook_data, parse_master
from .models import InspectionError


def register_master(db, master):
    existing = db.table('inspection_duty_masters').select('id').eq('fingerprint', master.fingerprint).execute().data
    if existing:
        return existing[0]['id']
    rows = db.table('inspection_duty_masters').insert({'version': master.version,
        'fingerprint': master.fingerprint, 'payload': master.model_dump(), 'active': False}).execute().data
    return rows[0]['id']


def main():
    parser = argparse.ArgumentParser(description='Convert duty master JSON without registering or activating by default')
    parser.add_argument('--input', required=True)
    parser.add_argument('--output')
    parser.add_argument('--register', action='store_true')
    parser.add_argument('--activate', action='store_true', help='Invalidates older-basis drafts and publications')
    args = parser.parse_args()
    if args.activate and not args.register:
        parser.error('--activate requires --register')
    try:
        source = Path(args.input)
        if source.stat().st_size > 40000000:
            raise InspectionError('master_limit')
        payload = json.loads(source.read_text(encoding='utf-8'))
        master = convert_workbook_data(payload) if 'profiles' in payload else parse_master(payload)
        if args.output:
            Path(args.output).write_text(master.model_dump_json(indent=2), encoding='utf-8')
        result = {'version': master.version, 'fingerprint': master.fingerprint,
                  'department_count': len(master.departments), 'duty_count': len(master.duties), 'registered': False}
        if args.register:
            from src.config.settings import load_env, get_supabase_service_role_key
            from src.db.client import get_supabase_client
            load_env()
            if not get_supabase_service_role_key():
                raise InspectionError('not_configured')
            db = get_supabase_client()
            identifier = register_master(db, master)
            if args.activate:
                db.rpc('inspection_master_activate', {'p_id': identifier}).execute()
            result.update(id=identifier, registered=True, activated=args.activate)
        print(json.dumps(result))
    except InspectionError as exc:
        raise SystemExit(str(exc)) from None
    except Exception:
        raise SystemExit('master_import_failed') from None


if __name__ == '__main__':
    main()
