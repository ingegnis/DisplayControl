#!/usr/bin/env python3
"""Read private coordinator/Core readiness without printing cluster credentials."""
import argparse
import json
from pathlib import Path

from cluster import json_request, load_config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path(__file__).resolve().parent / 'data/cluster.json')
    args = parser.parse_args()
    config = load_config(args.config)
    result = {}
    for name, origin, suffix in [('coordinator', config['coordinator'], '/cluster/status'),
                                  *[(node, url, '/api/cluster/health') for node, url in config['nodes'].items()]]:
        try:
            result[name] = json_request(origin + suffix, config['key'], timeout=3)
        except Exception:
            result[name] = {'reachable': False}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get('coordinator', {}).get('active') else 1


if __name__ == '__main__':
    raise SystemExit(main())
